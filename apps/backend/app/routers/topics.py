import asyncio
import json
import re
import time as _time

import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, async_session_factory
from app.repositories import topic_repo, capsule_repo
from app.schemas.topic import TopicStart, TopicOut
from app.schemas.capsule import CapsuleCreate, CapsuleOut, ReviewQuestionIn, ReviewQuestionOut
from app.models.capsule import Capsule
from app.models.review_question import ReviewQuestion
from app.models.topic_material import TopicMaterial
from app.models.learning_event import LearningEvent
from app.models.llm_usage_log import LlmUsageLog
from app.services.sse_bridge import create_stream, get_stream, remove_stream, stream_from_queue

router = APIRouter(tags=["topics"])


# ── Basic topic endpoints ─────────────────────────────────────────────────────

@router.post("/topics/start", response_model=TopicOut, status_code=201)
async def start_topic(data: TopicStart, db: AsyncSession = Depends(get_db)):
    topic = await topic_repo.start_topic(db, data)
    db.add(LearningEvent(
        user_id=data.user_id, event_type="topic_created",
        payload={"topic_id": topic.id, "name": data.name},
    ))
    await db.commit()
    return topic


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
    db.add(LearningEvent(
        user_id=user_id, event_type="material_uploaded",
        payload={"type": "file", "topic_id": topic_id, "name": file.filename, "size": len(data)},
    ))
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
    db.add(LearningEvent(
        user_id=data.user_id, event_type="material_uploaded",
        payload={"type": "link", "topic_id": topic_id, "url": data.url},
    ))
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

# Thresholds for chunked generation
_SINGLE_PASS_LIMIT = 12_000   # chars — below this, one LLM call is enough
_CHUNK_SIZE = 7_000            # chars per chunk in map phase


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


def _split_chunks(text: str, size: int) -> list[str]:
    """Split text into ≤size chunks, preferring paragraph/line boundaries."""
    if len(text) <= size:
        return [text]
    chunks = []
    while text:
        if len(text) <= size:
            chunks.append(text)
            break
        split_at = text.rfind("\n\n", 0, size)
        if split_at < size // 3:
            split_at = text.rfind("\n", 0, size)
        if split_at < size // 3:
            split_at = size
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip()
    return chunks


async def _llm_call(
    client: httpx.AsyncClient, settings, prompt: str, max_tokens: int = 1200
) -> tuple[str, dict]:
    """Returns (content, usage_dict). usage_dict has prompt_tokens, completion_tokens, total_tokens."""
    t0 = _time.monotonic()
    response = await client.post(
        f"{settings.llm_base_url}/chat/completions",
        headers={"Authorization": f"Bearer {settings.llm_api_key}", "Content-Type": "application/json"},
        json={
            "model": settings.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.4,
        },
    )
    response.raise_for_status()
    latency_ms = int((_time.monotonic() - t0) * 1000)
    data = response.json()
    usage = data.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
    msg = data["choices"][0]["message"]
    return msg.get("content") or msg.get("reasoning") or "", {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "latency_ms": latency_ms,
    }


async def _extract_concepts_from_chunk(
    client: httpx.AsyncClient, settings, topic_name: str, material_name: str, chunk: str
) -> tuple[str, dict]:
    """Map phase: returns (concepts_text, usage_dict)."""
    prompt = f"""Из фрагмента материала «{material_name}» (тема: «{topic_name}») извлеки ключевые концепции, определения и важные факты.

Фрагмент:
{chunk}

Ответь кратким структурированным списком — только суть, без воды. Без JSON, просто текст."""
    content, usage = await _llm_call(client, settings, prompt, max_tokens=800)
    return f"[Источник: {material_name}]\n{content}", usage


async def _generate_single_pass(
    client: httpx.AsyncClient, settings, topic_name: str, materials_block: str
) -> tuple[dict, dict]:
    """Returns (parsed_capsule, usage_dict)."""
    prompt = f"""Ты — эксперт-преподаватель для IT-специалистов. На основе материалов создай обучающую капсулу по теме «{topic_name}».

## Материалы

{materials_block}

---

Ответь ТОЛЬКО валидным JSON без markdown-блоков:

{{
  "summary": "Одно предложение — что охватывает капсула",
  "content_md": "Структурированный markdown (600-900 слов). Разделы: ## Обзор, ## Ключевые концепции, ## Практические примеры, ## Важно запомнить",
  "review_questions": [
    {{"question": "...", "correct_answer": "...", "difficulty": 1}},
    {{"question": "...", "correct_answer": "...", "difficulty": 1}},
    {{"question": "...", "correct_answer": "...", "difficulty": 2}},
    {{"question": "...", "correct_answer": "...", "difficulty": 2}},
    {{"question": "...", "correct_answer": "...", "difficulty": 3}},
    {{"question": "...", "correct_answer": "...", "difficulty": 3}}
  ]
}}

Основывайся на материалах. Язык: русский (термины на языке оригинала). 6 вопросов разной сложности."""
    raw, usage = await _llm_call(client, settings, prompt, max_tokens=4000)
    return _extract_json(raw), usage


async def _generate_chunked(
    client: httpx.AsyncClient, settings, topic_name: str, materials: list
) -> tuple[dict, dict]:
    """Map-reduce generation for large materials. Returns (parsed_capsule, aggregated_usage)."""
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "latency_ms": 0}

    # MAP: extract concepts from each chunk
    extracts: list[str] = []
    for material in materials:
        chunks = _split_chunks(material.content_text, _CHUNK_SIZE)
        for chunk in chunks:
            extract, usage = await _extract_concepts_from_chunk(
                client, settings, topic_name, material.name, chunk
            )
            extracts.append(extract)
            for k in ("prompt_tokens", "completion_tokens", "total_tokens", "latency_ms"):
                total_usage[k] += usage.get(k, 0)

    # REDUCE: synthesize capsule from all extracted concepts
    combined = "\n\n---\n\n".join(extracts)
    prompt = f"""Ты — эксперт-преподаватель. На основе этих концепций по теме «{topic_name}» создай обучающую капсулу.

## Извлечённые концепции из всех материалов

{combined[:20_000]}

---

Ответь ТОЛЬКО валидным JSON без markdown-блоков:

{{
  "summary": "Одно предложение — что охватывает капсула",
  "content_md": "Структурированный markdown (700-1000 слов). Разделы: ## Обзор, ## Ключевые концепции, ## Практические примеры, ## Важно запомнить",
  "review_questions": [
    {{"question": "...", "correct_answer": "...", "difficulty": 1}},
    {{"question": "...", "correct_answer": "...", "difficulty": 1}},
    {{"question": "...", "correct_answer": "...", "difficulty": 2}},
    {{"question": "...", "correct_answer": "...", "difficulty": 2}},
    {{"question": "...", "correct_answer": "...", "difficulty": 3}},
    {{"question": "...", "correct_answer": "...", "difficulty": 3}}
  ]
}}

Язык: русский (термины на языке оригинала). 6 вопросов разной сложности."""
    raw, reduce_usage = await _llm_call(client, settings, prompt, max_tokens=4000)
    for k in ("prompt_tokens", "completion_tokens", "total_tokens", "latency_ms"):
        total_usage[k] += reduce_usage.get(k, 0)
    return _extract_json(raw), total_usage


async def _run_capsule_generation(
    capsule_id: str,
    topic_id: str,
    topic_name: str,
    user_id: str,
    materials_snapshot: list,
) -> None:
    """Background task: generate capsule content and stream progress via SSE bridge."""
    from app.config import settings

    q = get_stream(capsule_id)
    if q is None:
        return

    t0 = _time.monotonic()
    usage: dict = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "latency_ms": 0}

    try:
        total_chars = sum(len(m["content_text"]) for m in materials_snapshot)
        use_chunked = total_chars > _SINGLE_PASS_LIMIT
        est_chunks = max(1, total_chars // _CHUNK_SIZE)
        timeout = 90 + est_chunks * 30

        parsed: dict = {}

        async with httpx.AsyncClient(timeout=timeout) as client:
            if use_chunked:
                total_chunks = sum(
                    len(_split_chunks(m["content_text"], _CHUNK_SIZE)) for m in materials_snapshot
                )
                chunk_idx = 0
                extracts: list[str] = []

                for mat in materials_snapshot:
                    chunks = _split_chunks(mat["content_text"], _CHUNK_SIZE)
                    for chunk in chunks:
                        chunk_idx += 1
                        await q.put(("progress", {
                            "phase": "extract",
                            "label": f"Обрабатываю материал {chunk_idx}/{total_chunks}...",
                            "current": chunk_idx,
                            "total": total_chunks,
                        }))
                        extract, u = await _extract_concepts_from_chunk(
                            client, settings, topic_name, mat["name"], chunk
                        )
                        extracts.append(extract)
                        for k in ("prompt_tokens", "completion_tokens", "total_tokens", "latency_ms"):
                            usage[k] = usage.get(k, 0) + u.get(k, 0)

                await q.put(("progress", {"phase": "synthesize", "label": "Синтезирую капсулу..."}))
                combined = "\n\n---\n\n".join(extracts)
                reduce_prompt = f"""Ты — эксперт-преподаватель. На основе этих концепций по теме «{topic_name}» создай обучающую капсулу.

## Извлечённые концепции из всех материалов

{combined[:20_000]}

---

Ответь ТОЛЬКО валидным JSON без markdown-блоков:

{{
  "summary": "Одно предложение — что охватывает капсула",
  "content_md": "Структурированный markdown (700-1000 слов). Разделы: ## Обзор, ## Ключевые концепции, ## Практические примеры, ## Важно запомнить",
  "review_questions": [
    {{"question": "...", "correct_answer": "...", "difficulty": 1}},
    {{"question": "...", "correct_answer": "...", "difficulty": 1}},
    {{"question": "...", "correct_answer": "...", "difficulty": 2}},
    {{"question": "...", "correct_answer": "...", "difficulty": 2}},
    {{"question": "...", "correct_answer": "...", "difficulty": 3}},
    {{"question": "...", "correct_answer": "...", "difficulty": 3}}
  ]
}}

Язык: русский (термины на языке оригинала). 6 вопросов разной сложности."""
                raw, reduce_u = await _llm_call(client, settings, reduce_prompt, max_tokens=4000)
                for k in ("prompt_tokens", "completion_tokens", "total_tokens", "latency_ms"):
                    usage[k] = usage.get(k, 0) + reduce_u.get(k, 0)
                parsed = _extract_json(raw)
            else:
                await q.put(("progress", {"phase": "synthesize", "label": "Генерирую капсулу..."}))
                materials_block = "\n\n---\n\n".join(
                    f"### Материал: {m['name']}\n\n{m['content_text']}"
                    for m in materials_snapshot
                )
                parsed, u = await _generate_single_pass(client, settings, topic_name, materials_block)
                for k in ("prompt_tokens", "completion_tokens", "total_tokens", "latency_ms"):
                    usage[k] = usage.get(k, 0) + u.get(k, 0)

        total_latency_ms = int((_time.monotonic() - t0) * 1000)
        total_tokens = usage.get("total_tokens", 0)
        cost_usd = total_tokens * settings.llm_cost_per_1k_tokens / 1000

        import markdown as _md
        content_md = parsed.get("content_md", "")
        content_html = _md.markdown(content_md, extensions=["fenced_code", "tables"])
        summary = parsed.get("summary", "")

        async with async_session_factory() as db:
            result = await db.execute(select(Capsule).where(Capsule.id == capsule_id))
            capsule = result.scalar_one_or_none()
            if capsule:
                capsule.content_md = content_md
                capsule.content_html = content_html
                capsule.summary = summary
                capsule.status = "ready"

                for rq in parsed.get("review_questions", []):
                    db.add(ReviewQuestion(
                        capsule_id=capsule_id,
                        question=rq.get("question", ""),
                        correct_answer=rq.get("correct_answer", rq.get("answer", "")),
                        difficulty=rq.get("difficulty", 1),
                    ))

                db.add(LlmUsageLog(
                    user_id=user_id,
                    call_type="capsule_gen",
                    topic_id=topic_id,
                    capsule_id=capsule_id,
                    model=settings.llm_model,
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    total_tokens=total_tokens,
                    cost_usd=cost_usd,
                    latency_ms=total_latency_ms,
                    status="success",
                ))
                db.add(LearningEvent(
                    user_id=user_id,
                    event_type="capsule_generated",
                    payload={
                        "topic_id": topic_id,
                        "capsule_id": capsule_id,
                        "total_tokens": total_tokens,
                        "cost_usd": round(cost_usd, 6),
                        "latency_ms": total_latency_ms,
                        "chunked": use_chunked,
                        "material_count": len(materials_snapshot),
                    },
                ))
                await db.commit()

        await q.put(("complete", {"capsule_id": capsule_id}))

    except Exception as exc:
        async with async_session_factory() as db:
            result = await db.execute(select(Capsule).where(Capsule.id == capsule_id))
            capsule = result.scalar_one_or_none()
            if capsule:
                capsule.status = "error"
                await db.commit()
        await q.put(("error", {"message": str(exc)}))

    finally:
        remove_stream(capsule_id)


@router.post("/topics/{topic_id}/capsule/generate", status_code=201)
async def generate_capsule_from_materials(
    topic_id: str,
    data: GenerateCapsuleRequest,
    db: AsyncSession = Depends(get_db),
):
    """Start capsule generation asynchronously. Returns capsule_id immediately; stream progress via /events."""
    from app.config import settings

    if not settings.llm_api_key:
        raise HTTPException(status_code=503, detail="LLM не настроен")

    topic = await topic_repo.get_topic(db, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    result = await db.execute(
        select(TopicMaterial)
        .where(TopicMaterial.topic_id == topic_id)
        .order_by(TopicMaterial.created_at.asc())
    )
    materials = result.scalars().all()
    if not materials:
        raise HTTPException(status_code=422, detail="Добавь материалы перед генерацией капсулы")

    materials_snapshot = [
        {"name": m.name, "content_text": m.content_text}
        for m in materials
    ]

    # Create skeleton capsule immediately
    capsule = Capsule(
        user_id=data.user_id,
        topic_id=topic_id,
        content_md="",
        content_html="",
        summary="",
        status="generating",
    )
    db.add(capsule)
    await db.commit()
    await db.refresh(capsule)

    create_stream(capsule.id)
    asyncio.create_task(_run_capsule_generation(
        capsule.id, topic_id, topic.name, data.user_id, materials_snapshot
    ))

    return {"topic_id": topic_id, "capsule_id": capsule.id, "status": "generating"}


@router.get("/topics/{topic_id}/capsule/events")
async def capsule_events(topic_id: str, capsule_id: str, db: AsyncSession = Depends(get_db)):
    """SSE stream for capsule generation progress."""
    q = get_stream(capsule_id)

    if q is None:
        capsule = await capsule_repo.get_capsule(db, capsule_id)
        if not capsule:
            raise HTTPException(status_code=404, detail="Capsule not found")

        async def _immediate():
            yield f"event: complete\ndata: {json.dumps({'capsule_id': capsule_id})}\n\n"

        return StreamingResponse(
            _immediate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return StreamingResponse(
        stream_from_queue(q),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
