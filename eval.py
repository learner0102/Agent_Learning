# eval.py - RAG 检索质量评测（分层）
"""
评测脚本：验证 RAG 检索质量与端到端回答正确率，按【常规题 / 难例题 / 库外拒答】分层报告。

用法（和 main.py 一样，在 E:\\山理工\\LLM_study\\Codes 目录下运行）：
    python study_line/eni/eval.py                 # 仅检索命中率（快，不调 LLM）
    python study_line/eni/eval.py --with-answer   # 额外跑 Agent + LLM 判定回答正确率（慢）
    python study_line/eni/eval.py --limit 5       # 只评测前 5 条，快速验证
    python study_line/eni/eval.py --top-k 5       # 调整检索返回条数

指标说明：
    Hit@k       = 至少命中 1 个期望关键词的用例占比（检索是否找对文档）
    Recall@k    = 期望关键词的平均召回比例（检索覆盖是否完整）
    回答正确率   = LLM-as-judge 判定 Agent 回答与参考答案一致的比例
    库外拒答率   = 对知识库外问题，模型正确说"不知道"而非编造的比例

用例字段：type（retrieval/negative）、difficulty（easy/hard）、question、expected_keywords、reference_answer
"""
import argparse
import json
import os
from typing import Dict, List, Tuple
from config import logger, API_KEY, BASE_URL, MODEL_NAME
from knowledge_base import KnowledgeBase
from langchain_openai import ChatOpenAI

PAPER_PATH = r"study_line\eni\paper2.txt"


def load_golden(path: str) -> List[Dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ================== 检索命中率评测（仅 retrieval 类） ==================
def eval_retrieval(kb: KnowledgeBase, cases: List[Dict], top_k: int = 3) -> Dict:
    ret_cases = [c for c in cases if c.get("type", "retrieval") == "retrieval"]
    print("\n" + "=" * 70)
    print(f"RAG 检索质量评测  top_k={top_k}  检索类用例={len(ret_cases)}")
    print("=" * 70)

    groups: Dict[str, List[Dict]] = {}
    for c in ret_cases:
        groups.setdefault(c.get("difficulty", "easy"), []).append(c)

    total_hit = total_recall = total_n = 0
    miss_cases: List[Dict] = []

    for diff in ["easy", "hard"]:
        group = groups.get(diff, [])
        if not group:
            continue
        hit_cnt = 0
        recall_sum = 0.0
        print(f"\n----- [{diff}] {len(group)} 条 -----")
        for i, case in enumerate(group, 1):
            q = case["question"]
            expected = [kw.lower() for kw in case["expected_keywords"]]
            contents, _, _ = kb.retrieve_with_meta(q, top_k=top_k)
            joined = "\n".join(contents).lower()

            hit_kws = [kw for kw in expected if kw in joined]
            hit = len(hit_kws) > 0
            recall = len(hit_kws) / len(expected) if expected else 0.0

            hit_cnt += int(hit)
            recall_sum += recall
            total_hit += int(hit)
            total_recall += recall
            total_n += 1

            mark = "✅" if hit else "❌"
            print(f"[{i:>2}/{len(group)}] {mark} {q}")
            print(f"      命中: {hit_kws if hit_kws else '无'}  召回率: {recall:.0%}")
            if not hit:
                print(f"      期望: {case['expected_keywords']}")
                miss_cases.append(case)

        print(f"  >>> [{diff}] Hit@{top_k}={hit_cnt}/{len(group)}={hit_cnt/len(group):.1%}  "
              f"Recall@{top_k}={recall_sum/len(group):.1%}")

    print("\n" + "=" * 70)
    if total_n:
        print(f"检索类整体: Hit@{top_k}={total_hit}/{total_n}={total_hit/total_n:.1%}  "
              f"Recall@{top_k}={total_recall/total_n:.1%}")
    print("=" * 70)

    if miss_cases:
        print(f"\n⚠️ 未命中的 {len(miss_cases)} 个用例（据此改进分块/检索）：")
        for c in miss_cases:
            print(f"  - {c['id']}: {c['question']}")

    return {
        "hit_rate": total_hit / total_n if total_n else 0.0,
        "recall": total_recall / total_n if total_n else 0.0,
    }


# ================== 回答正确率评测（LLM-as-judge） ==================
JUDGE_PROMPT = """你是严格的 AI 评测员。判断下面的"模型回答"是否达到了"参考答案"的期望。
允许措辞不同，但关键事实不能缺失或冲突；对于参考答案要求"说明无法回答"的情形，只有模型明确表示不知道/知识库中无此信息才算达标，若编造具体内容则判为错误。
只输出一行，格式：数字 空格 一句话理由。数字 1 表示达标，0 表示不达标。

问题：{question}
参考答案：{reference}
模型回答：{answer}"""


def create_judge() -> ChatOpenAI:
    return ChatOpenAI(
        api_key=API_KEY,
        base_url=BASE_URL,
        model=MODEL_NAME,
        temperature=0.0,  # 判定需要确定性
        max_tokens=200,
        timeout=60.0,
    )


def judge_one(judge: ChatOpenAI, question: str, reference: str, answer: str) -> Tuple[int, str]:
    prompt = JUDGE_PROMPT.format(question=question, reference=reference, answer=answer)
    try:
        resp = judge.invoke(prompt)
        text = (resp.content or "").strip()
        score = 1 if text.startswith("1") else 0
        reason = text[2:].strip() if len(text) > 2 else ""
        return score, reason
    except Exception as e:
        logger.error(f"判定失败: {e}")
        return 0, f"判定异常: {e}"


def _bucket_of(case: Dict) -> str:
    if case.get("type", "retrieval") == "negative":
        return "库外拒答"
    return "常规题" if case.get("difficulty", "easy") == "easy" else "难例题"


def eval_answer(agent, cases: List[Dict], judge: ChatOpenAI) -> Dict:
    print("\n" + "=" * 70)
    print("端到端回答正确率（LLM-as-judge，分层）")
    print("=" * 70)

    buckets: Dict[str, List[int]] = {}
    total_c = total_n = 0
    for i, case in enumerate(cases, 1):
        key = _bucket_of(case)
        print(f"\n[{i}/{len(cases)}][{key}] {case['question']}")
        result = agent.run(case["question"])
        answer = result["final_answer"]
        score, reason = judge_one(judge, case["question"], case["reference_answer"], answer)
        print(f"    判定: {score}  {reason}")
        print(f"    回答前80字: {answer[:80]}...")
        b = buckets.setdefault(key, [0, 0])
        b[0] += score
        b[1] += 1
        total_c += score
        total_n += 1

    print("\n" + "=" * 70)
    for key in ["常规题", "难例题", "库外拒答"]:
        if key in buckets:
            c, n = buckets[key]
            print(f"{key}: {c}/{n} = {c/n:.1%}")
    overall = total_c / total_n if total_n else 0.0
    print(f"整体回答正确率: {total_c}/{total_n} = {overall:.1%}")
    print("=" * 70)
    return {"answer_accuracy": overall}


def main():
    parser = argparse.ArgumentParser(description="RAG 检索质量评测")
    parser.add_argument("--golden", default=r"study_line\eni\golden.json", help="评测集路径")
    parser.add_argument("--paper", default=PAPER_PATH, help="知识库文档路径")
    parser.add_argument("--data_dir", default=r"study_line\eni\knowledge_base\data_test2",
                        help="FAISS 索引缓存目录（与 main.py 共用，避免重复向量化）")
    parser.add_argument("--top-k", type=int, default=3, help="检索返回条数")
    parser.add_argument("--limit", type=int, default=0, help="只评测前 N 条（0=全部）")
    parser.add_argument("--with-answer", action=argparse.BooleanOptionalAction, default=False,
                        help="额外运行 Agent 评测回答正确率（较慢，需调用 LLM）")
    args = parser.parse_args()

    cases = load_golden(args.golden)
    if args.limit > 0:
        cases = cases[:args.limit]

    logger.info(f"加载评测集: {len(cases)} 条用例")

    # 初始化知识库（复用 main.py 的 FAISS 缓存，避免重复向量化与 GPU 开销）
    print("=" * 70)
    print("开始评测：加载知识库 ...")
    print("=" * 70, flush=True)
    kb = KnowledgeBase(chunk_size=500, chunk_overlap=50)
    if os.path.exists(args.data_dir):
        kb.load_faiss(args.data_dir)
    else:
        os.makedirs(args.data_dir, exist_ok=True)
        kb.load_and_index(args.paper)
        kb.save_faiss(args.data_dir)

    # 1) 检索命中率
    ret_metrics = eval_retrieval(kb, cases, top_k=args.top_k)

    # 2) 端到端回答正确率
    if args.with_answer:
        from tools import init_tools
        from agent import RAGAgent

        init_tools(kb)
        agent = RAGAgent(max_steps=5)
        judge = create_judge()
        ans_metrics = eval_answer(agent, cases, judge)
        print(f"\n📊 汇总: Hit@{args.top_k}={ret_metrics['hit_rate']:.1%} | "
              f"Recall@{args.top_k}={ret_metrics['recall']:.1%} | "
              f"回答正确率={ans_metrics['answer_accuracy']:.1%}")
    else:
        print(f"\n📊 汇总: Hit@{args.top_k}={ret_metrics['hit_rate']:.1%} | "
              f"Recall@{args.top_k}={ret_metrics['recall']:.1%}")
        print("💡 想看回答正确率，加 --with-answer 参数（会调用模型，需要 API）")


if __name__ == "__main__":
    main()
