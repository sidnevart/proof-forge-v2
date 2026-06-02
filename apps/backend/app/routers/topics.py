from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.repositories import topic_repo
from app.schemas.topic import TopicStart, TopicOut

router = APIRouter(tags=["topics"])


@router.post("/topics/start", response_model=TopicOut, status_code=201)
async def start_topic(data: TopicStart, db: AsyncSession = Depends(get_db)):
    return await topic_repo.start_topic(db, data)


class TopicCompleteRequest(BaseModel):
    user_id: str


@router.post("/topics/{topic_id}/complete", response_model=TopicOut)
async def complete_topic(topic_id: str, data: TopicCompleteRequest, db: AsyncSession = Depends(get_db)):
    topic = await topic_repo.complete_topic(db, topic_id, data.user_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic
