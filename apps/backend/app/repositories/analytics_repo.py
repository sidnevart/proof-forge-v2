from sqlalchemy.ext.asyncio import AsyncSession
from app.models.web_event import WebEvent
from app.schemas.analytics import EventCreate


async def log_event(db: AsyncSession, data: EventCreate) -> WebEvent:
    event = WebEvent(
        session_id=data.session_id,
        user_id=data.user_id,
        event_type=data.event_type,
        properties=data.properties,
        url=data.url,
        referrer=data.referrer,
        device=data.device,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


async def log_batch(db: AsyncSession, events: list[EventCreate]) -> int:
    records = [
        WebEvent(
            session_id=e.session_id,
            user_id=e.user_id,
            event_type=e.event_type,
            properties=e.properties,
            url=e.url,
            referrer=e.referrer,
            device=e.device,
        )
        for e in events
    ]
    db.add_all(records)
    await db.commit()
    return len(records)
