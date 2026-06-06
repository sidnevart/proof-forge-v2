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
