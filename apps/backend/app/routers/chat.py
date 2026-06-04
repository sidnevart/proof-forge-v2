from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import settings as app_settings
from app.repositories import capsule_repo, chat_repo

router = APIRouter(tags=["chat"])

_SKILLS_DIR = Path(__file__).parent.parent / "skills"


def _load_system_prompt() -> str:
    try:
        mentor = (_SKILLS_DIR / "study-mentor-v2.md").read_text(encoding="utf-8")
        pedagogy = (_SKILLS_DIR / "_pedagogy.md").read_text(encoding="utf-8")
        return f"{mentor}\n\n---\n\n## Педагогические принципы (_pedagogy.md)\n\n{pedagogy}"
    except FileNotFoundError:
        return (
            "Ты — учебный ментор для IT-специалистов. "
            "Помогай пользователю изучать темы, объясняй концепции, давай практические задания."
        )


_SYSTEM_PROMPT: str | None = None


def get_system_prompt() -> str:
    global _SYSTEM_PROMPT
    if _SYSTEM_PROMPT is None:
        _SYSTEM_PROMPT = _load_system_prompt()
    return _SYSTEM_PROMPT


# ── Legacy / universal chat endpoint ──────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    user_id: str
    message: str
    history: list[ChatMessage] = []
    topic_id: str | None = None


class ChatResponse(BaseModel):
    message: str


@router.post("/chat", response_model=ChatResponse)
async def chat(data: ChatRequest, db: AsyncSession = Depends(get_db)):
    if not app_settings.llm_api_key:
        raise HTTPException(status_code=503, detail="LLM не настроен")

    system = get_system_prompt()

    # Append capsule content if topic provided
    if data.topic_id:
        capsules = await capsule_repo.get_user_capsules(db, data.user_id, data.topic_id)
        if capsules:
            cap = capsules[0]
            system += f"\n\n## Материал темы\n\n{cap.content_md}"

    # Append mastery weak spots
    weak = await capsule_repo.get_user_weak_spots(db, data.user_id)
    if weak:
        spots = ", ".join(f"{w.concept} (severity={w.severity})" for w in weak[:5])
        system += f"\n\n## Контекст ученика\n\nСлабые места: {spots}"

    messages = [{"role": m.role, "content": m.content} for m in data.history]
    messages.append({"role": "user", "content": data.message})

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{app_settings.llm_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {app_settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": app_settings.llm_model,
                "messages": [{"role": "system", "content": system}] + messages,
                "max_tokens": 2048,
                "temperature": 0.7,
            },
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"LLM error: {resp.text[:200]}")

    result = resp.json()
    reply = result["choices"][0]["message"]["content"]
    return ChatResponse(message=reply)


# ── Chat session persistence endpoints ────────────────────────────────────────

class ChatSessionCreate(BaseModel):
    user_id: str
    topic_id: str
    study_session_id: str | None = None
    title: str


class ChatMessageIn(BaseModel):
    role: str
    content: str


class ChatSessionOut(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    user_id: str
    topic_id: str
    study_session_id: str | None
    title: str
    status: str
    created_at: str


class ChatMessageOut(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    session_id: str
    role: str
    content: str
    created_at: str


@router.post("/chat/sessions", response_model=ChatSessionOut, status_code=201)
async def create_session(data: ChatSessionCreate, db: AsyncSession = Depends(get_db)):
    session = await chat_repo.create_chat_session(
        db, data.user_id, data.topic_id, data.study_session_id, data.title
    )
    return ChatSessionOut.model_validate(session)


@router.get("/chat/sessions", response_model=list[ChatSessionOut])
async def list_sessions(user_id: str, db: AsyncSession = Depends(get_db)):
    sessions = await chat_repo.list_chat_sessions(db, user_id)
    return [ChatSessionOut.model_validate(s) for s in sessions]


@router.get("/chat/sessions/{session_id}", response_model=ChatSessionOut)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await chat_repo.get_chat_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return ChatSessionOut.model_validate(session)


@router.post("/chat/sessions/{session_id}/messages", response_model=ChatMessageOut, status_code=201)
async def create_message(session_id: str, data: ChatMessageIn, db: AsyncSession = Depends(get_db)):
    session = await chat_repo.get_chat_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    msg = await chat_repo.create_chat_message(db, session_id, data.role, data.content)
    return ChatMessageOut.model_validate(msg)


@router.get("/chat/sessions/{session_id}/messages", response_model=list[ChatMessageOut])
async def list_messages(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await chat_repo.get_chat_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    messages = await chat_repo.list_chat_messages(db, session_id)
    return [ChatMessageOut.model_validate(m) for m in messages]
