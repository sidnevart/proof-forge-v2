from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class StudySessionCreate(BaseModel):
    user_id: str
    topic_id: str
    conspect_md: str = ""
    learning_goals: list[str] = Field(default_factory=list)


class StudySessionOut(BaseModel):
    id: str
    user_id: str
    topic_id: str
    status: str
    conspect_md: str
    learning_goals: list[str]
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class PracticeTaskCreate(BaseModel):
    user_id: str
    topic_id: str
    study_session_id: str
    type: str
    title: str
    instructions_md: str
    target_concepts: list[str] = Field(default_factory=list)
    difficulty: int = Field(default=1, ge=1, le=3)
    expected_evidence: list[str] = Field(default_factory=list)
    check_commands: list[str] = Field(default_factory=list)


class PracticeTaskOut(BaseModel):
    id: str
    user_id: str
    topic_id: str
    study_session_id: str
    type: str
    title: str
    instructions_md: str
    target_concepts: list[str]
    difficulty: int
    expected_evidence: list[str]
    check_commands: list[str]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class IdeSessionCreate(BaseModel):
    user_id: str
    ide: str = "jetbrains"
    ide_product: str = "unknown"
    plugin_version: str = "unknown"


class IdeSessionOut(BaseModel):
    id: str
    user_id: str
    ide: str
    ide_product: str
    plugin_version: str
    paired_at: datetime
    last_seen_at: datetime

    model_config = {"from_attributes": True}


class IdeSubmissionCreate(BaseModel):
    practice_task_id: str | None = None
    user_id: str
    ide_session_id: str | None = None
    files: list[dict[str, Any]] = Field(default_factory=list)
    diff: str = ""
    test_output: str = ""
    check_command: str = ""
    exit_code: int | None = None
    reflection: str = ""
    language: str = "unknown"


class IdeSubmissionOut(BaseModel):
    id: str
    practice_task_id: str
    user_id: str
    ide_session_id: str | None
    files: list[dict[str, Any]]
    diff: str
    test_output: str
    check_command: str
    exit_code: int | None
    reflection: str
    language: str
    submitted_at: datetime

    model_config = {"from_attributes": True}


class EvaluationCreate(BaseModel):
    submission_id: str
    user_id: str
    score: float = Field(ge=0.0, le=1.0)
    status: Literal["passed", "needs_revision", "failed"]
    feedback_md: str
    concept_scores: dict[str, float] = Field(default_factory=dict)
    weak_spots: list[dict[str, Any]] = Field(default_factory=list)
    next_action: str


class EvaluationOut(BaseModel):
    id: str
    submission_id: str
    score: float
    status: str
    feedback_md: str
    concept_scores: dict[str, float]
    weak_spots: list[dict[str, Any]]
    next_action: str
    created_at: datetime

    model_config = {"from_attributes": True}


class FollowUpCreate(BaseModel):
    evaluation_id: str
    question: str
    expected_answer: str = ""


class FollowUpAnswer(BaseModel):
    user_answer: str
    score: float = Field(ge=0.0, le=1.0)
    feedback_md: str = ""


class FollowUpOut(BaseModel):
    id: str
    evaluation_id: str
    question: str
    expected_answer: str
    user_answer: str
    score: float | None
    feedback_md: str

    model_config = {"from_attributes": True}
