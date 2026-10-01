# server/routers/settings.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..deps import get_db, get_current_user
from ..models import User, SessionModel, Message, Document

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _uid(user: User) -> str:
    return f"user_{user.id}"


@router.get("/info")
def info(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """当前用户的统计信息。"""
    n_sessions = db.query(SessionModel).filter_by(user_id=user.id).count()
    n_messages = (
        db.query(Message)
          .join(SessionModel, Message.session_id == SessionModel.id)
          .filter(SessionModel.user_id == user.id)
          .count()
    )
    n_documents = db.query(Document).filter_by(user_id=user.id).count()

    # 长期记忆数
    from ..main import APP_CTX
    n_memories = 0
    try:
        mem = APP_CTX.get_memory(_uid(user), "__info__")
        n_memories = len(mem.get_long_all())
    except Exception:
        pass

    return {
        "username": user.username,
        "nickname": user.nickname or user.username,
        "sessions": n_sessions,
        "messages": n_messages,
        "documents": n_documents,
        "long_term_memories": n_memories,
    }


@router.get("/memory")
def list_memory(user: User = Depends(get_current_user)):
    """查看当前用户的长期记忆列表。"""
    from ..main import APP_CTX
    mem = APP_CTX.get_memory(_uid(user), "__settings__")
    items = mem.get_long_all()
    return [
        {
            "idx": i,
            "content": m.get("content", ""),
            "memory_type": m.get("memory_type", ""),
            "importance": m.get("importance", 0),
            "event_type": m.get("event_type"),
            "create_time": m.get("create_time"),
        }
        for i, m in enumerate(items)
    ]


@router.delete("/memory/{idx}")
def delete_memory(idx: int, user: User = Depends(get_current_user)):
    """删除某条长期记忆。"""
    from ..main import APP_CTX
    mem = APP_CTX.get_memory(_uid(user), "__settings__")
    ok = mem.delete_long_term(idx)
    if not ok:
        raise HTTPException(404, f"记忆索引 {idx} 不存在")
    return {"ok": True}


@router.delete("/memory")
def clear_memory(user: User = Depends(get_current_user)):
    """清空当前用户的所有长期记忆。"""
    from ..main import APP_CTX
    mem = APP_CTX.get_memory(_uid(user), "__settings__")
    mem.clear_long_term()
    return {"ok": True}


@router.post("/session/{sid}/clear")
def clear_session(
    sid: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """清空指定会话的短期记忆（working），不动数据库里的消息记录。"""
    s = db.query(SessionModel).filter_by(id=sid, user_id=user.id).first()
    if not s:
        raise HTTPException(404, "会话不存在或不属于你")

    from ..main import APP_CTX
    mem = APP_CTX.get_memory(_uid(user), sid)
    mem.clear_short_term()
    return {"ok": True}