from datetime import datetime
from pydantic import BaseModel


class AgentContextOut(BaseModel):
    user_id: str
    topic: str | None
    profile: dict
    capsules: list[dict]
    weak_spots: list[dict]
    recent_events: list[dict]
    generated_at: datetime
