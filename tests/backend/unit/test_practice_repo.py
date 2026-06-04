import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.models import Evaluation
from app.repositories import practice_repo, topic_repo, user_repo
from app.schemas.practice import (
    EvaluationCreate,
    IdeSubmissionCreate,
    IdeSessionCreate,
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


@pytest.mark.asyncio
async def test_cross_user_topic_session_creation_raises_value_error(db):
    owner = await user_repo.create_user(
        db, UserCreate(email="topic-owner@example.com", display_name="Topic Owner")
    )
    other_user = await user_repo.create_user(
        db, UserCreate(email="topic-other@example.com", display_name="Topic Other")
    )
    topic = await topic_repo.start_topic(
        db, TopicStart(user_id=owner.id, name="Owned Topic")
    )

    with pytest.raises(ValueError, match="Topic not found for user"):
        await practice_repo.create_study_session(
            db,
            StudySessionCreate(user_id=other_user.id, topic_id=topic.id),
        )


@pytest.mark.asyncio
async def test_mismatched_study_session_user_or_topic_raises_value_error(db):
    owner = await user_repo.create_user(
        db, UserCreate(email="session-owner@example.com", display_name="Session Owner")
    )
    other_user = await user_repo.create_user(
        db, UserCreate(email="session-other@example.com", display_name="Session Other")
    )
    topic = await topic_repo.start_topic(db, TopicStart(user_id=owner.id, name="Owned Topic"))
    other_topic = await topic_repo.start_topic(
        db, TopicStart(user_id=owner.id, name="Other Topic")
    )
    session = await practice_repo.create_study_session(
        db,
        StudySessionCreate(user_id=owner.id, topic_id=topic.id),
    )

    with pytest.raises(ValueError, match="Study session not found for user/topic"):
        await practice_repo.create_practice_task(
            db,
            PracticeTaskCreate(
                user_id=other_user.id,
                topic_id=topic.id,
                study_session_id=session.id,
                type="exercise",
                title="Wrong user",
                instructions_md="This user does not own the session.",
            ),
        )

    with pytest.raises(ValueError, match="Study session not found for user/topic"):
        await practice_repo.create_practice_task(
            db,
            PracticeTaskCreate(
                user_id=owner.id,
                topic_id=other_topic.id,
                study_session_id=session.id,
                type="exercise",
                title="Wrong topic",
                instructions_md="This topic does not match the session.",
            ),
        )


@pytest.mark.asyncio
async def test_foreign_or_missing_ide_session_raises_value_error(db):
    owner = await user_repo.create_user(
        db, UserCreate(email="ide-owner@example.com", display_name="IDE Owner")
    )
    other_user = await user_repo.create_user(
        db, UserCreate(email="ide-other@example.com", display_name="IDE Other")
    )
    topic = await topic_repo.start_topic(db, TopicStart(user_id=owner.id, name="IDE Topic"))
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
            title="Submit from IDE",
            instructions_md="Submit with a paired IDE session.",
        ),
    )
    foreign_ide_session = await practice_repo.pair_ide_session(
        db, IdeSessionCreate(user_id=other_user.id)
    )

    with pytest.raises(ValueError, match="IDE session not found for user"):
        await practice_repo.create_submission(
            db,
            IdeSubmissionCreate(
                practice_task_id=task.id,
                user_id=owner.id,
                ide_session_id=foreign_ide_session.id,
            ),
        )

    with pytest.raises(ValueError, match="IDE session not found for user"):
        await practice_repo.create_submission(
            db,
            IdeSubmissionCreate(
                practice_task_id=task.id,
                user_id=owner.id,
                ide_session_id="missing-ide-session",
            ),
        )


@pytest.mark.asyncio
async def test_create_evaluation_for_missing_submission_raises_value_error(db):
    with pytest.raises(ValueError, match="Submission not found"):
        await practice_repo.create_evaluation(
            db,
            EvaluationCreate(
                submission_id="missing-submission",
                score=0.5,
                status="needs_revision",
                feedback_md="No submission exists.",
                next_action="revise",
            ),
        )


@pytest.mark.asyncio
async def test_create_evaluation_for_missing_practice_task_raises_value_error(db):
    user = await user_repo.create_user(
        db, UserCreate(email="missing-task@example.com", display_name="Missing Task")
    )
    topic = await topic_repo.start_topic(
        db, TopicStart(user_id=user.id, name="Missing Task Topic")
    )
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
            title="Deleted task",
            instructions_md="The task row is deleted before evaluation.",
        ),
    )
    submission = await practice_repo.create_submission(
        db,
        IdeSubmissionCreate(practice_task_id=task.id, user_id=user.id),
    )

    await db.delete(task)
    await db.commit()

    with pytest.raises(ValueError, match="Practice task not found"):
        await practice_repo.create_evaluation(
            db,
            EvaluationCreate(
                submission_id=submission.id,
                score=0.5,
                status="needs_revision",
                feedback_md="Task row is missing.",
                next_action="revise",
            ),
        )


@pytest.mark.asyncio
async def test_duplicate_evaluation_reuses_id_and_updates_fields(db):
    user = await user_repo.create_user(
        db, UserCreate(email="idempotent@example.com", display_name="Idempotent")
    )
    topic = await topic_repo.start_topic(
        db, TopicStart(user_id=user.id, name="Idempotent Topic")
    )
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
            title="Retry evaluation",
            instructions_md="Submit once, evaluate twice.",
        ),
    )
    submission = await practice_repo.create_submission(
        db,
        IdeSubmissionCreate(practice_task_id=task.id, user_id=user.id),
    )

    first_evaluation = await practice_repo.create_evaluation(
        db,
        EvaluationCreate(
            submission_id=submission.id,
            score=0.35,
            status="failed",
            feedback_md="Initial failure.",
            concept_scores={"ownership": 0.2},
            weak_spots=[{"concept": "ownership"}],
            next_action="revise",
        ),
    )
    second_evaluation = await practice_repo.create_evaluation(
        db,
        EvaluationCreate(
            submission_id=submission.id,
            score=0.9,
            status="passed",
            feedback_md="Passed after revision.",
            concept_scores={"ownership": 0.9},
            weak_spots=[],
            next_action="continue_lesson",
        ),
    )
    completed_task = await practice_repo.get_practice_task(db, task.id)
    result = await db.execute(
        select(Evaluation).where(Evaluation.submission_id == submission.id)
    )
    evaluations = list(result.scalars().all())

    assert second_evaluation.id == first_evaluation.id
    assert len(evaluations) == 1
    assert second_evaluation.score == 0.9
    assert second_evaluation.status == "passed"
    assert second_evaluation.feedback_md == "Passed after revision."
    assert second_evaluation.concept_scores == {"ownership": 0.9}
    assert second_evaluation.weak_spots == []
    assert second_evaluation.next_action == "continue_lesson"
    assert completed_task is not None
    assert completed_task.status == "completed"


def test_invalid_evaluation_score_is_rejected_by_pydantic():
    with pytest.raises(ValidationError):
        EvaluationCreate(
            submission_id="submission-id",
            score=1.1,
            status="passed",
            feedback_md="Score is too high.",
            next_action="continue_lesson",
        )


def test_invalid_practice_task_difficulty_is_rejected_by_pydantic():
    with pytest.raises(ValidationError):
        PracticeTaskCreate(
            user_id="user-id",
            topic_id="topic-id",
            study_session_id="session-id",
            type="exercise",
            title="Invalid difficulty",
            instructions_md="Difficulty must be between 1 and 3.",
            difficulty=4,
        )
