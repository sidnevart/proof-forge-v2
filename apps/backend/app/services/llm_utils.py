"""
LLM resilience utilities: exponential backoff retry on 429 Too Many Requests.

Used by practice_generation.py for streaming and non-streaming calls.
topics.py has its own inline retry in _llm_call.
"""
import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_RETRY_DELAYS = (5, 15, 30)


def _parse_retry_after(response: httpx.Response, attempt: int) -> float:
    for header in ("Retry-After", "x-ratelimit-reset-requests"):
        val = response.headers.get(header)
        if val:
            try:
                return min(float(val), 60.0)
            except (ValueError, TypeError):
                pass
    return _RETRY_DELAYS[min(attempt, len(_RETRY_DELAYS) - 1)]


async def http_post_with_retry(
    client: httpx.AsyncClient,
    url: str,
    headers: dict,
    json_body: dict,
    retries: int = 3,
) -> httpx.Response:
    """POST with exponential backoff on 429."""
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = await client.post(url, headers=headers, json=json_body)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 429 or attempt == retries:
                raise
            last_exc = exc
            delay = _parse_retry_after(exc.response, attempt)
            logger.warning("LLM 429 attempt %d/%d — waiting %.0fs", attempt + 1, retries + 1, delay)
            await asyncio.sleep(delay)
    raise last_exc  # type: ignore[misc]


async def http_stream_with_retry(
    client: httpx.AsyncClient,
    url: str,
    headers: dict,
    json_body: dict,
    retries: int = 2,
) -> AsyncGenerator[str, None]:
    """Stream POST with retry on 429 (restarts stream from beginning)."""
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            async with client.stream("POST", url, headers=headers, json=json_body) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        return
                    import json as _json
                    try:
                        data = _json.loads(data_str)
                        token = data["choices"][0]["delta"].get("content") or ""
                        if token:
                            yield token
                    except (ValueError, KeyError, IndexError):
                        continue
            return
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 429 or attempt == retries:
                raise
            last_exc = exc
            delay = _parse_retry_after(exc.response, attempt)
            logger.warning("LLM stream 429 attempt %d/%d — restarting in %.0fs", attempt + 1, retries + 1, delay)
            await asyncio.sleep(delay)
    raise last_exc  # type: ignore[misc]
