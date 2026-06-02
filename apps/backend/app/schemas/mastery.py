from pydantic import BaseModel


class MasteryRecordCreate(BaseModel):
    user_id: str
    topic_id: str
    concept: str
    kind: str  # "theory" | "practice"
    difficulty: int = 0
    quality_score: float = 0.0
    struggle_passed: int = 0


class ConceptMasteryOut(BaseModel):
    id: str
    user_id: str
    topic_id: str
    concept: str
    theory_reps: int
    practice_reps: int
    practice_quality: float
    max_difficulty: int
    struggle_passed: int
    mastery_level: str

    model_config = {"from_attributes": True}
