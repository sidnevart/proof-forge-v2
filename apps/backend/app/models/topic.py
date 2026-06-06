import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="active")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    folder_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("topic_folders.id", ondelete="SET NULL"), nullable=True
    )
    # Subject domain (coding/language/theory_math/humanities/general), classified at
    # topic start; parametrizes conspect, tasks and chat. See services/domain_profiles.py.
    domain: Mapped[str] = mapped_column(String, nullable=False, default="general")
    # Learner-chosen strategy knobs (depth, theory/practice mix, difficulty, pacing,
    # diagrams, weak-spot focus). None = default preset. See services/strategy_presets.py.
    strategy_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
