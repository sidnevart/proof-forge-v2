import json
import re

import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.repositories import topic_repo, capsule_repo
from app.schemas.topic import TopicStart, TopicOut
from app.schemas.capsule import CapsuleCreate, CapsuleOut, ReviewQuestionIn, ReviewQuestionOut
from app.models.topic_material import TopicMaterial

router = APIRouter(tags=["topics"])


# ── Basic topic endpoints ─────────────────────────────────────────────────────

@router.post("/topics/start", response_model=TopicOut, status_code=201)
async def start_topic(data: TopicStart, db: AsyncSession = Depends(get_db)):
    return await topic_repo.start_topic(db, data)


@router.get("/topics")
async def list_topics(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(topic_repo.Topic).where(topic_repo.Topic.user_id == user_id)
        .order_by(topic_repo.Topic.started_at.desc())
    )
    return result.scalars().all()


@router.get("/topics/{topic_id}", response_model=TopicOut)
async def get_topic(topic_id: str, db: AsyncSession = Depends(get_db)):
    topic = await topic_repo.get_topic(db, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


class TopicCompleteRequest(BaseModel):
    user_id: str


@router.post("/topics/{topic_id}/complete", response_model=TopicOut)
async def complete_topic(topic_id: str, data: TopicCompleteRequest, db: AsyncSession = Depends(get_db)):
    topic = await topic_repo.complete_topic(db, topic_id, data.user_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


# ── Material models ───────────────────────────────────────────────────────────

class MaterialOut(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    topic_id: str
    user_id: str
    type: str
    name: str
    url: str | None
    content_text: str
    file_size: int | None
    created_at: str

    @classmethod
    def from_orm(cls, obj: TopicMaterial):  # type: ignore[override]
        return cls(
            id=obj.id,
            topic_id=obj.topic_id,
            user_id=obj.user_id,
            type=obj.type,
            name=obj.name,
            url=obj.url,
            content_text=obj.content_text,
            file_size=obj.file_size,
            created_at=obj.created_at.isoformat(),
        )


class AddLinkRequest(BaseModel):
    user_id: str
    url: str


# ── Material endpoints ────────────────────────────────────────────────────────

@router.get("/topics/{topic_id}/materials")
async def list_materials(topic_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TopicMaterial)
        .where(TopicMaterial.topic_id == topic_id)
        .order_by(TopicMaterial.created_at.asc())
    )
    materials = result.scalars().all()
    return [MaterialOut.from_orm(m) for m in materials]


@router.post("/topics/{topic_id}/materials/file", status_code=201)
async def upload_material_file(
    topic_id: str,
    user_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    from app.services.file_parser import extract_from_bytes

    data = await file.read()
    content_text = extract_from_bytes(file.filename or "file", data)

    material = TopicMaterial(
        topic_id=topic_id,
        user_id=user_id,
        type="file",
        name=file.filename or "file",
        content_text=content_text,
        file_size=len(data),
    )
    db.add(material)
    await db.commit()
    await db.refresh(material)
    return MaterialOut.from_orm(material)


@router.post("/topics/{topic_id}/materials/link", status_code=201)
async def add_material_link(
    topic_id: str,
    data: AddLinkRequest,
    db: AsyncSession = Depends(get_db),
):
    from app.services.file_parser import extract_from_url

    title, content_text = await extract_from_url(data.url)

    material = TopicMaterial(
        topic_id=topic_id,
        user_id=data.user_id,
        type="link",
        name=title,
        url=data.url,
        content_text=content_text,
    )
    db.add(material)
    await db.commit()
    await db.refresh(material)
    return MaterialOut.from_orm(material)


@router.delete("/topics/{topic_id}/materials/{material_id}", status_code=204)
async def delete_material(topic_id: str, material_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TopicMaterial)
        .where(TopicMaterial.id == material_id, TopicMaterial.topic_id == topic_id)
    )
    material = result.scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    await db.delete(material)
    await db.commit()


# ── Capsule generation from materials ────────────────────────────────────────

class GenerateCapsuleRequest(BaseModel):
    user_id: str


class GenerateTopicOut(BaseModel):
    topic_id: str
    capsule_id: str
    capsule: CapsuleOut


def _extract_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON object found in LLM response")
    return json.loads(text[start:end])


@router.post("/topics/{topic_id}/capsule/generate", response_model=GenerateTopicOut, status_code=201)
async def generate_capsule_from_materials(
    topic_id: str,
    data: GenerateCapsuleRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate a capsule from all materials uploaded to the topic."""
    from app.config import settings

    if not settings.llm_api_key:
        raise HTTPException(status_code=503, detail="LLM не настроен")

    topic = await topic_repo.get_topic(db, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    # Gather all material texts
    result = await db.execute(
        select(TopicMaterial)
        .where(TopicMaterial.topic_id == topic_id)
        .order_by(TopicMaterial.created_at.asc())
    )
    materials = result.scalars().all()
    if not materials:
        raise HTTPException(status_code=422, detail="Добавь материалы перед генерацией капсулы")

    materials_block = "\n\n---\n\n".join(
        f"### Материал: {m.name}\n\n{m.content_text[:8000]}"
        for m in materials
    )

    prompt = f"""Ты — эксперт-преподаватель для IT-специалистов. На основе материалов ниже создай обучающую капсулу по теме «{topic.name}».

## Материалы для изучения

{materials_block}

---

Ответь ТОЛЬКО валидным JSON без markdown-блоков и пояснений:

{{
  "summary": "Одно предложение — что охватывает капсула",
  "content_md": "Структурированный markdown (600-900 слов) на основе материалов. Разделы: ## Обзор, ## Ключевые концепции, ## Практические примеры, ## Важно запомнить",
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
- Основывайся строго на загруженных материалах, не добавляй лишнего
- Язык: русский (термины на языке оригинала)
- 6 вопросов разной сложности
- Конкретные ответы без воды"""

    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(
            f"{settings.llm_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.llm_model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 4000,
                "temperature": 0.4,
            },
        )
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"]

    try:
        parsed = _extract_json(raw)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM вернул невалидный JSON: {e}")

    questions = [ReviewQuestionIn(**q) for q in parsed.get("review_questions", [])]
    capsule_data = CapsuleCreate(
        user_id=data.user_id,
        topic_id=topic_id,
        content_md=parsed["content_md"],
        summary=parsed["summary"],
        review_questions=questions,
    )
    capsule = await capsule_repo.store_capsule(db, capsule_data)
    capsule_questions = await capsule_repo.get_capsule_questions(db, capsule.id)

    capsule_out = CapsuleOut.model_validate(capsule)
    capsule_out.review_questions = [ReviewQuestionOut.model_validate(q) for q in capsule_questions]

    return GenerateTopicOut(topic_id=topic_id, capsule_id=capsule.id, capsule=capsule_out)
