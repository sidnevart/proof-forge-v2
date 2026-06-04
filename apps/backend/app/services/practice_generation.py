from app.models import Topic
from app.schemas.practice import PracticeTaskCreate, StudySessionCreate


def build_study_session(topic: Topic) -> StudySessionCreate:
    return StudySessionCreate(
        user_id=topic.user_id,
        topic_id=topic.id,
        conspect_md=(
            f"## Конспект: {topic.name}\n\n"
            "Сессия сфокусирована на понимании ключевых концепций через короткую теорию "
            "и практику в реальной IDE.\n\n"
            "## План\n\n"
            "1. **Теория** — разберём ключевые концепции.\n"
            "2. **Mini-project** — реализуй решение локально и отправь evidence через JetBrains plugin.\n"
        ),
        learning_goals=[
            f"Understand {topic.name} at conceptual level",
            f"Apply {topic.name} in a small real project",
        ],
    )


def build_theory_task(session_id: str, topic: Topic) -> PracticeTaskCreate:
    return PracticeTaskCreate(
        user_id=topic.user_id,
        topic_id=topic.id,
        study_session_id=session_id,
        type="theory",
        title=f"Теория: {topic.name}",
        instructions_md=(
            f"## Теоретический блок: {topic.name}\n\n"
            "Прочитай конспект сессии и подготовь краткое объяснение:\n\n"
            "- Что делает эта концепция?\n"
            "- Зачем она нужна?\n"
            "- В каких ситуациях применяется?\n\n"
            "Это подготовка к mini-project."
        ),
        target_concepts=[topic.name],
        difficulty=1,
        expected_evidence=["written_explanation"],
        check_commands=[],
    )


def build_mini_project_task(session_id: str, topic: Topic) -> PracticeTaskCreate:
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


def build_study_tasks(session_id: str, topic: Topic) -> list[PracticeTaskCreate]:
    """Build the ordered set of practice tasks for a study session.

    Matches study-mentor-v2 flow: theory first, then capstone mini-project.
    """
    return [
        build_theory_task(session_id, topic),
        build_mini_project_task(session_id, topic),
    ]
