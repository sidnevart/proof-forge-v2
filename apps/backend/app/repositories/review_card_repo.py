from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Capsule, ReviewCard, ReviewQuestion, Topic, TopicCard


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


async def get_due_cards_by_topic(db: AsyncSession, user_id: str) -> list[dict]:
    """Topics that currently have at least one card due, with per-topic due counts.

    Unions both card sources (ReviewCard via capsule join, TopicCard direct) using
    the same ``next_review_at <= now`` predicate as :func:`get_due_cards`. Returns
    ``[{topic_id, topic_name, due_count}]`` for topics with due_count > 0, sorted by
    topic name — the data the review page's topic filter needs.
    """
    now = datetime.now(timezone.utc)

    rc_query = (
        select(Topic.id, Topic.name, func.count(ReviewCard.id))
        .join(ReviewQuestion, ReviewCard.question_id == ReviewQuestion.id)
        .join(Capsule, ReviewQuestion.capsule_id == Capsule.id)
        .join(Topic, Capsule.topic_id == Topic.id)
        .where(ReviewCard.user_id == user_id, ReviewCard.next_review_at <= now)
        .group_by(Topic.id, Topic.name)
    )
    tc_query = (
        select(Topic.id, Topic.name, func.count(TopicCard.id))
        .join(Topic, TopicCard.topic_id == Topic.id)
        .where(TopicCard.user_id == user_id, TopicCard.next_review_at <= now)
        .group_by(Topic.id, Topic.name)
    )

    counts: dict[str, int] = {}
    names: dict[str, str] = {}
    for query in (rc_query, tc_query):
        for topic_id, topic_name, count in (await db.execute(query)).all():
            counts[topic_id] = counts.get(topic_id, 0) + count
            names[topic_id] = topic_name

    return sorted(
        (
            {"topic_id": tid, "topic_name": names[tid], "due_count": n}
            for tid, n in counts.items()
            if n > 0
        ),
        key=lambda r: r["topic_name"].lower(),
    )


async def get_due_cards(
    db: AsyncSession, user_id: str, limit: int = 10, topic_id: str | None = None
) -> list[dict]:
    now = datetime.now(timezone.utc)
    review_query = (
        select(ReviewCard, ReviewQuestion, Capsule, Topic)
        .join(ReviewQuestion, ReviewCard.question_id == ReviewQuestion.id)
        .join(Capsule, ReviewQuestion.capsule_id == Capsule.id)
        .join(Topic, Capsule.topic_id == Topic.id)
        .where(ReviewCard.user_id == user_id)
        .where(ReviewCard.next_review_at <= now)
    )
    if topic_id:
        review_query = review_query.where(Topic.id == topic_id)
    review_result = await db.execute(
        review_query.order_by(ReviewCard.next_review_at).limit(limit)
    )
    review_rows = review_result.all()
    due_cards = [
        {
            "source": "capsule",
            "card_type": "FLASHCARD",
            "card_id": card.id,
            "question_id": question.id,
            "question": question.question,
            "correct_answer": question.correct_answer,
            "difficulty": question.difficulty,
            "topic_id": topic.id,
            "topic_name": topic.name,
            "interval_days": card.interval_days,
            "repetitions": card.repetitions,
            "_next_review_at": card.next_review_at,
            "_source_order": 0,
        }
        for card, question, capsule, topic in review_rows
    ]

    topic_query = (
        select(TopicCard, Topic)
        .join(Topic, TopicCard.topic_id == Topic.id)
        .where(TopicCard.user_id == user_id)
        .where(TopicCard.next_review_at <= now)
    )
    if topic_id:
        topic_query = topic_query.where(TopicCard.topic_id == topic_id)
    topic_result = await db.execute(
        topic_query.order_by(TopicCard.next_review_at).limit(limit)
    )
    topic_rows = topic_result.all()
    due_cards.extend(
        {
            "source": "topic",
            "card_type": card.card_type,
            "card_id": card.id,
            "question_id": None,
            "question": card.front,
            "correct_answer": card.back,
            "difficulty": card.difficulty,
            "topic_id": topic.id,
            "topic_name": topic.name,
            "interval_days": card.interval_days,
            "repetitions": card.repetitions,
            "_next_review_at": card.next_review_at,
            "_source_order": 1,
        }
        for card, topic in topic_rows
    )
    due_cards.sort(key=lambda item: (item["_next_review_at"], item["_source_order"]))
    return [
        {key: value for key, value in item.items() if not key.startswith("_")}
        for item in due_cards[:limit]
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


async def log_topic_card_attempt(
    db: AsyncSession, card_id: str, user_id: str, rating: int
) -> TopicCard | None:
    result = await db.execute(
        select(TopicCard).where(TopicCard.id == card_id, TopicCard.user_id == user_id)
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
    return ease + 0.1, new_interval, reps + 1
