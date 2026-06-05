"""
LLM resilience utilities: exponential backoff retry on 429, with fallback model.
"""
import asyncio
import logging
from collections.abc import AsyncGenerator

import httpx

logger = logging.getLogger(__name__)

_RETRY_DELAYS = (10, 30, 60)


def _parse_retry_after(response: httpx.Response, attempt: int) -> float:
    for header in ("Retry-After", "x-ratelimit-reset-requests", "x-ratelimit-reset"):
        val = response.headers.get(header)
        if val:
            try:
                seconds = float(val)
                # If it looks like a unix timestamp (>1e9), compute delta from now
                if seconds > 1_000_000_000:
                    import time
                    seconds = max(0, seconds - time.time())
                return min(seconds, 120.0)
            except (ValueError, TypeError):
                pass
    return _RETRY_DELAYS[min(attempt, len(_RETRY_DELAYS) - 1)]


async def http_post_with_retry(
    client: httpx.AsyncClient,
    url: str,
    headers: dict,
    json_body: dict,
    retries: int = 3,
    fallback_model: str | None = None,
) -> httpx.Response:
    """POST with exponential backoff on 429. Switches to fallback_model after first failure."""
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        body = dict(json_body)
        if attempt > 0 and fallback_model:
            body["model"] = fallback_model
        try:
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 429 or attempt == retries:
                raise
            last_exc = exc
            delay = _parse_retry_after(exc.response, attempt)
            model_label = body.get("model", "?")
            logger.warning(
                "LLM 429 attempt %d/%d [%s] — waiting %.0fs then %s",
                attempt + 1, retries + 1, model_label, delay,
                f"switching to {fallback_model}" if (attempt == 0 and fallback_model) else "retrying",
            )
            await asyncio.sleep(delay)
    raise last_exc  # type: ignore[misc]


async def http_stream_with_retry(
    client: httpx.AsyncClient,
    url: str,
    headers: dict,
    json_body: dict,
    retries: int = 2,
    fallback_model: str | None = None,
) -> AsyncGenerator[str, None]:
    """Stream POST with retry on 429. Switches to fallback_model after first failure."""
    import json as _json

    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        body = dict(json_body)
        if attempt > 0 and fallback_model:
            body["model"] = fallback_model
        try:
            async with client.stream("POST", url, headers=headers, json=body) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        return
                    try:
                        data = _json.loads(data_str)
                        delta = data["choices"][0]["delta"]
                        token = delta.get("content") or ""
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
            model_label = body.get("model", "?")
            logger.warning(
                "LLM stream 429 attempt %d/%d [%s] — restarting in %.0fs then %s",
                attempt + 1, retries + 1, model_label, delay,
                f"switching to {fallback_model}" if (attempt == 0 and fallback_model) else "retrying",
            )
            await asyncio.sleep(delay)
    raise last_exc  # type: ignore[misc]
