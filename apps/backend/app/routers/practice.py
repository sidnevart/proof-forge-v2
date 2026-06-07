import asyncio
import base64
import json
import logging

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

logger = logging.getLogger(__name__)
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, async_session_factory
from app.config import settings as app_settings
from app.models.topic_material import TopicMaterial
from app.models.learning_event import LearningEvent
from app.models.topic import Topic as TopicModel
from app.models import PracticeTask, StudySession as StudySessionModel
from app.repositories import mastery_repo, practice_repo, topic_repo
from app.schemas.practice import (
    AnswerSubmissionOut,
    AttachmentOut,
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
from app.services.ai_evaluation import evaluate_submission_ai
from app.services.file_parser import extract_from_bytes, image_mime, is_image
from app.models.submission_attachment import SubmissionAttachment
from app.services.practice_generation import (
    TopicInfo,
    build_study_session,
    build_study_tasks,
    generate_tasks_from_conspect,
    stream_conspect_to_queue,
    stream_study_content_to_queue,
)
from app.services.card_generation import generate_cards_for_topic_background
from app.services.sse_bridge import create_stream, get_stream, remove_stream, stream_from_queue
from app.services.study_completion import forge_capsule_from_session

router = APIRouter(tags=["practice"])

# Practice answer attachment limits — mirror chat (app/routers/chat.py).
_MAX_ATTACHMENTS = 5
_MAX_ATTACHMENT_BYTES = 8_000_000  # 8 MB per file


def _format_card_context_from_materials(topic_name: str, materials_list: list[dict]) -> str:
    if not materials_list:
        return f"Тема: {topic_name}"
    blocks = []
    for material in materials_list[:6]:
        blocks.append(
            f"### {material['name']} ({material.get('type', 'material')})\n"
            f"{material['content_text'][:3000]}"
        )
    return f"## Тема\n{topic_name}\n\n## Материалы\n\n" + "\n\n---\n\n".join(blocks)


def _format_card_context_from_session(
    topic_name: str,
    conspect_md: str,
    tasks: list,
) -> str:
    """Build card-generation context from the freshly generated conspect and tasks.

    Richer than raw materials: the conspect is the distilled theory and the task
    concepts highlight what's worth memorising.
    """
    parts = [f"## Тема\n{topic_name}"]
    if conspect_md.strip():
        parts.append("## Конспект\n\n" + conspect_md[:6000])
    concepts: list[str] = []
    task_titles: list[str] = []
    for t in tasks:
        title = getattr(t, "title", None)
        if title:
            task_titles.append(str(title))
        for concept in getattr(t, "target_concepts", None) or []:
            if concept and concept not in concepts:
                concepts.append(str(concept))
    if task_titles:
        parts.append("## Задания\n" + "\n".join(f"- {title}" for title in task_titles))
    if concepts:
        parts.append("## Ключевые концепции\n" + ", ".join(concepts))
    return "\n\n".join(parts)


def _spawn_card_generation(topic: TopicInfo, context_md: str) -> None:
    """Fire-and-forget base card generation; never blocks session completion."""
    asyncio.create_task(
        generate_cards_for_topic_background(topic.id, topic.user_id, context_md)
    )


# ── Background generation task ─────────────────────────────────────────────────

async def _run_session_generation(
    session_id: str,
    topic: TopicInfo,
    materials_list: list[dict],
) -> None:
    """Generate study content in background, streaming events via SSE bridge.

    When LLM is not configured (e.g. tests) we fall back to template content so
    the session is still usable.  When LLM is configured we stream the conspect
    and then generate tasks; if task generation fails the conspect is kept but
    no tasks are created.
    """
    q = get_stream(session_id)
    if q is None:
        return

    # Classify the topic's domain (once) before generation so conspect/tasks adapt.
    # Only runs when an LLM is configured; the fallback path below stays "general".
    if app_settings.llm_api_key and topic.domain == "general":
        try:
            from app.services.domain_classifier import classify_domain

            preview = "\n".join(m.get("content_text", "")[:300] for m in materials_list[:3])
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
                detected = await classify_domain(client, app_settings, topic.name, preview)
            topic.domain = detected
            if detected != "general":
                async with async_session_factory() as db:
                    result = await db.execute(
                        select(TopicModel).where(TopicModel.id == topic.id)
                    )
                    topic_obj = result.scalar_one_or_none()
                    if topic_obj:
                        topic_obj.domain = detected
                        await db.commit()
        except Exception as exc:  # noqa: BLE001 — classification must not break generation
            logger.warning("Domain classification skipped for %s: %s", topic.id, exc)

    # ── No LLM configured → immediate fallback (keeps tests happy) ────────────
    if not app_settings.llm_api_key:
        try:
            async with async_session_factory() as db:
                result = await db.execute(
                    select(StudySessionModel).where(StudySessionModel.id == session_id)
                )
                session_obj = result.scalar_one_or_none()
                if session_obj:
                    fallback = build_study_session(topic)
                    session_obj.conspect_md = fallback.conspect_md
                    session_obj.learning_goals = fallback.learning_goals
                    session_obj.status = "active"
                    await db.commit()
                    for ft in build_study_tasks(session_id, topic):
                        db.add(PracticeTask(
                            user_id=topic.user_id,
                            topic_id=topic.id,
                            study_session_id=session_id,
                            type=ft.type,
                            title=ft.title,
                            instructions_md=ft.instructions_md,
                            target_concepts=ft.target_concepts,
                            difficulty=ft.difficulty,
                            expected_evidence=ft.expected_evidence,
                            check_commands=ft.check_commands,
                            status="assigned",
                        ))
                    await db.commit()

                    # Notify clients about the created tasks
                    result = await db.execute(
                        select(PracticeTask)
                        .where(PracticeTask.study_session_id == session_id)
                        .order_by(PracticeTask.created_at.asc())
                    )
                    for task_obj in result.scalars().all():
                        task_out = PracticeTaskOut.model_validate(task_obj)
                        await q.put(("task_ready", task_out.model_dump(mode="json")))

            # Seed base cards from materials (no LLM conspect available here)
            _spawn_card_generation(
                topic, _format_card_context_from_materials(topic.name, materials_list)
            )
            await q.put(("complete", {"session_id": session_id}))
        except Exception as exc:
            await q.put(("error", {"message": str(exc), "fallback": True}))
            await q.put(("complete", {"session_id": session_id}))
        finally:
            remove_stream(session_id)
        return

    # ── LLM configured → stream conspect, then generate tasks ─────────────────
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

        # Seed base cards from the freshly generated conspect + tasks
        _spawn_card_generation(
            topic,
            _format_card_context_from_session(topic.name, conspect_md, task_creates),
        )
        await q.put(("complete", {"session_id": session_id}))

    except Exception as exc:
        logger.error("Task generation failed for session %s: %s", session_id, exc, exc_info=True)
        # Tasks failed but the conspect is ready — still seed base cards from it
        _spawn_card_generation(
            topic, _format_card_context_from_session(topic.name, conspect_md, [])
        )
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

    # Learner profile/strategy chosen at topic start — persist on the topic so it
    # parametrizes this and future generations. The adaptive onboarding sends a rich
    # `study_profile`; the legacy preset path sends `strategy`. None keeps whatever the
    # topic already has (the onboarding /plan step may have stored it), else the default.
    strategy = data.get("study_profile") or data.get("strategy")
    if strategy is not None:
        topic.strategy_config = strategy
        await db.commit()
        await db.refresh(topic)

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

    db.add(LearningEvent(
        user_id=topic.user_id,
        event_type="study_session_started",
        payload={"topic_id": topic.id, "session_id": session_obj.id, "domain": topic.domain},
    ))
    await db.commit()

    topic_info = TopicInfo(
        id=topic.id,
        name=topic.name,
        user_id=topic.user_id,
        domain=topic.domain,
        strategy_config=topic.strategy_config,
    )
    create_stream(session_obj.id)
    # Cards are generated *inside* _run_session_generation, after the conspect and
    # tasks are ready, so they're seeded from the richest available context.
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


@router.post("/practice-tasks/{task_id}/answer", response_model=AnswerSubmissionOut, status_code=201)
async def submit_answer(
    task_id: str,
    user_id: str = Form(...),
    solution_text: str = Form(""),
    files: list[UploadFile] = File(default=[]),
    db: AsyncSession = Depends(get_db),
):
    """Submit a web practice answer with optional file/image attachments and get AI feedback.

    Mirrors the multipart upload pattern of ``topics.upload_material_file``: creates an
    IdeSubmission (web origin), stores each file as a SubmissionAttachment (text → extracted
    text, image → base64), then runs the AI evaluator and returns the combined result.
    """
    task = await practice_repo.get_practice_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Practice task not found")

    try:
        submission = await practice_repo.create_submission(
            db,
            IdeSubmissionCreate(
                practice_task_id=task_id,
                user_id=user_id,
                reflection=solution_text,
                language="web",
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    real_files = [f for f in files if f and f.filename]
    if len(real_files) > _MAX_ATTACHMENTS:
        raise HTTPException(
            status_code=400,
            detail=f"Слишком много вложений (максимум {_MAX_ATTACHMENTS})",
        )
    for upload in real_files:
        data = await upload.read()
        if not data:
            continue
        if len(data) > _MAX_ATTACHMENT_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"Файл слишком большой: {upload.filename} (максимум 8 МБ)",
            )
        if is_image(upload.filename):
            attachment = SubmissionAttachment(
                submission_id=submission.id,
                user_id=user_id,
                name=upload.filename,
                mime_type=image_mime(upload.filename),
                kind="image",
                data_b64=base64.b64encode(data).decode("ascii"),
                file_size=len(data),
            )
        else:
            attachment = SubmissionAttachment(
                submission_id=submission.id,
                user_id=user_id,
                name=upload.filename,
                mime_type=upload.content_type or "text/plain",
                kind="text",
                content_text=extract_from_bytes(upload.filename, data),
                file_size=len(data),
            )
        await practice_repo.add_attachment(db, attachment)

    evaluation = await evaluate_submission_ai(db, submission)

    # The web Practice tab never answers follow-ups (they're shown read-only), so
    # mastery would never advance via finalize_evaluation_mastery. Record practice
    # mastery directly on a passing answer instead.
    if evaluation.status == "passed" and task.target_concepts:
        # struggle_passed gates the top "explain" mastery level. The web Practice tab
        # never collects follow-up answers, so granting it on every pass handed "explain"
        # to easy wins. Grant it only when a genuinely hard task (difficulty 3) is passed
        # with high quality — an honest proxy for "handled a hard case under pressure".
        hard_pass = 1 if (task.difficulty >= 3 and evaluation.score >= 0.8) else 0
        for concept in task.target_concepts:
            await mastery_repo.record(
                db,
                user_id=user_id,
                topic_id=task.topic_id,
                concept=concept,
                kind="practice",
                difficulty=task.difficulty,
                quality_score=evaluation.score,
                struggle_passed=hard_pass,
            )

    db.add(LearningEvent(
        user_id=user_id,
        event_type="task_submitted",
        payload={
            "topic_id": task.topic_id,
            "task_id": task_id,
            "task_type": task.type,
            "score": evaluation.score,
            "passed": evaluation.status == "passed",
        },
    ))
    if evaluation.status == "passed":
        db.add(LearningEvent(
            user_id=user_id,
            event_type="task_completed",
            payload={"topic_id": task.topic_id, "task_id": task_id, "task_type": task.type},
        ))
    await db.commit()

    follow_ups = await practice_repo.list_follow_ups_by_evaluation(db, evaluation.id)
    attachments = await practice_repo.list_attachments(db, submission.id)

    return AnswerSubmissionOut(
        submission=IdeSubmissionOut.model_validate(submission),
        evaluation=EvaluationOut.model_validate(evaluation),
        follow_ups=[FollowUpOut.model_validate(fu) for fu in follow_ups],
        attachments=[AttachmentOut.model_validate(a) for a in attachments],
    )


@router.post("/submissions/{submission_id}/evaluate", response_model=EvaluationOut, status_code=201)
async def evaluate_submission_endpoint(submission_id: str, db: AsyncSession = Depends(get_db)):
    submission = await practice_repo.get_submission(db, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    evaluation = await evaluate_submission_ai(db, submission)
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
    db.add(LearningEvent(
        user_id=data["user_id"],
        event_type="study_session_completed",
        payload={"topic_id": completed.topic_id, "session_id": session_id, "capsule_id": capsule.id},
    ))
    await db.commit()
    return {
        "session": StudySessionOut.model_validate(completed),
        "capsule": CapsuleOut.model_validate(capsule),
    }
