# server/schemas.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=64)
    nickname: Optional[str] = None

class LoginIn(BaseModel):
    username: str
    password: str

class UserOut(BaseModel):
    id: int
    username: str
    nickname: str

class TokenOut(BaseModel):
    token: str
    user: UserOut

class SessionOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime

class MessageOut(BaseModel):
    role: str
    content: str
    steps: int = 0
    tool_calls: int = 0
    created_at: datetime

class ChatIn(BaseModel):
    message: str = Field(min_length=1)
    session_id: Optional[str] = None   # 不传则新建
    save: bool = False                 # 是否写长期记忆

class ChatOut(BaseModel):
    session_id: str
    final_answer: str
    steps: int
    tool_results: List[str] = []
    thought_process: List[str] = []
    auto_saved: bool = False

class SessionCreateIn(BaseModel):
    title: Optional[str] = "新会话"