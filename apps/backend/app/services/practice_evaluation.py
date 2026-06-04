from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IdeSubmission
from app.repositories import mastery_repo, practice_repo
from app.schemas.practice import EvaluationCreate, FollowUpCreate


async def evaluate_submission(db: AsyncSession, submission: IdeSubmission):
    task = await practice_repo.get_practice_task(db, submission.practice_task_id)
    passed = (
        submission.exit_code == 0
        or "passed" in submission.test_output.lower()
        or "success" in submission.test_output.lower()
    )
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
            user_id=submission.user_id,
            score=score,
            status=status,
            feedback_md=feedback,
            concept_scores={concept: score for concept in (task.target_concepts if task else [submission.language])},
            weak_spots=[] if status == "passed" else [{"concept": "evidence quality", "severity": 1.0}],
            next_action="continue_lesson" if status == "passed" else "revise",
        ),
    )

    # Create follow-up questions for passed submissions; mastery updates after follow-ups
    if task and status == "passed":
        await practice_repo.create_follow_up(
            db,
            FollowUpCreate(
                evaluation_id=evaluation.id,
                question=f"Explain the core concept behind {task.target_concepts[0] if task.target_concepts else 'this task'} in 1-2 sentences.",
                expected_answer="Clear explanation demonstrating understanding.",
            ),
        )
        if len(task.target_concepts) > 1:
            await practice_repo.create_follow_up(
                db,
                FollowUpCreate(
                    evaluation_id=evaluation.id,
                    question=f"What trade-off did you face when implementing {task.target_concepts[0]}?",
                    expected_answer="Named a realistic trade-off with reasoning.",
                ),
            )

    return evaluation


async def finalize_evaluation_mastery(db: AsyncSession, evaluation_id: str) -> bool:
    """Update mastery if all follow-ups for this evaluation are answered with score >= 0.7."""
    evaluation = await practice_repo.get_evaluation(db, evaluation_id)
    if not evaluation:
        return False

    follow_ups = await practice_repo.list_follow_ups_by_evaluation(db, evaluation_id)
    if not follow_ups:
        # No follow-ups required — mastery already updated
        return True

    pending = [fu for fu in follow_ups if fu.score is None or fu.score < 0.7]
    if pending:
        return False

    submission = await practice_repo.get_submission(db, evaluation.submission_id)
    if not submission:
        return False

    task = await practice_repo.get_practice_task(db, submission.practice_task_id)
    if not task:
        return False

    for concept in task.target_concepts:
        await mastery_repo.record(
            db,
            user_id=submission.user_id,
            topic_id=task.topic_id,
            concept=concept,
            kind="practice",
            difficulty=task.difficulty,
            quality_score=evaluation.score,
            struggle_passed=1 if len(follow_ups) >= 2 else 0,
        )

    return True
