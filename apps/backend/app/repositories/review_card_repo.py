from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ReviewCard, ReviewQuestion, Capsule, Topic


async def create_cards_from_capsule(db: AsyncSession, user_id: str, capsule_id: str) -> int:
    questions_result = await db.execute(
        select(ReviewQuestion).where(ReviewQuestion.capsule_id == capsule_id)
    )
    questions = list(questions_result.scalars().all())

    existing_result = await db.execute(
        select(ReviewCard.question_id).where(
            ReviewCard.user_id == user_id,
            ReviewCard.question_id.in_([q.id for q in questions]),
        )
    )
    existing_ids = {row for row in existing_result.scalars()}

    created = 0
    for q in questions:
        if q.id not in existing_ids:
            card = ReviewCard(question_id=q.id, user_id=user_id)
            db.add(card)
            created += 1

    await db.commit()
    return created


async def get_due_cards(db: AsyncSession, user_id: str, limit: int = 10) -> list[dict]:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(ReviewCard, ReviewQuestion, Capsule, Topic)
        .join(ReviewQuestion, ReviewCard.question_id == ReviewQuestion.id)
        .join(Capsule, ReviewQuestion.capsule_id == Capsule.id)
        .join(Topic, Capsule.topic_id == Topic.id)
        .where(ReviewCard.user_id == user_id)
        .where(ReviewCard.next_review_at <= now)
        .order_by(ReviewCard.next_review_at)
        .limit(limit)
    )
    rows = result.all()
    return [
        {
            "card_id": card.id,
            "question_id": question.id,
            "question": question.question,
            "correct_answer": question.correct_answer,
            "difficulty": question.difficulty,
            "topic_name": topic.name,
            "interval_days": card.interval_days,
            "repetitions": card.repetitions,
        }
        for card, question, capsule, topic in rows
    ]


async def log_card_attempt(
    db: AsyncSession, card_id: str, user_id: str, rating: int, user_answer: str
) -> ReviewCard | None:
    result = await db.execute(
        select(ReviewCard).where(ReviewCard.id == card_id, ReviewCard.user_id == user_id)
    )
    card = result.scalar_one_or_none()
    if not card:
        return None

    card.ease_factor, card.interval_days, card.repetitions = _sm2(
        card.ease_factor, card.interval_days, card.repetitions, rating
    )
    card.next_review_at = datetime.now(timezone.utc) + timedelta(days=card.interval_days)
    await db.commit()
    await db.refresh(card)
    return card


def _sm2(ease: float, interval: int, reps: int, rating: int) -> tuple[float, int, int]:
    """SM-2 algorithm. rating: 1=Again, 2=Hard, 3=Good, 4=Easy."""
    if rating == 1:
        return max(1.3, ease - 0.2), 1, 0
    if rating == 2:
        return max(1.3, ease - 0.15), max(1, int(interval * 1.2)), reps
    if rating == 3:
        new_interval = 1 if reps == 0 else (6 if reps == 1 else int(interval * ease))
        return ease, new_interval, reps + 1
    # rating == 4
    new_interval = 1 if reps == 0 else (6 if reps == 1 else int(interval * ease * 1.3))
    return min(2.5, ease + 0.1), new_interval, reps + 1
