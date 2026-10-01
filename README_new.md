# RAG Agent 智能问答系统（前后端分离）

[GitHub - learner0102/Agent_Learning: I want to learn AIAgent(langchain, llm, mcp.etc) technologies, and all filed are used to study(based hello-agents). · GitHub](https://github.com/learner0102/Agent_Learning)

基于 **LangGraph + LangChain** 的 RAG 智能问答 Agent，从最初的 CLI 脚本演进为**前后端分离的完整 Web 应用**：FastAPI 后端（JWT 认证 + MySQL 会话持久化 + SSE 流式输出）+ Vue3 前端（Element Plus + Pinia），支持多用户、多会话、按用户隔离的知识库。模型接入通义千问（Qwen），Embedding 使用本地 Qwen3-Embedding-0.6B，全程本地化部署（CUDA）。

## 功能特性

**对话与 Agent**

- 🤖 LangGraph 多步 Agent 决策循环，**原生 Function Calling** 驱动工具调用
- 📡 **SSE 流式输出**：回答逐字显示，过程可感知
- 🔧 **真实外部工具**：SQLite 只读查询（员工/产品/销售）+ 当前时间；**MCP 协议**可选接入

**RAG 与知识库**

- 🔍 **FAISS 向量检索** + 本地 Embedding（进程内复用，模型只加载一次）
- 📄 **中文友好分块**：Markdown 标题感知 + CJK Token 估算
- 📁 **文件上传**：`.txt` / `.md`，上传后自动索引
- 🔒 **按用户隔离**：每用户独立 FAISS 索引，与公共知识库合并检索

**记忆系统**

- 🧠 **分层记忆**：`working` 短期会话（内存）/ `episodic`·`semantic` 长期记忆（重要度 ≥ 0.7 自动落盘）
- 🔎 **语义召回优先、关键词兜底**，跨会话记住用户说过什么
- ⚙️ **可视化管理**：设置页查看 / 删除 / 清空长期记忆

**上下文工程**

- 🧩 **GSSC**：Gather-Select-Structure-Compress 四阶段组装上下文，按 token 预算截断

**用户与会话**

- 🔐 **JWT 认证**（bcrypt 存密码，7 天有效期）
- 💬 **多会话管理**：列表、新建、删除、重命名、历史消息（落 MySQL）
- 🛡️ **越权防护**：`user_id` 只从 token 解析，请求参数不被信任

## 系统架构

```
┌───────────────────────────────────────────────┐
│  Vue3 + Element Plus 前端                      │
│  登录/注册 · 多会话 · 聊天(SSE) · 知识库 · 设置   │
└───────────────────┬───────────────────────────┘
                    │  /api/*  (Vite proxy → 8000)
┌───────────────────▼───────────────────────────┐
│  FastAPI 后端                                  │
│  JWT 认证 · 会话归属 · 消息落库 · SSE 流式       │
│  文件上传/索引 · 按用户隔离 kb · 记忆管理         │
└────────┬──────────────────────┬───────────────┘
         │                      │
┌────────▼────────┐   ┌─────────▼─────────────────┐
│  MySQL 8.0      │   │  AppContext（单例）        │
│  users          │   │  RAGAgent（LangGraph）      │
│  sessions       │   │  KnowledgeBase × N（共享模型）│
│  messages       │   │  MemoryManager × M         │
│  documents      │   │  ContextBuilder（GSSC）     │
└─────────────────┘   └───────────────────────────┘
```

一次问答：`用户输入 → 记忆层(working + 长期召回) → ContextBuilder(GSSC) → RAGAgent(LangGraph: agent_node → tool_node → 回填) → 工具层[知识库检索按 user_id 路由 / 数据库 / 时间] → 输出`

## 技术栈

| 分类      | 技术                                                                  |
| ------- | ------------------------------------------------------------------- |
| 后端      | Python 3.10+、FastAPI、uvicorn、SQLAlchemy 2.0、Pydantic                |
| Agent   | LangChain、LangGraph（StateGraph、条件边、原生 Function Calling）             |
| RAG     | FAISS、HuggingFace Embeddings（本地 Qwen3-Embedding-0.6B）               |
| 分块      | RecursiveCharacterTextSplitter + 自研 Markdown 标题感知 Token 分块          |
| 工具 / 协议 | LangChain `@tool`、SQLite 只读查询、MCP（FastMCP + langchain-mcp-adapters） |
| 上下文工程   | GSSC（Gather-Select-Structure-Compress）、token 预算管理                   |
| 记忆      | 分层记忆（working / episodic / semantic）、重要度阈值持久化                        |
| 认证      | JWT（python-jose）、bcrypt（passlib）                                    |
| 数据库     | MySQL 8.0（Docker）、PyMySQL、utf8mb4                                   |
| 前端      | Vue3 组合式 API、Element Plus、Pinia、vue-router、axios                    |
| 流式      | SSE（Server-Sent Events）、fetch + ReadableStream                      |
| 模型接入    | 通义千问 Qwen（OpenAI 兼容协议 / DashScope）                                  |
| 评测      | golden set + `eval.py`（Hit@k / Recall@k / LLM-as-judge）             |
| 部署      | Docker（MySQL）、Windows/Linux 本地运行（CUDA）                              |

## 目录结构

```
Agent/
├── server/                      # FastAPI 后端
│   ├── main.py                  # 应用入口，lifespan 构造 AppContext
│   ├── db.py                    # SQLAlchemy engine + SessionLocal + SET NAMES
│   ├── models.py                # ORM：User / SessionModel / Message / Document
│   ├── schemas.py               # Pydantic 请求/响应模型
│   ├── auth.py                  # JWT + bcrypt
│   ├── deps.py                  # get_db / get_current_user
│   └── routers/
│       ├── auth.py              # 注册 / 登录 / me
│       ├── sessions.py          # 会话 CRUD
│       ├── chat.py              # /api/chat + /api/chat/stream（SSE）
│       ├── documents.py         # 上传 / 列表 / 删除
│       └── settings.py          # 统计 / 记忆管理
├── frontend/                    # Vue3 前端
│   ├── src/
│   │   ├── api/index.js         # axios 实例 + 拦截器
│   │   ├── router/index.js      # 路由 + 登录守卫
│   │   ├── stores/{auth,sessions}.js
│   │   ├── views/{Login,Layout,Chat,Documents,Settings}.vue
│   │   ├── App.vue / main.js / styles.css
│   └── vite.config.js           # /api 代理到 8000
├── app_core.py                  # AppContext：模型单例、每用户 kb、会话记忆
├── agent.py                     # RAGAgent：LangGraph 状态机
├── tools.py                     # 工具：知识库检索 + 数据库 + 时间（ContextVar 路由）
├── mcp_server.py                # 本地 MCP Server（stdio）
├── db_utils.py                  # SQLite 只读查询
├── context_builder.py           # GSSC 上下文工程
├── knowledge_base.py            # FAISS 索引管理，支持 add_file 追加
├── chunks.py                    # Markdown 标题感知 + CJK Token 分块
├── memory_manager.py            # 分层记忆
├── config.py                    # 环境变量 + 日志
├── create_demo_db.py            # 生成示例数据库
├── eval.py / golden.json        # RAG 分层评测
├── knowledge_base/              # FAISS 索引（data_test2 公共 / user_<id> 每用户）
├── uploads/                     # 用户上传文件（user_<id>/）
├── memory_store/                # 长期记忆落盘（mem_user_<id>.json）
├── docker-compose.yml           # MySQL 服务
└── .env                         # 环境变量
```

## 快速开始

### 1. 环境准备

Python 3.10+、Node.js 18+、Docker Desktop、CUDA 环境。

### 2. 启动 MySQL

```bash
docker compose up -d
docker ps          # 应看到 rag-mysql 状态 Up
```

### 3. 安装依赖

```bash
pip install fastapi uvicorn "sqlalchemy>=2.0" pymysql cryptography \
            "passlib[bcrypt]" "python-jose[cryptography]" python-multipart \
            langchain langgraph langchain-openai langchain-community \
            langchain-text-splitters faiss-cpu sentence-transformers \
            openai python-dotenv
# 可选：MCP 协议
pip install mcp langchain-mcp-adapters
```

### 4. 配置 `.env`

```ini
# 大模型
Qwen_API_KEY=你的DashScope_API_KEY
DB_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MODEL_NAME=你的模型名
# MySQL
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3307
MYSQL_USER=rag
MYSQL_PASSWORD=rag123
MYSQL_DB=rag_agent
# JWT
JWT_SECRET=用 python -c "import secrets;print(secrets.token_hex(32))" 生成
JWT_ALGORITHM=HS256
JWT_EXPIRE_DAYS=7
```

### 5. 生成示例数据库

```bash
python create_demo_db.py
```

### 6. 启动后端

**必须在项目根目录下**（`app_core.py` 使用了相对路径）：

```bash
uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload --workers 1
```

> ⚠️ `--workers 1` 必须：本地大模型不能多进程各加载一份，否则 CUDA OOM。

### 7. 启动前端

```bash
cd frontend
npm install
npm run dev
```

打开 http://localhost:5173 → 注册 → 登录 → 开始问答。

### 8. 运行分层评测（可选）

```bash
python eval.py
python eval.py --with-answer
```

## 核心设计

- **模型只加载一次（AppContext 单例）**：`AppContext` 在 FastAPI **lifespan** 里构造，而非模块 import 时——`uvicorn --reload` 会重复 import，模块级构造会导致每改一次代码就重载模型 → CUDA OOM。
- **多用户知识库隔离（共享 embedding + 独立 FAISS）**：`KnowledgeBase` 接受外部传入的 `embeddings`；`AppContext` 只建一个 `default_kb` 并取出 `embeddings`，每用户 kb 复用它，避免每实例各加载一份模型。
- **工具按用户路由（ContextVar）**：工具是全局注册的，用 `contextvars.ContextVar` 在每次请求开始时 `set_current_user(user_id)`，检索工具运行时按当前用户取对应 kb——协程安全、零开销。
- **公共库 + 用户库合并检索**：用户 kb 从空开始，检索时同时查公共 kb（top 2）与用户 kb（top 3），合并去重排序取 top 5，公共知识不重复存储。
- **GSSC 上下文工程**：Gather（收集）→ Select（筛选）→ Structure（分区）→ Compress（按 token 预算截断）。
- **分层记忆**：短期在内存、长期按重要度 ≥ 0.7 落盘，语义召回优先、关键词兜底。
- **SSE 流式**：后端拿到完整答案后按块 `yield`（`text/event-stream`），前端用 `fetch` + `ReadableStream` 解析 `event:`/`data:`，配合 `reactive` 对象实现打字机效果。
- **数据库字符集**：MySQL 存中文乱码的根因是客户端字符集未声明——用 `connect_args={"charset":"utf8mb4"}` + `SET NAMES utf8mb4` 事件监听双保险。
