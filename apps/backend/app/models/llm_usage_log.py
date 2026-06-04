import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Integer, Float
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class LlmUsageLog(Base):
    __tablename__ = "llm_usage_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    call_type: Mapped[str] = mapped_column(String, nullable=False)  # capsule_gen | concept_extract | feedback
    topic_id: Mapped[str | None] = mapped_column(String, nullable=True)
    capsule_id: Mapped[str | None] = mapped_column(String, nullable=True)
    model: Mapped[str] = mapped_column(String, nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="success")  # success | error
    error_msg: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
