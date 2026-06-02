import markdown
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Capsule, ReviewQuestion, WeakSpot
from app.schemas.capsule import CapsuleCreate


async def store_capsule(db: AsyncSession, data: CapsuleCreate) -> Capsule:
    content_html = markdown.markdown(data.content_md, extensions=["fenced_code", "tables"])
    capsule = Capsule(
        user_id=data.user_id,
        topic_id=data.topic_id,
        content_md=data.content_md,
        content_html=content_html,
        summary=data.summary,
    )
    db.add(capsule)
    await db.flush()
    for q in data.review_questions:
        question = ReviewQuestion(
            capsule_id=capsule.id,
            question=q.question,
            correct_answer=q.correct_answer,
            difficulty=q.difficulty,
        )
        db.add(question)
    await db.commit()
    await db.refresh(capsule)
    return capsule


async def get_capsule(db: AsyncSession, capsule_id: str) -> Capsule | None:
    result = await db.execute(select(Capsule).where(Capsule.id == capsule_id))
    return result.scalar_one_or_none()


async def get_capsule_questions(db: AsyncSession, capsule_id: str) -> list[ReviewQuestion]:
    result = await db.execute(select(ReviewQuestion).where(ReviewQuestion.capsule_id == capsule_id))
    return list(result.scalars().all())


async def get_user_capsules(db: AsyncSession, user_id: str, topic_id: str | None = None) -> list[Capsule]:
    q = select(Capsule).where(Capsule.user_id == user_id)
    if topic_id:
        q = q.where(Capsule.topic_id == topic_id)
    result = await db.execute(q.order_by(Capsule.created_at.desc()))
    return list(result.scalars().all())


async def get_user_weak_spots(db: AsyncSession, user_id: str, topic_id: str | None = None) -> list[WeakSpot]:
    q = select(WeakSpot).where(WeakSpot.user_id == user_id)
    if topic_id:
        q = q.where(WeakSpot.topic_id == topic_id)
    result = await db.execute(q.order_by(WeakSpot.severity.desc()))
    return list(result.scalars().all())
