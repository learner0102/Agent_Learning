# mcp_server.py - 本地 MCP Server（stdio 传输），暴露轻量外部工具
#
# 设计说明：知识库检索（search_knowledge_base）刻意不放在本 Server——
# 它需要加载本地 embedding 模型，若主进程与 MCP 子进程各加载一份会导致 CUDA OOM。
# 因此知识库检索留在主进程内（复用已加载的模型），本 Server 只暴露无重型依赖的外部工具：
#   1. query_database   - SQLite 只读查询（纯标准库）
#   2. get_current_time - 当前时间
# 这样 MCP Server 启动快、不吃显存，Agent 通过 MCP 拿到外部工具，知识库走进程内。
import os
import sys
from datetime import datetime
from pathlib import Path
from config import logger

def _redirect_stderr_to_file():
    """把 stderr 重定向到日志文件：MCP stdio 协议独占 stdout，且避免 stderr 管道阻塞子进程。"""
    try:
        log_path = Path(__file__).resolve().parent / "logs" / "mcp_server_stderr.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(log_path), os.O_WRONLY | os.O_CREAT | os.O_APPEND)
        os.dup2(fd, 2)
    except Exception:
        pass


_redirect_stderr_to_file()


def _log(msg: str):
    logger.info(msg)


_log("starting import ...")

from db_utils import DB_PATH, run_db_query  # noqa: E402
from mcp.server.fastmcp import FastMCP  # noqa: E402

mcp = FastMCP("rag-external-tools")


@mcp.tool()
def query_database(sql: str) -> str:
    """对本地示例数据库执行只读 SQL 查询。当用户询问员工/产品/销售等业务数据、需要统计或计算时使用。
    表结构：employees(id,name,department,city,salary)；products(id,name,category,price,stock)；
    sales(id,product_id,quantity,amount,sale_date)，amount 单位人民币元。输入：完整的 SELECT 语句。"""
    return run_db_query(sql, DB_PATH)


@mcp.tool()
def get_current_time() -> str:
    """获取当前日期和时间。当用户询问当前时间或日期时使用。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


_log("module imported OK, starting mcp.run(stdio) ...")

if __name__ == "__main__":
    try:
        mcp.run(transport="stdio")
    except TypeError:
        # 旧版 mcp 可能不支持 transport 参数，回退默认（stdio）
        _log("transport arg not supported, fallback to mcp.run()")
        mcp.run()
