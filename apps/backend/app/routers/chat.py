from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as app_settings
from app.database import get_db
from app.models import PracticeTask, StudySession
from app.repositories import capsule_repo, chat_repo

router = APIRouter(tags=["chat"])


def _load_system_prompt() -> str:
    return """Ты — учебный ментор Proof Forge для IT-специалистов.

Отвечай по-русски, конкретно и по делу. Твоя задача — вести пользователя через системное обучение темы: объяснять материал, проверять понимание, давать задания и связывать ответы с текущим конспектом.

Работай так:
- Если пользователь просит начать или продолжить тему, дай короткий конспект, затем задания: 1 теоретическое и 1 практическое или mini-project.
- Если в системном контексте есть текущая учебная сессия, опирайся на ее конспект, learning goals и practice tasks.
- Для практики формулируй результат, файлы/артефакты, критерии приемки и команды проверки, если они уместны.
- Для вопросов по коду проси минимальный фрагмент, если данных не хватает; если данных хватает, разбирай конкретно.
- Не обещай, что проверил код или запустил тесты, если в сообщении нет таких данных.
- Когда пользователь ошибается, объясняй причину и давай следующий маленький шаг.
- Не пиши общие мотивационные фразы. Не делай длинные лекции без запроса.

Формат ответа по умолчанию:
1. Короткое объяснение.
2. Что сделать сейчас.
3. Как понять, что получилось.
"""


_SYSTEM_PROMPT: str | None = None


def get_system_prompt() -> str:
    global _SYSTEM_PROMPT
    if _SYSTEM_PROMPT is None:
        _SYSTEM_PROMPT = _load_system_prompt()
    return _SYSTEM_PROMPT


def _clip(text: str, max_chars: int) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n\n..."


async def _build_topic_context(db: AsyncSession, user_id: str, topic_id: str) -> str:
    parts: list[str] = []

    capsules = await capsule_repo.get_user_capsules(db, user_id, topic_id)
    if capsules:
        cap = capsules[0]
        parts.append(f"## Материал темы из capsule\n\n{_clip(cap.content_md, 5000)}")

    session_result = await db.execute(
        select(StudySession)
        .where(
            StudySession.user_id == user_id,
            StudySession.topic_id == topic_id,
        )
        .order_by(StudySession.created_at.desc())
    )
    session = session_result.scalar_one_or_none()
    if session:
        session_parts = [
            "## Текущая учебная сессия",
            f"Статус: {session.status}",
        ]
        if session.learning_goals:
            goals = "\n".join(f"- {goal}" for goal in session.learning_goals[:8])
            session_parts.append(f"### Цели обучения\n{goals}")
        if session.conspect_md:
            session_parts.append(f"### Конспект\n{_clip(session.conspect_md, 6000)}")

        task_result = await db.execute(
            select(PracticeTask)
            .where(
                PracticeTask.user_id == user_id,
                PracticeTask.topic_id == topic_id,
                PracticeTask.study_session_id == session.id,
            )
            .order_by(PracticeTask.created_at.asc())
        )
        tasks = list(task_result.scalars().all())
        if tasks:
            formatted_tasks = []
            for task in tasks[:6]:
                task_lines = [
                    f"- [{task.type}] {task.title}",
                    f"  Статус: {task.status}; сложность: {task.difficulty}",
                ]
                if task.target_concepts:
                    task_lines.append(
                        "  Концепты: " + ", ".join(task.target_concepts[:8])
                    )
                if task.instructions_md:
                    task_lines.append(
                        f"  Инструкция: {_clip(task.instructions_md, 1200)}"
                    )
                if task.check_commands:
                    task_lines.append(
                        "  Проверка: " + "; ".join(task.check_commands[:4])
                    )
                formatted_tasks.append("\n".join(task_lines))
            session_parts.append("### Задания\n" + "\n".join(formatted_tasks))

        parts.append("\n\n".join(session_parts))

    return "\n\n".join(parts)


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

    if data.topic_id:
        topic_context = await _build_topic_context(db, data.user_id, data.topic_id)
        if topic_context:
            system += f"\n\n{topic_context}"

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
    created_at: datetime


class ChatMessageOut(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    session_id: str
    role: str
    content: str
    created_at: datetime


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
