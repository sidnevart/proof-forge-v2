import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class IdeSubmission(Base):
    __tablename__ = "ide_submissions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    practice_task_id: Mapped[str] = mapped_column(String, ForeignKey("practice_tasks.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    ide_session_id: Mapped[str | None] = mapped_column(String, ForeignKey("ide_sessions.id"), nullable=True)
    files: Mapped[list] = mapped_column(JSON, default=list)
    diff: Mapped[str] = mapped_column(Text, default="")
    test_output: Mapped[str] = mapped_column(Text, default="")
    check_command: Mapped[str] = mapped_column(Text, default="")
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reflection: Mapped[str] = mapped_column(Text, default="")
    language: Mapped[str] = mapped_column(String, default="unknown")
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
