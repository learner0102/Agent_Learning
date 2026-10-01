# server/routers/chat.py
import asyncio
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..deps import get_db, get_current_user
from ..models import User, SessionModel, Message
from ..schemas import ChatIn, ChatOut
from config import logger

router = APIRouter(prefix="/api", tags=["chat"])

def _uid(user: User) -> str:
    """统一的 user_id 格式：user_<db_id>，和 memory_store 文件名一致。"""
    return f"user_{user.id}"

@router.post("/chat", response_model=ChatOut)
async def chat(body: ChatIn,
               user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    # 延迟导入，避免循环依赖
    from ..main import APP_CTX

    # ---------- 1. 会话归属 ----------
    if body.session_id:
        s = db.query(SessionModel).filter_by(id=body.session_id, user_id=user.id).first()
        if not s:
            raise HTTPException(404, "会话不存在或不属于你")
    else:
        # 新建会话，标题取首条消息前 20 字
        title = (body.message.strip()[:20] or "新会话")
        s = SessionModel(id=uuid.uuid4().hex, user_id=user.id, title=title)
        db.add(s); db.commit(); db.refresh(s)

    # ---------- 2. user 消息落库 ----------
    db.add(Message(session_id=s.id, role="user", content=body.message))
    db.commit()

    # ---------- 3. 跑 Agent（同步阻塞，丢线程池）----------
    uid = _uid(user)
    try:
        result = await asyncio.to_thread(
            APP_CTX.answer_once, body.message, uid, s.id
        )
    except Exception as e:
        logger.exception("agent run failed")
        raise HTTPException(500, f"Agent 执行失败: {e}")

    # ---------- 4. assistant 消息落库 ----------
    db.add(Message(
        session_id=s.id, role="assistant",
        content=result["final_answer"],
        steps=result.get("steps", 0),
        tool_calls=len(result.get("tool_results", [])),
    ))
    s.updated_at = datetime.utcnow()
    db.commit()

    # ---------- 5. 可选：写长期记忆 ----------
    if body.save:
        try:
            APP_CTX.save_long_term(body.message, result["final_answer"], uid, s.id)
        except Exception as e:
            logger.warning(f"save_long_term failed: {e}")

    return ChatOut(
        session_id=s.id,
        final_answer=result["final_answer"],
        steps=result.get("steps", 0),
        tool_results=result.get("tool_results", []),
        thought_process=result.get("thought_process", []),
        auto_saved=result.get("auto_saved", False),
    )

import json
from fastapi.responses import StreamingResponse

def _sse(event: str, data: dict) -> str:
    """SSE 格式：event: xxx\ndata: {...}\n\n"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

@router.post("/chat/stream")
async def chat_stream(body: ChatIn,
                      user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    """
    和 /chat 逻辑一致，但：
    - 先落库 user 消息
    - 跑 agent（阻塞，在线程池里）
    - 拿到完整答案后，按块 yield，前端有打字机效果
    """
    from ..main import APP_CTX

    # 1. 会话归属
    if body.session_id:
        s = db.query(SessionModel).filter_by(id=body.session_id, user_id=user.id).first()
        if not s:
            raise HTTPException(404, "会话不存在或不属于你")
    else:
        title = (body.message.strip()[:20] or "新会话")
        s = SessionModel(id=uuid.uuid4().hex, user_id=user.id, title=title)
        db.add(s); db.commit(); db.refresh(s)

    sid = s.id

    # 2. user 消息落库
    db.add(Message(session_id=sid, role="user", content=body.message))
    db.commit()

    uid = _uid(user)

    async def event_gen():
        # 先告诉前端 session_id（新会话时前端要跳 URL）
        yield _sse("session", {"session_id": sid})

        # 3. 跑 agent（阻塞）
        try:
            result = await asyncio.to_thread(APP_CTX.answer_once, body.message, uid, sid)
        except Exception as e:
            logger.exception("agent run failed")
            yield _sse("error", {"message": f"Agent 执行失败: {e}"})
            return

        answer = result["final_answer"]

        # 4. 按块吐 answer
        CHUNK = 3
        for i in range(0, len(answer), CHUNK):
            yield _sse("delta", {"text": answer[i:i+CHUNK]})
            await asyncio.sleep(0.02)

        # 5. 落库 assistant 消息 + 更新会话时间
        try:
            db.add(Message(
                session_id=sid, role="assistant",
                content=answer,
                steps=result.get("steps", 0),
                tool_calls=len(result.get("tool_results", [])),
            ))
            s.updated_at = datetime.utcnow()
            db.commit()
        except Exception as e:
            logger.warning(f"落库 assistant 消息失败: {e}")

        # 6. 可选：写长期记忆
        if body.save:
            try:
                APP_CTX.save_long_term(body.message, answer, uid, sid)
            except Exception as e:
                logger.warning(f"save_long_term failed: {e}")

        # 7. 结束事件，带 meta
        yield _sse("done", {
            "session_id": sid,
            "steps": result.get("steps", 0),
            "tool_calls": len(result.get("tool_results", [])),
            "auto_saved": result.get("auto_saved", False),
        })

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # 禁用 nginx 缓冲
        },
    )