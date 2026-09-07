# RAG Agent 智能问答系统（（目前仍在学习[基于Hello-Agents]））

基于 **LangGraph + LangChain** 的 RAG 智能问答 Agent，集成多步 Agent 决策、知识库检索增强（RAG）、分层记忆、真实外部工具与 **MCP 协议**。模型接入通义千问（Qwen），Embedding 使用本地 Qwen3-Embedding-0.6B，全程本地化部署（CUDA）。

## ✨ 功能特性

- 💬 交互式命令行问答，支持多轮会话
- 🔍 基于知识库的 RAG 检索增强生成，返回相关度分数
- 🤖 LangGraph 多步 Agent 决策循环，**原生 Function Calling** 驱动工具调用
- 🔧 **真实外部工具**：SQLite 数据库只读查询（employees/products/sales 三表）+ 当前时间查询
- 🔌 **MCP 协议接入**（`--use-mcp`）：经本地 MCP Server（stdio）暴露轻量外部工具（SQLite 查询、当前时间），`langchain-mcp-adapters` 转接；知识库检索复用主进程内已加载的模型，避免双份 GPU 模型导致 CUDA OOM
- 🧩 **GSSC 上下文工程**：Gather-Select-Structure-Compress 四阶段组装上下文，按 token 预算管理
- 🧠 **分层记忆系统**：
  - `working` 短期会话记忆（纯内存，重启清空）
  - `episodic / semantic` 长期记忆（重要度 ≥ 0.7 自动持久化到本地 JSON）
  - 检索时**语义召回优先、关键词兜底**，实现跨会话"记住用户说过什么"
- 📄 中文友好的智能分块（Markdown 标题感知 + CJK Token 估算）
- 🛡️ 批量向量化构建 FAISS 索引，单批失败自动跳过，不中断整体流程

## 🏗️ 架构流程

```
用户输入
   │
   ▼
┌─────────────────────────────┐
│ 记忆层  MemoryManager       │
│  ├─ 写入短期记忆 working     │
│  └─ 检索长期记忆（语义召回） │
│      └─ session + memory    │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ 上下文工程  ContextBuilder  │  GSSC
│  Gather ─ Select ─          │
│  Structure ─ Compress       │  (token 预算)
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ Agent 层  RAGAgent          │
│ LangGraph StateGraph        │
│  agent_node:                │
│   ChatOpenAI + bind_tools   │
│      │                      │
│      ├─ 有 tool_calls ─►    │
│      │    tool_node         │
│      │    执行工具           │
│      │    ToolMessage 回填  │
│      │    └──► 回到 agent   │
│      │                      │
│      └─ 生成最终回答 ─► 输出 │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ 工具层                       │
│  ├─ search_knowledge_base   │ 本地（主进程内复用模型）
│  ├─ query_database          │ MCP（外部工具）
│  └─ get_current_time        │ MCP（外部工具）
└─────────────────────────────┘
```

## 📂 目录结构

```
eni/
├── main.py             # 程序入口：初始化 + 交互式问答循环（--use-mcp 可选）
├── agent.py            # RAGAgent：LangGraph 状态机 + 原生 Function Calling
├── tools.py            # 工具：知识库检索(本地) + 数据库/时间(本地 or MCP)
├── mcp_server.py       # 本地 MCP Server（stdio），暴露外部工具（数据库/时间）
├── db_utils.py         # SQLite 只读查询实现（纯标准库，供本地与 MCP 共用）
├── context_builder.py  # GSSC 上下文工程：Gather-Select-Structure-Compress
├── knowledge_base.py   # 知识库：分块 / Embedding / FAISS 索引 / 检索
├── chunks.py           # 自研分块：Markdown 标题感知 + CJK Token 估算
├── memory_manager.py   # 分层记忆：短期/长期、重要度持久化、语义召回
├── create_demo_db.py   # 生成示例业务数据库 demo.db
├── config.py           # 环境变量 + 日志配置
├── paper.txt           # 示例知识库文档
├── demo.db             # 示例业务数据库（运行 create_demo_db.py 生成）
├── golden.json         # RAG 评测 golden set
├── eval.py             # RAG 评测脚本（Hit@k / Recall@k / 回答正确率）
├── memory_store/       # 长期记忆落盘目录（mem_<user_id>.json）
└── logs/               # 运行日志
```

## 🛠️ 技术栈

| 分类 | 技术 |
| --- | --- |
| 语言 / 框架 | Python 3.10+, LangChain, LangGraph |
| Agent | LangGraph StateGraph、条件边、原生 Function Calling（`bind_tools`）、最大步数限流 |
| RAG | FAISS 向量检索、HuggingFace Embeddings（本地 Qwen3-Embedding-0.6B / SentenceTransformers） |
| 分块 | RecursiveCharacterTextSplitter + 自研 Markdown 标题感知 Token 分块、CJK Token 估算 |
| 工具 | LangChain `@tool`、SQLite 只读查询（`db_utils.py`）、MCP（Model Context Protocol / `langchain-mcp-adapters`，用于外部工具） |
| 上下文工程 | GSSC（Gather-Select-Structure-Compress）、token 预算管理 |
| 记忆 | 分层记忆（working / episodic / semantic）、重要度阈值持久化、语义召回 + 关键词兜底 |
| 模型接入 | 通义千问 Qwen（OpenAI 兼容协议 / DashScope），langchain-openai `ChatOpenAI` |
| 评测 | golden set + eval.py（Hit@k / Recall@k / LLM-as-judge 回答正确率） |
| 工程 | 批量向量化 + 单批容错、logging、dotenv 配置分离、CUDA 本地推理 |

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install langchain langgraph langchain-openai langchain-community \
            langchain-text-splitters faiss-cpu sentence-transformers \
            openai python-dotenv
# 使用 MCP 协议时需要额外安装：
pip install mcp langchain-mcp-adapters
```

### 2. 配置环境变量

在 `.env` 中配置：

```ini
Qwen_API_KEY=你的DashScope_API_KEY
DB_URL=你的大模型路径(默认Openai，指定云端，例如百炼或者本地ollama)
MODEL_NAME=你的模型名
```

### 3. 生成示例业务数据库

```bash
python study_line/eni/create_demo_db.py
```

### 4. 运行

```bash
python study_line/eni/main.py            # 本地工具（知识库 + 数据库 + 时间全本地）
python study_line/eni/main.py --use-mcp  # MCP 模式：知识库本地 + 数据库/时间经 MCP Server
```

### 5. 使用命令

| 命令 | 说明 |
| --- | --- |
| `exit` / `quit` | 退出系统 |
| `#showsession` | 查看当前会话短期记忆 |
| `#save <问题>` | 将本轮问答保存为长期记忆（示例：`#save 我叫小明`） |

直接输入问题即触发问答；命中"我叫 / 我是 / 我喜欢"等个人关键词时，自动存入长期记忆。

## 🧠 记忆系统设计

采用**分层记忆**，各司其职：

| 类型 | 存储位置 | 生命周期 | 用途 |
| --- | --- | --- | --- |
| `working`（短期会话） | 内存 | 当前会话，重启清空 | 保存完整对话，用于多轮上下文 |
| `episodic`（情景） | 内存 + 磁盘 | 重要度 ≥ 0.7 落盘 | 重要问答、文档加载事件 |
| `semantic`（语义） | 内存 + 磁盘 | 重要度 ≥ 0.7 落盘 | 用户个人事实、知识点 |

检索策略：**先语义召回**（与知识库共享本地 Embedding 构建 FAISS 索引），**再关键词兜底**（中英文分词 + bigram 匹配），避免"换个说法就失忆"。

## 🧩 上下文工程（GSSC）

喂给模型的上下文经 `ContextBuilder` 统一组装：

- **Gather**：收集长期记忆、会话历史、可选知识库预检索结果
- **Select**：剔除占位/无效内容，按优先级保留
- **Structure**：按【知识库检索】/【长期记忆】/【会话历史】分区组织
- **Compress**：按 token 预算截断，优先保留最关键信息

## 💡 设计要点与权衡

- **为什么用原生 Function Calling 而不是手写正则 ReAct**：工具调用由模型结构化输出 `tool_calls`，框架用 `tool_call_id` 严格匹配回填，解析稳定、天然支持多工具并行。
- **为什么加 MCP**：工具/数据源的访问标准化为统一协议，Agent 消费外部能力的方式与具体实现解耦，是 2025 年后 Agent 工程的事实标准。
- **为什么知识库检索不走 MCP 子进程**：检索依赖本地 embedding 模型，主进程（记忆语义召回）与 MCP 子进程各加载一份会导致 CUDA OOM / 双份显存。因此重工具留在主进程复用已加载的模型，MCP 只负责无重型依赖的外部工具——体现"模型只加载一次"的工程约束。
- **为什么用本地 Embedding**：数据不出本地、无 API 调用成本、可离线；与记忆系统共用同一模型实例，避免重复加载。
- **为什么自研分块**：固定字符切分会切断语义，尤其是中文没有天然空格。自研方案感知 Markdown 标题层次，按 CJK 字符近似 Token 数分块。
- **为什么用 SQLite 做真实工具**：自包含、无需 API key、可演示，且能考察模型生成 SQL 的能力，是"Agent 执行真实动作"的最低成本示例。

## 🗺️ Roadmap

已实现：
- [x] 检索质量评测（golden set + eval.py：Hit@k / Recall@k / 回答正确率）
- [x] 真实外部工具（SQLite 数据库查询、当前时间）
- [x] MCP 协议接入（本地 stdio MCP Server）
- [x] GSSC 上下文工程（token 预算管理）

规划中：
- [ ] 混合检索（向量 + BM25）与 Rerank 精排
- [ ] LLM 驱动的记忆提取 / 合并 / 去重（Mem0 / MemGPT）
- [ ] LangGraph Checkpointer 会话持久化
- [ ] FastAPI 服务化 + 流式输出
- [ ] 可观测性（Langfuse / LangSmith）
- [ ] 单元测试与 CI
