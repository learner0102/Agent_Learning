# server/deps.py
from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session
from jose import JWTError
from .db import SessionLocal
from .models import User
from .auth import decode_token

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(authorization: str = Header(...), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "缺少 Bearer token")
    try:
        uid = decode_token(authorization[7:])
    except (JWTError, Exception):
        raise HTTPException(401, "token 无效或已过期")
    u = db.get(User, uid)
    if not u:
        raise HTTPException(401, "用户不存在")
    return u