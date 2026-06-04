from pydantic import BaseModel
from typing import Any
from datetime import datetime


class EventCreate(BaseModel):
    session_id: str
    user_id: str | None = None
    event_type: str
    properties: dict[str, Any] = {}
    url: str | None = None
    referrer: str | None = None
    device: str | None = None


class BatchEventCreate(BaseModel):
    events: list[EventCreate]


class EventOut(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    session_id: str
    event_type: str
    occurred_at: datetime
