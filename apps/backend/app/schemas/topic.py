from datetime import datetime
from pydantic import BaseModel


class TopicStart(BaseModel):
    user_id: str
    name: str


class TopicOut(BaseModel):
    id: str
    user_id: str
    name: str
    status: str
    started_at: datetime

    model_config = {"from_attributes": True}
