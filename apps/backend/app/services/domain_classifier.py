"""Domain classifier — a single cheap LLM call that labels a topic into one of the
canonical domains (see domain_profiles.DOMAINS) at topic start.

Deterministic fallback to `general` whenever the LLM is unavailable or returns an
unexpected label, mirroring the fallback discipline in practice_generation.py.
"""
import logging
from typing import Any

import httpx

from app.services.domain_profiles import DEFAULT_DOMAIN, DOMAINS

logger = logging.getLogger(__name__)

_PROMPT = (
    "Классифицируй учебную тему в ОДИН домен. Ответь строго одним словом из списка:\n"
    "- coding — программирование, разработка ПО, инфраструктура, алгоритмы\n"
    "- language — изучение иностранного языка (грамматика, лексика, разговор)\n"
    "- theory_math — математика, физика, формальная теория, доказательства\n"
    "- humanities — история, философия, право, литература, общество\n"
    "- general — всё остальное / непонятно\n\n"
    "Тема: «{name}»\n"
    "{materials}\n"
    "Ответ (одно слово):"
)


def _normalize(raw: str) -> str:
    token = (raw or "").strip().lower()
    # Reasoning models may add punctuation/preamble — scan for the first known label.
    for domain in DOMAINS:
        if domain in token:
            return domain
    return DEFAULT_DOMAIN


async def classify_domain(
    client: httpx.AsyncClient,
    settings: Any,
    name: str,
    materials_preview: str = "",
) -> str:
    """Return one of DOMAINS. Falls back to `general` on any error or empty key."""
    if not getattr(settings, "llm_api_key", ""):
        return DEFAULT_DOMAIN

    materials_line = (
        f"Фрагмент материалов: {materials_preview[:600]}" if materials_preview.strip() else ""
    )
    prompt = _PROMPT.format(name=name, materials=materials_line)

    from app.services.llm_utils import http_post_with_retry

    try:
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
                "max_tokens": 16,
                "temperature": 0.0,
            },
            retries=1,
            fallback_model=getattr(settings, "llm_fallback_model", None),
        )
        data = response.json()
        msg = data["choices"][0]["message"]
        raw = msg.get("content") or msg.get("reasoning") or ""
        return _normalize(raw)
    except Exception as exc:  # noqa: BLE001 — classification must never break topic start
        logger.warning("Domain classification failed, defaulting to general: %s", exc)
        return DEFAULT_DOMAIN
