"""Unit tests for domain profiles, strategy presets, and the domain classifier
fallback — all pure / no-LLM paths so they run in CI."""
import pytest

from app.services.domain_profiles import DOMAINS, get_profile
from app.services.strategy_presets import (
    PRESETS,
    conspect_word_count,
    resolve_strategy,
)
from app.services import practice_generation as pg
from app.services.domain_classifier import _normalize, classify_domain


def test_every_domain_has_a_profile_with_two_task_types():
    for d in DOMAINS:
        p = get_profile(d)
        assert p.domain == d
        assert len(p.task_recipe) >= 2  # theory + practice


def test_unknown_domain_falls_back_to_general():
    assert get_profile("nonsense").domain == "general"
    assert get_profile(None).domain == "general"


def test_language_domain_forbids_code():
    lang = get_profile("language")
    assert lang.allow_code is False
    strat = resolve_strategy(None)
    system = pg.build_conspect_system(lang, strat)
    assert "НЕ используй программный код" in system


def test_coding_domain_allows_code():
    assert get_profile("coding").allow_code is True


def test_conspect_prompt_always_has_prereq_and_glossary():
    strat = resolve_strategy(None)
    for d in DOMAINS:
        prompt = pg._build_conspect_prompt("Тема", "материалы", get_profile(d), strat)
        assert "Пререквизиты" in prompt
        assert "Глоссарий" in prompt


def test_strategy_presets_resolve():
    assert resolve_strategy(None).depth == PRESETS["deep_dive"].depth
    assert resolve_strategy({"preset": "exam_cram"}).depth == "brief"
    # partial override on top of a preset
    custom = resolve_strategy({"preset": "deep_dive", "depth": "brief", "include_diagrams": False})
    assert custom.depth == "brief"
    assert custom.include_diagrams is False
    # invalid values are ignored, fall back to preset defaults
    assert resolve_strategy({"depth": "bogus"}).depth == PRESETS["deep_dive"].depth


def test_word_count_scales_with_depth():
    assert conspect_word_count(resolve_strategy({"depth": "brief"})) != conspect_word_count(
        resolve_strategy({"depth": "comprehensive"})
    )


def test_math_domains_enable_latex_notation():
    for d in ("coding", "theory_math", "general"):
        assert get_profile(d).math_notation is True
    for d in ("language", "humanities"):
        assert get_profile(d).math_notation is False


def test_theory_math_conspect_requires_latex_formulas():
    strat = resolve_strategy(None)
    p = get_profile("theory_math")
    assert "Формулы и ключевые соотношения" in p.conspect_sections
    system = pg.build_conspect_system(p, strat)
    assert "LaTeX" in system
    body = pg._build_conspect_prompt("Теорема Байеса", "материалы", p, strat)
    assert "$$" in body  # formula-sheet LaTeX guidance present


def test_tasks_prompt_uses_full_conspect_not_truncated():
    strat = resolve_strategy(None)
    p = get_profile("coding")
    long_conspect = "КОНСПЕКТ " * 1000  # ~9000 chars, well past the old 2500-char cap
    prompt = pg._build_tasks_prompt("Тема", long_conspect, p, strat)
    # The old cap let only ~277 occurrences through; the fix carries most of the conspect.
    assert prompt.count("КОНСПЕКТ") > 500


def test_practice_generation_emits_discrete_gradable_tasks():
    topic = pg.TopicInfo(id="t", name="Хеш-таблицы", user_id="u", domain="coding")
    pspec = get_profile("coding").task_recipe[1]
    items = [
        {"title": f"T{i}", "instructions_md": f"### T{i}", "target_concepts": ["c"]}
        for i in range(5)
    ]
    tasks = pg._build_practice_task_creates(topic, pspec, items)
    assert len(tasks) == 5  # one PracticeTask row per item, not a single blob
    diffs = [t.difficulty for t in tasks]
    assert diffs == sorted(diffs)            # ascending gradient
    assert all(1 <= d <= 3 for d in diffs)   # clamped to schema range
    assert all(t.type == pspec.key for t in tasks)
    # an out-of-range model difficulty is ignored, not passed through
    weird = pg._build_practice_task_creates(topic, pspec, [{"difficulty": 9, "instructions_md": "x"}])
    assert 1 <= weird[0].difficulty <= 3
    # never leaves a session with zero practice
    assert len(pg._build_practice_task_creates(topic, pspec, [])) == 1


def test_conspect_validator_flags_short_and_missing_formulas():
    strat = resolve_strategy(None)
    long_ok = "слово " * 1300  # comfortably above the length floor
    # too short -> flagged
    assert pg._conspect_quality_gaps("очень короткий конспект", get_profile("coding"), strat)
    # math topic without any LaTeX -> flagged
    math_gaps = pg._conspect_quality_gaps(long_ok, get_profile("theory_math"), strat)
    assert any("формул" in g for g in math_gaps)
    # long math conspect with a formula -> clean
    assert pg._conspect_quality_gaps(long_ok + " $E=mc^2$", get_profile("theory_math"), strat) == []
    # long coding conspect without formulas -> clean (only theory_math requires them)
    assert pg._conspect_quality_gaps(long_ok, get_profile("coding"), strat) == []


def test_generation_respects_explicit_language():
    p = get_profile("coding")
    strat = resolve_strategy(None)
    # explicit English forces an English instruction into conspect system + tasks
    assert "English" in pg.build_conspect_system(p, strat, lang="en")
    assert pg._build_conspect_prompt("Hash tables", "m", p, strat, lang="en").startswith("Language: write")
    assert "English" in pg._build_tasks_prompt("Hash tables", "x" * 100, p, strat, lang="en")
    # default stays Russian (backward compatible)
    assert "Язык: русский" in pg.build_conspect_system(p, strat)
    # _resolve_lang: explicit wins, auto detects from text
    assert pg._resolve_lang("en", "что-то") == "en"
    assert pg._resolve_lang("auto", "Kotlin Coroutines") == "en"
    assert pg._resolve_lang("auto", "Эконометрика регрессия") == "ru"


def test_classifier_normalize():
    assert _normalize("coding") == "coding"
    assert _normalize("  Language.") == "language"
    assert _normalize("I think this is theory_math") == "theory_math"
    assert _normalize("???") == "general"


@pytest.mark.asyncio
async def test_classify_domain_without_llm_returns_general():
    class _Settings:
        llm_api_key = ""

    result = await classify_domain(None, _Settings(), "Английская грамматика")
    assert result == "general"
