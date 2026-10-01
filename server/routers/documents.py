# server/routers/documents.py
import os
import uuid
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from ..deps import get_db, get_current_user
from ..models import User, Document
from config import logger

router = APIRouter(prefix="/api/documents", tags=["documents"])

UPLOAD_ROOT = "uploads"
ALLOWED_EXTS = {".txt", ".md"}


def _uid(user: User) -> str:
    return f"user_{user.id}"


def _user_upload_dir(user: User) -> str:
    d = os.path.join(UPLOAD_ROOT, _uid(user))
    os.makedirs(d, exist_ok=True)
    return d


@router.post("/upload")
async def upload(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 1. 校验扩展名
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(400, f"只支持 {ALLOWED_EXTS} 格式")

    # 2. 存文件（用 uuid 前缀，防重名/路径穿越）
    save_dir = _user_upload_dir(user)
    safe_name = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(save_dir, safe_name)
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    size = os.path.getsize(save_path)

    # 3. 落库
    doc = Document(
        user_id=user.id,
        filename=file.filename,           # 原始文件名（给用户看）
        filepath=save_path,               # 服务器上的路径
        size=size,
        status="pending",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # 4. 索引到用户 kb
    from ..main import APP_CTX
    uid = _uid(user)
    try:
        kb = APP_CTX.get_kb(uid)
        n_chunks = kb.add_file(save_path)
        kb.save_faiss(os.path.join("knowledge_base", uid))   # 持久化
        doc.status = "indexed"
        db.commit()
        logger.info(f"[Upload] {file.filename} → {n_chunks} 块，已索引")
    except Exception as e:
        logger.exception("索引失败")
        doc.status = "failed"
        db.commit()
        raise HTTPException(500, f"索引失败: {e}")

    return {
        "id": doc.id,
        "filename": doc.filename,
        "size": doc.size,
        "status": doc.status,
    }


@router.get("")
def list_documents(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (db.query(Document)
              .filter_by(user_id=user.id)
              .order_by(Document.created_at.desc())
              .all())
    return [
        {
            "id": d.id,
            "filename": d.filename,
            "size": d.size,
            "status": d.status,
            "created_at": d.created_at.isoformat(),
        }
        for d in rows
    ]


@router.delete("/{doc_id}")
def delete_document(
    doc_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter_by(id=doc_id, user_id=user.id).first()
    if not doc:
        raise HTTPException(404, "文档不存在或不属于你")

    # 1. 删物理文件
    try:
        if os.path.exists(doc.filepath):
            os.remove(doc.filepath)
    except Exception as e:
        logger.warning(f"删除文件失败: {e}")

    # 2. 从数据库删除
    db.delete(doc)
    db.commit()

    # 3. 重建该用户索引（简单粗暴但正确）
    from ..main import APP_CTX
    uid = _uid(user)
    try:
        _rebuild_user_index(APP_CTX, uid, db, user)
    except Exception as e:
        logger.warning(f"重建索引失败: {e}")

    return {"ok": True}


def _rebuild_user_index(app_ctx, uid: str, db: Session, user: User):
    """全量重建该用户索引：清空 + 重新索引所有 indexed 状态的文件。"""
    from knowledge_base import KnowledgeBase
    import os as _os

    base_dir = _os.path.join("knowledge_base", uid)
    index_file = _os.path.join(base_dir, "index.faiss")

    # 清空磁盘索引
    if _os.path.exists(index_file):
        for f in _os.listdir(base_dir):
            p = _os.path.join(base_dir, f)
            if _os.path.isfile(p):
                _os.remove(p)

    # 新建空 kb
    kb = KnowledgeBase(chunk_size=500, chunk_overlap=50, embeddings=app_ctx.embeddings)
    app_ctx.kbs[uid] = kb

    # 重新索引所有该用户的文件
    docs = db.query(Document).filter_by(user_id=user.id, status="indexed").all()
    for d in docs:
        if _os.path.exists(d.filepath):
            try:
                kb.add_file(d.filepath)
            except Exception as e:
                logger.warning(f"重建索引跳过 {d.filename}: {e}")

    if kb.vectorstore is not None:
        kb.save_faiss(base_dir)
        logger.info(f"[KB] 用户 {uid} 索引重建完成，{len(docs)} 个文件")