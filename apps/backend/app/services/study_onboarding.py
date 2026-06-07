"""Adaptive pre-topic onboarding — a chat-styled interview that produces a
StudyProfile before generation.

A fixed backbone of up to 5 slots; the AI fills the *content* (candidate concepts and
focus subtopics) from the topic + materials, while the rest of the slots are assembled
deterministically from the domain profile. The resolved StudyProfile is a superset of
the old strategy_config: it carries the strategy knobs (so resolve_strategy keeps
working) plus richer signals (known_concepts, focus_subtopics, goal, task_format) that
steer conspect/task generation and the mentor chat.

Everything degrades gracefully without an LLM: slots fall back to generic
domain-derived options, and the plan falls back to a templated summary. The interview
changes format/focus/emphasis only — never the quality bar.

This module depends only on llm_utils and domain_profiles, and is testable in isolation.
"""
import json
import logging
import re
from typing import Any

import httpx

from app.services.domain_profiles import get_profile

logger = logging.getLogger(__name__)

# ── Slot vocabularies (fixed structure; option content is filled per topic) ─────

GOAL_OPTIONS = [
    {"value": "understand", "label": "Понять с нуля"},
    {"value": "refresh", "label": "Освежить знания"},
    {"value": "interview", "label": "Подготовка к собесу"},
    {"value": "solve_task", "label": "Решить конкретную задачу"},
]

CONSPECT_FORMAT_OPTIONS = [
    {"value": "thorough", "label": "Подробно, с примерами"},
    {"value": "concise", "label": "Кратко и по делу"},
    {"value": "diagrams", "label": "С диаграммами"},
    {"value": "analogies", "label": "С бытовыми аналогиями"},
]

# goal → strategy knobs (so resolve_strategy and the generators get sensible values)
GOAL_OPTIONS_EN = [
    {"value": "understand", "label": "Learn from scratch"},
    {"value": "refresh", "label": "Refresh my knowledge"},
    {"value": "interview", "label": "Interview preparation"},
    {"value": "solve_task", "label": "Solve a specific task"},
]

CONSPECT_FORMAT_OPTIONS_EN = [
    {"value": "thorough", "label": "Detailed, with examples"},
    {"value": "concise", "label": "Concise and to the point"},
    {"value": "diagrams", "label": "With diagrams"},
    {"value": "analogies", "label": "With everyday analogies"},
]


def _detect_lang(text: str) -> str:
    """Heuristic: count ASCII alpha vs Cyrillic chars; return 'en' if mostly Latin."""
    sample = text[:300]
    latin = sum(1 for c in sample if c.isascii() and c.isalpha())
    cyrillic = sum(1 for c in sample if "Ѐ" <= c <= "ӿ")
    return "en" if latin > cyrillic else "ru"


_GOAL_KNOBS = {
    "understand": {"depth": "comprehensive", "difficulty": "gentle"},
    "refresh": {"depth": "brief", "difficulty": "standard"},
    "interview": {"depth": "moderate", "difficulty": "challenging"},
    "solve_task": {"depth": "moderate", "difficulty": "standard"},
}


# ── LLM helper ──────────────────────────────────────────────────────────────────

def _extract_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object in response")
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError("unbalanced JSON in response")


async def _llm_concepts_and_subtopics(
    client: httpx.AsyncClient, settings: Any, topic_name: str, materials_preview: str, domain: str
) -> tuple[list[str], list[str]]:
    """One cheap call: candidate concepts the learner might already know + focus subtopics."""
    from app.services.llm_utils import http_post_with_retry

    materials_line = (
        f"Фрагмент материалов:\n{materials_preview[:1500]}" if materials_preview.strip() else ""
    )
    prompt = (
        f"Тема обучения: «{topic_name}» (домен: {domain}).\n{materials_line}\n\n"
        "Верни ТОЛЬКО JSON без markdown:\n"
        '{\n'
        '  "concepts": ["до 6 конкретных под-понятий темы, которые ученик МОГ бы уже знать"],\n'
        '  "subtopics": ["до 6 под-тем, на которых можно сделать фокус при изучении"]\n'
        "}\n"
        "Формулируй коротко (2-4 слова), на языке темы. Без вступлений."
    )
    response = await http_post_with_retry(
        client,
        f"{settings.llm_base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://proof-forge.ru",
            "X-Title": "Grasp",
        },
        json_body={
            "model": settings.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 400,
            "temperature": 0.3,
        },
        retries=1,
        fallback_model=getattr(settings, "llm_fallback_model", None),
    )
    data = response.json()
    msg = data["choices"][0]["message"]
    raw = msg.get("content") or msg.get("reasoning") or ""
    parsed = _extract_json(raw)
    concepts = [str(c).strip() for c in parsed.get("concepts", []) if str(c).strip()][:6]
    subtopics = [str(s).strip() for s in parsed.get("subtopics", []) if str(s).strip()][:6]
    return concepts, subtopics


# ── Slot assembly ───────────────────────────────────────────────────────────────

def _task_format_options(domain: str) -> list[dict]:
    """Domain-aware task-format chips, derived from the domain profile's task recipe."""
    profile = get_profile(domain)
    seen: dict[str, str] = {}
    for spec in profile.task_recipe:
        seen[spec.key] = spec.title_hint
    # Always offer a couple of recognizable formats per domain.
    extras = {
        "coding": [("code", "Код"), ("mini_project", "Мини-проект"), ("interview", "Собес-задачи")],
        "language": [("dialogue", "Диалоги"), ("grammar", "Грамматика"), ("vocabulary", "Лексика")],
        "theory_math": [("problems", "Задачи с разбором"), ("proofs", "Доказательства")],
        "humanities": [("essay", "Эссе"), ("analysis", "Анализ источника")],
        "general": [("written", "Практические задания")],
    }.get(domain, [("written", "Практические задания")])
    options: list[dict] = [{"value": k, "label": v} for k, v in extras]
    # Fold in the recipe keys not already present.
    for key, hint in seen.items():
        if key not in {o["value"] for o in options}:
            options.append({"value": key, "label": hint})
    return options[:4]


def _build_slots(domain: str, concepts: list[str], subtopics: list[str], lang: str = "ru") -> list[dict]:
    """Assemble the (up to) 5-slot backbone. Slots with no content are skipped."""
    profile = get_profile(domain)
    en = lang == "en"
    goal_opts = GOAL_OPTIONS_EN if en else GOAL_OPTIONS
    cf_opts_all = CONSPECT_FORMAT_OPTIONS_EN if en else CONSPECT_FORMAT_OPTIONS
    slots: list[dict] = [
        {
            "id": "goal",
            "question": "What is your goal for this topic?" if en else "Какая у тебя цель по этой теме?",
            "multiselect": False,
            "allow_free_text": True,
            "options": goal_opts,
        }
    ]
    if concepts:
        slots.append({
            "id": "known",
            "question": "What do you already know? (I'll skip basics)" if en else "Что из этого ты уже знаешь? (отмечу — не буду разжёвывать)",
            "multiselect": True,
            "allow_free_text": True,
            "options": [{"value": c, "label": c} for c in concepts],
        })
    if subtopics:
        slots.append({
            "id": "focus",
            "question": "What should I focus on?" if en else "На чём сделать акцент?",
            "multiselect": True,
            "allow_free_text": True,
            "options": [{"value": s, "label": s} for s in subtopics],
        })
    conspect_opts = [
        o for o in cf_opts_all
        if o["value"] != "diagrams" or profile.allow_diagrams
    ]
    slots.append({
        "id": "conspect_format",
        "question": "What style of notes do you prefer?" if en else "Каким хочешь конспект?",
        "multiselect": True,
        "allow_free_text": True,
        "options": conspect_opts,
    })
    slots.append({
        "id": "task_format",
        "question": "What type of exercises do you prefer?" if en else "Какие задания тебе ближе?",
        "multiselect": True,
        "allow_free_text": True,
        "options": _task_format_options(domain),
    })
    return slots


async def generate_questions(
    settings: Any, topic_name: str, materials_preview: str, domain: str, lang: str = "auto"
) -> list[dict]:
    """Return the interview slots. AI fills concepts/subtopics; deterministic fallback."""
    if lang == "auto":
        lang = _detect_lang(topic_name + " " + materials_preview)
    concepts: list[str] = []
    subtopics: list[str] = []
    if getattr(settings, "llm_api_key", ""):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
                concepts, subtopics = await _llm_concepts_and_subtopics(
                    client, settings, topic_name, materials_preview, domain
                )
        except Exception as exc:  # noqa: BLE001 — never block the interview
            logger.warning("Onboarding question generation failed for %s: %s", topic_name, exc)
    return _build_slots(domain, concepts, subtopics, lang=lang)


# ── Answer → StudyProfile ─────────────────────────────────────────────────────

def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return []


def build_study_profile(answers: dict, domain: str) -> dict:
    """Resolve raw slot answers into a StudyProfile (superset of strategy_config).

    `answers` is a dict keyed by slot id; each value is a string or list of strings
    (chip values and/or free-text). Missing slots inherit balanced defaults.
    """
    answers = answers or {}
    goal = (answers.get("goal") or "understand")
    if isinstance(goal, list):
        goal = goal[0] if goal else "understand"
    goal = str(goal)
    knobs = _GOAL_KNOBS.get(goal, _GOAL_KNOBS["understand"])

    conspect_fmt = _as_list(answers.get("conspect_format"))
    include_diagrams = "diagrams" in conspect_fmt and get_profile(domain).allow_diagrams
    depth = "brief" if "concise" in conspect_fmt else knobs["depth"]

    return {
        "goal": goal,
        "known_concepts": _as_list(answers.get("known")),
        "focus_subtopics": _as_list(answers.get("focus")),
        "conspect_format": conspect_fmt,
        "task_format": _as_list(answers.get("task_format")),
        # strategy-knob superset so resolve_strategy keeps working
        "depth": depth,
        "difficulty": knobs["difficulty"],
        "include_diagrams": include_diagrams or "diagrams" not in conspect_fmt,
        "theory_practice_ratio": "practice_heavy" if goal in ("interview", "solve_task") else "balanced",
    }


# ── Plan synthesis ────────────────────────────────────────────────────────────

_GOAL_LABELS = {o["value"]: o["label"] for o in GOAL_OPTIONS}


def _templated_plan(topic_name: str, profile: dict) -> str:
    lang = _detect_lang(topic_name)
    if lang == "en":
        parts = [f'I will write notes on the topic "{topic_name}".']
        if profile.get("focus_subtopics"):
            parts.append("Focus: " + ", ".join(profile["focus_subtopics"]) + ".")
        if profile.get("known_concepts"):
            parts.append("You already know (brief mention): " + ", ".join(profile["known_concepts"]) + ".")
        goal = _GOAL_LABELS.get(profile.get("goal", ""), "")
        if goal:
            parts.append(f"Goal: {goal}.")
        if profile.get("task_format"):
            parts.append("Exercises: " + ", ".join(profile["task_format"]) + ".")
        parts.append("Shall we start?")
    else:
        parts = [f"Напишу конспект по теме «{topic_name}»."]
        if profile.get("focus_subtopics"):
            parts.append("Фокус: " + ", ".join(profile["focus_subtopics"]) + ".")
        if profile.get("known_concepts"):
            parts.append("Уже знаешь (упомяну кратко): " + ", ".join(profile["known_concepts"]) + ".")
        goal = _GOAL_LABELS.get(profile.get("goal", ""), "")
        if goal:
            parts.append(f"Цель: {goal}.")
        if profile.get("task_format"):
            parts.append("Задания: " + ", ".join(profile["task_format"]) + ".")
        parts.append("Поехали?")
    return " ".join(parts)


async def generate_plan(settings: Any, topic_name: str, profile: dict, lang: str = "auto") -> str:
    """Short human-readable plan bubble. LLM-written when available, templated otherwise."""
    if not getattr(settings, "llm_api_key", ""):
        return _templated_plan(topic_name, profile)
    from app.services.llm_utils import http_post_with_retry

    if lang == "auto":
        lang = _detect_lang(topic_name)
    if lang == "en":
        prompt = (
            f'You are a learning mentor. Briefly (2-3 sentences, first person) describe your plan: '
            f'what you will cover in the notes for the topic "{topic_name}" '
            f"given the learner's preferences:\n"
            f"{json.dumps(profile, ensure_ascii=False)}\n\n"
            'No markdown headers. End with "Shall we start?". Only the plan text itself.'
        )
    else:
        prompt = (
            f"Ты — учебный ментор. Кратко (2-3 предложения, от первого лица) опиши план: что "
            f"напишешь в конспекте по теме «{topic_name}» с учётом предпочтений ученика:\n"
            f"{json.dumps(profile, ensure_ascii=False)}\n\n"
            "Без markdown-заголовков. Заверши вопросом «Поехали?». Только сам текст плана."
        )
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            response = await http_post_with_retry(
                client,
                f"{settings.llm_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.llm_api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://proof-forge.ru",
                    "X-Title": "Grasp",
                },
                json_body={
                    "model": settings.llm_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 300,
                    "temperature": 0.4,
                },
                retries=1,
                fallback_model=getattr(settings, "llm_fallback_model", None),
            )
        data = response.json()
        msg = data["choices"][0]["message"]
        text = (msg.get("content") or msg.get("reasoning") or "").strip()
        return text or _templated_plan(topic_name, profile)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Onboarding plan generation failed for %s: %s", topic_name, exc)
        return _templated_plan(topic_name, profile)
