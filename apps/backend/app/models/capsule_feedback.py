import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, JSON, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class CapsuleFeedback(Base):
    __tablename__ = "capsule_feedback"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    capsule_id: Mapped[str] = mapped_column(String, ForeignKey("capsules.id"), nullable=False)
    weak_spots: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    suggestions_md: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    model_version: Mapped[str] = mapped_column(String, nullable=False, default="claude-sonnet-4-6")
