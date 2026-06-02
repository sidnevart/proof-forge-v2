from client import get
from session import get_uid


async def get_agent_context(topic: str | None = None, user_id: str = "") -> dict:
    """Get a compact context bundle — profile, capsules, weak spots, recent events."""
    params = {"userId": await get_uid(user_id)}
    if topic:
        params["topic"] = topic
    return await get("/api/agent-context", params)
