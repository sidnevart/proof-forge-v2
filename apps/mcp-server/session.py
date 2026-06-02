import os
from pathlib import Path

_IDENTITY_FILE = Path.home() / ".proof-forge" / "identity"
_user_id: str = ""


def _load_from_file() -> str:
    if _IDENTITY_FILE.exists():
        return _IDENTITY_FILE.read_text().strip()
    return ""


def _persist(uid: str) -> None:
    global _user_id
    _user_id = uid
    _IDENTITY_FILE.parent.mkdir(parents=True, exist_ok=True)
    _IDENTITY_FILE.write_text(uid)


async def get_uid(explicit: str = "") -> str:
    """Return current user_id. Raises if not configured — Claude will ask for email."""
    global _user_id
    uid = explicit or _user_id or os.environ.get("PROOF_FORGE_USER_ID", "") or _load_from_file()
    if not uid:
        raise ValueError(
            "No identity found. Ask the user: "
            "'Какой у тебя email? Напиши его и я сразу настрою твой профиль.' "
            "Then call identify(email='...') with their answer."
        )
    _user_id = uid
    return uid


def set_uid(uid: str) -> None:
    _persist(uid)
