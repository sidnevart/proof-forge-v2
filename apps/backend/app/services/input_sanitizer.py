"""
Input sanitization to mitigate prompt-injection and off-topic abuse.
"""
import re

from fastapi import HTTPException

_MAX_MESSAGE_LENGTH = 4_000

# Patterns that try to override system instructions or switch roles
_INJECTION_PATTERNS = [
    r"ignore\s+(?:all\s+|previous\s+)?instructions",
    r"forget\s+(?:all\s+|previous\s+)?instructions",
    r"system\s*:",
    r"you\s+are\s+now\s+(?:a\s+)?",
    r"new\s+role\s*:",
    r"override\s+(?:system\s+|previous\s+)?prompt",
    r"disregard\s+(?:all\s+|previous\s+)?(?:instructions|rules)",
    r"simulate\s+(?:being|as)\s+(?:a\s+)?",
    r"pretend\s+(?:to\s+be|you\s+are)\s+(?:a\s+)?",
    r"act\s+as\s+(?:if\s+you\s+(?:are|were)\s+)?",
    r"\bDAN\b",
    r"\bjailbreak\b",
    r"\bhacked\b",
    r"###\s*system",
    r"###\s*assistant",
    r"###\s*user",
]

_INJECTION_RE = re.compile(
    "|".join(f"(?:{p})" for p in _INJECTION_PATTERNS),
    re.IGNORECASE,
)


def sanitize_chat_input(text: str) -> str:
    """Sanitize a single chat message.

    - Rejects known prompt-injection patterns.
    - Clips to _MAX_MESSAGE_LENGTH.
    - Strips leading/trailing whitespace.
    """
    if not isinstance(text, str):
        raise HTTPException(status_code=400, detail="Invalid input: message must be a string")

    stripped = text.strip()

    if _INJECTION_RE.search(stripped):
        raise HTTPException(status_code=400, detail="Invalid input: message contains disallowed patterns")

    if len(stripped) > _MAX_MESSAGE_LENGTH:
        stripped = stripped[:_MAX_MESSAGE_LENGTH].rstrip()

    return stripped
