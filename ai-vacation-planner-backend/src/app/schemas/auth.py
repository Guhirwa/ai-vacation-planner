from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=2, max_length=20)
    password: str = Field(..., min_length=8)

class UserLogin(BaseModel):
    username: str
    password: str

class UserOut(BaseModel):
    id: int
    email: str
    username: str
    created_at: Optional[datetime] = None

    class Config:
        from_attribute = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

