# context_builder.py - GSSC 上下文工程
# Gather-Select-Structure-Compress：把喂给模型的上下文当作可管理资源
from typing import Dict, List, Tuple

from chunks import _approx_token_len
from config import logger


class ContextBuilder:
    """
    GSSC 上下文工程四阶段：
      Gather   - 收集所有可用上下文（长期记忆、会话历史、可选知识库片段）
      Select   - 按可用性/优先级筛选，剔除占位与无效内容
      Structure- 按固定分区模板组织，便于模型识别信息来源
      Compress - 按 token 预算截断/压缩，优先保留最关键信息

    使用：每次问答前调用 build()，返回可直接放进 prompt 的上下文块。
    """

    def __init__(self, token_budget: int = 1200, kb=None):
        self.token_budget = token_budget
        self.kb = kb  # 可选：传入则在 build 时可预检索知识库

    def build(self, memory: str = "", session: str = "", kb_query: str = "") -> str:
        """组装并压缩上下文，返回结构化文本（喂给模型用）。"""
        gathered = self._gather(memory, session, kb_query)
        selected = self._select(gathered)
        sections = self._structure(selected)
        return self._compress(sections)

    # ---------------- Gather ----------------
    def _gather(self, memory: str, session: str, kb_query: str) -> Dict:
        data = {"memory": memory or "", "session": session or ""}
        if kb_query and self.kb is not None:
            try:
                contents, scores = self.kb.retrieve(kb_query, top_k=3)
                data["kb"] = self.kb.format_retrieved_context(contents, scores)
            except Exception as e:
                logger.warning(f"上下文预检索失败: {e}")
                data["kb"] = ""
        return data

    # ---------------- Select ----------------
    def _select(self, data: Dict) -> Dict:
        selected = {}
        for key, value in data.items():
            v = (value or "").strip()
            if v and v != "没有找到相关长期记忆。":
                selected[key] = v
        return selected

    # ---------------- Structure ----------------
    def _structure(self, selected: Dict) -> List[Tuple[str, str]]:
        order = [("kb", "知识库检索", 0), ("memory", "长期记忆", 1), ("session", "会话历史", 2)]
        return [(title, selected[key]) for key, title, _ in order if key in selected]

    # ---------------- Compress ----------------
    def _compress(self, sections: List[Tuple[str, str]]) -> str:
        if not sections:
            return ""

        priority = {"知识库检索": 0, "长期记忆": 1, "会话历史": 2}
        ordered = sorted(sections, key=lambda s: priority.get(s[0], 3))

        budget = self.token_budget
        parts: List[str] = []
        used = 0
        for title, content in ordered:
            tok = _approx_token_len(content)
            if used + tok <= budget:
                parts.append(f"【{title}】\n{content}")
                used += tok
            elif used < budget:
                # 预算不足：截断当前段，保留开头关键信息
                remain_chars = max(30, budget - used)
                truncated = content[:remain_chars].rstrip("。，； ") + "…"
                parts.append(f"【{title}】\n{truncated}")
                used = budget
                break
            else:
                break

        return "\n\n".join(parts)
