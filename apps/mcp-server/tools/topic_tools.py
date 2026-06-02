from client import post
from session import get_uid


async def start_topic(topic_name: str, user_id: str = "") -> dict:
    """Start a new learning topic session. Returns {topic_id}."""
    return await post("/api/topics/start", {"user_id": await get_uid(user_id), "name": topic_name})


async def complete_topic(topic_id: str, user_id: str = "") -> dict:
    """Mark a learning topic as completed. Call when the user finishes studying a topic."""
    return await post(f"/api/topics/{topic_id}/complete", {"user_id": await get_uid(user_id)})
