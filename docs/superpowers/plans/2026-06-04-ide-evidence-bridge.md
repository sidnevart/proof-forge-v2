# IDE Evidence Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first vertical slice of the IDE Evidence Bridge: active study sessions, practice tasks, IDE submissions, evaluation, web visibility, and a minimal JetBrains plugin bridge.

**Architecture:** The backend owns learning state, task generation, submissions, evaluation, mastery updates, and capsule memory. The web app starts study sessions and displays tasks/evaluations. The JetBrains plugin is a thin evidence transport client: pair account, select active task, preview local files, submit evidence, and link back to Proof Forge.

**Tech Stack:** FastAPI, SQLAlchemy async ORM, Alembic, Pydantic, pytest, Next.js App Router, TypeScript, IntelliJ Platform plugin in Kotlin with Gradle.

---

## Scope Check

The approved spec spans three subsystems: backend, web, and JetBrains plugin. This plan implements them as one vertical slice because each subsystem is only useful when connected end-to-end:

- Backend data/API creates the contract.
- Web exposes the learning flow and evaluation.
- JetBrains plugin proves that IDE evidence can return without archive uploads.

The first useful release is intentionally narrow:

- JetBrains first, IntelliJ IDEA as the tested product.
- One active study session flow per topic.
- Practice task generation creates a deterministic starter mini-project task from the current topic/materials; LLM refinement can be added behind the same service contract after the slice is stable.
- Plugin submits files/diff/test output/reflection; it does not manage dependencies or modify user code.

## File Structure

Backend:

- Create `apps/backend/app/models/study_session.py` for active topic learning sessions.
- Create `apps/backend/app/models/practice_task.py` for generated tasks inside a session.
- Create `apps/backend/app/models/ide_session.py` for plugin pairing/session metadata.
- Create `apps/backend/app/models/ide_submission.py` for submitted IDE evidence.
- Create `apps/backend/app/models/evaluation.py` for submission evaluations and follow-ups.
- Modify `apps/backend/app/models/__init__.py` to export new models.
- Create `apps/backend/alembic/versions/0008_ide_evidence_bridge.py` for new tables.
- Create `apps/backend/app/schemas/practice.py` for request/response models.
- Create `apps/backend/app/repositories/practice_repo.py` for database operations.
- Create `apps/backend/app/services/practice_generation.py` for conspect/task generation.
- Create `apps/backend/app/services/practice_evaluation.py` for deterministic evaluation and mastery update mapping.
- Create `apps/backend/app/services/study_completion.py` for capsule generation from a study session.
- Create `apps/backend/app/routers/practice.py` for API endpoints.
- Modify `apps/backend/app/main.py` to include the router.
- Add tests in `tests/backend/unit/test_practice_repo.py`.
- Add tests in `tests/backend/integration/test_practice_api.py`.

Web:

- Modify `apps/web/lib/api.ts` to add study session, practice task, submission, and evaluation types/API calls.
- Create `apps/web/app/(app)/study/[id]/page.tsx` for a study session view.
- Create `apps/web/app/(app)/practice/[id]/page.tsx` for a practice task and evaluation view.
- Modify `apps/web/app/(app)/topics/[id]/page.tsx` to add `Start study session` and show generated practice tasks.
- Modify `apps/web/components/AppNav.tsx` only if a top-level study link is needed after the pages exist.

JetBrains plugin:

- Create `apps/jetbrains-plugin/settings.gradle.kts`.
- Create `apps/jetbrains-plugin/build.gradle.kts`.
- Create `apps/jetbrains-plugin/gradle.properties`.
- Create `apps/jetbrains-plugin/src/main/resources/META-INF/plugin.xml`.
- Create `apps/jetbrains-plugin/src/main/kotlin/ru/proofforge/bridge/ProofForgeSettings.kt`.
- Create `apps/jetbrains-plugin/src/main/kotlin/ru/proofforge/bridge/ProofForgeApiClient.kt`.
- Create `apps/jetbrains-plugin/src/main/kotlin/ru/proofforge/bridge/ProofForgeToolWindowFactory.kt`.
- Create `apps/jetbrains-plugin/src/main/kotlin/ru/proofforge/bridge/SubmissionCollector.kt`.
- Create `apps/jetbrains-plugin/README.md`.

---

## Task 1: Backend Models And Migration

**Files:**

- Create: `apps/backend/app/models/study_session.py`
- Create: `apps/backend/app/models/practice_task.py`
- Create: `apps/backend/app/models/ide_session.py`
- Create: `apps/backend/app/models/ide_submission.py`
- Create: `apps/backend/app/models/evaluation.py`
- Modify: `apps/backend/app/models/__init__.py`
- Create: `apps/backend/alembic/versions/0008_ide_evidence_bridge.py`
- Test: `tests/backend/unit/test_practice_repo.py`

- [ ] **Step 1: Write the failing model/repository smoke test**

Create `tests/backend/unit/test_practice_repo.py`:

```python
import pytest

from app.repositories import practice_repo, topic_repo, user_repo
from app.schemas.practice import (
    EvaluationCreate,
    IdeSubmissionCreate,
    PracticeTaskCreate,
    StudySessionCreate,
)
from app.schemas.topic import TopicStart
from app.schemas.user import UserCreate


@pytest.mark.asyncio
async def test_study_session_task_submission_evaluation_round_trip(db):
    user = await user_repo.create_user(db, UserCreate(email="bridge@example.com", display_name="Bridge"))
    topic = await topic_repo.start_topic(db, TopicStart(user_id=user.id, name="Kotlin Coroutines"))

    session = await practice_repo.create_study_session(
        db,
        StudySessionCreate(
            user_id=user.id,
            topic_id=topic.id,
            conspect_md="## Конспект\nStructured concurrency and cancellation.",
            learning_goals=["Understand structured concurrency"],
        ),
    )

    task = await practice_repo.create_practice_task(
        db,
        PracticeTaskCreate(
            user_id=user.id,
            topic_id=topic.id,
            study_session_id=session.id,
            type="mini_project",
            title="Build a cancellable worker",
            instructions_md="Implement cancellation-aware worker logic.",
            target_concepts=["structured concurrency", "cancellation"],
            difficulty=2,
            expected_evidence=["source_files", "test_output", "reflection"],
            check_commands=["./gradlew test"],
        ),
    )

    submission = await practice_repo.create_submission(
        db,
        IdeSubmissionCreate(
            practice_task_id=task.id,
            user_id=user.id,
            ide_session_id=None,
            files=[{"path": "src/main/kotlin/Worker.kt", "content": "class Worker"}],
            diff="diff --git a/src/main/kotlin/Worker.kt b/src/main/kotlin/Worker.kt",
            test_output="BUILD SUCCESSFUL",
            check_command="./gradlew test",
            exit_code=0,
            reflection="I used cancellation propagation.",
            language="kotlin",
        ),
    )

    evaluation = await practice_repo.create_evaluation(
        db,
        EvaluationCreate(
            submission_id=submission.id,
            score=0.82,
            status="passed",
            feedback_md="Good use of cancellation.",
            concept_scores={"cancellation": 0.85},
            weak_spots=[],
            next_action="continue_lesson",
        ),
    )

    active_tasks = await practice_repo.list_active_tasks(db, user.id)

    assert session.status == "active"
    assert task.status == "submitted"
    assert submission.exit_code == 0
    assert evaluation.status == "passed"
    assert active_tasks[0].id == task.id
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/backend/unit/test_practice_repo.py -q
```

Expected: FAIL with import errors for `app.repositories.practice_repo` and `app.schemas.practice`.

- [ ] **Step 3: Add SQLAlchemy models**

Create `apps/backend/app/models/study_session.py`:

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StudySession(Base):
    __tablename__ = "study_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    topic_id: Mapped[str] = mapped_column(String, ForeignKey("topics.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, default="active")
    conspect_md: Mapped[str] = mapped_column(Text, default="")
    learning_goals: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

Create `apps/backend/app/models/practice_task.py`:

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PracticeTask(Base):
    __tablename__ = "practice_tasks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    topic_id: Mapped[str] = mapped_column(String, ForeignKey("topics.id"), nullable=False)
    study_session_id: Mapped[str] = mapped_column(String, ForeignKey("study_sessions.id"), nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    instructions_md: Mapped[str] = mapped_column(Text, nullable=False)
    target_concepts: Mapped[list] = mapped_column(JSON, default=list)
    difficulty: Mapped[int] = mapped_column(Integer, default=1)
    expected_evidence: Mapped[list] = mapped_column(JSON, default=list)
    check_commands: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String, default="assigned")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
```

Create `apps/backend/app/models/ide_session.py`:

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class IdeSession(Base):
    __tablename__ = "ide_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    ide: Mapped[str] = mapped_column(String, default="jetbrains")
    ide_product: Mapped[str] = mapped_column(String, default="unknown")
    plugin_version: Mapped[str] = mapped_column(String, default="unknown")
    paired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
```

Create `apps/backend/app/models/ide_submission.py`:

```python
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
```

Create `apps/backend/app/models/evaluation.py`:

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    submission_id: Mapped[str] = mapped_column(String, ForeignKey("ide_submissions.id"), nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String, default="needs_revision")
    feedback_md: Mapped[str] = mapped_column(Text, default="")
    concept_scores: Mapped[dict] = mapped_column(JSON, default=dict)
    weak_spots: Mapped[list] = mapped_column(JSON, default=list)
    next_action: Mapped[str] = mapped_column(String, default="revise")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class FollowUp(Base):
    __tablename__ = "follow_ups"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    evaluation_id: Mapped[str] = mapped_column(String, ForeignKey("evaluations.id"), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    expected_answer: Mapped[str] = mapped_column(Text, default="")
    user_answer: Mapped[str] = mapped_column(Text, default="")
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    feedback_md: Mapped[str] = mapped_column(Text, default="")
```

- [ ] **Step 4: Export models**

Modify `apps/backend/app/models/__init__.py` by adding imports:

```python
from app.models.study_session import StudySession
from app.models.practice_task import PracticeTask
from app.models.ide_session import IdeSession
from app.models.ide_submission import IdeSubmission
from app.models.evaluation import Evaluation, FollowUp
```

Add names to `__all__`:

```python
"StudySession", "PracticeTask", "IdeSession", "IdeSubmission", "Evaluation", "FollowUp",
```

- [ ] **Step 5: Add Alembic migration**

Create `apps/backend/alembic/versions/0008_ide_evidence_bridge.py`:

```python
"""ide evidence bridge tables

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "study_sessions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("topic_id", sa.String(), sa.ForeignKey("topics.id"), nullable=False),
        sa.Column("status", sa.String(), server_default="active"),
        sa.Column("conspect_md", sa.Text(), server_default=""),
        sa.Column("learning_goals", sa.JSON(), server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_study_sessions_user_topic", "study_sessions", ["user_id", "topic_id"])

    op.create_table(
        "practice_tasks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("topic_id", sa.String(), sa.ForeignKey("topics.id"), nullable=False),
        sa.Column("study_session_id", sa.String(), sa.ForeignKey("study_sessions.id"), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("instructions_md", sa.Text(), nullable=False),
        sa.Column("target_concepts", sa.JSON(), server_default="[]"),
        sa.Column("difficulty", sa.Integer(), server_default="1"),
        sa.Column("expected_evidence", sa.JSON(), server_default="[]"),
        sa.Column("check_commands", sa.JSON(), server_default="[]"),
        sa.Column("status", sa.String(), server_default="assigned"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_practice_tasks_user_status", "practice_tasks", ["user_id", "status"])
    op.create_index("ix_practice_tasks_session", "practice_tasks", ["study_session_id"])

    op.create_table(
        "ide_sessions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("ide", sa.String(), server_default="jetbrains"),
        sa.Column("ide_product", sa.String(), server_default="unknown"),
        sa.Column("plugin_version", sa.String(), server_default="unknown"),
        sa.Column("paired_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ide_sessions_user_id", "ide_sessions", ["user_id"])

    op.create_table(
        "ide_submissions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("practice_task_id", sa.String(), sa.ForeignKey("practice_tasks.id"), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("ide_session_id", sa.String(), sa.ForeignKey("ide_sessions.id"), nullable=True),
        sa.Column("files", sa.JSON(), server_default="[]"),
        sa.Column("diff", sa.Text(), server_default=""),
        sa.Column("test_output", sa.Text(), server_default=""),
        sa.Column("check_command", sa.Text(), server_default=""),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("reflection", sa.Text(), server_default=""),
        sa.Column("language", sa.String(), server_default="unknown"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ide_submissions_task", "ide_submissions", ["practice_task_id"])

    op.create_table(
        "evaluations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("submission_id", sa.String(), sa.ForeignKey("ide_submissions.id"), nullable=False),
        sa.Column("score", sa.Float(), server_default="0"),
        sa.Column("status", sa.String(), server_default="needs_revision"),
        sa.Column("feedback_md", sa.Text(), server_default=""),
        sa.Column("concept_scores", sa.JSON(), server_default="{}"),
        sa.Column("weak_spots", sa.JSON(), server_default="[]"),
        sa.Column("next_action", sa.String(), server_default="revise"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_evaluations_submission", "evaluations", ["submission_id"])

    op.create_table(
        "follow_ups",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("evaluation_id", sa.String(), sa.ForeignKey("evaluations.id"), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("expected_answer", sa.Text(), server_default=""),
        sa.Column("user_answer", sa.Text(), server_default=""),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("feedback_md", sa.Text(), server_default=""),
    )


def downgrade() -> None:
    op.drop_table("follow_ups")
    op.drop_table("evaluations")
    op.drop_table("ide_submissions")
    op.drop_table("ide_sessions")
    op.drop_table("practice_tasks")
    op.drop_table("study_sessions")
```

- [ ] **Step 6: Run test again**

Run:

```bash
pytest tests/backend/unit/test_practice_repo.py -q
```

Expected: still FAIL because schemas and repository do not exist yet.

- [ ] **Step 7: Commit**

```bash
git add apps/backend/app/models apps/backend/alembic/versions/0008_ide_evidence_bridge.py tests/backend/unit/test_practice_repo.py
git commit -m "feat: add practice bridge data models"
```

---

## Task 2: Backend Schemas And Repository

**Files:**

- Create: `apps/backend/app/schemas/practice.py`
- Create: `apps/backend/app/repositories/practice_repo.py`
- Modify: `apps/backend/app/repositories/__init__.py` if needed for import consistency
- Test: `tests/backend/unit/test_practice_repo.py`

- [ ] **Step 1: Add Pydantic schemas**

Create `apps/backend/app/schemas/practice.py`:

```python
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class StudySessionCreate(BaseModel):
    user_id: str
    topic_id: str
    conspect_md: str = ""
    learning_goals: list[str] = Field(default_factory=list)


class StudySessionOut(BaseModel):
    id: str
    user_id: str
    topic_id: str
    status: str
    conspect_md: str
    learning_goals: list[str]
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class PracticeTaskCreate(BaseModel):
    user_id: str
    topic_id: str
    study_session_id: str
    type: str
    title: str
    instructions_md: str
    target_concepts: list[str] = Field(default_factory=list)
    difficulty: int = 1
    expected_evidence: list[str] = Field(default_factory=list)
    check_commands: list[str] = Field(default_factory=list)


class PracticeTaskOut(BaseModel):
    id: str
    user_id: str
    topic_id: str
    study_session_id: str
    type: str
    title: str
    instructions_md: str
    target_concepts: list[str]
    difficulty: int
    expected_evidence: list[str]
    check_commands: list[str]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class IdeSessionCreate(BaseModel):
    user_id: str
    ide: str = "jetbrains"
    ide_product: str = "unknown"
    plugin_version: str = "unknown"


class IdeSessionOut(BaseModel):
    id: str
    user_id: str
    ide: str
    ide_product: str
    plugin_version: str
    paired_at: datetime
    last_seen_at: datetime

    model_config = {"from_attributes": True}


class IdeSubmissionCreate(BaseModel):
    practice_task_id: str
    user_id: str
    ide_session_id: str | None = None
    files: list[dict[str, Any]] = Field(default_factory=list)
    diff: str = ""
    test_output: str = ""
    check_command: str = ""
    exit_code: int | None = None
    reflection: str = ""
    language: str = "unknown"


class IdeSubmissionOut(BaseModel):
    id: str
    practice_task_id: str
    user_id: str
    ide_session_id: str | None
    files: list[dict[str, Any]]
    diff: str
    test_output: str
    check_command: str
    exit_code: int | None
    reflection: str
    language: str
    submitted_at: datetime

    model_config = {"from_attributes": True}


class EvaluationCreate(BaseModel):
    submission_id: str
    score: float
    status: str
    feedback_md: str
    concept_scores: dict[str, float] = Field(default_factory=dict)
    weak_spots: list[dict[str, Any]] = Field(default_factory=list)
    next_action: str


class EvaluationOut(BaseModel):
    id: str
    submission_id: str
    score: float
    status: str
    feedback_md: str
    concept_scores: dict[str, float]
    weak_spots: list[dict[str, Any]]
    next_action: str
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Add repository**

Create `apps/backend/app/repositories/practice_repo.py`:

```python
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Evaluation, IdeSession, IdeSubmission, PracticeTask, StudySession
from app.schemas.practice import (
    EvaluationCreate,
    IdeSessionCreate,
    IdeSubmissionCreate,
    PracticeTaskCreate,
    StudySessionCreate,
)


async def create_study_session(db: AsyncSession, data: StudySessionCreate) -> StudySession:
    session = StudySession(
        user_id=data.user_id,
        topic_id=data.topic_id,
        conspect_md=data.conspect_md,
        learning_goals=data.learning_goals,
        status="active",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_study_session(db: AsyncSession, session_id: str) -> StudySession | None:
    result = await db.execute(select(StudySession).where(StudySession.id == session_id))
    return result.scalar_one_or_none()


async def create_practice_task(db: AsyncSession, data: PracticeTaskCreate) -> PracticeTask:
    task = PracticeTask(
        user_id=data.user_id,
        topic_id=data.topic_id,
        study_session_id=data.study_session_id,
        type=data.type,
        title=data.title,
        instructions_md=data.instructions_md,
        target_concepts=data.target_concepts,
        difficulty=data.difficulty,
        expected_evidence=data.expected_evidence,
        check_commands=data.check_commands,
        status="assigned",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def get_practice_task(db: AsyncSession, task_id: str) -> PracticeTask | None:
    result = await db.execute(select(PracticeTask).where(PracticeTask.id == task_id))
    return result.scalar_one_or_none()


async def list_active_tasks(db: AsyncSession, user_id: str) -> list[PracticeTask]:
    result = await db.execute(
        select(PracticeTask)
        .where(PracticeTask.user_id == user_id)
        .where(PracticeTask.status.in_(["assigned", "opened_in_ide", "submitted", "needs_revision"]))
        .order_by(PracticeTask.created_at.desc())
    )
    return list(result.scalars().all())


async def pair_ide_session(db: AsyncSession, data: IdeSessionCreate) -> IdeSession:
    session = IdeSession(
        user_id=data.user_id,
        ide=data.ide,
        ide_product=data.ide_product,
        plugin_version=data.plugin_version,
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def create_submission(db: AsyncSession, data: IdeSubmissionCreate) -> IdeSubmission:
    submission = IdeSubmission(
        practice_task_id=data.practice_task_id,
        user_id=data.user_id,
        ide_session_id=data.ide_session_id,
        files=data.files,
        diff=data.diff,
        test_output=data.test_output,
        check_command=data.check_command,
        exit_code=data.exit_code,
        reflection=data.reflection,
        language=data.language,
    )
    db.add(submission)

    task = await get_practice_task(db, data.practice_task_id)
    if task:
        task.status = "submitted"

    await db.commit()
    await db.refresh(submission)
    return submission


async def get_submission(db: AsyncSession, submission_id: str) -> IdeSubmission | None:
    result = await db.execute(select(IdeSubmission).where(IdeSubmission.id == submission_id))
    return result.scalar_one_or_none()


async def create_evaluation(db: AsyncSession, data: EvaluationCreate) -> Evaluation:
    evaluation = Evaluation(
        submission_id=data.submission_id,
        score=data.score,
        status=data.status,
        feedback_md=data.feedback_md,
        concept_scores=data.concept_scores,
        weak_spots=data.weak_spots,
        next_action=data.next_action,
    )
    db.add(evaluation)

    submission = await get_submission(db, data.submission_id)
    if submission:
        task = await get_practice_task(db, submission.practice_task_id)
        if task:
            task.status = "completed" if data.status == "passed" else "needs_revision"

    await db.commit()
    await db.refresh(evaluation)
    return evaluation
```

- [ ] **Step 3: Run repository test**

Run:

```bash
pytest tests/backend/unit/test_practice_repo.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add apps/backend/app/schemas/practice.py apps/backend/app/repositories/practice_repo.py tests/backend/unit/test_practice_repo.py
git commit -m "feat: add practice bridge repository"
```

---

## Task 3: Practice Generation Service And API

**Files:**

- Create: `apps/backend/app/services/practice_generation.py`
- Create: `apps/backend/app/routers/practice.py`
- Modify: `apps/backend/app/main.py`
- Test: `tests/backend/integration/test_practice_api.py`

- [ ] **Step 1: Write failing API test**

Create `tests/backend/integration/test_practice_api.py`:

```python
import pytest

from app.repositories import topic_repo, user_repo
from app.schemas.topic import TopicStart
from app.schemas.user import UserCreate


@pytest.mark.asyncio
async def test_create_study_session_generates_conspect_and_task(client, db):
    user = await user_repo.create_user(db, UserCreate(email="study@example.com", display_name="Study"))
    topic = await topic_repo.start_topic(db, TopicStart(user_id=user.id, name="Go interfaces"))

    res = await client.post(
        "/api/study-sessions",
        json={"user_id": user.id, "topic_id": topic.id},
    )

    assert res.status_code == 201
    body = res.json()
    assert body["session"]["topic_id"] == topic.id
    assert "Go interfaces" in body["session"]["conspect_md"]
    assert len(body["tasks"]) == 1
    assert body["tasks"][0]["type"] == "mini_project"


@pytest.mark.asyncio
async def test_plugin_can_pair_list_tasks_and_submit(client, db):
    user = await user_repo.create_user(db, UserCreate(email="plugin@example.com", display_name="Plugin"))
    topic = await topic_repo.start_topic(db, TopicStart(user_id=user.id, name="Python async"))

    created = await client.post("/api/study-sessions", json={"user_id": user.id, "topic_id": topic.id})
    task_id = created.json()["tasks"][0]["id"]

    paired = await client.post(
        "/api/ide-sessions/pair",
        json={"user_id": user.id, "ide_product": "IntelliJ IDEA", "plugin_version": "0.1.0"},
    )
    assert paired.status_code == 201

    listed = await client.get(f"/api/practice-tasks?user_id={user.id}&status=active")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == task_id

    submission = await client.post(
        f"/api/practice-tasks/{task_id}/submissions",
        json={
            "user_id": user.id,
            "ide_session_id": paired.json()["id"],
            "files": [{"path": "main.py", "content": "print('ok')"}],
            "diff": "diff --git a/main.py b/main.py",
            "test_output": "1 passed",
            "check_command": "pytest",
            "exit_code": 0,
            "reflection": "I handled the async flow.",
            "language": "python",
        },
    )
    assert submission.status_code == 201

    evaluated = await client.post(f"/api/submissions/{submission.json()['id']}/evaluate")
    assert evaluated.status_code == 201
    assert evaluated.json()["status"] == "passed"
```

- [ ] **Step 2: Run API test to verify it fails**

Run:

```bash
pytest tests/backend/integration/test_practice_api.py -q
```

Expected: FAIL with `404 Not Found` for `/api/study-sessions`.

- [ ] **Step 3: Add deterministic generation service**

Create `apps/backend/app/services/practice_generation.py`:

```python
from app.models import Topic
from app.schemas.practice import PracticeTaskCreate, StudySessionCreate


def build_study_session(topic: Topic) -> StudySessionCreate:
    return StudySessionCreate(
        user_id=topic.user_id,
        topic_id=topic.id,
        conspect_md=(
            f"## Конспект: {topic.name}\n\n"
            "Сессия сфокусирована на понимании ключевых концепций через короткую теорию "
            "и mini-project в реальной IDE.\n\n"
            "## Практика\n\n"
            "Реши mini-project локально и отправь evidence через JetBrains plugin."
        ),
        learning_goals=[f"Understand and apply {topic.name} in a small project"],
    )


def build_initial_mini_project(session_id: str, topic: Topic) -> PracticeTaskCreate:
    return PracticeTaskCreate(
        user_id=topic.user_id,
        topic_id=topic.id,
        study_session_id=session_id,
        type="mini_project",
        title=f"Mini-project: {topic.name}",
        instructions_md=(
            f"## Задание\n\n"
            f"Создай небольшой проект или измени текущий проект так, чтобы показать понимание темы "
            f"**{topic.name}**.\n\n"
            "## Что отправить\n\n"
            "- измененные исходные файлы или diff;\n"
            "- вывод тестов или команды проверки, если есть;\n"
            "- короткую рефлексию: что сделал, где были сложности, какие trade-offs выбрал.\n"
        ),
        target_concepts=[topic.name],
        difficulty=2,
        expected_evidence=["source_files", "diff", "test_output", "reflection"],
        check_commands=[],
    )
```

- [ ] **Step 4: Add practice router**

Create `apps/backend/app/routers/practice.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.repositories import practice_repo, topic_repo
from app.schemas.practice import (
    EvaluationOut,
    IdeSessionCreate,
    IdeSessionOut,
    IdeSubmissionCreate,
    IdeSubmissionOut,
    PracticeTaskOut,
    StudySessionOut,
)
from app.services.practice_evaluation import evaluate_submission
from app.services.practice_generation import build_initial_mini_project, build_study_session

router = APIRouter(tags=["practice"])


@router.post("/study-sessions", status_code=201)
async def create_study_session(data: dict, db: AsyncSession = Depends(get_db)):
    topic = await topic_repo.get_topic(db, data["topic_id"])
    if not topic or topic.user_id != data["user_id"]:
        raise HTTPException(status_code=404, detail="Topic not found")

    session = await practice_repo.create_study_session(db, build_study_session(topic))
    task = await practice_repo.create_practice_task(db, build_initial_mini_project(session.id, topic))
    return {
        "session": StudySessionOut.model_validate(session),
        "tasks": [PracticeTaskOut.model_validate(task)],
    }


@router.get("/study-sessions/{session_id}", response_model=StudySessionOut)
async def get_study_session(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await practice_repo.get_study_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Study session not found")
    return session


@router.get("/practice-tasks", response_model=list[PracticeTaskOut])
async def list_practice_tasks(
    user_id: str,
    status: str = Query("active"),
    db: AsyncSession = Depends(get_db),
):
    if status != "active":
        raise HTTPException(status_code=422, detail="Only status=active is supported in v1")
    return await practice_repo.list_active_tasks(db, user_id)


@router.get("/practice-tasks/{task_id}", response_model=PracticeTaskOut)
async def get_practice_task(task_id: str, db: AsyncSession = Depends(get_db)):
    task = await practice_repo.get_practice_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Practice task not found")
    return task


@router.post("/ide-sessions/pair", response_model=IdeSessionOut, status_code=201)
async def pair_ide_session(data: IdeSessionCreate, db: AsyncSession = Depends(get_db)):
    return await practice_repo.pair_ide_session(db, data)


@router.post("/practice-tasks/{task_id}/submissions", response_model=IdeSubmissionOut, status_code=201)
async def submit_practice_task(
    task_id: str,
    data: IdeSubmissionCreate,
    db: AsyncSession = Depends(get_db),
):
    task = await practice_repo.get_practice_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Practice task not found")
    if data.practice_task_id != task_id:
        data.practice_task_id = task_id
    return await practice_repo.create_submission(db, data)


@router.post("/submissions/{submission_id}/evaluate", response_model=EvaluationOut, status_code=201)
async def evaluate_submission_endpoint(submission_id: str, db: AsyncSession = Depends(get_db)):
    submission = await practice_repo.get_submission(db, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    evaluation = await evaluate_submission(db, submission)
    return evaluation
```

- [ ] **Step 5: Add evaluation service stub used by router**

Create `apps/backend/app/services/practice_evaluation.py`:

```python
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IdeSubmission
from app.repositories import practice_repo
from app.schemas.practice import EvaluationCreate


async def evaluate_submission(db: AsyncSession, submission: IdeSubmission):
    passed = submission.exit_code == 0 or "passed" in submission.test_output.lower() or "success" in submission.test_output.lower()
    has_reflection = len((submission.reflection or "").strip()) >= 12
    score = 0.8 if passed and has_reflection else 0.45
    status = "passed" if score >= 0.7 else "needs_revision"
    feedback = (
        "## Evaluation\n\n"
        "The submitted evidence passed the deterministic checks and includes a useful reflection."
        if status == "passed"
        else "## Evaluation\n\nThe evidence is incomplete. Include passing output and a short reflection."
    )
    return await practice_repo.create_evaluation(
        db,
        EvaluationCreate(
            submission_id=submission.id,
            score=score,
            status=status,
            feedback_md=feedback,
            concept_scores={submission.language: score} if submission.language else {},
            weak_spots=[] if status == "passed" else [{"concept": "evidence quality", "severity": 1.0}],
            next_action="continue_lesson" if status == "passed" else "revise",
        ),
    )
```

- [ ] **Step 6: Include router in FastAPI app**

Modify `apps/backend/app/main.py`:

```python
from app.routers import users, events, topics, capsules, reviews, agent_context, cards, mastery, auth, analytics, metrics, practice

app.include_router(practice.router, prefix="/api")
```

- [ ] **Step 7: Run API test**

Run:

```bash
pytest tests/backend/integration/test_practice_api.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add apps/backend/app/services/practice_generation.py apps/backend/app/services/practice_evaluation.py apps/backend/app/routers/practice.py apps/backend/app/main.py tests/backend/integration/test_practice_api.py
git commit -m "feat: add practice bridge API"
```

---

## Task 4: Evaluation Updates Mastery Signals

**Files:**

- Modify: `apps/backend/app/services/practice_evaluation.py`
- Test: `tests/backend/integration/test_practice_api.py`

- [ ] **Step 1: Add failing test for mastery update**

Append to `tests/backend/integration/test_practice_api.py`:

```python
@pytest.mark.asyncio
async def test_passing_submission_updates_mastery(client, db):
    user = await user_repo.create_user(db, UserCreate(email="mastery-bridge@example.com", display_name="Mastery"))
    topic = await topic_repo.start_topic(db, TopicStart(user_id=user.id, name="TypeScript narrowing"))

    created = await client.post("/api/study-sessions", json={"user_id": user.id, "topic_id": topic.id})
    task_id = created.json()["tasks"][0]["id"]

    submission = await client.post(
        f"/api/practice-tasks/{task_id}/submissions",
        json={
            "practice_task_id": task_id,
            "user_id": user.id,
            "files": [{"path": "src/narrow.ts", "content": "export const ok = true"}],
            "test_output": "1 passed",
            "exit_code": 0,
            "reflection": "I used type guards to narrow union types.",
            "language": "typescript",
        },
    )

    await client.post(f"/api/submissions/{submission.json()['id']}/evaluate")

    progress = await client.get(f"/api/mastery/progress?userId={user.id}&topic={topic.id}")
    assert progress.status_code == 200
    concepts = progress.json()["concepts"]
    assert concepts[0]["concept"] == "TypeScript narrowing"
    assert concepts[0]["practice_reps"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/backend/integration/test_practice_api.py::test_passing_submission_updates_mastery -q
```

Expected: FAIL because `practice_evaluation.py` does not call `mastery_repo.record`.

- [ ] **Step 3: Update evaluation service**

Modify `apps/backend/app/services/practice_evaluation.py`:

```python
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IdeSubmission
from app.repositories import mastery_repo, practice_repo
from app.schemas.practice import EvaluationCreate


async def evaluate_submission(db: AsyncSession, submission: IdeSubmission):
    task = await practice_repo.get_practice_task(db, submission.practice_task_id)
    passed = submission.exit_code == 0 or "passed" in submission.test_output.lower() or "success" in submission.test_output.lower()
    has_reflection = len((submission.reflection or "").strip()) >= 12
    score = 0.8 if passed and has_reflection else 0.45
    status = "passed" if score >= 0.7 else "needs_revision"
    feedback = (
        "## Evaluation\n\n"
        "The submitted evidence passed the deterministic checks and includes a useful reflection."
        if status == "passed"
        else "## Evaluation\n\nThe evidence is incomplete. Include passing output and a short reflection."
    )
    evaluation = await practice_repo.create_evaluation(
        db,
        EvaluationCreate(
            submission_id=submission.id,
            score=score,
            status=status,
            feedback_md=feedback,
            concept_scores={concept: score for concept in (task.target_concepts if task else [submission.language])},
            weak_spots=[] if status == "passed" else [{"concept": "evidence quality", "severity": 1.0}],
            next_action="continue_lesson" if status == "passed" else "revise",
        ),
    )

    if task and status == "passed":
        for concept in task.target_concepts:
            await mastery_repo.record(
                db,
                user_id=submission.user_id,
                topic_id=task.topic_id,
                concept=concept,
                kind="practice",
                difficulty=task.difficulty,
                quality_score=score,
                struggle_passed=0,
            )

    return evaluation
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/backend/unit/test_practice_repo.py tests/backend/integration/test_practice_api.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/services/practice_evaluation.py tests/backend/integration/test_practice_api.py
git commit -m "feat: update mastery from IDE submissions"
```

---

## Task 5: Web API Client And Study Session Page

**Files:**

- Modify: `apps/web/lib/api.ts`
- Create: `apps/web/app/(app)/study/[id]/page.tsx`
- Create: `apps/web/app/(app)/practice/[id]/page.tsx`

- [ ] **Step 1: Add API types and client methods**

Modify `apps/web/lib/api.ts` by adding after the topic section:

```ts
// -- Practice Bridge --
export type StudySession = {
  id: string
  user_id: string
  topic_id: string
  status: 'active' | 'paused' | 'completed'
  conspect_md: string
  learning_goals: string[]
  created_at: string
  completed_at: string | null
}

export type PracticeTask = {
  id: string
  user_id: string
  topic_id: string
  study_session_id: string
  type: 'theory' | 'written' | 'coding' | 'debugging' | 'mini_project'
  title: string
  instructions_md: string
  target_concepts: string[]
  difficulty: number
  expected_evidence: string[]
  check_commands: string[]
  status: 'assigned' | 'opened_in_ide' | 'submitted' | 'evaluated' | 'needs_revision' | 'completed'
  created_at: string
  updated_at: string
}

export type IdeSubmission = {
  id: string
  practice_task_id: string
  user_id: string
  ide_session_id: string | null
  files: Array<{ path: string; content: string }>
  diff: string
  test_output: string
  check_command: string
  exit_code: number | null
  reflection: string
  language: string
  submitted_at: string
}

export type Evaluation = {
  id: string
  submission_id: string
  score: number
  status: 'passed' | 'needs_revision' | 'failed'
  feedback_md: string
  concept_scores: Record<string, number>
  weak_spots: Array<{ concept: string; severity: number }>
  next_action: string
  created_at: string
}

export const practice = {
  startSession: (userId: string, topicId: string) =>
    req<{ session: StudySession; tasks: PracticeTask[] }>('/api/study-sessions', {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, topic_id: topicId }),
    }),
  getSession: (sessionId: string) =>
    req<StudySession>(`/api/study-sessions/${sessionId}`),
  listActiveTasks: (userId: string) =>
    req<PracticeTask[]>(`/api/practice-tasks?user_id=${userId}&status=active`),
  getTask: (taskId: string) =>
    req<PracticeTask>(`/api/practice-tasks/${taskId}`),
}
```

- [ ] **Step 2: Create study session page**

Create `apps/web/app/(app)/study/[id]/page.tsx`:

```tsx
'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { getStoredUser } from '@/lib/auth'
import { practice, type PracticeTask, type StudySession } from '@/lib/api'
import { SkeletonText } from '@/components/ui/Skeleton'

export default function StudySessionPage() {
  const { id } = useParams<{ id: string }>()
  const user = getStoredUser()
  const [session, setSession] = useState<StudySession | null>(null)
  const [tasks, setTasks] = useState<PracticeTask[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!user) return
    Promise.all([
      practice.getSession(id),
      practice.listActiveTasks(user.user_id),
    ]).then(([s, active]) => {
      setSession(s)
      setTasks(active.filter((task) => task.study_session_id === s.id))
    }).finally(() => setLoading(false))
  }, [id, user?.user_id])

  if (loading) {
    return <div className="max-w-3xl mx-auto px-5 py-8"><SkeletonText lines={8} /></div>
  }

  if (!session) {
    return <div className="max-w-3xl mx-auto px-5 py-16 text-center text-mute">Сессия не найдена</div>
  }

  return (
    <div className="max-w-3xl mx-auto px-5 py-8">
      <Link href="/dashboard" className="text-sm text-mute hover:text-ink font-mono">← назад</Link>
      <div className="mt-6 mb-8">
        <div className="text-xs font-mono text-accent mb-2">Учебная сессия</div>
        <h1 className="font-display text-3xl font-bold text-ink">Конспект и практика</h1>
      </div>

      <section className="prose-grasp mb-8">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{session.conspect_md}</ReactMarkdown>
      </section>

      <section>
        <h2 className="text-sm font-mono text-mute mb-3">Задания</h2>
        <div className="space-y-3">
          {tasks.map((task) => (
            <Link key={task.id} href={`/practice/${task.id}`} className="surface surface-hover rounded-xl p-4 block">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-xs font-mono text-accent mb-1">{task.type}</div>
                  <div className="font-semibold text-ink">{task.title}</div>
                  <div className="text-sm text-mute mt-1">{task.target_concepts.join(', ')}</div>
                </div>
                <span className="text-xs font-mono text-mute">{task.status}</span>
              </div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  )
}
```

- [ ] **Step 3: Create practice task page**

Create `apps/web/app/(app)/practice/[id]/page.tsx`:

```tsx
'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { practice, type PracticeTask } from '@/lib/api'
import { SkeletonText } from '@/components/ui/Skeleton'

export default function PracticeTaskPage() {
  const { id } = useParams<{ id: string }>()
  const [task, setTask] = useState<PracticeTask | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    practice.getTask(id).then(setTask).finally(() => setLoading(false))
  }, [id])

  if (loading) {
    return <div className="max-w-3xl mx-auto px-5 py-8"><SkeletonText lines={8} /></div>
  }

  if (!task) {
    return <div className="max-w-3xl mx-auto px-5 py-16 text-center text-mute">Задание не найдено</div>
  }

  return (
    <div className="max-w-3xl mx-auto px-5 py-8">
      <Link href={`/study/${task.study_session_id}`} className="text-sm text-mute hover:text-ink font-mono">← к сессии</Link>
      <div className="mt-6 mb-6">
        <div className="text-xs font-mono text-accent mb-2">IDE task</div>
        <h1 className="font-display text-3xl font-bold text-ink">{task.title}</h1>
        <p className="text-sm text-mute mt-2 font-mono">status: {task.status}</p>
      </div>

      <div className="surface rounded-2xl p-5 mb-6">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{task.instructions_md}</ReactMarkdown>
      </div>

      <div className="grid sm:grid-cols-2 gap-3 mb-6">
        <div className="surface rounded-xl p-4">
          <div className="text-xs font-mono text-mute mb-2">Ожидаем evidence</div>
          <ul className="text-sm text-ink space-y-1">
            {task.expected_evidence.map((item) => <li key={item}>• {item}</li>)}
          </ul>
        </div>
        <div className="surface rounded-xl p-4">
          <div className="text-xs font-mono text-mute mb-2">Команды проверки</div>
          {task.check_commands.length
            ? task.check_commands.map((cmd) => <code key={cmd} className="block text-sm text-ink">{cmd}</code>)
            : <p className="text-sm text-mute">Запусти проверки в IDE и отправь вывод через plugin.</p>
          }
        </div>
      </div>

      <div className="surface rounded-2xl p-5 border border-accent/20 bg-accentsoft/20">
        <div className="font-semibold text-ink mb-1">Submit from JetBrains</div>
        <p className="text-sm text-mute">
          Открой Proof Forge plugin в JetBrains, выбери это задание и отправь файлы, diff, вывод тестов и reflection.
        </p>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Build web app**

Run:

```bash
npm run build
```

Working directory: `apps/web`

Expected: build succeeds.

- [ ] **Step 5: Commit**

```bash
git add apps/web/lib/api.ts apps/web/app/'(app)'/study/'[id]'/page.tsx apps/web/app/'(app)'/practice/'[id]'/page.tsx
git commit -m "feat: add practice bridge web pages"
```

---

## Task 6: Web Topic Entry Point

**Files:**

- Modify: `apps/web/app/(app)/topics/[id]/page.tsx`

- [ ] **Step 1: Add start study session handler**

Modify imports in `apps/web/app/(app)/topics/[id]/page.tsx`:

```ts
import { topics, practice, type Topic, type TopicMaterial } from '@/lib/api'
```

Add state near existing generation state:

```ts
const [startingStudy, setStartingStudy] = useState(false)
const [studyError, setStudyError] = useState('')
```

Add handler near `handleGenerate`:

```ts
const handleStartStudy = async () => {
  if (!user || !topic) return
  setStartingStudy(true)
  setStudyError('')
  try {
    const result = await practice.startSession(user.user_id, topic.id)
    router.push(`/study/${result.session.id}`)
  } catch (err: unknown) {
    setStudyError(err instanceof Error ? err.message : 'Ошибка запуска обучения')
  } finally {
    setStartingStudy(false)
  }
}
```

- [ ] **Step 2: Add study CTA above capsule generation**

In the return block before the existing `Generate button` section, insert:

```tsx
{studyError && (
  <div className="mb-4 px-4 py-3 rounded-xl bg-danger/10 border border-danger/20 text-sm text-danger">
    {studyError}
  </div>
)}

<div className="surface rounded-2xl p-5 mb-6 border border-accent/20 bg-accentsoft/20">
  <div className="text-xs font-mono text-accent mb-1">Новый flow</div>
  <h2 className="font-display text-xl font-bold text-ink mb-2">Учиться с практикой</h2>
  <p className="text-sm text-mute mb-4">
    Создай конспект и mini-project. Решение отправишь из JetBrains без ручной загрузки файлов.
  </p>
  <button
    onClick={handleStartStudy}
    disabled={startingStudy}
    className="w-full py-3 rounded-xl bg-accent text-[#06140d] font-semibold text-sm hover:bg-accentdk transition-colors disabled:opacity-50"
  >
    {startingStudy ? 'Запускаем...' : 'Начать обучение →'}
  </button>
</div>
```

- [ ] **Step 3: Build web app**

Run:

```bash
npm run build
```

Working directory: `apps/web`

Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add apps/web/app/'(app)'/topics/'[id]'/page.tsx
git commit -m "feat: add study session entry point"
```

---

## Task 7: JetBrains Plugin Scaffold And API Client

**Files:**

- Create: `apps/jetbrains-plugin/settings.gradle.kts`
- Create: `apps/jetbrains-plugin/build.gradle.kts`
- Create: `apps/jetbrains-plugin/gradle.properties`
- Create: `apps/jetbrains-plugin/src/main/resources/META-INF/plugin.xml`
- Create: `apps/jetbrains-plugin/src/main/kotlin/ru/proofforge/bridge/ProofForgeSettings.kt`
- Create: `apps/jetbrains-plugin/src/main/kotlin/ru/proofforge/bridge/ProofForgeApiClient.kt`
- Create: `apps/jetbrains-plugin/README.md`

- [ ] **Step 1: Add Gradle settings**

Create `apps/jetbrains-plugin/settings.gradle.kts`:

```kotlin
pluginManagement {
    repositories {
        mavenCentral()
        gradlePluginPortal()
        intellijPlatform {
            defaultRepositories()
        }
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        mavenCentral()
        intellijPlatform {
            defaultRepositories()
        }
    }
}

rootProject.name = "proof-forge-jetbrains-plugin"
```

- [ ] **Step 2: Add Gradle build**

Create `apps/jetbrains-plugin/build.gradle.kts`:

```kotlin
plugins {
    kotlin("jvm") version "2.1.21"
    id("org.jetbrains.intellij.platform") version "2.7.2"
}

group = "ru.proofforge"
version = "0.1.0"

dependencies {
    intellijPlatform {
        intellijIdeaCommunity("2025.1.3")
        bundledPlugin("com.intellij.java")
    }
}

intellijPlatform {
    pluginConfiguration {
        id = "ru.proofforge.bridge"
        name = "Proof Forge"
        version = project.version.toString()
        vendor {
            name = "Proof Forge"
        }
    }
}

kotlin {
    jvmToolchain(21)
}
```

- [ ] **Step 3: Add Gradle properties**

Create `apps/jetbrains-plugin/gradle.properties`:

```properties
org.gradle.jvmargs=-Xmx2g
kotlin.code.style=official
```

- [ ] **Step 4: Add plugin descriptor**

Create `apps/jetbrains-plugin/src/main/resources/META-INF/plugin.xml`:

```xml
<idea-plugin>
    <id>ru.proofforge.bridge</id>
    <name>Proof Forge</name>
    <vendor>Proof Forge</vendor>

    <depends>com.intellij.modules.platform</depends>

    <extensions defaultExtensionNs="com.intellij">
        <toolWindow id="Proof Forge" anchor="right" factoryClass="ru.proofforge.bridge.ProofForgeToolWindowFactory"/>
    </extensions>
</idea-plugin>
```

- [ ] **Step 5: Add settings model**

Create `apps/jetbrains-plugin/src/main/kotlin/ru/proofforge/bridge/ProofForgeSettings.kt`:

```kotlin
package ru.proofforge.bridge

data class ProofForgeSettings(
    val apiBaseUrl: String = "http://localhost:8000",
    val userId: String = "",
    val ideSessionId: String = "",
)
```

- [ ] **Step 6: Add API client**

Create `apps/jetbrains-plugin/src/main/kotlin/ru/proofforge/bridge/ProofForgeApiClient.kt`:

```kotlin
package ru.proofforge.bridge

import java.net.URI
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse

class ProofForgeApiClient(private val settings: ProofForgeSettings) {
    private val client = HttpClient.newHttpClient()

    fun listActiveTasks(): String {
        require(settings.userId.isNotBlank()) { "Proof Forge user id is required" }
        val request = HttpRequest.newBuilder()
            .uri(URI.create("${settings.apiBaseUrl}/api/practice-tasks?user_id=${settings.userId}&status=active"))
            .GET()
            .build()
        return client.send(request, HttpResponse.BodyHandlers.ofString()).body()
    }

    fun pair(ideProduct: String, pluginVersion: String): String {
        require(settings.userId.isNotBlank()) { "Proof Forge user id is required" }
        val json = """{"user_id":"${settings.userId}","ide":"jetbrains","ide_product":"$ideProduct","plugin_version":"$pluginVersion"}"""
        val request = HttpRequest.newBuilder()
            .uri(URI.create("${settings.apiBaseUrl}/api/ide-sessions/pair"))
            .header("Content-Type", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString(json))
            .build()
        return client.send(request, HttpResponse.BodyHandlers.ofString()).body()
    }

    fun submit(taskId: String, payloadJson: String): String {
        val request = HttpRequest.newBuilder()
            .uri(URI.create("${settings.apiBaseUrl}/api/practice-tasks/$taskId/submissions"))
            .header("Content-Type", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString(payloadJson))
            .build()
        return client.send(request, HttpResponse.BodyHandlers.ofString()).body()
    }
}
```

- [ ] **Step 7: Add plugin README**

Create `apps/jetbrains-plugin/README.md`:

```markdown
# Proof Forge JetBrains Plugin

Minimal IDE Evidence Bridge for Proof Forge.

V1 responsibilities:

- pair a JetBrains IDE session with a Proof Forge user id;
- list active practice tasks;
- submit selected files, command output, and reflection.

The plugin does not generate projects, manage dependencies, or modify user code.
```

- [ ] **Step 8: Run plugin build**

Run:

```bash
./gradlew buildPlugin
```

Working directory: `apps/jetbrains-plugin`

Expected: plugin builds, or fails only because Gradle wrapper is not present. If wrapper is not present, run `gradle wrapper` with a local Gradle install or add wrapper files from the IntelliJ Platform template before retrying.

- [ ] **Step 9: Commit**

```bash
git add apps/jetbrains-plugin
git commit -m "feat: scaffold JetBrains evidence bridge plugin"
```

---

## Task 8: JetBrains Tool Window And Submission Collector

**Files:**

- Create: `apps/jetbrains-plugin/src/main/kotlin/ru/proofforge/bridge/SubmissionCollector.kt`
- Create: `apps/jetbrains-plugin/src/main/kotlin/ru/proofforge/bridge/ProofForgeToolWindowFactory.kt`

- [ ] **Step 1: Add submission collector**

Create `apps/jetbrains-plugin/src/main/kotlin/ru/proofforge/bridge/SubmissionCollector.kt`:

```kotlin
package ru.proofforge.bridge

import com.intellij.openapi.project.Project
import com.intellij.openapi.vfs.VfsUtilCore
import com.intellij.openapi.vfs.VirtualFile

class SubmissionCollector(private val project: Project) {
    fun collectProjectFiles(limit: Int = 20): List<Pair<String, String>> {
        val baseDir = project.baseDir ?: return emptyList()
        val result = mutableListOf<Pair<String, String>>()
        collect(baseDir, baseDir, result, limit)
        return result
    }

    private fun collect(root: VirtualFile, current: VirtualFile, result: MutableList<Pair<String, String>>, limit: Int) {
        if (result.size >= limit) return
        if (current.isDirectory) {
            if (current.name in setOf(".git", ".gradle", "build", "node_modules", ".idea")) return
            current.children.forEach { collect(root, it, result, limit) }
            return
        }
        if (current.length > 64_000) return
        val path = VfsUtilCore.getRelativePath(current, root, '/') ?: current.name
        val text = String(current.contentsToByteArray(), Charsets.UTF_8)
        result.add(path to text)
    }
}
```

- [ ] **Step 2: Add tool window UI**

Create `apps/jetbrains-plugin/src/main/kotlin/ru/proofforge/bridge/ProofForgeToolWindowFactory.kt`:

```kotlin
package ru.proofforge.bridge

import com.intellij.openapi.project.Project
import com.intellij.openapi.wm.ToolWindow
import com.intellij.openapi.wm.ToolWindowFactory
import com.intellij.ui.components.JBPanel
import com.intellij.ui.content.ContentFactory
import java.awt.BorderLayout
import javax.swing.JButton
import javax.swing.JLabel
import javax.swing.JScrollPane
import javax.swing.JTextArea
import javax.swing.JTextField

class ProofForgeToolWindowFactory : ToolWindowFactory {
    override fun createToolWindowContent(project: Project, toolWindow: ToolWindow) {
        val panel = ProofForgePanel(project)
        val content = ContentFactory.getInstance().createContent(panel.component(), null, false)
        toolWindow.contentManager.addContent(content)
    }
}

class ProofForgePanel(private val project: Project) {
    private val output = JTextArea().apply {
        isEditable = false
        lineWrap = true
        text = "Enter user id, load tasks, then submit evidence from the current project."
    }
    private val apiBase = JTextField("http://localhost:8000")
    private val userId = JTextField("")
    private val taskId = JTextField("")
    private val reflection = JTextArea("I solved the task and ran local checks.").apply { lineWrap = true }

    fun component(): JBPanel<JBPanel<*>> {
        val panel = JBPanel<JBPanel<*>>(BorderLayout())
        val form = JBPanel<JBPanel<*>>().apply {
            layout = java.awt.GridLayout(0, 1, 4, 4)
            add(JLabel("API base URL"))
            add(apiBase)
            add(JLabel("Proof Forge user id"))
            add(userId)
            add(JButton("List active tasks").apply {
                addActionListener { listTasks() }
            })
            add(JLabel("Practice task id"))
            add(taskId)
            add(JLabel("Reflection"))
            add(JScrollPane(reflection))
            add(JButton("Submit current project").apply {
                addActionListener { submit() }
            })
        }
        panel.add(form, BorderLayout.NORTH)
        panel.add(JScrollPane(output), BorderLayout.CENTER)
        return panel
    }

    private fun settings() = ProofForgeSettings(apiBaseUrl = apiBase.text.trim(), userId = userId.text.trim())

    private fun listTasks() {
        runCatching {
            ProofForgeApiClient(settings()).listActiveTasks()
        }.onSuccess {
            output.text = it
        }.onFailure {
            output.text = it.message ?: "Failed to load tasks"
        }
    }

    private fun submit() {
        val files = SubmissionCollector(project).collectProjectFiles()
        val filesJson = files.joinToString(",") { (path, content) ->
            """{"path":${json(path)},"content":${json(content)}}"""
        }
        val payload = """
            {
              "practice_task_id": ${json(taskId.text.trim())},
              "user_id": ${json(userId.text.trim())},
              "files": [$filesJson],
              "diff": "",
              "test_output": "",
              "check_command": "",
              "exit_code": null,
              "reflection": ${json(reflection.text)},
              "language": "unknown"
            }
        """.trimIndent()
        runCatching {
            ProofForgeApiClient(settings()).submit(taskId.text.trim(), payload)
        }.onSuccess {
            output.text = it
        }.onFailure {
            output.text = it.message ?: "Failed to submit"
        }
    }

    private fun json(value: String): String {
        return "\"" + value
            .replace("\\", "\\\\")
            .replace("\"", "\\\"")
            .replace("\n", "\\n") + "\""
    }
}
```

- [ ] **Step 3: Run plugin build**

Run:

```bash
./gradlew buildPlugin
```

Working directory: `apps/jetbrains-plugin`

Expected: plugin builds.

- [ ] **Step 4: Commit**

```bash
git add apps/jetbrains-plugin/src/main/kotlin/ru/proofforge/bridge
git commit -m "feat: add JetBrains task submission UI"
```

---

## Task 9: Complete Study Session Into Capsule

**Files:**

- Create: `apps/backend/app/services/study_completion.py`
- Modify: `apps/backend/app/repositories/practice_repo.py`
- Modify: `apps/backend/app/routers/practice.py`
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/app/(app)/study/[id]/page.tsx`
- Test: `tests/backend/integration/test_practice_api.py`

- [ ] **Step 1: Add failing test for session completion**

Append to `tests/backend/integration/test_practice_api.py`:

```python
@pytest.mark.asyncio
async def test_complete_study_session_forges_capsule(client, db):
    user = await user_repo.create_user(db, UserCreate(email="complete-session@example.com", display_name="Complete"))
    topic = await topic_repo.start_topic(db, TopicStart(user_id=user.id, name="Java streams"))

    created = await client.post("/api/study-sessions", json={"user_id": user.id, "topic_id": topic.id})
    session_id = created.json()["session"]["id"]

    completed = await client.post(f"/api/study-sessions/{session_id}/complete", json={"user_id": user.id})

    assert completed.status_code == 201
    body = completed.json()
    assert body["session"]["status"] == "completed"
    assert body["capsule"]["topic_id"] == topic.id
    assert "Java streams" in body["capsule"]["content_md"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/backend/integration/test_practice_api.py::test_complete_study_session_forges_capsule -q
```

Expected: FAIL with `404 Not Found` for `/api/study-sessions/{id}/complete`.

- [ ] **Step 3: Add repository complete helper**

Add to `apps/backend/app/repositories/practice_repo.py`:

```python
async def complete_study_session(db: AsyncSession, session_id: str) -> StudySession | None:
    session = await get_study_session(db, session_id)
    if not session:
        return None
    session.status = "completed"
    session.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(session)
    return session


async def list_session_tasks(db: AsyncSession, session_id: str) -> list[PracticeTask]:
    result = await db.execute(
        select(PracticeTask)
        .where(PracticeTask.study_session_id == session_id)
        .order_by(PracticeTask.created_at.asc())
    )
    return list(result.scalars().all())
```

- [ ] **Step 4: Add completion service**

Create `apps/backend/app/services/study_completion.py`:

```python
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import capsule_repo, practice_repo
from app.schemas.capsule import CapsuleCreate, ReviewQuestionIn


async def forge_capsule_from_session(db: AsyncSession, session_id: str):
    session = await practice_repo.get_study_session(db, session_id)
    if not session:
        return None

    tasks = await practice_repo.list_session_tasks(db, session_id)
    task_lines = "\n".join(f"- {task.title}: {task.status}" for task in tasks) or "- No tasks completed yet"
    content_md = (
        f"# Study Capsule\n\n"
        f"## Topic\n\n{session.topic_id}\n\n"
        f"## Conspect\n\n{session.conspect_md}\n\n"
        f"## Practice Evidence\n\n{task_lines}\n\n"
        f"## Next Steps\n\n"
        f"Review weak spots from IDE submissions and continue with one harder task."
    )
    capsule = await capsule_repo.store_capsule(
        db,
        CapsuleCreate(
            user_id=session.user_id,
            topic_id=session.topic_id,
            content_md=content_md,
            summary="Capsule forged from active study session and practice evidence.",
            review_questions=[
                ReviewQuestionIn(
                    question="What did you practice in this study session?",
                    correct_answer="Summarize the key task, evidence, and concept learned.",
                    difficulty=1,
                )
            ],
        ),
    )
    completed = await practice_repo.complete_study_session(db, session_id)
    return completed, capsule
```

- [ ] **Step 5: Add router endpoint**

Add to `apps/backend/app/routers/practice.py`:

```python
from app.schemas.capsule import CapsuleOut
from app.services.study_completion import forge_capsule_from_session
```

Then add endpoint:

```python
@router.post("/study-sessions/{session_id}/complete", status_code=201)
async def complete_study_session(session_id: str, data: dict, db: AsyncSession = Depends(get_db)):
    session = await practice_repo.get_study_session(db, session_id)
    if not session or session.user_id != data["user_id"]:
        raise HTTPException(status_code=404, detail="Study session not found")
    result = await forge_capsule_from_session(db, session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Study session not found")
    completed, capsule = result
    return {
        "session": StudySessionOut.model_validate(completed),
        "capsule": CapsuleOut.model_validate(capsule),
    }
```

- [ ] **Step 6: Add web API method**

Add to `practice` in `apps/web/lib/api.ts`:

```ts
completeSession: (sessionId: string, userId: string) =>
  req<{ session: StudySession; capsule: Capsule }>(`/api/study-sessions/${sessionId}/complete`, {
    method: 'POST',
    body: JSON.stringify({ user_id: userId }),
  }),
```

- [ ] **Step 7: Add complete button to study page**

In `apps/web/app/(app)/study/[id]/page.tsx`, add state:

```tsx
const [completing, setCompleting] = useState(false)
```

Add handler:

```tsx
const handleComplete = async () => {
  if (!user || !session) return
  setCompleting(true)
  try {
    const result = await practice.completeSession(session.id, user.user_id)
    window.location.href = `/capsule/${result.capsule.id}`
  } finally {
    setCompleting(false)
  }
}
```

Add button after the tasks list:

```tsx
<button
  onClick={handleComplete}
  disabled={completing}
  className="mt-8 w-full py-3 rounded-xl bg-accent text-[#06140d] font-semibold text-sm hover:bg-accentdk transition-colors disabled:opacity-50"
>
  {completing ? 'Форжим капсулу...' : 'Завершить сегмент и создать капсулу →'}
</button>
```

- [ ] **Step 8: Run tests and build**

Run:

```bash
pytest tests/backend/integration/test_practice_api.py -q
```

Expected: PASS.

Run:

```bash
npm run build
```

Working directory: `apps/web`

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add apps/backend/app/services/study_completion.py apps/backend/app/repositories/practice_repo.py apps/backend/app/routers/practice.py apps/web/lib/api.ts apps/web/app/'(app)'/study/'[id]'/page.tsx tests/backend/integration/test_practice_api.py
git commit -m "feat: forge capsule from study session"
```

---

## Task 10: End-To-End Verification

**Files:**

- Modify: `README.md`
- Test: backend and web verification commands

- [ ] **Step 1: Add README section**

Append to `README.md`:

```markdown
## IDE Evidence Bridge

The first IDE bridge target is JetBrains.

Flow:

1. Start a topic in the web app.
2. Click "Начать обучение" to create a study session and mini-project task.
3. Open the Proof Forge tool window in JetBrains.
4. Enter API URL and Proof Forge user id.
5. List active tasks and copy the task id.
6. Submit current project evidence.
7. Open Proof Forge web to review evaluation and progress.

The plugin is an evidence bridge. It does not manage dependencies, create full local projects, or modify user code.
```

- [ ] **Step 2: Run backend tests**

Run:

```bash
pytest tests/backend/unit/test_practice_repo.py tests/backend/integration/test_practice_api.py -q
```

Expected: PASS.

- [ ] **Step 3: Run web build**

Run:

```bash
npm run build
```

Working directory: `apps/web`

Expected: PASS.

- [ ] **Step 4: Run plugin build**

Run:

```bash
./gradlew buildPlugin
```

Working directory: `apps/jetbrains-plugin`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: document IDE evidence bridge"
```

---

## Self-Review

Spec coverage:

- Study sessions: Task 1, Task 2, Task 3, Task 5, Task 6.
- Practice tasks and mini-project tasks: Task 1, Task 2, Task 3, Task 5, Task 6.
- IDE sessions and JetBrains-first pairing: Task 1, Task 2, Task 3, Task 7, Task 8.
- IDE submission without archive upload: Task 1, Task 2, Task 3, Task 8.
- Evaluation using evidence and reflection: Task 3, Task 4.
- Mastery updates: Task 4.
- Web visibility: Task 5, Task 6.
- JetBrains thin bridge boundary: Task 7, Task 8, Task 9.
- Capsule after learning segment: Task 9.

Placeholder scan:

- No placeholder markers and no vague "add tests" steps.
- Each code-changing task includes concrete files, snippets, and commands.

Type consistency:

- `StudySessionCreate`, `PracticeTaskCreate`, `IdeSubmissionCreate`, and `EvaluationCreate` are defined before repository/router usage.
- API route paths match web and plugin clients.
- Status names match the spec and frontend union types.
