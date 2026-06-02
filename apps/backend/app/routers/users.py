from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.repositories import user_repo
from app.schemas.user import UserCreate, UserOut, LearnerProfileOut

router = APIRouter(tags=["users"])


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(data: UserCreate, db: AsyncSession = Depends(get_db)):
    return await user_repo.create_user(db, data)


class IdentifyRequest(BaseModel):
    email: str
    display_name: str = ""


@router.post("/users/identify", response_model=UserOut)
async def identify_user(data: IdentifyRequest, db: AsyncSession = Depends(get_db)):
    """Find or create a user by email. Idempotent — same email always returns the same profile."""
    return await user_repo.find_or_create(db, data.email, data.display_name)


@router.get("/users/{user_id}/profile", response_model=LearnerProfileOut)
async def get_profile(user_id: str, db: AsyncSession = Depends(get_db)):
    profile = await user_repo.get_profile(db, user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile
