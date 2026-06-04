import json
import re

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.repositories import topic_repo, capsule_repo
from app.schemas.topic import TopicStart, TopicOut
from app.schemas.capsule import CapsuleCreate, CapsuleOut, ReviewQuestionIn, ReviewQuestionOut

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


class GenerateTopicRequest(BaseModel):
    user_id: str
    topic: str
    description: str = ""


class GenerateTopicOut(BaseModel):
    topic_id: str
    capsule_id: str
    capsule: CapsuleOut


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown code fences."""
    # Strip markdown code fences if present
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    # Find first { and last }
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON object found in LLM response")
    return json.loads(text[start:end])


@router.post("/topics/generate-web", response_model=GenerateTopicOut, status_code=201)
async def generate_topic_from_web(data: GenerateTopicRequest, db: AsyncSession = Depends(get_db)):
    """Generate a full learning capsule + questions from a topic name using LLM."""
    from app.config import settings

    if not settings.llm_api_key:
        raise HTTPException(status_code=503, detail="LLM не настроен — AI-генерация недоступна")

    context_block = f"\nДополнительный контекст от пользователя: {data.description}" if data.description else ""

    prompt = f"""Ты — эксперт-преподаватель для IT-специалистов. Создай обучающую капсулу.

Тема: {data.topic}{context_block}

Ответь ТОЛЬКО валидным JSON без markdown-блоков и пояснений:

{{
  "summary": "Одно предложение — что охватывает капсула",
  "content_md": "Полный markdown (600-900 слов). Структура: ## Обзор, ## Ключевые концепции (с подзаголовками), ## Практический пример (код если уместно), ## Типичные ошибки",
  "review_questions": [
    {{"question": "...", "correct_answer": "...", "difficulty": 1}},
    {{"question": "...", "correct_answer": "...", "difficulty": 1}},
    {{"question": "...", "correct_answer": "...", "difficulty": 2}},
    {{"question": "...", "correct_answer": "...", "difficulty": 2}},
    {{"question": "...", "correct_answer": "...", "difficulty": 3}},
    {{"question": "...", "correct_answer": "...", "difficulty": 3}}
  ]
}}

Требования:
- Язык: русский (термины — на языке оригинала)
- 6 вопросов: 2 лёгких (recall), 2 средних (понимание), 2 сложных (применение)
- Практический фокус: примеры из реальной работы IT-специалиста
- Чёткие, конкретные ответы без воды"""

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{settings.llm_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.llm_model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 3000,
                "temperature": 0.5,
            },
        )
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"]

    try:
        parsed = _extract_json(raw)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM вернул невалидный JSON: {e}")

    # Create topic
    from app.schemas.topic import TopicStart
    topic = await topic_repo.start_topic(db, TopicStart(user_id=data.user_id, name=data.topic))

    # Build capsule
    questions = [ReviewQuestionIn(**q) for q in parsed.get("review_questions", [])]
    capsule_data = CapsuleCreate(
        user_id=data.user_id,
        topic_id=topic.id,
        content_md=parsed["content_md"],
        summary=parsed["summary"],
        review_questions=questions,
    )
    capsule = await capsule_repo.store_capsule(db, capsule_data)
    capsule_questions = await capsule_repo.get_capsule_questions(db, capsule.id)

    capsule_out = CapsuleOut.model_validate(capsule)
    capsule_out.review_questions = [ReviewQuestionOut.model_validate(q) for q in capsule_questions]

    return GenerateTopicOut(topic_id=topic.id, capsule_id=capsule.id, capsule=capsule_out)
