from datetime import datetime

from pydantic import BaseModel


class FaceSignupResponse(BaseModel):
    message: str
    name: str
    id: int
    role: str


class FaceLoginResponse(BaseModel):
    message: str
    name: str
    id: int
    role: str
    recognized: bool = True


class RegisteredUserItem(BaseModel):
    id: int
    name: str
    role: str
    created_at: datetime


class UserUpdateResponse(BaseModel):
    message: str
    user: RegisteredUserItem


class UserDeleteResponse(BaseModel):
    message: str


class RegisteredUsersResponse(BaseModel):
    count: int
    users: list[RegisteredUserItem]
