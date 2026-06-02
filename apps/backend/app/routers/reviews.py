from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.repositories import review_repo
from app.schemas.review import ReviewAnswerCreate, ReviewAttemptOut

router = APIRouter(tags=["reviews"])


@router.post("/reviews/answer", response_model=ReviewAttemptOut, status_code=201)
async def store_review_answer(data: ReviewAnswerCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await review_repo.store_review_answer(db, data)
    except IntegrityError:
        raise HTTPException(
            status_code=404,
            detail=f"Question {data.question_id} not found. Make sure to use question_id from a saved capsule."
        )
