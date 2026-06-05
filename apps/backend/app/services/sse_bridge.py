import asyncio
import json
from collections.abc import AsyncGenerator

_streams: dict[str, asyncio.Queue] = {}


def create_stream(stream_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _streams[stream_id] = q
    return q


def get_stream(stream_id: str) -> asyncio.Queue | None:
    return _streams.get(stream_id)


def remove_stream(stream_id: str) -> None:
    _streams.pop(stream_id, None)


def _format_sse(event: str, data: dict, event_id: int | None = None) -> str:
    lines: list[str] = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(data, ensure_ascii=False)}")
    lines.append("")
    lines.append("")
    return "\n".join(lines)


async def stream_from_queue(q: asyncio.Queue, heartbeat_interval: float = 15.0) -> AsyncGenerator[str, None]:
    """Yield SSE-formatted strings from queue until complete or error event."""
    event_id = 0
    while True:
        try:
            event_type, data = await asyncio.wait_for(q.get(), timeout=heartbeat_interval)
            event_id += 1
            yield _format_sse(event_type, data, event_id)
            if event_type in ("complete", "error"):
                break
        except asyncio.TimeoutError:
            yield ": ping\n\n"
