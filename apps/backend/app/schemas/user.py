from datetime import datetime
from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: str
    display_name: str


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class LearnerProfileOut(BaseModel):
    id: str
    user_id: str
    known_topics: list
    weak_spots: list
    skill_level: str
    updated_at: datetime

    model_config = {"from_attributes": True}
