from datetime import datetime
from pydantic import BaseModel


class CardFromCapsuleCreate(BaseModel):
    user_id: str
    capsule_id: str


class CardFromCapsuleOut(BaseModel):
    created: int


class DueCardOut(BaseModel):
    source: str
    card_type: str
    card_id: str
    question_id: str | None = None
    question: str
    correct_answer: str
    difficulty: int
    topic_id: str
    topic_name: str
    interval_days: int
    repetitions: int

    model_config = {"from_attributes": True}


class CardAttemptCreate(BaseModel):
    user_id: str
    rating: int  # 1=Again 2=Hard 3=Good 4=Easy
    user_answer: str


class CardAttemptOut(BaseModel):
    card_id: str
    next_review_at: datetime
    interval_days: int
    ease_factor: float

    model_config = {"from_attributes": True}
