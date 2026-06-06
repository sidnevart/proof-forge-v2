from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_attachment import ChatAttachment
from app.models.chat_session import ChatSession, ChatMessage


async def create_chat_session(
    db: AsyncSession, user_id: str, topic_id: str, study_session_id: str | None, title: str
) -> ChatSession:
    session = ChatSession(
        user_id=user_id,
        topic_id=topic_id,
        study_session_id=study_session_id,
        title=title,
        status="active",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_chat_session(db: AsyncSession, session_id: str) -> ChatSession | None:
    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
    return result.scalar_one_or_none()


async def list_chat_sessions(db: AsyncSession, user_id: str) -> list[ChatSession]:
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(ChatSession.updated_at.desc())
    )
    return list(result.scalars().all())


async def create_chat_message(
    db: AsyncSession, session_id: str, role: str, content: str
) -> ChatMessage:
    msg = ChatMessage(session_id=session_id, role=role, content=content)
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg


async def list_chat_messages(db: AsyncSession, session_id: str) -> list[ChatMessage]:
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    )
    return list(result.scalars().all())


async def add_chat_attachment(db: AsyncSession, attachment: ChatAttachment) -> ChatAttachment:
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    return attachment


async def list_chat_attachments(db: AsyncSession, message_id: str) -> list[ChatAttachment]:
    result = await db.execute(
        select(ChatAttachment)
        .where(ChatAttachment.message_id == message_id)
        .order_by(ChatAttachment.created_at.asc())
    )
    return list(result.scalars().all())


async def list_chat_attachments_for_messages(
    db: AsyncSession, message_ids: list[str]
) -> dict[str, list[ChatAttachment]]:
    """Batch-load attachments for many messages — avoids N+1 when loading history."""
    grouped: dict[str, list[ChatAttachment]] = {mid: [] for mid in message_ids}
    if not message_ids:
        return grouped
    result = await db.execute(
        select(ChatAttachment)
        .where(ChatAttachment.message_id.in_(message_ids))
        .order_by(ChatAttachment.created_at.asc())
    )
    for att in result.scalars().all():
        grouped.setdefault(att.message_id, []).append(att)
    return grouped
