# app_core.py
import os
from datetime import datetime
from typing import Dict

from config import logger
from knowledge_base import KnowledgeBase
from agent import RAGAgent
from tools import init_tools, init_mcp_tools, set_current_user
from memory_manager import MemoryManager
from context_builder import ContextBuilder


class AppContext:
    """全局单例：模型只加载一次，避免 CUDA OOM。"""
    def __init__(self, data_file: str, data_dir: str, use_mcp: bool = True):
        # 1. 第一个 kb：加载公共知识 + 初始化 embedding（模型只此一份）
        logger.info("【初始化】加载知识库")
        self.default_kb = KnowledgeBase(chunk_size=500, chunk_overlap=50)
        if os.path.exists(data_dir):
            self.default_kb.load_faiss(data_dir)
        else:
            os.makedirs(data_dir, exist_ok=True)
            self.default_kb.load_and_index(data_file)
            self.default_kb.save_faiss(data_dir)

        # 2. 全局共享的 embeddings（从 default_kb 拿到，之后所有 kb 复用）
        self.embeddings = self.default_kb.embeddings

        # 3. 每用户一个 kb：user_id -> KnowledgeBase
        self.kbs: Dict[str, KnowledgeBase] = {}

        # 4. 工具（把整个 AppContext 传进去，让工具能按 user_id 取 kb）
        logger.info("【初始化】加载工具")
        if use_mcp:
            init_mcp_tools(self)      # ← 传 self，不是 self.default_kb
        else:
            init_tools(self)          # ← 传 self，不是 self.default_kb

        # 5. Agent
        logger.info("【初始化】加载 Agent")
        self.agent = RAGAgent(max_steps=5)

        # 6. 上下文工程
        self.context_builder = ContextBuilder(token_budget=500)

        # 7. 会话管理
        self.sessions: Dict[str, MemoryManager] = {}

    def get_kb(self, user_id: str) -> KnowledgeBase:
        """每个用户一份 kb，懒加载。user_id 为 '__shared__' 时返回默认 kb。"""
        if user_id == "__shared__":
            return self.default_kb
        if user_id not in self.kbs:
            base = os.path.join("knowledge_base", user_id)
            os.makedirs(base, exist_ok=True)
            logger.info(f"[KB] 为用户 {user_id} 创建知识库实例")
            kb = KnowledgeBase(chunk_size=500, chunk_overlap=50,
                               embeddings=self.embeddings)   # ← 复用！
            index_file = os.path.join(base, "index.faiss")
            if os.path.exists(index_file):
                kb.load_faiss(base)
                logger.info(f"[KB] 用户 {user_id} 加载已有索引")
            else:
                logger.info(f"[KB] 用户 {user_id} 暂无索引（等待上传）")
            self.kbs[user_id] = kb
        return self.kbs[user_id]

    def get_memory(self, user_id: str, session_id: str) -> MemoryManager:
        key = f"{user_id}:{session_id}"
        if key not in self.sessions:
            self.sessions[key] = MemoryManager(
                user_id=user_id, embeddings=self.embeddings  # ← 这行
            )
        return self.sessions[key]

    def answer_once(self, question: str, user_id: str, session_id: str) -> dict:

        set_current_user(user_id)

        """单轮问答：和你 main.py 里那段逻辑一一对应。"""
        mem = self.get_memory(user_id, session_id)

        # 1. 用户提问写入短期记忆
        mem.add(content=f"用户：{question}", memory_type="working",
                session_id=session_id, importance=0.5)

        # 2. 检索长期记忆 + 会话上下文
        session_ctx = mem.get_session_context()
        recall_result = mem.search(question, limit=3)

        # 3. GSSC
        context = self.context_builder.build(memory=recall_result, session=session_ctx)

        # 4. Agent 运行
        result = self.agent.run(question, context=context)

        # 5. 回答写入短期记忆
        mem.add(content=f"Agent：{result['final_answer']}", memory_type="working",
                session_id=session_id, importance=0.5)

        # 6. 自动识别个人事实（和你 main.py 完全一致）
        personal_keywords = ["我叫", "我是", "我喜欢", "我的名字", "我住在",
                             "我工作在", "我讨厌", "我不爱", "我姓"]
        auto_saved = False
        if any(kw in question for kw in personal_keywords):
            mem.add(
                content=f"用户提到：{question}，Agent回答：{result['final_answer'][:400]}",
                memory_type="semantic", session_id=session_id,
                importance=0.8, event_type="user_fact",
            )
            auto_saved = True

        return {
            "final_answer": result["final_answer"],
            "steps": result["steps"],
            "tool_results": result["tool_results"],
            "thought_process": result["thought_process"],
            "auto_saved": auto_saved,
        }

    def save_long_term(self, question: str, answer: str, user_id: str, session_id: str):
        mem = self.get_memory(user_id, session_id)
        mem.add(
            content=f"重要问答：{question} → {answer[:400]}",
            memory_type="episodic", session_id=session_id,
            importance=0.85, event_type="qa_interaction",
        )

    def get_session_messages(self, user_id: str, session_id: str):
        return self.get_memory(user_id, session_id).get_short_term()