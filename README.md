# YouTube Agentic RAG System

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-blue?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/TypeScript-5.x-blue?style=flat-square&logo=typescript" alt="TypeScript">
  <img src="https://img.shields.io/badge/FastAPI-0.109+-green?style=flat-square&logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/Next.js-16-black?style=flat-square&logo=next.js" alt="Next.js">
  <img src="https://img.shields.io/badge/LangGraph-Latest-purple?style=flat-square" alt="LangGraph">
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License">
</p>

> 基于 YouTube 视频内容的智能问答系统 | AI-Powered Q&A over YouTube Videos

## 📖 简介

YouTube Agentic RAG 是一个生产级的检索增强生成（RAG）系统，专门用于构建基于 YouTube 视频内容的 AI 问答应用。系统采用 Multi-Agent 架构，支持多个专业 AI 角色，能够智能理解用户问题并进行精准回答。

### 核心能力

- 🎯 **智能问答**: 基于视频字幕的精准问答
- 🔍 **混合检索**: 向量 + 关键词 + 重排序融合
- 🌐 **网络搜索**: 实时补充外部知识
- 💬 **多角色**: 支持 Dan Koe、Naval Ravikant 等角色
- ⚡ **流式响应**: 实时流式输出体验

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              User Interface                              │
│                         (Next.js 16 + React 19)                         │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │ HTTP/WebSocket
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            API Gateway                                    │
│                         (FastAPI + Uvicorn)                              │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐  ┌──────────────┐  │
│  │  /health    │  │  /api/chat   │  │ /api/history│  │/api/feedback │  │
│  └─────────────┘  └──────────────┘  └─────────────┘  └──────────────┘  │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        LangGraph Agent Workflow                          │
│                                                                         │
│  ┌────────────┐    ┌─────────────┐    ┌─────────────┐                  │
│  │route_query │───►│  retrieve   │───►│  generate   │                  │
│  └────────────┘    └─────────────┘    └─────────────┘                  │
│       │                  │                   │                         │
│       ▼                  ▼                   ▼                         │
│  ┌────────────┐    ┌─────────────┐    ┌─────────────┐                  │
│  │chitchat    │    │grade_docs   │    │self_correct │                  │
│  └────────────┘    └─────────────┘    └─────────────┘                  │
│       │                  │                                               │
│       ▼                  ▼                                               │
│  ┌────────────┐    ┌─────────────┐                                       │
│  │web_search │◄───│ insufficient│                                        │
│  └────────────┘    └─────────────┘                                        │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        ▼                         ▼                         ▼
┌───────────────┐       ┌─────────────────┐       ┌─────────────────┐
│Hybrid Search  │       │   Web Search    │       │     LLM        │
│ - Vector      │       │ - FireCrawl     │       │  - DeepSeek    │
│ - BM25        │       │ - Tavily        │       │                 │
│ - RRF         │       │                 │       │                 │
└───────┬───────┘       └─────────────────┘       └─────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      Vector Storage Layer                                 │
│                   (PostgreSQL + PGVector)                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐                 │
│  │  channels   │  │   videos    │  │ subtitle_chunks │                 │
│  └─────────────┘  └─────────────┘  └─────────────────┘                 │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ 技术栈

### 后端技术

| 类别 | 技术 | 版本 |
|------|------|------|
| Web Framework | FastAPI | 0.109+ |
| ASGI Server | Uvicorn | latest |
| AI Agents | LangGraph | latest |
| AI Framework | LangChain | latest |
| Vector DB | PGVector (PostgreSQL) | 16 |
| Embedding | BAAI/bge-m3 | - |
| Reranking | BAEI/bge-reranker-v2-m3 | - |
| LLM | DeepSeek Chat | - |

### 前端技术

| 类别 | 技术 | 版本 |
|------|------|------|
| Framework | Next.js | 16 |
| UI Library | React | 19 |
| Styling | Tailwind CSS | 4 |
| Animation | Framer Motion | latest |
| Components | Radix UI | latest |

### 基础设施

| 类别 | 技术 |
|------|------|
| Container | Docker, Docker Compose |
| Database | PostgreSQL 16 + PGVector |
| Cache | Redis (可选) |

---

## 🚀 快速开始

### 前置要求

- Python 3.12+
- Node.js 18+
- Docker & Docker Compose (可选)

### 1. 克隆项目

```bash
git clone https://github.com/<your-username>/rag-youtube.git
cd rag-youtube
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入以下必需的配置：
# - DEEPSEEK_API_KEY
# - SUPABASE_URL, SUPABASE_KEY (或使用本地 PostgreSQL)
# - 其他可选配置
```

### 3. 本地开发

#### 使用 Docker Compose（推荐）

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

#### 手动启动

```bash
# 后端
pip install -r requirements.txt
uvicorn src.api.server:app --reload --port 8000

# 前端
cd frontend
npm install
npm run dev
```

### 4. 访问应用

- 前端: http://localhost:3000
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs

---

## 📝 环境变量

| 变量名 | 必需 | 说明 |
|--------|------|------|
| `DEEPSEEK_API_KEY` | ✅ | DeepSeek API Key |
| `DATABASE_URL` | ✅ | PostgreSQL 连接字符串 |
| `SUPABASE_URL` | ❓ | Supabase URL（如使用） |
| `SUPABASE_KEY` | ❓ | Supabase Anon Key |
| `EMBEDDING_MODEL` | ❌ | Embedding 模型 (默认: BAAI/bge-m3) |
| `RERANKER_MODEL` | ❓ | Reranker 模型 (默认: BAAI/bge-reranker-v2-m3) |
| `FIRECRAWL_API_KEY` | ❓ | FireCrawl API (网络搜索用) |
| `LOG_LEVEL` | ❌ | 日志级别 (默认: INFO) |

---

## 📂 项目结构

```
rag-youtube/
├── src/                          # 后端源代码
│   ├── api/                      # API 接口层
│   │   └── server.py            # FastAPI 应用入口
│   ├── agent/                    # Agent 核心
│   │   ├── graph.py             # LangGraph 工作流定义
│   │   ├── nodes.py             # Agent 节点实现
│   │   ├── state.py             # 状态管理
│   │   └── llm.py               # LLM 调用封装
│   ├── core/                     # 核心模块
│   │   ├── config.py            # 配置管理
│   │   └── models.py            # 数据模型
│   ├── retrieval/                # 检索引擎
│   │   ├── hybrid_search.py     # 混合搜索实现
│   │   ├── reranker.py          # 重排序
│   │   └── search_service.py    # 搜索服务
│   └── vector_storage/           # 向量存储
│       ├── pgvector_handler.py  # PGVector 操作
│       └── superabase_client.py # Supabase 客户端
├── frontend/                      # Next.js 前端
│   ├── app/                      # App Router
│   │   ├── api/                 # API 代理路由
│   │   ├── page.tsx             # 主页面
│   │   └── layout.tsx           # 布局
│   └── components/              # React 组件
│       ├── chat-interface.tsx  # 聊天界面
│       └── sidebar.tsx         # 侧边栏
├── scripts/                      # 工具脚本
├── tests/                        # 测试文件
├── init.sql                      # 数据库初始化
├── docker-compose.yml           # Docker 配置
├── pyproject.toml               # Python 项目配置
└── README.md                    # 项目文档
```

---

## 🔌 API 接口

### 聊天接口

```bash
POST /api/chat
Content-Type: application/json

{
  "message": "What is the main idea of this video?",
  "session_id": "optional-session-id"
}
```

### 获取历史

```bash
GET /api/history/{session_id}
```

### 反馈接口

```bash
POST /api/feedback
Content-Type: application/json

{
  "message_id": "msg_xxx",
  "rating": "positive|negative",
  "comment": "optional comment"
}
```

### 健康检查

```bash
GET /health
```

---

## 🔧 扩展开发

### 添加新的 Agent 角色

1. 在 `src/agent/nodes.py` 中添加新角色逻辑
2. 在 `src/core/models.py` 中定义角色配置
3. 更新前端角色选择器

### 添加新的检索源

1. 实现 `src/retrieval/` 中的检索接口
2. 在 `hybrid_search.py` 中集成

---

## 📦 部署

### 生产环境部署

推荐使用以下免费/低成本服务：

| 组件 | 推荐平台 |
|------|----------|
| 前端 | Vercel |
| 后端 API | Render / Railway |
| 数据库 | Neon (PostgreSQL) |

详见 [部署指南](./docs/deployment.md)

---

## 🧪 测试

```bash
# 运行单元测试
pytest tests/

# 运行特定测试
pytest tests/test_grader_hallucination.py -v
```

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

## 🙏 致谢

- [LangChain](https://github.com/langchain-ai/langchain) - AI Agent Framework
- [BAAI](https://github.com/FlagOpen/FlagEmbedding) - BGE Embeddings
- [DeepSeek](https://deepseek.com) - LLM Provider

