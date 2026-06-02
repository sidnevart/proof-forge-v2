from client import post
from session import get_uid


async def log_event(event_type: str, payload: dict, user_id: str = "") -> dict:
    """Log a learning event (note_added, insight, question, etc.)."""
    return await post("/api/events", {"user_id": await get_uid(user_id), "event_type": event_type, "payload": payload})


async def store_code_artifact(
    topic_id: str, filename: str, content: str, language: str, user_id: str = ""
) -> dict:
    """Store a code artifact from the developer's workspace."""
    return await post("/api/events", {
        "user_id": await get_uid(user_id),
        "event_type": "code_artifact",
        "payload": {"topic_id": topic_id, "filename": filename, "content": content, "language": language},
    })
