# db_utils.py - SQLite 只读查询工具实现
#
# 供 tools.py（本地工具）和 mcp_server.py（MCP 服务）共用。
# 刻意不导入 knowledge_base / langchain / torch：保证首次数据库查询响应迅速，
# 不会因为触发重型依赖的 import 而卡顿。
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent / "demo.db"

DB_SCHEMA_HINT = (
    "表结构：employees(id, name, department, city, salary) 员工表；"
    "products(id, name, category, price, stock) 产品表；"
    "sales(id, product_id, quantity, amount, sale_date) 销售表，amount 单位人民币元。"
)


def run_db_query(sql: str, db_path: Path = DB_PATH) -> str:
    """SQLite 只读查询实现（仅标准库，无重型依赖）。"""
    if not sql.strip().lower().startswith("select"):
        return "仅支持 SELECT 只读查询。"
    if not Path(db_path).exists():
        return f"数据库不存在: {Path(db_path)}，请先运行 create_demo_db.py 生成。"
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("PRAGMA query_only = ON")  # 连接级只读保护
            cur = conn.cursor()
            cur.execute(sql)
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchall()[:50]
            if not rows:
                return "查询无结果。"
            header = " | ".join(cols)
            sep = "-" * min(len(header), 60)
            lines = [header, sep] + [" | ".join(str(x) for x in r) for r in rows]
            return "\n".join(lines)
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"SQL 执行失败: {e}")
        return f"SQL 执行出错: {str(e)}"
