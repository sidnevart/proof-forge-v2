import json
import re
from difflib import SequenceMatcher
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory
from app.models import StudySession, Topic, TopicCard, TopicMaterial
from app.services.llm_utils import http_post_with_retry

SUPPORTED_CARD_TYPES = {"FLASHCARD", "FILL_BLANK", "CODE_REVIEW", "PRACTICAL"}
DEFAULT_MAX_CARDS = 12


def _clip(text: str, max_chars: int) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n\n..."


def _normalize_front(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


def _is_duplicate_front(front: str, existing_fronts: list[str]) -> bool:
    normalized = _normalize_front(front)
    if normalized in existing_fronts:
        return True
    return any(
        SequenceMatcher(None, normalized, existing).ratio() >= 0.92
        for existing in existing_fronts
    )


def _normalize_card_type(value: Any) -> str:
    card_type = str(value or "FLASHCARD").strip().upper().replace("-", "_")
    if card_type in {"FILLBLANK", "CLOZE"}:
        card_type = "FILL_BLANK"
    if card_type not in SUPPORTED_CARD_TYPES:
        return "FLASHCARD"
    return card_type


def _normalize_difficulty(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = 1
    return min(3, max(1, parsed))


def _extract_json_cards(text: str) -> list[dict[str, Any]]:
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start != -1 and end != -1 and end > start:
        parsed = json.loads(cleaned[start : end + 1])
    else:
        obj_start = cleaned.find("{")
        obj_end = cleaned.rfind("}")
        if obj_start == -1 or obj_end == -1 or obj_end <= obj_start:
            raise ValueError("No JSON cards found in LLM response")
        parsed_obj = json.loads(cleaned[obj_start : obj_end + 1])
        parsed = parsed_obj.get("cards", [])
    if not isinstance(parsed, list):
        raise ValueError("Card generation response must be a JSON array")
    return [item for item in parsed if isinstance(item, dict)]


def _build_generation_prompt(topic_name: str, context_md: str, lang: str = "auto") -> str:
    from app.services.study_onboarding import _detect_lang
    if lang not in ("ru", "en"):
        lang = _detect_lang(topic_name + " " + context_md)
    lang_line = (
        "IMPORTANT: write every card (front and back) in English. Keep technical terms in their original form."
        if lang == "en"
        else "Язык ответа: русский, технические термины на языке оригинала."
    )
    context = context_md.strip() or "(материалов нет — используй базовые знания по теме)"
    return f"""Ты — методист Proof Forge. Создай карточки интервального повторения по теме «{topic_name}».

Контекст темы:
{_clip(context, 10_000)}

Сгенерируй 8-12 карточек. Сам выбери релевантные типы:
- FLASHCARD: вопрос/ответ по теории.
- FILL_BLANK: пропуск в ключевой формулировке.
- CODE_REVIEW: короткий фрагмент кода и вопрос, что в нём важно или рискованно.
- PRACTICAL: сценарная задача без кода, если тема не про код.

Ответь ТОЛЬКО валидным JSON-массивом, без markdown-блоков и текста вне JSON:
[
  {{"type": "FLASHCARD", "front": "...", "back": "...", "difficulty": 1}},
  {{"type": "FILL_BLANK", "front": "... ___ ...", "back": "...", "difficulty": 2}}
]

Правила:
- front должен быть самостоятельным вопросом или заданием.
- back должен быть кратким, но достаточным ответом.
- difficulty: 1, 2 или 3.
- Для CODE_REVIEW используй fenced code block с языком, если код уместен.
- {lang_line}"""


def _fallback_cards(topic_name: str, context_md: str, lang: str = "auto") -> list[dict[str, Any]]:
    from app.services.study_onboarding import _detect_lang
    if lang not in ("ru", "en"):
        lang = _detect_lang(topic_name + " " + context_md)
    if lang == "en":
        return [
            {"type": "FLASHCARD", "front": f"What is the core idea of \"{topic_name}\"?", "back": f"State the main idea of {topic_name} and link it to a practical use.", "difficulty": 1},
            {"type": "PRACTICAL", "front": f"Describe a real scenario where knowing \"{topic_name}\" changes an engineering decision.", "back": "Name the context, the constraint, the chosen approach and why.", "difficulty": 2},
        ]
    context_hint = _clip(context_md, 300).replace("\n", " ") if context_md.strip() else topic_name
    return [
        {
            "type": "FLASHCARD",
            "front": f"Что важно понять в теме «{topic_name}»?",
            "back": f"Сформулируй основную идею темы и свяжи её с практическим применением. Контекст: {context_hint}",
            "difficulty": 1,
        },
        {
            "type": "FILL_BLANK",
            "front": f"Тема «{topic_name}» помогает ___ в реальном проекте.",
            "back": "объяснить механизм, выбрать подход и избежать типичных ошибок",
            "difficulty": 1,
        },
        {
            "type": "PRACTICAL",
            "front": f"Опиши реальный сценарий, где знание «{topic_name}» влияет на инженерное решение.",
            "back": "Нужно указать контекст, ограничение, выбранный подход и причину выбора.",
            "difficulty": 2,
        },
    ]


async def _generate_cards_with_llm(topic_name: str, context_md: str, lang: str = "auto") -> list[dict[str, Any]]:
    if not settings.llm_api_key:
        return _fallback_cards(topic_name, context_md, lang)

    prompt = _build_generation_prompt(topic_name, context_md, lang)
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
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
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a JSON-only API. Return only valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 3000,
                "temperature": 0.25,
            },
            fallback_model=getattr(settings, "llm_fallback_model", None),
        )
    data = response.json()
    msg = data["choices"][0]["message"]
    raw = msg.get("content") or msg.get("reasoning") or ""
    return _extract_json_cards(raw)


async def build_topic_card_context(
    db: AsyncSession,
    topic_id: str,
    user_id: str,
    extra_context: str = "",
) -> str:
    parts: list[str] = []

    materials_result = await db.execute(
        select(TopicMaterial)
        .where(TopicMaterial.topic_id == topic_id, TopicMaterial.user_id == user_id)
        .order_by(TopicMaterial.created_at.asc())
    )
    materials = list(materials_result.scalars().all())
    if materials:
        material_lines = []
        for material in materials[:6]:
            material_lines.append(
                f"### {material.name} ({material.type})\n{_clip(material.content_text, 2500)}"
            )
        parts.append("## Материалы темы\n\n" + "\n\n---\n\n".join(material_lines))

    session_result = await db.execute(
        select(StudySession)
        .where(StudySession.topic_id == topic_id, StudySession.user_id == user_id)
        .order_by(StudySession.created_at.desc())
    )
    session = session_result.scalar_one_or_none()
    if session and session.conspect_md:
        parts.append("## Последний конспект\n\n" + _clip(session.conspect_md, 4000))

    if extra_context.strip():
        parts.append("## Контекст диалога\n\n" + _clip(extra_context, 5000))

    return "\n\n".join(parts)


async def generate_cards_for_topic(
    topic_id: str,
    user_id: str,
    db: AsyncSession,
    context_md: str,
    max_new_cards: int | None = DEFAULT_MAX_CARDS,
    lang: str = "auto",
) -> list[TopicCard]:
    topic_result = await db.execute(
        select(Topic).where(Topic.id == topic_id, Topic.user_id == user_id)
    )
    topic = topic_result.scalar_one_or_none()
    if topic is None:
        return []

    if not context_md.strip():
        context_md = await build_topic_card_context(db, topic_id, user_id)

    existing_result = await db.execute(
        select(TopicCard.front).where(
            TopicCard.topic_id == topic_id,
            TopicCard.user_id == user_id,
        )
    )
    existing_fronts = [_normalize_front(front) for front in existing_result.scalars().all()]

    generated = await _generate_cards_with_llm(topic.name, context_md, lang)
    created: list[TopicCard] = []
    for item in generated:
        front = str(item.get("front") or item.get("question") or "").strip()
        back = str(item.get("back") or item.get("answer") or item.get("correct_answer") or "").strip()
        if not front or not back:
            continue
        if _is_duplicate_front(front, existing_fronts):
            continue

        card = TopicCard(
            topic_id=topic_id,
            user_id=user_id,
            card_type=_normalize_card_type(item.get("type") or item.get("card_type")),
            front=front,
            back=back,
            difficulty=_normalize_difficulty(item.get("difficulty")),
        )
        db.add(card)
        created.append(card)
        existing_fronts.append(_normalize_front(front))

        if max_new_cards is not None and len(created) >= max_new_cards:
            break

    if not created:
        return []

    await db.commit()
    for card in created:
        await db.refresh(card)
    return created


async def generate_cards_for_topic_background(
    topic_id: str,
    user_id: str,
    context_md: str = "",
    max_new_cards: int | None = DEFAULT_MAX_CARDS,
    lang: str = "auto",
) -> None:
    try:
        async with async_session_factory() as db:
            await generate_cards_for_topic(
                topic_id,
                user_id,
                db,
                context_md=context_md,
                max_new_cards=max_new_cards,
                lang=lang,
            )
    except Exception:
        # Card generation is opportunistic background work. Request flows must not
        # fail because the LLM or card persistence failed.
        return
