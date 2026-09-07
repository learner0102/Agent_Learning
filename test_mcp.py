# test_mcp.py - 独立测试本地 MCP Server 能否正常连接（诊断用）
# 用法：在 E:\\山理工\\LLM_study\\Codes 目录下运行：
#   python study_line/eni/test_mcp.py
#
# 通过测试的两种结果：
#   1. "✅ MCP 连接成功" → 服务端没问题，问题出在 main.py 的调用方式
#   2. 抛异常 → 服务端启动失败，根据报错定位（import 失败 / 环境问题）
import asyncio
import sys
from pathlib import Path

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

ENI = Path(__file__).resolve().parent
SERVER = str(ENI / "mcp_server.py")


async def main():
    print(f"🔌 测试连接 MCP Server: {SERVER}")

    client = MultiServerMCPClient({
        "rag": {
            "transport": "stdio",
            "command": sys.executable,
            "args": [SERVER],
        }
    })

    try:
        async with client.session("rag") as session:
            tools = await load_mcp_tools(session)
            print(f"✅ MCP 连接成功，加载工具: {[t.name for t in tools]}")

            # 调用一个最简单的工具验证往返
            time_tool = next(t for t in tools if t.name == "get_current_time")
            result = await time_tool.ainvoke({})
            print(f"✅ 工具往返测试 get_current_time → {result}")

            # 验证数据库工具（如果 demo.db 已生成）
            db_tool = next(t for t in tools if t.name == "query_database")
            db_result = await db_tool.ainvoke({"sql": "SELECT COUNT(*) AS n FROM employees"})
            print(f"✅ 数据库工具测试 → {db_result[:80]}")
    except Exception as e:
        print(f"❌ MCP 连接失败: {type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
