from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.repositories import event_repo
from app.schemas.event import EventCreate, EventOut

router = APIRouter(tags=["events"])


@router.post("/events", response_model=EventOut, status_code=201)
async def create_event(data: EventCreate, db: AsyncSession = Depends(get_db)):
    return await event_repo.create_event(db, data)
