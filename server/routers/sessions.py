# server/routers/sessions.py
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..deps import get_db, get_current_user
from ..models import User, SessionModel, Message
from ..schemas import SessionOut, MessageOut, SessionCreateIn

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

def _own_session(db: Session, sid: str, user: User) -> SessionModel:
    """取会话并校验归属，防止越权访问别人的会话。"""
    s = db.query(SessionModel).filter_by(id=sid, user_id=user.id).first()
    if not s:
        raise HTTPException(404, "会话不存在或不属于你")
    return s

@router.get("", response_model=list[SessionOut])
def list_sessions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (db.query(SessionModel)
              .filter_by(user_id=user.id)
              .order_by(SessionModel.updated_at.desc())
              .all())
    return rows

@router.post("", response_model=SessionOut)
def create_session(body: SessionCreateIn,
                   user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    s = SessionModel(id=uuid.uuid4().hex, user_id=user.id, title=body.title or "新会话")
    db.add(s); db.commit(); db.refresh(s)
    return s

@router.delete("/{sid}")
def delete_session(sid: str,
                   user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    s = _own_session(db, sid, user)
    db.delete(s); db.commit()
    # 同步清掉内存里的 MemoryManager（如果 AppContext 里有缓存）
    from ..main import APP_CTX
    APP_CTX.sessions.pop(f"user_{user.id}:{sid}", None)
    return {"ok": True}

@router.get("/{sid}/messages", response_model=list[MessageOut])
def get_messages(sid: str,
                 user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    _own_session(db, sid, user)
    rows = (db.query(Message)
              .filter_by(session_id=sid)
              .order_by(Message.created_at.asc())
              .all())
    return rows

@router.patch("/{sid}")
def rename_session(sid: str, body: SessionCreateIn,
                   user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    s = _own_session(db, sid, user)
    if body.title: s.title = body.title
    db.commit()
    return {"ok": True}