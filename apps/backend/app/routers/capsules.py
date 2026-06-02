from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.repositories import capsule_repo
from app.schemas.capsule import CapsuleCreate, CapsuleOut, ReviewQuestionOut

router = APIRouter(tags=["capsules"])


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
