from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import settings as app_settings
from app.models.topic_material import TopicMaterial
from app.repositories import practice_repo, topic_repo
from app.schemas.practice import (
    EvaluationCreate,
    EvaluationOut,
    FollowUpAnswer,
    FollowUpCreate,
    FollowUpOut,
    IdeSessionCreate,
    IdeSessionOut,
    IdeSubmissionCreate,
    IdeSubmissionOut,
    PracticeTaskOut,
    StudySessionOut,
)
from app.schemas.capsule import CapsuleOut
from app.services.practice_evaluation import evaluate_submission, finalize_evaluation_mastery
from app.services.practice_generation import build_study_session, build_study_tasks, generate_study_content
from app.services.study_completion import forge_capsule_from_session

router = APIRouter(tags=["practice"])


@router.post("/study-sessions", status_code=201)
async def create_study_session(data: dict, db: AsyncSession = Depends(get_db)):
    topic = await topic_repo.get_topic(db, data["topic_id"])
    if not topic or topic.user_id != data["user_id"]:
        raise HTTPException(status_code=404, detail="Topic not found")

    # Load materials for AI generation
    result = await db.execute(
        select(TopicMaterial)
        .where(TopicMaterial.topic_id == topic.id)
        .order_by(TopicMaterial.created_at.asc())
    )
    materials = result.scalars().all()
    materials_list = [
        {"name": m.name, "type": m.type, "content_text": m.content_text}
        for m in materials
    ]

    # Try AI generation; fallback to templates
    generated = await generate_study_content(app_settings, topic, materials_list)
    if generated:
        session_data, task_list = generated
        session = await practice_repo.create_study_session(db, session_data)
        tasks = []
        for t in task_list:
            t.study_session_id = session.id
            task = await practice_repo.create_practice_task(db, t)
            tasks.append(PracticeTaskOut.model_validate(task))
    else:
        session = await practice_repo.create_study_session(db, build_study_session(topic))
        tasks = []
        for task_data in build_study_tasks(session.id, topic):
            task = await practice_repo.create_practice_task(db, task_data)
            tasks.append(PracticeTaskOut.model_validate(task))

    return {
        "session": StudySessionOut.model_validate(session),
        "tasks": tasks,
    }


@router.get("/study-sessions", response_model=list[StudySessionOut])
async def list_study_sessions(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(practice_repo.StudySession)
        .where(practice_repo.StudySession.user_id == user_id)
        .order_by(practice_repo.StudySession.created_at.desc())
    )
    return result.scalars().all()


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


@router.post("/evaluations/{evaluation_id}/follow-ups", response_model=FollowUpOut, status_code=201)
async def create_follow_up(
    evaluation_id: str,
    data: FollowUpCreate,
    db: AsyncSession = Depends(get_db),
):
    evaluation = await practice_repo.get_evaluation_by_submission(db, evaluation_id)
    if evaluation is None:
        # fallback: try by evaluation id directly
        from sqlalchemy import select
        from app.models import Evaluation as EvalModel
        result = await db.execute(select(EvalModel).where(EvalModel.id == evaluation_id))
        evaluation = result.scalar_one_or_none()
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    follow_up = await practice_repo.create_follow_up(
        db, FollowUpCreate(evaluation_id=evaluation_id, question=data.question, expected_answer=data.expected_answer)
    )
    return follow_up


@router.get("/evaluations/{evaluation_id}/follow-ups", response_model=list[FollowUpOut])
async def list_follow_ups(evaluation_id: str, db: AsyncSession = Depends(get_db)):
    return await practice_repo.list_follow_ups_by_evaluation(db, evaluation_id)


@router.post("/follow-ups/{follow_up_id}/answer", response_model=FollowUpOut)
async def answer_follow_up(
    follow_up_id: str,
    data: FollowUpAnswer,
    db: AsyncSession = Depends(get_db),
):
    follow_up = await practice_repo.answer_follow_up(db, follow_up_id, data)
    # Attempt to finalize mastery if all follow-ups for this evaluation are now answered
    await finalize_evaluation_mastery(db, follow_up.evaluation_id)
    return follow_up


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
