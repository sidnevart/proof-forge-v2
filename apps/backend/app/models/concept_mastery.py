import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Float, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class ConceptMastery(Base):
    __tablename__ = "concept_mastery"
    __table_args__ = (UniqueConstraint("user_id", "topic_id", "concept", name="uq_mastery_user_topic_concept"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    topic_id: Mapped[str] = mapped_column(String, ForeignKey("topics.id"), nullable=False)
    concept: Mapped[str] = mapped_column(String, nullable=False)

    theory_reps: Mapped[int] = mapped_column(Integer, default=0)
    practice_reps: Mapped[int] = mapped_column(Integer, default=0)
    practice_quality: Mapped[float] = mapped_column(Float, default=0.0)
    max_difficulty: Mapped[int] = mapped_column(Integer, default=0)
    struggle_passed: Mapped[int] = mapped_column(Integer, default=0)
    mastery_level: Mapped[str] = mapped_column(String, default="unknown")

    last_practiced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
