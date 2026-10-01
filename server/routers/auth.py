# server/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..deps import get_db, get_current_user
from ..models import User
from ..schemas import RegisterIn, LoginIn, TokenOut, UserOut
from ..auth import hash_password, verify_password, create_token

router = APIRouter(prefix="/api/auth", tags=["auth"])

def _to_out(u: User) -> UserOut:
    return UserOut(id=u.id, username=u.username, nickname=u.nickname or u.username)

@router.post("/register", response_model=TokenOut)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if db.query(User).filter_by(username=body.username).first():
        raise HTTPException(400, "用户名已存在")
    u = User(username=body.username,
             password_hash=hash_password(body.password),
             nickname=body.nickname or body.username)
    db.add(u); db.commit(); db.refresh(u)
    return TokenOut(token=create_token(u.id), user=_to_out(u))

@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.query(User).filter_by(username=body.username).first()
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "用户名或密码错误")
    return TokenOut(token=create_token(u.id), user=_to_out(u))

@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return _to_out(user)