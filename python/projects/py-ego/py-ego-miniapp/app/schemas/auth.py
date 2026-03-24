from pydantic import BaseModel
from app.schemas.user import UserResponse


class LoginRequest(BaseModel):
    code: str


class TokenResponse(BaseModel):
    token: str
    refresh_token: str
    user: UserResponse


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    token: str