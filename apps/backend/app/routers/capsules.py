from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.repositories import capsule_repo, capsule_feedback_repo
from app.schemas.capsule import CapsuleCreate, CapsuleOut, ReviewQuestionOut

router = APIRouter(tags=["capsules"])


class FeedbackOut(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    capsule_id: str
    weak_spots: list
    suggestions_md: str
    generated_at: datetime
    model_version: str


@router.post("/capsules", response_model=CapsuleOut, status_code=201)
async def store_capsule(data: CapsuleCreate, db: AsyncSession = Depends(get_db)):
    capsule = await capsule_repo.store_capsule(db, data)
    questions = await capsule_repo.get_capsule_questions(db, capsule.id)
    result = CapsuleOut.model_validate(capsule)
    result.review_questions = [ReviewQuestionOut.model_validate(q) for q in questions]
    return result


@router.get("/capsules/{capsule_id}", response_model=CapsuleOut)
async def get_capsule(capsule_id: str, db: AsyncSession = Depends(get_db)):
    capsule = await capsule_repo.get_capsule(db, capsule_id)
    if not capsule:
        raise HTTPException(status_code=404, detail="Capsule not found")
    questions = await capsule_repo.get_capsule_questions(db, capsule_id)
    result = CapsuleOut.model_validate(capsule)
    result.review_questions = [ReviewQuestionOut.model_validate(q) for q in questions]
    return result


@router.get("/capsules/{capsule_id}/feedback", response_model=FeedbackOut | None)
async def get_capsule_feedback(capsule_id: str, db: AsyncSession = Depends(get_db)):
    return await capsule_feedback_repo.get_latest_feedback(db, capsule_id)


@router.post("/capsules/{capsule_id}/feedback", response_model=FeedbackOut, status_code=202)
async def request_capsule_feedback(
    capsule_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    capsule = await capsule_repo.get_capsule(db, capsule_id)
    if not capsule:
        raise HTTPException(status_code=404, detail="Capsule not found")

    from app.config import settings
    if not settings.llm_api_key:
        raise HTTPException(status_code=503, detail="AI feedback недоступен: не настроен LLM_API_KEY")

    feedback = await capsule_feedback_repo.generate_and_store_feedback(db, capsule_id)
    return feedback
