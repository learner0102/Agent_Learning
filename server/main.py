# server/main.py
import os
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import Base, engine
from . import models  # noqa
from .routers import auth as auth_router
from .routers import sessions as sessions_router
from .routers import chat as chat_router
from .routers import documents as documents_router
from .routers import settings as settings_router
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config import logger

# ---------- 全局模型上下文（启动时构造，只此一份）----------
APP_CTX = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global APP_CTX
    Base.metadata.create_all(bind=engine)
    logger.info("数据库表已就绪")

    # 延迟到 lifespan 里构造，避免 import 时就加载模型（uvicorn --reload 会重复触发）
    from app_core import AppContext
    logger.info("加载模型（首次约 10~30s）...")
    APP_CTX = AppContext(
        data_file=r"paper2.txt",
        data_dir=r"knowledge_base\data_test2",
        use_mcp=False,   # 服务化建议先关 MCP，稳定后再开
    )
    logger.info("模型加载完成")
    yield

app = FastAPI(title="RAG Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(sessions_router.router)
app.include_router(chat_router.router)
app.include_router(documents_router.router)
app.include_router(settings_router.router)

@app.get("/api/health")
def health():
    return {"ok": True, "model_loaded": APP_CTX is not None}