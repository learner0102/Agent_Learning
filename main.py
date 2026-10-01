
import os

from app_core import AppContext

# 显存分配策略：必须在 import torch（经 knowledge_base 间接导入）之前设置才生效
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import argparse
from datetime import datetime

from config import logger
from knowledge_base import KnowledgeBase
from agent import RAGAgent
from tools import init_tools, init_mcp_tools
from memory_manager import MemoryManager
from context_builder import ContextBuilder

def main():
    parser = argparse.ArgumentParser(description="Agent + RAG 智能问答系统")
    parser.add_argument("--use-mcp", action=argparse.BooleanOptionalAction, default=True,
                        help="通过本地 MCP Server 加载外部工具（数据库/时间）；--no-use-mcp 用全本地")
    parser.add_argument("--data_file", default=r"paper2.txt",
                            help="加载本地数据文件")
    parser.add_argument("--data_dir", default=r"knowledge_base\data_test2",
                                help="加载本地数据文件")
    args = parser.parse_args()

    data_name = args.data_file.split("\\")[-1].split(".")[0]
    

    print("=" * 60)
    print("Agent + RAG 智能问答系统（自动读取长期记忆）")
    print("=" * 60)

    # 一次性初始化（和原来等价）
    ctx = AppContext(args.data_file, args.data_dir, use_mcp=args.use_mcp)

    user_id = "local_user_02"
    session_id = f"ses_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    mem = ctx.get_memory(user_id, session_id)

    print("💡 #save 保存长期记忆；#showsession 查看会话；exit 退出\n")
    print("=" * 60)
    print("Agent 已就绪")
    print("=" * 60)

    while True:
        question = input("\n💬 用户: ").strip()
        if question.lower() in ['exit', 'quit', 'q']:
            print("退出系统。")
            break
        if not question:
            continue

        # #showsession
        if question.startswith("#showsession"):
            print("\n📒 当前会话短期记忆：")
            for item in mem.get_short_term():
                print(f"- {item['content']}")
            continue

        # #save
        is_save = question.startswith("#save")
        real_q = question.removeprefix("#save").strip() if is_save else question
        if is_save and not real_q:
            print("⚠️ #save 后面要跟具体问题")
            continue

        print("\n🤖 Agent 思考中...")
        result = ctx.answer_once(real_q, user_id, session_id)

        print("\n" + "-" * 40)
        print("📝 最终回答:")
        print("-" * 40)
        print(result["final_answer"])
        print("-" * 40)
        print(f"⏱️ 步骤数: {result['steps']}")
        print(f"🛠️ 工具调用次数: {len(result['tool_results'])}")

        if result["thought_process"]:
            print("\n🧠 思考过程:")
            for i, t in enumerate(result["thought_process"], 1):
                print(f"  Step {i}: {t}...")

        if is_save:
            ctx.save_long_term(real_q, result["final_answer"], user_id, session_id)
            print("✅ 已保存到长期记忆！")

        if result["auto_saved"]:
            print(" 检测到个人事实，已自动保存到长期记忆。")


if __name__ == "__main__":
    main()
