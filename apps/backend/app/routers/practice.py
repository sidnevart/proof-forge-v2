import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, async_session_factory
from app.config import settings as app_settings
from app.models.topic_material import TopicMaterial
from app.models import PracticeTask, StudySession as StudySessionModel
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
from app.services.practice_generation import (
    TopicInfo,
    generate_tasks_from_conspect,
    stream_conspect_to_queue,
    stream_study_content_to_queue,
)
from app.services.sse_bridge import create_stream, get_stream, remove_stream, stream_from_queue
from app.services.study_completion import forge_capsule_from_session

router = APIRouter(tags=["practice"])


# ── Background generation task ─────────────────────────────────────────────────

async def _run_session_generation(
    session_id: str,
    topic: TopicInfo,
    materials_list: list[dict],
) -> None:
    """Generate study content in background, streaming events via SSE bridge.

    Conspect is streamed and saved immediately. Tasks are generated separately;
    if they fail the session still gets the conspect but no tasks.
    No template fallback content is ever written.
    """
    q = get_stream(session_id)
    if q is None:
        return

    try:
        conspect_md = await stream_conspect_to_queue(
            app_settings, topic, materials_list, q
        )
    except Exception as exc:
        await q.put(("error", {"message": str(exc), "fallback": False}))
        await q.put(("complete", {"session_id": session_id}))
        remove_stream(session_id)
        return

    # Save conspect immediately so the session is usable even if tasks fail
    try:
        async with async_session_factory() as db:
            result = await db.execute(
                select(StudySessionModel).where(StudySessionModel.id == session_id)
            )
            session_obj = result.scalar_one_or_none()
            if session_obj:
                session_obj.conspect_md = conspect_md
                session_obj.status = "active"
                await db.commit()
    except Exception:
        pass

    # Generate tasks
    try:
        learning_goals, task_creates = await generate_tasks_from_conspect(
            app_settings, topic, conspect_md, q
        )

        async with async_session_factory() as db:
            result = await db.execute(
                select(StudySessionModel).where(StudySessionModel.id == session_id)
            )
            session_obj = result.scalar_one_or_none()
            if session_obj:
                session_obj.learning_goals = learning_goals
                await db.commit()

                for t in task_creates:
                    t.study_session_id = session_id
                    task_obj = PracticeTask(
                        user_id=topic.user_id,
                        topic_id=topic.id,
                        study_session_id=session_id,
                        type=t.type,
                        title=t.title,
                        instructions_md=t.instructions_md,
                        target_concepts=t.target_concepts,
                        difficulty=t.difficulty,
                        expected_evidence=t.expected_evidence,
                        check_commands=t.check_commands,
                        status="assigned",
                    )
                    db.add(task_obj)
                    await db.flush()
                    await db.refresh(task_obj)
                    task_out = PracticeTaskOut.model_validate(task_obj)
                    await q.put(("task_ready", task_out.model_dump(mode="json")))

                await db.commit()

        await q.put(("complete", {"session_id": session_id}))

    except Exception as exc:
        await q.put(("error", {"message": str(exc), "fallback": False}))
        await q.put(("complete", {"session_id": session_id}))

    finally:
        remove_stream(session_id)


# ── Study session endpoints ────────────────────────────────────────────────────

@router.post("/study-sessions", status_code=201)
async def create_study_session(data: dict, db: AsyncSession = Depends(get_db)):
    topic = await topic_repo.get_topic(db, data["topic_id"])
    if not topic or topic.user_id != data["user_id"]:
        raise HTTPException(status_code=404, detail="Topic not found")

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

    # Create skeleton session immediately
    session_obj = StudySessionModel(
        user_id=data["user_id"],
        topic_id=data["topic_id"],
        conspect_md="",
        learning_goals=[],
        status="generating",
    )
    db.add(session_obj)
    await db.commit()
    await db.refresh(session_obj)

    topic_info = TopicInfo(id=topic.id, name=topic.name, user_id=topic.user_id)
    create_stream(session_obj.id)
    asyncio.create_task(_run_session_generation(session_obj.id, topic_info, materials_list))

    return {
        "session": StudySessionOut.model_validate(session_obj),
        "tasks": [],
        "generation_status": "generating",
        "generation_error": None,
    }


@router.get("/study-sessions/{session_id}/events")
async def study_session_events(session_id: str, db: AsyncSession = Depends(get_db)):
    q = get_stream(session_id)

    if q is None:
        # Background task already finished — send immediate complete
        session_obj = await practice_repo.get_study_session(db, session_id)
        if not session_obj:
            raise HTTPException(status_code=404, detail="Study session not found")

        async def _immediate():
            yield f"event: complete\ndata: {json.dumps({'session_id': session_id})}\n\n"

        return StreamingResponse(
            _immediate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return StreamingResponse(
        stream_from_queue(q),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
