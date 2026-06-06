"""Shared chunking + map-reduce helpers for distilling large materials.

Large files would otherwise either blow the LLM context or (worse) get silently
truncated to their first few thousand characters. These helpers split materials into
bounded chunks, extract concepts per chunk (MAP), and cap the total number of LLM calls
so a single huge file can't drain the free-tier daily quota.
"""
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Below this many total chars, one LLM call sees everything — no map-reduce needed.
SINGLE_PASS_LIMIT = 12_000
# Chars per chunk in the MAP phase.
CHUNK_SIZE = 8_000
# Hard cap on MAP calls per generation — bounds requests against the daily quota.
MAX_MAP_CHUNKS = 16


def split_chunks(text: str, size: int = CHUNK_SIZE) -> list[str]:
    """Split text into ≤size chunks, preferring paragraph/line boundaries."""
    if len(text) <= size:
        return [text]
    chunks = []
    while text:
        if len(text) <= size:
            chunks.append(text)
            break
        split_at = text.rfind("\n\n", 0, size)
        if split_at < size // 3:
            split_at = text.rfind("\n", 0, size)
        if split_at < size // 3:
            split_at = size
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip()
    return chunks


def plan_chunks(
    materials: list[tuple[str, str]],
    chunk_size: int = CHUNK_SIZE,
    max_chunks: int = MAX_MAP_CHUNKS,
) -> tuple[list[tuple[str, str]], int]:
    """Chunk every material and cap the total to ``max_chunks``.

    ``materials`` is a list of ``(name, content_text)``. Returns
    ``(planned_chunks, dropped_count)`` where ``planned_chunks`` is a list of
    ``(material_name, chunk_text)``. When the corpus exceeds the cap, chunks are sampled
    evenly across the whole corpus (so coverage stays spread out, not front-loaded) and
    the number dropped is reported — never silently truncated.
    """
    all_chunks: list[tuple[str, str]] = []
    for name, text in materials:
        for chunk in split_chunks(text, chunk_size):
            if chunk.strip():
                all_chunks.append((name, chunk))

    if len(all_chunks) <= max_chunks:
        return all_chunks, 0

    step = len(all_chunks) / max_chunks
    sampled = [all_chunks[int(i * step)] for i in range(max_chunks)]
    dropped = len(all_chunks) - len(sampled)
    logger.warning(
        "map-reduce: %d chunks exceed cap %d — sampled %d evenly, dropped %d",
        len(all_chunks), max_chunks, len(sampled), dropped,
    )
    return sampled, dropped


def build_extract_prompt(topic_name: str, material_name: str, chunk: str) -> str:
    """MAP prompt: pull the key concepts/facts out of one chunk."""
    return f"""Из фрагмента материала «{material_name}» (тема: «{topic_name}») извлеки ключевые концепции, определения и важные факты.

Фрагмент:
{chunk}

Ответь кратким структурированным списком — только суть, без воды. Без JSON, просто текст."""


async def _digest_llm_call(
    client: httpx.AsyncClient, settings: Any, prompt: str, max_tokens: int = 800
) -> str:
    """Minimal non-streaming LLM call returning just the text content."""
    from app.services.llm_utils import http_post_with_retry
    response = await http_post_with_retry(
        client,
        f"{settings.llm_base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://proof-forge.ru",
            "X-Title": "Grasp",
        },
        json_body={
            "model": settings.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.4,
        },
        fallback_model=getattr(settings, "llm_fallback_model", None),
    )
    data = response.json()
    msg = data["choices"][0]["message"]
    return msg.get("content") or msg.get("reasoning") or ""


async def map_reduce_digest(
    client: httpx.AsyncClient,
    settings: Any,
    topic_name: str,
    materials: list[tuple[str, str]],
    *,
    chunk_size: int = CHUNK_SIZE,
    max_chunks: int = MAX_MAP_CHUNKS,
    progress: Any = None,
) -> str:
    """Distil large materials into a combined concept digest (the REDUCE input).

    ``materials`` is a list of ``(name, content_text)``. ``progress`` is an optional
    ``async (current, total) -> None`` callback for streaming UI updates.
    """
    planned, dropped = plan_chunks(materials, chunk_size, max_chunks)
    total = len(planned)
    extracts: list[str] = []
    for idx, (name, chunk) in enumerate(planned, 1):
        if progress is not None:
            await progress(idx, total)
        content = await _digest_llm_call(
            client, settings, build_extract_prompt(topic_name, name, chunk)
        )
        extracts.append(f"[Источник: {name}]\n{content}")

    digest = "\n\n---\n\n".join(extracts)
    if dropped:
        digest += (
            f"\n\n[Примечание: материалов больше, чем помещается в один разбор — "
            f"обработано {total} фрагментов, {dropped} пропущено для экономии лимитов.]"
        )
    return digest
