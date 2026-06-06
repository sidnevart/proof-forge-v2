"""Adaptive pre-topic onboarding — two stateless endpoints.

  POST /api/onboarding/questions  → classify domain + return interview slots
  POST /api/onboarding/plan       → build + persist StudyProfile, return plan text

Answers are held client-side and sent in one batch to /plan; nothing is stored
server-side between calls. The resolved profile lands in topics.strategy_config so the
existing generation pipeline and the mentor chat pick it up.
"""
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as app_settings
from app.database import get_db
from app.models.topic import Topic
from app.models.topic_material import TopicMaterial
from app.repositories import topic_repo
from app.services import study_onboarding
from app.services.domain_classifier import classify_domain
from app.services.domain_profiles import DEFAULT_DOMAIN

router = APIRouter(tags=["onboarding"])


class QuestionsRequest(BaseModel):
    topic_id: str
    user_id: str


class PlanRequest(BaseModel):
    topic_id: str
    user_id: str
    answers: dict = {}


async def _materials_preview(db: AsyncSession, topic_id: str) -> str:
    result = await db.execute(
        select(TopicMaterial)
        .where(TopicMaterial.topic_id == topic_id)
        .order_by(TopicMaterial.created_at.asc())
    )
    mats = result.scalars().all()
    return "\n".join((m.content_text or "")[:600] for m in mats[:3])


async def _resolve_domain(db: AsyncSession, topic: Topic, preview: str) -> str:
    """Use the topic's stored domain if already classified; otherwise classify now."""
    if topic.domain and topic.domain != DEFAULT_DOMAIN:
        return topic.domain
    if not app_settings.llm_api_key:
        return DEFAULT_DOMAIN
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
        domain = await classify_domain(client, app_settings, topic.name, preview)
    if domain != DEFAULT_DOMAIN:
        topic.domain = domain
        await db.commit()
    return domain


@router.post("/onboarding/questions")
async def onboarding_questions(data: QuestionsRequest, db: AsyncSession = Depends(get_db)):
    topic = await topic_repo.get_topic(db, data.topic_id)
    if not topic or topic.user_id != data.user_id:
        raise HTTPException(status_code=404, detail="Topic not found")
    preview = await _materials_preview(db, topic.id)
    domain = await _resolve_domain(db, topic, preview)
    slots = await study_onboarding.generate_questions(app_settings, topic.name, preview, domain)
    return {"domain": domain, "slots": slots}


@router.post("/onboarding/plan")
async def onboarding_plan(data: PlanRequest, db: AsyncSession = Depends(get_db)):
    topic = await topic_repo.get_topic(db, data.topic_id)
    if not topic or topic.user_id != data.user_id:
        raise HTTPException(status_code=404, detail="Topic not found")
    domain = topic.domain or DEFAULT_DOMAIN
    profile = study_onboarding.build_study_profile(data.answers, domain)
    plan_md = await study_onboarding.generate_plan(app_settings, topic.name, profile)
    # Persist the profile so chat (and a later session) can read it immediately.
    topic.strategy_config = profile
    await db.commit()
    return {"plan_md": plan_md, "study_profile": profile}
