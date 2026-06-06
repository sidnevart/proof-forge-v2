from pydantic import BaseModel, EmailStr
from datetime import datetime


class SendLinkRequest(BaseModel):
    email: str
    display_name: str = ""


class SendLinkResponse(BaseModel):
    message: str


class VerifyRequest(BaseModel):
    token: str


class VerifyResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    display_name: str


class MeResponse(BaseModel):
    user_id: str
    email: str
    display_name: str


class ApiKeyCreateResponse(BaseModel):
    id: str
    name: str
    raw_key: str
    created_at: datetime


class ApiKeyOut(BaseModel):
    id: str
    name: str
    created_at: datetime
    last_used_at: datetime | None = None
