from datetime import datetime
from pydantic import BaseModel


class ReviewAnswerCreate(BaseModel):
    user_id: str
    question_id: str
    user_answer: str
    score: float
    feedback: str
    is_weak_spot: bool = False


class ReviewAttemptOut(BaseModel):
    id: str
    question_id: str
    user_id: str
    user_answer: str
    score: float
    feedback: str
    is_weak_spot: bool
    answered_at: datetime

    model_config = {"from_attributes": True}
