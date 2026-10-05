from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

class LoginRequest(BaseModel):
    email: str
    password: str

class ChatRequest(BaseModel):
    session_id: str
    message: str = Field(min_length=1, max_length=5000)
    mode: str = Field(default="demo", pattern="^(demo|real)$")

class ApprovalDecision(BaseModel):
    comment: str = Field(min_length=1, max_length=1000)
