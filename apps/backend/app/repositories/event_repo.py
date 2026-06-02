from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LearningEvent, CodeArtifact
from app.schemas.event import EventCreate


async def create_event(db: AsyncSession, data: EventCreate) -> LearningEvent:
    event = LearningEvent(user_id=data.user_id, event_type=data.event_type, payload=data.payload)
    db.add(event)
    if data.event_type == "code_artifact":
        p = data.payload
        artifact = CodeArtifact(
            user_id=data.user_id,
            topic_id=p.get("topic_id", ""),
            filename=p.get("filename", ""),
            content=p.get("content", ""),
            language=p.get("language", ""),
        )
        db.add(artifact)
    await db.commit()
    await db.refresh(event)
    return event


async def get_recent_events(db: AsyncSession, user_id: str, limit: int = 20) -> list[LearningEvent]:
    result = await db.execute(
        select(LearningEvent)
        .where(LearningEvent.user_id == user_id)
        .order_by(LearningEvent.occurred_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
