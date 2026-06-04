from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Evaluation, FollowUp, IdeSession, IdeSubmission, PracticeTask, StudySession, Topic
from app.schemas.practice import (
    EvaluationCreate,
    FollowUpCreate,
    FollowUpAnswer,
    IdeSessionCreate,
    IdeSubmissionCreate,
    PracticeTaskCreate,
    StudySessionCreate,
)


async def create_study_session(db: AsyncSession, data: StudySessionCreate) -> StudySession:
    result = await db.execute(
        select(Topic).where(
            Topic.id == data.topic_id,
            Topic.user_id == data.user_id,
        )
    )
    topic = result.scalar_one_or_none()
    if topic is None:
        raise ValueError("Topic not found for user")

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
    session = await get_study_session(db, data.study_session_id)
    if (
        session is None
        or session.user_id != data.user_id
        or session.topic_id != data.topic_id
    ):
        raise ValueError("Study session not found for user/topic")

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


async def get_practice_task_for_user(
    db: AsyncSession, task_id: str, user_id: str
) -> PracticeTask | None:
    result = await db.execute(
        select(PracticeTask).where(
            PracticeTask.id == task_id,
            PracticeTask.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def list_active_tasks(db: AsyncSession, user_id: str) -> list[PracticeTask]:
    result = await db.execute(
        select(PracticeTask)
        .where(PracticeTask.user_id == user_id)
        .where(
            PracticeTask.status.in_(
                ["assigned", "opened_in_ide", "submitted", "needs_revision"]
            )
        )
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


async def get_ide_session_for_user(
    db: AsyncSession, ide_session_id: str, user_id: str
) -> IdeSession | None:
    result = await db.execute(
        select(IdeSession).where(
            IdeSession.id == ide_session_id,
            IdeSession.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def create_submission(db: AsyncSession, data: IdeSubmissionCreate) -> IdeSubmission:
    task = await get_practice_task_for_user(db, data.practice_task_id, data.user_id)
    if task is None:
        raise ValueError("Practice task not found for user")

    if data.ide_session_id is not None:
        ide_session = await get_ide_session_for_user(
            db, data.ide_session_id, data.user_id
        )
        if ide_session is None:
            raise ValueError("IDE session not found for user")

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
    task.status = "submitted"

    await db.commit()
    await db.refresh(submission)
    return submission


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


async def get_submission(db: AsyncSession, submission_id: str) -> IdeSubmission | None:
    result = await db.execute(select(IdeSubmission).where(IdeSubmission.id == submission_id))
    return result.scalar_one_or_none()


async def get_evaluation(db: AsyncSession, evaluation_id: str) -> Evaluation | None:
    result = await db.execute(select(Evaluation).where(Evaluation.id == evaluation_id))
    return result.scalar_one_or_none()


async def get_evaluation_by_submission(
    db: AsyncSession, submission_id: str
) -> Evaluation | None:
    result = await db.execute(
        select(Evaluation).where(Evaluation.submission_id == submission_id)
    )
    return result.scalar_one_or_none()


def apply_evaluation_data(evaluation: Evaluation, data: EvaluationCreate) -> None:
    evaluation.score = data.score
    evaluation.status = data.status
    evaluation.feedback_md = data.feedback_md
    evaluation.concept_scores = data.concept_scores
    evaluation.weak_spots = data.weak_spots
    evaluation.next_action = data.next_action


async def create_evaluation(db: AsyncSession, data: EvaluationCreate) -> Evaluation:
    submission = await get_submission(db, data.submission_id)
    if submission is None:
        raise ValueError("Submission not found")
    if submission.user_id != data.user_id:
        raise ValueError("Submission not found for user")
    practice_task_id = submission.practice_task_id

    task = await get_practice_task(db, practice_task_id)
    if task is None:
        raise ValueError("Practice task not found")

    evaluation = await get_evaluation_by_submission(db, data.submission_id)
    if evaluation is None:
        evaluation = Evaluation(submission_id=data.submission_id)
        db.add(evaluation)

    apply_evaluation_data(evaluation, data)
    task.status = "completed" if data.status == "passed" else "needs_revision"

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()

        evaluation = await get_evaluation_by_submission(db, data.submission_id)
        if evaluation is None:
            raise

        task = await get_practice_task(db, practice_task_id)
        if task is None:
            raise ValueError("Practice task not found")

        apply_evaluation_data(evaluation, data)
        task.status = "completed" if data.status == "passed" else "needs_revision"
        await db.commit()

    await db.refresh(evaluation)
    return evaluation


async def create_follow_up(db: AsyncSession, data: FollowUpCreate) -> FollowUp:
    follow_up = FollowUp(
        evaluation_id=data.evaluation_id,
        question=data.question,
        expected_answer=data.expected_answer,
    )
    db.add(follow_up)
    await db.commit()
    await db.refresh(follow_up)
    return follow_up


async def get_follow_up(db: AsyncSession, follow_up_id: str) -> FollowUp | None:
    result = await db.execute(select(FollowUp).where(FollowUp.id == follow_up_id))
    return result.scalar_one_or_none()


async def list_follow_ups_by_evaluation(db: AsyncSession, evaluation_id: str) -> list[FollowUp]:
    result = await db.execute(
        select(FollowUp).where(FollowUp.evaluation_id == evaluation_id).order_by(FollowUp.id)
    )
    return list(result.scalars().all())


async def answer_follow_up(db: AsyncSession, follow_up_id: str, data: FollowUpAnswer) -> FollowUp:
    follow_up = await get_follow_up(db, follow_up_id)
    if follow_up is None:
        raise ValueError("Follow-up not found")
    follow_up.user_answer = data.user_answer
    follow_up.score = data.score
    follow_up.feedback_md = data.feedback_md
    await db.commit()
    await db.refresh(follow_up)
    return follow_up
