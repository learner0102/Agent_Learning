# tools.py - 工具定义与加载
#
# 工具来源分两类：
#   1. 本地工具：search_knowledge_base —— 复用主进程已加载的 embedding 模型（不额外占显存）
#   2. MCP 工具：query_database / get_current_time —— 经本地 MCP Server 暴露的轻量外部工具
#
# 架构决策：知识库检索放在主进程而不是 MCP 子进程，因为检索依赖本地 embedding 模型，
# 若两进程各加载一份会 CUDA OOM / 双份显存。重工具留主进程，MCP 负责外部能力。
import asyncio
import threading
from datetime import datetime
from pathlib import Path
from typing import List

from langchain_core.tools import StructuredTool, tool

from knowledge_base import KnowledgeBase
from config import logger
from db_utils import DB_PATH, DB_SCHEMA_HINT, run_db_query


# ---------------- 本地工具工厂 ----------------
def create_search_tool(kb: KnowledgeBase):
    """知识库检索工具（闭包绑定 KnowledgeBase，复用主进程已加载的模型）"""
    @tool
    def search_knowledge_base(query: str) -> str:
        """
        从知识库中检索相关信息。当用户需要基于已有知识库（技术论文、行业报告等）回答问题、查找特定主题内容时使用。
        输入：简洁明确的检索查询。
        """
        try:
            contents, scores = kb.retrieve(query, top_k=3)
            if not contents:
                return "知识库中未找到相关信息"
            return kb.format_retrieved_context(contents, scores)
        except Exception as e:
            logger.error(f"检索失败: {e}")
            return f"检索过程出错: {str(e)}"
    return search_knowledge_base


def create_database_tool(db_path: Path = DB_PATH):
    """SQLite 数据库查询工具（本地版本，MCP 模式下走 MCP）"""
    @tool
    def query_database(sql: str) -> str:
        """
        对本地示例数据库执行只读 SQL 查询。当用户询问员工/产品/销售等业务数据、需要统计或计算时使用。
        {DB_SCHEMA_HINT}
        输入：完整的 SELECT 语句，如 SELECT * FROM employees LIMIT 5。
        """
        return run_db_query(sql, db_path)
    return query_database


def create_time_tool():
    """当前时间工具（本地版本，MCP 模式下走 MCP）"""
    @tool
    def get_current_time() -> str:
        """
        获取当前日期和时间。当用户询问当前时间或日期时使用。
        """
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return get_current_time


# ---------------- MCP 客户端桥接 ----------------
_tools: List = []
_mcp_client = None
_loop: asyncio.AbstractEventLoop | None = None


def _get_loop() -> asyncio.AbstractEventLoop:
    """返回常驻后台线程的事件循环，用于驱动 async 的 MCP 客户端。"""
    global _loop
    if _loop is None:
        _loop = asyncio.new_event_loop()
        threading.Thread(target=_loop.run_forever, daemon=True, name="mcp-event-loop").start()
    return _loop


def _make_sync(mcp_tool) -> StructuredTool:
    """把 async-only 的 MCP 工具桥接为可同步 invoke 的 LangChain 工具。"""
    loop = _get_loop()

    async def _acall(args: dict):
        raw = await mcp_tool.ainvoke(args)
        # MCP 返回 content block 列表，归一化成普通字符串
        if isinstance(raw, list):
            parts = []
            for b in raw:
                if isinstance(b, dict) and b.get("type") == "text":
                    parts.append(b.get("text", ""))
                else:
                    parts.append(str(b))
            return "\n".join(parts) if parts else str(raw)
        return str(raw)

    def _run(**kwargs):
        try:
            return asyncio.run_coroutine_threadsafe(_acall(kwargs), loop).result(timeout=60)
        except asyncio.TimeoutError:
            raise TimeoutError(
                "MCP 工具调用超时(>60s)，请查看 logs/mcp_server_stderr.log 定位"
            ) from None

    return StructuredTool(
        name=mcp_tool.name,
        description=getattr(mcp_tool, "description", None) or mcp_tool.name,
        args_schema=getattr(mcp_tool, "args_schema", None),
        func=_run,
    )


def _load_mcp_tools() -> List:
    """连接本地 MCP Server，取回工具并桥接为可同步调用。失败返回空列表。"""
    global _mcp_client
    import sys
    from langchain_mcp_adapters.client import MultiServerMCPClient

    server_path = str(Path(__file__).resolve().parent / "mcp_server.py")
    loop = _get_loop()

    logger.info("正在连接本地 MCP Server（最长等待 30s）...")

    async def _load():
        global _mcp_client
        _mcp_client = MultiServerMCPClient({
            "external": {
                "transport": "stdio",
                "command": sys.executable,
                "args": [server_path],
            }
        })
        # langchain-mcp-adapters 0.1.0+ 不支持 __aenter__；get_tools() 内部建立并保持连接
        return await _mcp_client.get_tools()

    try:
        tools_map = asyncio.run_coroutine_threadsafe(_load(), loop).result(timeout=30)
        if isinstance(tools_map, dict):
            mcp_tools = [t for v in tools_map.values() for t in v]
        else:
            mcp_tools = list(tools_map)
        return [_make_sync(t) for t in mcp_tools]
    except Exception as e:
        logger.warning(f"MCP Server 连接失败，外部工具回退本地实现: {e}")
        return []


# ---------------- 初始化入口 ----------------
def init_tools(knowledge_base: KnowledgeBase):
    """全本地工具：知识库检索 + 数据库 + 时间（eval.py 等不依赖 MCP 的场景使用）"""
    global _tools
    _tools = [
        create_search_tool(knowledge_base),
        create_database_tool(),
        create_time_tool(),
    ]
    logger.info(f"本地工具初始化完成: {[t.name for t in _tools]}")


def init_mcp_tools(knowledge_base: KnowledgeBase):
    """混合模式：知识库检索走本地（复用主进程模型），数据库/时间走 MCP。

    理由：知识库检索依赖本地 embedding 模型，若主进程与 MCP 子进程各加载一份会导致
    CUDA OOM / 双份显存。因此重工具留在主进程，MCP 只负责轻量外部工具。
    MCP 连不上时自动回退全本地，保证程序可用。
    """
    global _tools
    local_tools = [create_search_tool(knowledge_base)]
    mcp_tools = _load_mcp_tools()
    if mcp_tools:
        _tools = local_tools + mcp_tools
    else:
        _tools = local_tools + [create_database_tool(), create_time_tool()]
    logger.info(f"工具初始化完成: {[t.name for t in _tools]}")


def get_tools():
    """获取当前 Agent 可用的工具列表"""
    return _tools
