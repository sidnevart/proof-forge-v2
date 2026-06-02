from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ReviewAttempt, ReviewQuestion, WeakSpot, Capsule
from app.schemas.review import ReviewAnswerCreate


async def store_review_answer(db: AsyncSession, data: ReviewAnswerCreate) -> ReviewAttempt:
    attempt = ReviewAttempt(
        question_id=data.question_id,
        user_id=data.user_id,
        user_answer=data.user_answer,
        score=data.score,
        feedback=data.feedback,
        is_weak_spot=data.is_weak_spot,
    )
    db.add(attempt)

    if data.is_weak_spot:
        q_result = await db.execute(select(ReviewQuestion).where(ReviewQuestion.id == data.question_id))
        question = q_result.scalar_one_or_none()
        if question:
            cap_result = await db.execute(select(Capsule).where(Capsule.id == question.capsule_id))
            capsule = cap_result.scalar_one_or_none()
            topic_id = capsule.topic_id if capsule else "unknown"
            concept = question.question[:100]
            existing = await db.execute(
                select(WeakSpot).where(
                    WeakSpot.user_id == data.user_id,
                    WeakSpot.topic_id == topic_id,
                    WeakSpot.concept == concept,
                )
            )
            ws = existing.scalar_one_or_none()
            if ws:
                ws.severity = min(ws.severity + 0.5, 5.0)
            else:
                db.add(WeakSpot(
                    user_id=data.user_id,
                    topic_id=topic_id,
                    concept=concept,
                    severity=1.0,
                    detected_at=datetime.now(timezone.utc),
                ))

    await db.commit()
    await db.refresh(attempt)
    return attempt
