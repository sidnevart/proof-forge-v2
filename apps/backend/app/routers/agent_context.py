from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.repositories import user_repo, event_repo, capsule_repo
from app.schemas.agent_context import AgentContextOut

router = APIRouter(tags=["agent-context"])


@router.get("/agent-context", response_model=AgentContextOut)
async def get_agent_context(
    user_id: str = Query(..., alias="userId"),
    topic: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    profile = await user_repo.get_profile(db, user_id)
    profile_dict = {
        "known_topics": profile.known_topics if profile else [],
        "weak_spots": profile.weak_spots if profile else [],
        "skill_level": profile.skill_level if profile else "unknown",
    }

    capsules = await capsule_repo.get_user_capsules(db, user_id)
    capsules_list = [
        {"id": c.id, "topic_id": c.topic_id, "summary": c.summary, "created_at": c.created_at.isoformat()}
        for c in capsules[:5]
    ]

    weak_spots = await capsule_repo.get_user_weak_spots(db, user_id)
    spots_list = [
        {"concept": ws.concept, "severity": ws.severity, "topic_id": ws.topic_id}
        for ws in weak_spots[:10]
    ]

    events = await event_repo.get_recent_events(db, user_id)
    events_list = [
        {"event_type": e.event_type, "payload": e.payload, "occurred_at": e.occurred_at.isoformat()}
        for e in events
    ]

    return AgentContextOut(
        user_id=user_id,
        topic=topic,
        profile=profile_dict,
        capsules=capsules_list,
        weak_spots=spots_list,
        recent_events=events_list,
        generated_at=datetime.now(timezone.utc),
    )
