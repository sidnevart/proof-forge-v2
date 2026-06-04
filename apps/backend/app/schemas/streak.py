from pydantic import BaseModel
from datetime import date, datetime


class StreakOut(BaseModel):
    model_config = {"from_attributes": True}

    user_id: str
    current_streak: int
    longest_streak: int
    last_review_date: date | None


class CardStatsOut(BaseModel):
    due_today: int
    reviewed_today: int
    streak: int
    longest_streak: int
    next_due_at: datetime | None
