from datetime import datetime
from pydantic import BaseModel


class EventCreate(BaseModel):
    user_id: str
    event_type: str
    payload: dict = {}


class EventOut(BaseModel):
    id: str
    user_id: str
    event_type: str
    payload: dict
    occurred_at: datetime

    model_config = {"from_attributes": True}
