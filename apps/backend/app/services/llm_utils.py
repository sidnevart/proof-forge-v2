"""
LLM resilience utilities: exponential backoff retry on 429, with fallback model.
"""
import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def extract_json(text: str, *, container: str = "{") -> Any:
    """Decode the first complete JSON value (object or array) from an LLM response.

    Tolerates a ```json … ``` wrapper and reasoning-model preamble by scanning to the
    first '{'/'[' and letting a real JSON decoder consume exactly one value.

    Crucially it does NOT globally strip ``` fences or count braces by hand: generated
    markdown fields (instructions_md, card answers, capsule body) legitimately contain
    fenced code blocks and braces inside string values. A blanket fence strip turns
    ```kotlin … ``` into bare run-on text, and a naive brace counter mis-matches on a
    `{` inside code — both corrupt the output. The decoder respects string contents.

    container selects which bracket to anchor on first: "{" (object, default) or
    "[" (array). Whichever of '{'/'[' appears earliest from the preferred kind is used.

    strict=False: LLM-generated markdown/code fields routinely contain RAW newlines
    and tabs inside JSON string values (the model writes a multi-line `instructions_md`
    without escaping every \n). Standard json rejects control chars in strings; the
    lenient decoder accepts them, which is the single biggest cause of "valid-looking
    output that won't parse" from these models.
    """
    first_obj = text.find("{")
    first_arr = text.find("[")
    prefer, other = (first_obj, first_arr) if container == "{" else (first_arr, first_obj)
    candidates = [i for i in (prefer, other) if i != -1]
    if not candidates:
        raise ValueError(f"No JSON value found in LLM response (len={len(text)})")
    start = min(candidates)
    try:
        value, _ = json.JSONDecoder(strict=False).raw_decode(text, start)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in LLM response: {exc}") from None
    return value

# Free-tier 429s ("temporarily rate-limited upstream") are transient — they clear within
# a few seconds. A quick ramp rides them out without the long 30/60s stalls that used to
# make generation give up and fall back to template content.
_RETRY_DELAYS = (2, 4, 7, 11, 16, 22)
_MAX_RETRY_AFTER = 20.0


def _fallback_attempt_threshold(retries: int) -> int:
    """First attempt index at which we switch to the fallback model.

    Give the primary model the first attempts (transient 429s usually clear by then);
    only fall back for the final couple of tries when it's persistently unavailable.
    """
    return max(1, retries - 1)

# Cap concurrent LLM calls across all flows (session-gen + card-gen + capsule +
# map-reduce) so bursts can't trip the provider's per-minute rate limit. The free
# OpenRouter tier is the binding constraint, not the model context window.
_MAX_CONCURRENT_LLM_CALLS = 3
_LLM_GATE = asyncio.Semaphore(_MAX_CONCURRENT_LLM_CALLS)


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
                # Cap the honored wait: free-tier blips clear in seconds even when the
                # server suggests a long Retry-After, so don't stall a whole minute.
                return min(seconds, _MAX_RETRY_AFTER)
            except (ValueError, TypeError):
                pass
    return _RETRY_DELAYS[min(attempt, len(_RETRY_DELAYS) - 1)]


async def http_post_with_retry(
    client: httpx.AsyncClient,
    url: str,
    headers: dict,
    json_body: dict,
    retries: int = 6,
    fallback_model: str | None = None,
) -> httpx.Response:
    """POST with backoff on 429. Retries the primary model first, then the fallback model."""
    last_exc: Exception | None = None
    fallback_at = _fallback_attempt_threshold(retries)
    for attempt in range(retries + 1):
        body = dict(json_body)
        if fallback_model and attempt >= fallback_at:
            body["model"] = fallback_model
        try:
            # Hold the gate only for the request itself, not the backoff sleep.
            async with _LLM_GATE:
                response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 429 or attempt == retries:
                raise
            last_exc = exc
            delay = _parse_retry_after(exc.response, attempt)
            logger.warning(
                "LLM 429 attempt %d/%d [%s] — waiting %.0fs then retrying",
                attempt + 1, retries + 1, body.get("model", "?"), delay,
            )
            await asyncio.sleep(delay)
    raise last_exc  # type: ignore[misc]


async def http_stream_with_retry(
    client: httpx.AsyncClient,
    url: str,
    headers: dict,
    json_body: dict,
    retries: int = 4,
    fallback_model: str | None = None,
) -> AsyncGenerator[str, None]:
    """Stream POST with retry on 429. Retries the primary model first, then the fallback."""
    import json as _json

    last_exc: Exception | None = None
    fallback_at = _fallback_attempt_threshold(retries)
    for attempt in range(retries + 1):
        body = dict(json_body)
        if fallback_model and attempt >= fallback_at:
            body["model"] = fallback_model
        try:
            # Hold the gate for the whole stream — it caps concurrent open connections.
            async with _LLM_GATE, client.stream("POST", url, headers=headers, json=body) as response:
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
            logger.warning(
                "LLM stream 429 attempt %d/%d [%s] — restarting in %.0fs",
                attempt + 1, retries + 1, body.get("model", "?"), delay,
            )
            await asyncio.sleep(delay)
    raise last_exc  # type: ignore[misc]
