import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ChatAttachment(Base):
    """A file attached to a chat message.

    Text files store their extracted text in ``content_text``; images store
    base64-encoded bytes in ``data_b64`` (the backend is dumb storage — no S3,
    same as TopicMaterial / SubmissionAttachment). ``kind`` is 'text' or 'image'.
    """

    __tablename__ = "chat_attachments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id: Mapped[str] = mapped_column(
        String, ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    mime_type: Mapped[str] = mapped_column(String, default="application/octet-stream")
    kind: Mapped[str] = mapped_column(String, default="text")  # 'text' | 'image'
    content_text: Mapped[str] = mapped_column(Text, default="")
    data_b64: Mapped[str] = mapped_column(Text, default="")
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
