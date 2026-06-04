import pytest
from pydantic import ValidationError

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

    active_tasks = await practice_repo.list_active_tasks(db, user.id)

    assert task.status == "submitted"
    assert active_tasks[0].id == task.id

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

    completed_task = await practice_repo.get_practice_task(db, task.id)

    assert session.status == "active"
    assert submission.exit_code == 0
    assert evaluation.status == "passed"
    assert completed_task is not None
    assert completed_task.status == "completed"


@pytest.mark.asyncio
async def test_needs_revision_evaluation_marks_task_needs_revision(db):
    user = await user_repo.create_user(
        db, UserCreate(email="revision@example.com", display_name="Revision")
    )
    topic = await topic_repo.start_topic(db, TopicStart(user_id=user.id, name="Async Java"))
    session = await practice_repo.create_study_session(
        db,
        StudySessionCreate(user_id=user.id, topic_id=topic.id),
    )
    task = await practice_repo.create_practice_task(
        db,
        PracticeTaskCreate(
            user_id=user.id,
            topic_id=topic.id,
            study_session_id=session.id,
            type="exercise",
            title="Fix the async flow",
            instructions_md="Submit a revised async implementation.",
        ),
    )
    submission = await practice_repo.create_submission(
        db,
        IdeSubmissionCreate(
            practice_task_id=task.id,
            user_id=user.id,
            reflection="I need to improve error handling.",
        ),
    )

    evaluation = await practice_repo.create_evaluation(
        db,
        EvaluationCreate(
            submission_id=submission.id,
            score=0.45,
            status="needs_revision",
            feedback_md="Revise cancellation handling.",
            next_action="revise",
        ),
    )
    revised_task = await practice_repo.get_practice_task(db, task.id)

    assert evaluation.status == "needs_revision"
    assert revised_task is not None
    assert revised_task.status == "needs_revision"


@pytest.mark.asyncio
async def test_cross_user_submission_raises_value_error(db):
    owner = await user_repo.create_user(
        db, UserCreate(email="owner@example.com", display_name="Owner")
    )
    intruder = await user_repo.create_user(
        db, UserCreate(email="intruder@example.com", display_name="Intruder")
    )
    topic = await topic_repo.start_topic(db, TopicStart(user_id=owner.id, name="Ownership"))
    session = await practice_repo.create_study_session(
        db,
        StudySessionCreate(user_id=owner.id, topic_id=topic.id),
    )
    task = await practice_repo.create_practice_task(
        db,
        PracticeTaskCreate(
            user_id=owner.id,
            topic_id=topic.id,
            study_session_id=session.id,
            type="exercise",
            title="Owned task",
            instructions_md="Only the owner can submit.",
        ),
    )

    with pytest.raises(ValueError, match="Practice task not found for user"):
        await practice_repo.create_submission(
            db,
            IdeSubmissionCreate(
                practice_task_id=task.id,
                user_id=intruder.id,
                reflection="Attempted cross-user submission.",
            ),
        )

    unchanged_task = await practice_repo.get_practice_task(db, task.id)

    assert unchanged_task is not None
    assert unchanged_task.status == "assigned"


def test_invalid_evaluation_status_is_rejected_by_pydantic():
    with pytest.raises(ValidationError):
        EvaluationCreate(
            submission_id="submission-id",
            score=0.5,
            status="complete",
            feedback_md="Invalid status.",
            next_action="revise",
        )
