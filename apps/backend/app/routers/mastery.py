from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.repositories import mastery_repo
from app.schemas.mastery import MasteryRecordCreate, ConceptMasteryOut

router = APIRouter(tags=["mastery"])


@router.post("/mastery/record", response_model=ConceptMasteryOut, status_code=201)
async def record_mastery(data: MasteryRecordCreate, db: AsyncSession = Depends(get_db)):
    if data.kind not in ("theory", "practice"):
        raise HTTPException(status_code=422, detail="kind must be 'theory' or 'practice'")
    return await mastery_repo.record(
        db,
        user_id=data.user_id,
        topic_id=data.topic_id,
        concept=data.concept,
        kind=data.kind,
        difficulty=data.difficulty,
        quality_score=data.quality_score,
        struggle_passed=data.struggle_passed,
    )


@router.get("/mastery/progress")
async def get_progress(
    userId: str = Query(...),
    topic: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await mastery_repo.get_progress(db, userId, topic)


@router.get("/mastery/next")
async def get_next_focus(
    userId: str = Query(...),
    topic: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    focus = await mastery_repo.get_next_focus(db, userId, topic)
    if not focus:
        return {"focus": None, "message": "No concepts tracked yet. Start a topic."}
    return focus
