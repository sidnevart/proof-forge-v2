from datetime import datetime
from pydantic import BaseModel, model_validator


class ReviewQuestionIn(BaseModel):
    question: str
    correct_answer: str
    difficulty: int = 1

    @model_validator(mode="before")
    @classmethod
    def accept_answer_alias(cls, data):
        """Accept 'answer' as alias for 'correct_answer' — agents often use the shorter name."""
        if isinstance(data, dict) and "answer" in data and "correct_answer" not in data:
            data["correct_answer"] = data.pop("answer")
        return data


class CapsuleCreate(BaseModel):
    user_id: str
    topic_id: str
    content_md: str
    summary: str
    review_questions: list[ReviewQuestionIn] = []


class ReviewQuestionOut(BaseModel):
    id: str
    capsule_id: str
    question: str
    correct_answer: str
    difficulty: int

    model_config = {"from_attributes": True}


class CapsuleOut(BaseModel):
    id: str
    user_id: str
    topic_id: str
    content_md: str
    content_html: str
    summary: str
    title: str | None = None
    status: str = "ready"
    created_at: datetime
    review_questions: list[ReviewQuestionOut] = []

    model_config = {"from_attributes": True}
