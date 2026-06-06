from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Topic
from app.schemas.topic import TopicStart


async def start_topic(db: AsyncSession, data: TopicStart) -> Topic:
    topic = Topic(
        user_id=data.user_id,
        name=data.name,
        status="active",
        strategy_config=getattr(data, "strategy_config", None),
    )
    db.add(topic)
    await db.commit()
    await db.refresh(topic)
    return topic


async def get_topic(db: AsyncSession, topic_id: str) -> Topic | None:
    result = await db.execute(select(Topic).where(Topic.id == topic_id))
    return result.scalar_one_or_none()


async def complete_topic(db: AsyncSession, topic_id: str, user_id: str) -> Topic | None:
    result = await db.execute(
        select(Topic).where(Topic.id == topic_id, Topic.user_id == user_id)
    )
    topic = result.scalar_one_or_none()
    if not topic:
        return None
    topic.status = "completed"
    await db.commit()
    await db.refresh(topic)
    return topic
