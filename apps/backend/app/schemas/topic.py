from datetime import datetime
from pydantic import BaseModel


class TopicStart(BaseModel):
    user_id: str
    name: str
    strategy_config: dict | None = None


class TopicOut(BaseModel):
    id: str
    user_id: str
    name: str
    status: str
    started_at: datetime
    domain: str = "general"
    strategy_config: dict | None = None

    model_config = {"from_attributes": True}
