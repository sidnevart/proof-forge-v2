import time as _time
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.capsule_feedback import CapsuleFeedback
from app.models import Capsule, WeakSpot, ReviewAttempt, ReviewQuestion
from app.models.llm_usage_log import LlmUsageLog
from app.models.learning_event import LearningEvent


async def get_latest_feedback(db: AsyncSession, capsule_id: str) -> CapsuleFeedback | None:
    result = await db.execute(
        select(CapsuleFeedback)
        .where(CapsuleFeedback.capsule_id == capsule_id)
        .order_by(CapsuleFeedback.generated_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def generate_and_store_feedback(db: AsyncSession, capsule_id: str) -> CapsuleFeedback:
    from app.config import settings

    capsule_result = await db.execute(select(Capsule).where(Capsule.id == capsule_id))
    capsule = capsule_result.scalar_one_or_none()
    if not capsule:
        raise ValueError(f"Capsule {capsule_id} not found")

    weak_spots_result = await db.execute(
        select(WeakSpot).where(WeakSpot.user_id == capsule.user_id, WeakSpot.topic_id == capsule.topic_id)
        .order_by(WeakSpot.severity.desc()).limit(10)
    )
    weak_spots = list(weak_spots_result.scalars().all())

    questions_result = await db.execute(select(ReviewQuestion).where(ReviewQuestion.capsule_id == capsule_id))
    questions = list(questions_result.scalars().all())
    q_ids = [q.id for q in questions]

    attempts: list[ReviewAttempt] = []
    if q_ids:
        attempts_result = await db.execute(
            select(ReviewAttempt).where(ReviewAttempt.question_id.in_(q_ids))
            .order_by(ReviewAttempt.answered_at.desc()).limit(20)
        )
        attempts = list(attempts_result.scalars().all())

    weak_spots_text = "\n".join(
        f"- {ws.concept} (severity: {ws.severity:.1f})" for ws in weak_spots
    ) or "нет выявленных слабых мест"

    attempts_text = "\n".join(
        f"- score={a.score:.2f} weak={a.is_weak_spot}"
        for a in attempts[:10]
    ) or "нет попыток"

    prompt = f"""Ты — педагогический ассистент. Проанализируй прогресс студента.

## Тема (краткое содержание)
{capsule.summary}

## Слабые места
{weak_spots_text}

## Последние попытки
{attempts_text}

Напиши фидбэк на русском языке в Markdown:
1. Что усвоено хорошо (1-2 пункта)
2. Что нужно подтянуть (2-4 пункта)
3. Рекомендуемые следующие шаги (2-3 пункта)

Будь конкретным и мотивирующим. Не более 350 слов."""

    t0 = _time.monotonic()
    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(
            f"{settings.llm_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.llm_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://proof-forge.ru",
                "X-Title": "Grasp",
            },
            json={
                "model": settings.llm_model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1024,
                "temperature": 0.7,
            },
        )
        response.raise_for_status()
        resp_data = response.json()
        suggestions_md = resp_data["choices"][0]["message"]["content"]

    latency_ms = int((_time.monotonic() - t0) * 1000)
    usage = resp_data.get("usage", {})
    total_tokens = usage.get("total_tokens", usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0))
    cost_usd = total_tokens * settings.llm_cost_per_1k_tokens / 1000

    feedback = CapsuleFeedback(
        capsule_id=capsule_id,
        weak_spots=[{"concept": ws.concept, "severity": ws.severity} for ws in weak_spots],
        suggestions_md=suggestions_md,
        model_version=settings.llm_model,
    )
    db.add(feedback)

    db.add(LlmUsageLog(
        user_id=capsule.user_id,
        call_type="feedback",
        topic_id=capsule.topic_id,
        capsule_id=capsule_id,
        model=settings.llm_model,
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        status="success",
    ))

    db.add(LearningEvent(
        user_id=capsule.user_id,
        event_type="ai_feedback_generated",
        payload={"capsule_id": capsule_id, "total_tokens": total_tokens, "cost_usd": round(cost_usd, 6)},
    ))

    await db.commit()
    await db.refresh(feedback)
    return feedback
