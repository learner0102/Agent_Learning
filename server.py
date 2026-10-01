# server.py
import os
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import asyncio
import uuid
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app_core import AppContext
from config import logger

# ---------- 全局单例（模块级，只加载一次）----------
DATA_FILE = r"paper2.txt"
DATA_DIR  = r"knowledge_base\data_test2"

logger.info("启动服务，加载模型中……")
APP_CTX = AppContext(DATA_FILE, DATA_DIR, use_mcp=False)  # 服务化建议先关 MCP，稳定后再开
logger.info("模型加载完成")

app = FastAPI(title="RAG Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # 生产收紧
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- 请求模型 ----------
class ChatRequest(BaseModel):
    message: str
    user_id: str = "web_user"
    session_id: Optional[str] = None
    save: bool = False

# ---------- 接口 ----------
@app.post("/api/chat")
async def chat(req: ChatRequest):
    sid = req.session_id or f"ses_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    try:
        result = await asyncio.to_thread(
            APP_CTX.answer_once, req.message, req.user_id, sid
        )
    except Exception as e:
        logger.exception("chat failed")
        raise HTTPException(500, str(e))

    if req.save:
        APP_CTX.save_long_term(req.message, result["final_answer"], req.user_id, sid)

    return {"session_id": sid, **result}

@app.post("/api/save")
async def save(req: ChatRequest):
    sid = req.session_id
    if not sid:
        raise HTTPException(400, "session_id required")
    # 重新跑一次不划算，前端应在 chat 时带 save=True
    raise HTTPException(400, "请用 /api/chat 的 save 参数")

@app.get("/api/session/{user_id}/{session_id}")
async def show_session(user_id: str, session_id: str):
    return {"messages": APP_CTX.get_session_messages(user_id, session_id)}

# ---------- 静态前端 ----------
# 你的目录：eni/frontend/index.html
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")