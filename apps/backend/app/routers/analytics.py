from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.repositories import analytics_repo
from app.schemas.analytics import EventCreate, BatchEventCreate, EventOut

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.post("/event", response_model=EventOut, status_code=201)
async def log_event(data: EventCreate, db: AsyncSession = Depends(get_db)):
    return await analytics_repo.log_event(db, data)


@router.post("/batch", status_code=201)
async def log_batch(data: BatchEventCreate, db: AsyncSession = Depends(get_db)):
    count = await analytics_repo.log_batch(db, data.events)
    return {"logged": count}
