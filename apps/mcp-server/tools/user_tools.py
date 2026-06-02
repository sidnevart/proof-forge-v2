from client import post, get
from session import get_uid, set_uid


async def create_user(email: str, display_name: str) -> dict:
    """Create a new learner user explicitly. Returns user with id."""
    return await post("/api/users", {"email": email, "display_name": display_name})


async def identify(email: str, display_name: str = "") -> dict:
    """Find or create a user by email and set them as the current identity.
    Call once to link your email to this device's auto-generated identity."""
    user = await post("/api/users/identify", {"email": email, "display_name": display_name})
    set_uid(user["id"])
    return {**user, "message": "Identity set and saved to ~/.proof-forge/identity"}


async def get_profile(user_id: str = "") -> dict:
    """Get the learner profile. Auto-detects identity."""
    uid = await get_uid(user_id)
    return await get(f"/api/users/{uid}/profile")
