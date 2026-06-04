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
