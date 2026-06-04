import uuid
from datetime import datetime, timezone, date
from sqlalchemy import String, DateTime, Integer, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class UserStreak(Base):
    __tablename__ = "user_streaks"

    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), primary_key=True)
    current_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_review_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class CardSession(Base):
    __tablename__ = "card_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    session_date: Mapped[date] = mapped_column(Date, nullable=False)
    cards_reviewed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_rating: Mapped[float] = mapped_column(nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
