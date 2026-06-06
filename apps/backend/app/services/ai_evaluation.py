"""AI-backed evaluation of learner practice answers (web submissions).

Replaces the deterministic scorer for answers submitted via the web Practice tab.
Builds a multimodal user message (text + image attachments), routes image-bearing
submissions to a free vision model, parses a strict JSON contract, and persists an
``Evaluation`` plus any follow-up questions. Falls back to the deterministic
``practice_evaluation.evaluate_submission`` when the LLM is not configured or the
response can't be parsed — so tests and no-key environments keep working.
"""
import json
import logging
import re

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as app_settings
from app.models import IdeSubmission
from app.repositories import practice_repo
from app.schemas.practice import EvaluationCreate, FollowUpCreate
from app.services.evaluation_prompt import get_evaluation_system_prompt
from app.services.llm_utils import http_post_with_retry
from app.services.practice_evaluation import evaluate_submission as evaluate_submission_deterministic

logger = logging.getLogger(__name__)

_MAX_ATTACHMENT_CHARS = 8000
_MAX_IMAGES = 4


def _clip(text: str, max_chars: int) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n\n..."


def _extract_json(text: str) -> dict:
    """Strip markdown fences and isolate the outermost JSON object."""
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    start = text.find("{")
    if start == -1:
        raise ValueError(f"No JSON object found in LLM response (len={len(text)})")
    depth = 0
    end = -1
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end == -1:
        raise ValueError("Unmatched braces in LLM response")
    return json.loads(text[start:end])


def _build_user_content(task, solution_text: str, attachments: list) -> tuple[list | str, bool]:
    """Build the OpenAI-compatible message content.

    Returns ``(content, has_images)``. Without images, content is a plain string
    (text-only model); with images, a list of content parts (vision model).
    """
    task_lines = ["## Задание"]
    if task:
        task_lines.append(f"**{task.title}**")
        if task.instructions_md:
            task_lines.append(_clip(task.instructions_md, 4000))
        if task.target_concepts:
            task_lines.append("Целевые концепции: " + ", ".join(task.target_concepts))
        if task.expected_evidence:
            task_lines.append("Ожидаемое: " + "; ".join(task.expected_evidence))

    parts = ["\n\n".join(task_lines)]
    parts.append("## Ответ ученика\n" + (_clip(solution_text, _MAX_ATTACHMENT_CHARS) or "(текст не указан)"))

    images = []
    for att in attachments:
        if att.kind == "image" and att.data_b64 and len(images) < _MAX_IMAGES:
            images.append(att)
        elif att.kind == "text" and att.content_text:
            parts.append(f"## Файл: {att.name}\n```\n{_clip(att.content_text, _MAX_ATTACHMENT_CHARS)}\n```")

    text_block = "\n\n".join(parts)

    if not images:
        return text_block, False

    content: list = [{"type": "text", "text": text_block}]
    for att in images:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{att.mime_type};base64,{att.data_b64}"},
        })
    return content, True


async def evaluate_submission_ai(db: AsyncSession, submission: IdeSubmission):
    """Evaluate a submission with the LLM. Falls back to deterministic on failure."""
    task = await practice_repo.get_practice_task(db, submission.practice_task_id)
    attachments = await practice_repo.list_attachments(db, submission.id)

    if not app_settings.llm_api_key:
        return await evaluate_submission_deterministic(db, submission)

    content, has_images = _build_user_content(task, submission.reflection, attachments)
    model = app_settings.llm_vision_model if has_images else app_settings.llm_model
    fallback = (
        app_settings.llm_vision_fallback_model if has_images else app_settings.llm_fallback_model
    )

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await http_post_with_retry(
                client,
                f"{app_settings.llm_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {app_settings.llm_api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://proof-forge.ru",
                    "X-Title": "Grasp",
                },
                json_body={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": get_evaluation_system_prompt()},
                        {"role": "user", "content": content},
                    ],
                    "max_tokens": 2048,
                    "temperature": 0.3,
                },
                fallback_model=fallback,
            )
        raw = resp.json()["choices"][0]["message"]["content"]
        parsed = _extract_json(raw)
    except Exception as exc:
        logger.warning(
            "AI evaluation failed for submission %s (model=%s): %s — falling back",
            submission.id, model, exc,
        )
        return await evaluate_submission_deterministic(db, submission)

    score = max(0.0, min(1.0, float(parsed.get("score", 0.0))))
    status = parsed.get("status")
    if status not in ("passed", "needs_revision", "failed"):
        status = "passed" if score >= 0.7 else ("needs_revision" if score >= 0.4 else "failed")
    concept_scores = parsed.get("concept_scores") or {}
    if not isinstance(concept_scores, dict):
        concept_scores = {}
    weak_spots = parsed.get("weak_spots") or []
    if not isinstance(weak_spots, list):
        weak_spots = []
    next_action = parsed.get("next_action") or ("continue_lesson" if status == "passed" else "revise")

    evaluation = await practice_repo.create_evaluation(
        db,
        EvaluationCreate(
            submission_id=submission.id,
            user_id=submission.user_id,
            score=score,
            status=status,
            feedback_md=parsed.get("feedback_md") or "## Оценка\n\n(фидбэк не сформирован)",
            concept_scores={k: max(0.0, min(1.0, float(v))) for k, v in concept_scores.items() if isinstance(v, (int, float))},
            weak_spots=[w for w in weak_spots if isinstance(w, dict)],
            next_action=next_action,
        ),
    )

    if status == "passed":
        for fu in (parsed.get("follow_ups") or [])[:2]:
            if isinstance(fu, dict) and fu.get("question"):
                await practice_repo.create_follow_up(
                    db,
                    FollowUpCreate(
                        evaluation_id=evaluation.id,
                        question=str(fu["question"]),
                        expected_answer=str(fu.get("expected_answer", "")),
                    ),
                )

    return evaluation
