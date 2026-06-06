"""Unit tests for the adaptive onboarding service — all no-LLM (CI-safe) paths."""
import asyncio

import pytest

from app.services import study_onboarding as so
from app.services.strategy_presets import profile_generation_notes, resolve_strategy


class _NoLLM:
    llm_api_key = ""
    llm_base_url = ""
    llm_model = ""
    llm_fallback_model = ""


def test_questions_fallback_has_fixed_slots():
    slots = asyncio.run(so.generate_questions(_NoLLM(), "Go channels", "", "coding"))
    ids = [s["id"] for s in slots]
    # No LLM → no AI concepts/subtopics, so known/focus slots are skipped.
    assert ids[0] == "goal"
    assert "conspect_format" in ids and "task_format" in ids
    assert "known" not in ids and "focus" not in ids
    # Every slot allows a free-text answer and has options.
    for s in slots:
        assert s["allow_free_text"] is True
        assert isinstance(s["options"], list)


def test_task_format_options_are_domain_aware():
    coding = asyncio.run(so.generate_questions(_NoLLM(), "Go", "", "coding"))
    language = asyncio.run(so.generate_questions(_NoLLM(), "English", "", "language"))
    coding_tf = next(s for s in coding if s["id"] == "task_format")
    lang_tf = next(s for s in language if s["id"] == "task_format")
    coding_labels = " ".join(o["label"] for o in coding_tf["options"]).lower()
    lang_labels = " ".join(o["label"] for o in lang_tf["options"]).lower()
    assert "код" in coding_labels
    assert "код" not in lang_labels  # language never offers code tasks


def test_build_study_profile_maps_answers():
    profile = so.build_study_profile(
        {
            "goal": "interview",
            "known": ["синтаксис каналов"],
            "focus": ["select", "deadlock"],
            "conspect_format": ["concise", "diagrams"],
            "task_format": ["code", "mini_project"],
        },
        "coding",
    )
    assert profile["goal"] == "interview"
    assert profile["depth"] == "brief"          # "concise" wins
    assert profile["difficulty"] == "challenging"  # interview goal
    assert profile["known_concepts"] == ["синтаксис каналов"]
    assert profile["focus_subtopics"] == ["select", "deadlock"]
    assert profile["theory_practice_ratio"] == "practice_heavy"


def test_profile_roundtrips_through_resolve_strategy():
    profile = so.build_study_profile(
        {"goal": "understand", "focus": ["рекурсия"], "known": ["циклы"]}, "general"
    )
    strat = resolve_strategy(profile)
    assert strat.goal == "understand"
    assert strat.focus_subtopics == ["рекурсия"]
    assert strat.known_concepts == ["циклы"]
    notes = profile_generation_notes(strat)
    assert "рекурсия" in notes and "циклы" in notes


def test_empty_answers_resolve_to_defaults():
    profile = so.build_study_profile({}, "coding")
    strat = resolve_strategy(profile)
    # No focus/known → no profile notes; preset-only behavior preserved.
    assert profile_generation_notes(strat) == "" or "Цель" in profile_generation_notes(strat)
    assert profile["known_concepts"] == [] and profile["focus_subtopics"] == []


def test_plan_fallback_is_templated_without_llm():
    profile = so.build_study_profile({"goal": "interview", "focus": ["select"]}, "coding")
    plan = asyncio.run(so.generate_plan(_NoLLM(), "Go channels", profile))
    assert "Go channels" in plan
    assert "select" in plan
    assert plan.strip().endswith("Поехали?")
