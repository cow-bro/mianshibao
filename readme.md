# 面试宝 (Mianshibao) - 阶段 1 项目基建

本仓库采用“可运行优先 + 架构可扩展”的策略，已经将你引用的目标架构与当前可运行架构完成融合。

## 1. 架构对比与取舍

保留项（当前架构中表现更好）:

- `docker-compose.yml` 一键启动链路已可直接落地，保留为阶段 1 主入口。
- 后端 `ApiResponse(code, message, data)` 与全局异常处理已实现，作为统一 API 契约保留。
- 前端 `Axios` 刷新令牌拦截器已可用，保留并通过 `lib/api.ts` 统一导出。
- `pyproject.toml + Ruff + pre-commit` 与 `ESLint + Prettier + Husky` 工程规范链路保留。

吸收项（来自你引用架构的高价值补强）:

- 后端路由总入口命名统一为 `app/api/v1/api.py`（保留兼容层）。
- 新增 `core/dependencies.py`，为后续鉴权与 DB 依赖注入预留。
- 新增 `providers/llm` 抽象分层与 `llm_factory.py`，避免 LLM 调用耦合业务层。
- 新增 `prompts/`、`utils/`、`scripts/`、`alembic/versions/`，增强可维护性与演进空间。
- 新增 `docs/api.md`、`docs/database.md`，让架构与实现同步文档化。
- 前端补齐 `store/`、`lib/types.ts`、`lib/api.ts`，统一状态与请求层接口。

## 2. 融合后目录结构

```text
.
├── docker-compose.yml                       # 本地/开发环境总编排入口: 一条命令启动 PG/Redis/MinIO/Backend/Frontend
├── docs/                                    # 项目级设计文档层: 约束接口与数据设计, 降低跨角色沟通成本
│   ├── api.md                               # API 设计说明: 路由分组、入参/出参约定、错误码规范
│   └── database.md                          # 数据库设计说明: 核心表、索引策略、pgvector 使用约定
├── backend/                                 # 后端工程根目录: FastAPI 应用与数据/服务层实现
│   ├── Dockerfile                           # 后端镜像构建脚本: 安装依赖并暴露 8000 端口运行 Uvicorn
│   ├── pyproject.toml                       # Python 项目与依赖清单: 运行依赖 + Ruff 规则 + 开发依赖
│   ├── .pre-commit-config.yaml              # Git 提交前质量门禁: 自动 Ruff 检查与格式化
│   ├── .env.example                         # 后端环境变量模板: 数据库/缓存/存储/JWT 等配置样例
│   ├── alembic.ini                          # Alembic 全局配置: 数据库迁移脚本位置与连接配置
│   ├── alembic/                             # 数据库迁移目录: 管理 schema 演进历史
│   │   └── versions/                        # 迁移版本文件目录: 每次变更对应一份可回滚脚本
│   ├── scripts/                             # 离线任务层: 与在线 API 解耦的批处理脚本
│   │   ├── ingest_knowledge.py              # 知识入库脚本: 预留批量向量化与写入向量库流程
│   │   └── init_templates.py                # 初始化脚本: 预留基础模板与种子数据注入
│   └── app/                                 # 应用主代码目录: 按 DDD 分层组织业务实现
│       ├── main.py                          # FastAPI 入口: 创建应用、注册异常处理、挂载 v1 路由
│       ├── api/v1/                          # API 接口层(v1): 对外 HTTP 边界与路由聚合
│       │   ├── api.py                       # v1 路由对外入口: 统一导出 api_router 给 main.py 使用
│       │   ├── router.py                    # v1 路由注册中心: 聚合 health/auth 等子路由
│       │   └── endpoints/                   # 端点实现目录: 每个领域一个 endpoint 文件
│       ├── core/                            # 核心基础设施层: 配置、安全、响应、异常、依赖注入
│       │   ├── config.py                    # 配置管理: 通过 Pydantic Settings 读取并校验环境变量
│       │   ├── security.py                  # 安全能力: JWT 访问令牌/刷新令牌生成与解析
│       │   ├── response.py                  # 统一响应构建: 输出 ApiResponse(code,message,data)
│       │   ├── exceptions.py                # 全局异常处理: 业务异常/HTTP异常/校验异常统一收敛
│       │   └── dependencies.py              # FastAPI 依赖注入: DB Session/当前用户上下文占位
│       ├── models/                          # 领域实体(ORM)层: SQLAlchemy 模型定义与表结构映射
│       ├── schemas/                         # 数据契约(DTO)层: 请求/响应 Pydantic 模型定义
│       ├── services/                        # 业务编排层: 纯业务规则与流程组合, 不直接处理 HTTP
│       ├── providers/                       # 外部能力适配层: AI/对象存储/缓存/向量检索封装
│       │   ├── llm/                         # LLM 抽象子层: 模型适配器接口与具体实现
│       │   │   ├── base.py                  # LLM 抽象基类: 统一 chat() 协议, 便于多模型替换
│       │   │   ├── qwen_provider.py         # 通义千问适配实现: 预留生产模型接入点
│       │   │   └── fallback_provider.py     # 兜底实现: 上游不可用时保证链路可降级
│       │   ├── llm_factory.py               # LLM 工厂: 按业务场景选择最合适的 Provider
│       │   ├── vector_store.py              # 向量存储访问: pgvector 查询/写入与健康检查封装
│       │   ├── storage.py                   # 对象存储访问: MinIO 上传/下载/桶管理封装
│       │   └── cache.py                     # 缓存访问: Redis 连接与缓存读写基础能力
│       ├── prompts/                         # Prompt 资源层: 与代码解耦的提示词模板目录
│       └── utils/                           # 通用工具层: 文件解析、通用异常、跨模块复用函数
└── frontend/                                # 前端工程根目录: Next.js App Router 应用
    ├── Dockerfile                           # 前端镜像构建脚本: 依赖安装、构建产物与生产启动
    ├── package.json                         # Node 项目清单: 运行依赖、脚本、Lint/Format/Husky 配置
    ├── app/                                 # App Router 路由层: 页面、布局、路由分段入口
    ├── components/                          # 组件层: UI 组件与业务组件复用中心
    ├── lib/                                 # 前端基础库: 请求、类型、工具函数统一出口
    │   ├── http.ts                          # Axios 实例层: 请求/响应拦截器与 JWT 自动刷新逻辑
    │   ├── api.ts                           # API 访问入口: 对外统一导出请求客户端, 屏蔽底层细节
    │   ├── types.ts                         # 类型定义层: 前后端交互 DTO 与通用类型别名
    │   └── utils.ts                         # 通用函数层: 样式合并/格式化等可复用工具
    ├── store/                               # 全局状态层: Zustand Store 聚合
    │   ├── useAuthStore.ts                  # 认证状态仓库: access/refresh token 与登录态管理
    │   └── useInterviewStore.ts             # 面试会话状态仓库: 连接状态/消息流上下文管理
    └── public/                              # 静态资源层: 图片、图标、字体等构建时直出资源
```

## 3. 技术栈

- 后端: FastAPI + SQLAlchemy + Pydantic Settings + Ruff + pre-commit
- 前端: Next.js 14 (App Router) + Tailwind CSS + Shadcn UI + Axios
- 基础设施: PostgreSQL(pgvector) + Redis + MinIO + Docker Compose

## 4. 快速启动 (推荐)

### 4.1 前置条件

- Docker Desktop (含 Docker Compose v2)

### 4.2 一键启动

在仓库根目录执行:

```bash
docker compose up --build
```

### 4.3 访问地址

- 前端: `http://localhost:3000`
- 后端 OpenAPI: `http://localhost:8000/docs`
- 健康检查: `http://localhost:8000/api/v1/health`
- MinIO Console: `http://localhost:9001`
	- 用户名: `minioadmin`
	- 密码: `minioadmin`

## 5. 环境变量说明

后端默认读取 `backend/.env.example`，Compose 中已自动挂载。

关键变量:

- `DATABASE_URL=postgresql+psycopg_async://postgres:postgres@postgres:5432/mianshibao`
- `REDIS_URL=redis://redis:6379/0`
- `MINIO_ENDPOINT=minio:9000`
- `MINIO_ACCESS_KEY=minioadmin`
- `MINIO_SECRET_KEY=minioadmin`
- `JWT_SECRET_KEY=change-me`

前端通过 `NEXT_PUBLIC_API_BASE_URL` 连接后端，Compose 默认值为:

- `http://localhost:8000/api/v1`

## 6. 已实现的工程规范

### 6.1 后端

- DDD 目录分层已建立并落地
- 全局统一响应结构: `ApiResponse(code, message, data)`
- 全局异常处理: 业务异常、HTTP 异常、参数校验异常、未知异常
- 依赖注入骨架: `core/dependencies.py`
- LLM Provider 分层与工厂: `providers/llm/*` + `providers/llm_factory.py`
- Prompt 工程化目录: `app/prompts/`
- 代码规范: Ruff + pre-commit

### 6.2 前端

- Next.js 14+ App Router 项目结构
- Tailwind CSS + Shadcn UI 基础配置
- ESLint + Prettier + Husky + lint-staged
- Axios 请求拦截器 + 401 自动刷新 JWT 逻辑
- 请求入口统一: `lib/api.ts`
- 状态管理骨架: `store/useAuthStore.ts`、`store/useInterviewStore.ts`

## 7. 本地开发命令

### 7.1 后端

```bash
cd backend
pip install -e .[dev]
pre-commit install
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 7.2 前端

```bash
cd frontend
npm install
npm run prepare
npm run dev
```

## 8. API 示例

### 8.1 统一成功响应

```json
{
	"code": 0,
	"message": "success",
	"data": {
		"status": "ok"
	}
}
```

### 8.2 刷新令牌接口

- 路径: `POST /api/v1/auth/refresh`
- 请求体:

```json
{
	"refresh_token": "your_refresh_token"
}
```

## 9. 阶段 1 交付说明

已交付可直接 `docker compose up` 启动的前后端代码仓结构，并完成“当前可运行架构 + 参考目标架构”的融合。

## 10. 阶段 2 交付说明（数据建模与核心资产初始化）

已完成以下后端能力:

- SQLAlchemy 2.0 异步数据库会话改造（`AsyncSession` + `create_async_engine`）
- 核心 7 张表建模:
    - `user`
    - `resume`
    - `resume_template`
    - `knowledge_point`
    - `interview_session`
    - `interview_message`
    - `wrong_question`
- 统一时间戳字段基类: 所有核心表包含 `id`, `created_at`, `updated_at`
- pgvector 工程化配置:
    - ORM 向量字段: `Vector(1536)`
    - Alembic 中执行 `CREATE EXTENSION IF NOT EXISTS vector;`
    - `knowledge_point.embedding` HNSW 索引
- JWT + RBAC:
    - 登录签发 Access/Refresh Token
    - 刷新 Token
    - `get_current_active_user` 依赖
    - `require_roles(...)` 角色依赖
- 数据摄入脚手架:
    - `backend/scripts/sample_ingest.py`
    - 展示 CSV/JSON 读取、Embedding 调用、异步批量写入 `knowledge_point`

## 11. 阶段 2 使用指南（Docker 容器模式）

### 11.1 更新后端镜像（包含依赖变更）

当 `backend/pyproject.toml` 或后端代码有变更时，先重建镜像:

```bash
docker compose build backend
```

### 11.2 启动依赖服务并执行迁移

```bash
docker compose up -d postgres redis minio
docker compose run --rm backend alembic upgrade head
```

如果 backend 已经在运行，也可以改用:

```bash
docker compose exec backend alembic upgrade head
```

### 11.3 认证接口

- 登录: `POST /api/v1/auth/login`
- 刷新: `POST /api/v1/auth/refresh`

### 11.4 摄入脚手架示例（容器内执行）

```bash
docker compose run --rm backend python -m scripts.sample_ingest
```

### 11.5 阶段 2 测试步骤（容器）

1. 启动后端与前端:

```bash
docker compose up -d backend frontend
```

2. 健康检查:

```bash
curl http://localhost:8000/api/v1/health
```

3. 登录接口测试:

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"demo","password":"demo"}'
```

4. 刷新令牌接口测试:

```bash
curl -X POST http://localhost:8000/api/v1/auth/refresh \
    -H "Content-Type: application/json" \
    -d '{"refresh_token":"<your_refresh_token>"}'
```

5. 查看后端日志确认迁移与接口调用正常:

```bash
docker compose logs -f backend
```

## 12. 阶段 3 交付说明（大模型统一适配层）

已完成以下能力:

- `BaseLLMProvider` 抽象基类，定义 `chat()` 与 `chat_stream()`
- `QwenProvider` 接入 DashScope 调用协议（支持本地无 Key mock 回退）
- `FallbackProvider` 提供规则/随机降级回复
- `LLMService` 工厂模式按场景动态路由 Provider
- 配置化场景映射（`RESUME_PARSING`, `INTERVIEW`, `RAG`, `DEFAULT`）
- `tenacity` 指数退避重试（3 次）
- `circuitbreaker` 熔断保护（阈值 5，恢复 30 秒）

核心代码位置:

- `backend/app/providers/llm/base.py`
- `backend/app/providers/llm/qwen_provider.py`
- `backend/app/providers/llm/fallback_provider.py`
- `backend/app/providers/llm_factory.py`
- `backend/app/core/config.py`

## 13. 阶段 3 Docker 更新与测试步骤

### 13.1 更新容器镜像

```bash
docker compose build backend
```

### 13.2 启动/重启后端服务

```bash
docker compose up -d backend
```

### 13.3 检查服务日志

```bash
docker compose logs -f backend
```

### 13.4 在容器内快速验证 LLM Factory

```bash
docker compose run --rm backend python -c "from app.providers.llm_factory import LLMService; s=LLMService(); print('INTERVIEW=>', s.chat('INTERVIEW', '请做一个自我介绍问题')); print('RAG=>', s.chat('RAG', '解释什么是向量检索')); print('UNKNOWN=>', s.chat('UNKNOWN', 'fallback check'))"
```

### 13.5 可选：配置 DashScope Key（生产建议）

在 `backend/.env.example` 或运行环境中设置:

```bash
DASHSCOPE_API_KEY=your_real_key
```

## 14. 阶段 4 交付说明（双引擎简历解析与优化）

已完成以下能力:

- `ResumeService` 业务编排：上传、解析、评分、优化、下载
- 多格式解析:
    - `pdfplumber` 处理 PDF
    - `python-docx` 处理 Word
    - `PaddleOCR` 处理图片/扫描件
- 双引擎结构化提取:
    - 主引擎：`ResumeStructured` + `PydanticOutputParser` + Few-Shot Prompt
    - 兜底引擎：正则提取 `email`、`phone`
- 简历评分与优化:
    - 四维打分（完整性、经历匹配度、技能相关性、排版规范性）
    - `optimize_resume()` 进行 STAR 法则润色
- 接口交付:
    - `POST /api/v1/resumes/upload`
    - `POST /api/v1/resumes/{resume_id}/parse`
    - `POST /api/v1/resumes/{resume_id}/score`
    - `POST /api/v1/resumes/{resume_id}/optimize`
    - `GET /api/v1/resumes/{resume_id}/download-optimized`

核心代码位置:

- `backend/app/services/resume_service.py`
- `backend/app/api/v1/endpoints/resume.py`
- `backend/app/utils/file_parser.py`
- `backend/app/schemas/resume.py`
- `backend/app/providers/storage.py`

## 15. 阶段 4 Docker 更新与测试步骤

### 15.1 更新后端镜像

```bash
docker compose build backend
```

### 15.2 启动服务

```bash
docker compose up -d postgres redis minio backend
```

### 15.3 登录获取 Access Token

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"demo","password":"demo123"}'
```

### 15.4 上传简历到 MinIO

```bash
curl -X POST http://localhost:8000/api/v1/resumes/upload \
    -H "Authorization: Bearer <access_token>" \
    -F "file=@./sample_resume.pdf"
```

### 15.5 解析简历（双引擎）

```bash
curl -X POST http://localhost:8000/api/v1/resumes/<resume_id>/parse \
    -H "Authorization: Bearer <access_token>"
```

### 15.6 简历评分

```bash
curl -X POST http://localhost:8000/api/v1/resumes/<resume_id>/score \
    -H "Authorization: Bearer <access_token>"
```

### 15.7 STAR 优化

```bash
curl -X POST http://localhost:8000/api/v1/resumes/<resume_id>/optimize \
    -H "Authorization: Bearer <access_token>"
```

### 15.8 下载优化后简历

```bash
curl -L http://localhost:8000/api/v1/resumes/<resume_id>/download-optimized \
    -H "Authorization: Bearer <access_token>" \
    -o optimized_resume.txt
```

## 16. 阶段 5 交付说明（结构化 RAG 知识引擎）

已完成以下能力:

- **知识写入 (Indexing)**:
    - `KnowledgeService.ingest_cards()` 批量写入知识卡片
    - 使用 DashScope `text-embedding-v2` 生成 1536 维向量
    - 向量存入 `knowledge_point.embedding` (pgvector HNSW 索引)
    - 全文检索向量存入 `knowledge_point.search_vector` (tsvector GIN 索引)
    - 支持 JSON 和 Markdown 两种知识卡片格式

- **双路召回与重排序 (Retrieval)**:
    - Path A (向量): pgvector 余弦相似度搜索 Top K
    - Path B (关键词): PostgreSQL tsvector 全文检索 Top K
    - 合并去重后通过模拟 bge-reranker-large 重排序（0.7 向量 + 0.2 关键词 + title/tag bonus）
    - 返回 Top 3 最相关知识点

- **RAG 问答链 (Chain)**:
    - System Prompt: "你是专业的校招面试官助手。请仅基于以下提供的参考资料回答用户的问题。如果资料中没有答案，请直接告知用户无法回答，不要编造。"
    - 检索 → 构建上下文 → LLM 生成 → 返回答案 + 参考来源
    - LLM 场景配置: `RAG` (qwen-plus, temperature=0.3)

- **接口交付**:
    - `POST /api/v1/knowledge/ingest` — 批量导入知识卡片
    - `POST /api/v1/knowledge/search` — 双路混合检索
    - `POST /api/v1/knowledge/ask` — RAG 问答
    - 全部受 JWT 鉴权保护

核心代码位置:

- `backend/app/services/knowledge_service.py` — 知识写入、双路召回、重排序、RAG 问答
- `backend/app/providers/embedding.py` — DashScope text-embedding-v2 封装
- `backend/app/api/v1/endpoints/knowledge.py` — API 端点
- `backend/app/schemas/knowledge.py` — 请求/响应数据结构
- `backend/app/models/knowledge_point.py` — ORM 模型（含 search_vector）
- `backend/app/prompts/rag_qa.txt` — RAG 系统提示词
- `backend/scripts/ingest_knowledge.py` — 离线知识导入脚本
- `backend/data/sample_knowledge.json` — 5 条样例知识卡片

## 17. 阶段 5 Docker 更新与测试步骤

### 17.1 更新后端镜像

```bash
docker compose build backend
```

### 17.2 启动/重启服务

```bash
docker compose up -d postgres redis minio backend
```

### 17.3 执行数据库迁移（新增 search_vector 列 + GIN 索引）

```bash
docker compose exec backend alembic upgrade head
```

### 17.4 导入样例知识数据

```bash
docker compose exec backend python -m scripts.ingest_knowledge data/sample_knowledge.json
```

### 17.5 登录获取 Access Token

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"demo","password":"demo123"}'
```

### 17.6 知识导入（API 方式）

```bash
curl -X POST http://localhost:8000/api/v1/knowledge/ingest \
    -H "Authorization: Bearer <access_token>" \
    -H "Content-Type: application/json" \
    -d '{
      "cards": [
        {
          "title": "什么是 RESTful API？",
          "content": "REST 是一种软件架构风格...",
          "category": "计算机网络",
          "difficulty": "EASY",
          "tags": ["REST", "API", "HTTP"]
        }
      ]
    }'
```

### 17.7 知识检索（双路混合搜索）

```bash
curl -X POST http://localhost:8000/api/v1/knowledge/search \
    -H "Authorization: Bearer <access_token>" \
    -H "Content-Type: application/json" \
    -d '{"query": "TCP 三次握手", "top_k": 3}'
```

### 17.8 RAG 知识问答

```bash
curl -X POST http://localhost:8000/api/v1/knowledge/ask \
    -H "Authorization: Bearer <access_token>" \
    -H "Content-Type: application/json" \
    -d '{"question": "请解释 TCP 三次握手的过程"}'
```

## 18. 阶段 5.1 交付说明（RAG 知识引擎三项质量升级）

在阶段 5 基础上完成三项核心优化：

### 18.1 中文分词升级 (jieba)

- **方案**：应用层 `jieba` 分词，无需修改 PostgreSQL 镜像或安装扩展
- 写入时：`jieba.lcut()` 对 `title + content + tags` 分词 → 空格连接 → `to_tsvector('simple', segmented_text)`
- 查询时：`jieba.lcut()` 对 query 分词 → `plainto_tsquery('simple', segmented_query)`
- 已有数据通过 `reindex_knowledge_fts` 脚本一键重建索引
- 代码位置：`backend/app/utils/text_splitter.py` → `segment_chinese()`

### 18.2 真实 Reranker (DashScope gte-rerank)

- **方案**：调用 DashScope `gte-rerank` cross-encoder API 对候选集精排
- API 不可用时自动降级为加权公式 fallback（0.7×向量 + 0.2×关键词 + title/tag bonus）
- 零配置：有 `DASHSCOPE_API_KEY` 即自动启用
- 代码位置：`backend/app/providers/reranker.py`

### 18.3 文档上传与自动分块

- **接口**：`POST /api/v1/knowledge/upload`（multipart/form-data）
- 支持格式：`.pdf`、`.txt`、`.md`、`.markdown`（最大 20 MB）
- Markdown 按 `#`/`##`/`###` 标题自动切分章节，过大章节递归分块
- PDF/TXT 使用 `RecursiveTextSplitter`（chunk_size=500, overlap=100，中文分隔符优先）
- 每个分块自动打上 `source:<filename>` 标签
- 代码位置：`backend/app/utils/text_splitter.py`、`backend/app/services/knowledge_service.py` → `ingest_document()`

### 18.4 新增/变更文件清单

| 文件 | 状态 | 说明 |
|------|------|------|
| `backend/app/utils/text_splitter.py` | 新增 | jieba 分词、文本提取、RecursiveTextSplitter |
| `backend/app/providers/reranker.py` | 新增 | DashScope gte-rerank 封装 |
| `backend/scripts/reindex_knowledge_fts.py` | 新增 | jieba 分词索引重建脚本 |
| `backend/app/services/knowledge_service.py` | 修改 | 集成 jieba FTS、reranker、文档上传 |
| `backend/app/api/v1/endpoints/knowledge.py` | 修改 | 新增 `/upload` 端点 |
| `backend/app/schemas/knowledge.py` | 修改 | 新增 `UploadResponse` |
| `backend/pyproject.toml` | 修改 | 新增 `jieba>=0.42.1` 依赖 |

## 19. 阶段 5.1 测试指南与验收标准

### 19.1 环境准备

```bash
# 1. 重建后端镜像（包含 jieba 依赖）
docker compose build backend

# 2. 启动服务
docker compose up -d postgres redis minio backend

# 3. 执行数据库迁移（如未执行过）
docker compose exec backend alembic upgrade head

# 4. 导入样例知识数据（如首次部署）
docker compose exec backend python -m scripts.ingest_knowledge data/sample_knowledge.json

# 5. 用 jieba 重建已有记录的 FTS 索引
docker compose exec backend python -m scripts.reindex_knowledge_fts
```

预期：reindex 脚本输出 `Re-indexed N knowledge points with jieba segmentation.`

### 19.2 获取 Access Token

后续所有测试请求均需 JWT 鉴权：

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"demo","password":"demo123"}' | jq -r '.data.access_token')
```

### 19.3 测试一：中文分词精准检索

**目标**：验证 jieba 分词后，中文关键词能精准命中知识卡片。

```bash
curl -s -X POST http://localhost:8000/api/v1/knowledge/search \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"query": "TCP三次握手", "top_k": 3}' | jq '.data.results[] | {id, title, rerank_score}'
```

**验收标准**：
- ✅ 返回 `code: 0`
- ✅ 结果中包含 "TCP 三次握手" 相关卡片，且排名第一
- ✅ 第一名 `rerank_score` 显著高于其余结果（>0.5 vs <0.3）

**对比测试**（中文短语拆词能力）：

```bash
curl -s -X POST http://localhost:8000/api/v1/knowledge/search \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"query": "进程线程区别", "top_k": 3}' | jq '.data.results[] | {id, title, rerank_score}'
```

**验收标准**：
- ✅ "进程和线程的区别" 相关卡片出现在结果中
- ✅ jieba 能将 "进程线程区别" 拆分为 "进程"、"线程"、"区别" 独立匹配

### 19.4 测试二：Reranker 精排

**目标**：验证 gte-rerank 或 fallback 排序工作正常。

```bash
curl -s -X POST http://localhost:8000/api/v1/knowledge/search \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"query": "哈希表的底层实现原理", "top_k": 5}' | jq '.data.results[] | {id, title, rerank_score}'
```

**验收标准**：
- ✅ 所有结果包含 `rerank_score` 字段
- ✅ 结果按 `rerank_score` 降序排列
- ✅ 语义最相关的卡片排名最高
- ✅ 若配置了 `DASHSCOPE_API_KEY`，rerank_score 来自 gte-rerank API（分数范围 0~1）；若未配置，降级为加权公式（仍有合理排序）

**验证 reranker 降级**（查看后端日志）：

```bash
docker compose logs backend --tail 20 | grep -i rerank
```

### 19.5 测试三：Markdown 文档上传

**目标**：验证 Markdown 文件上传后自动按标题分块、向量化、入库。

```bash
# 创建测试文档
cat > /tmp/test_knowledge.md << 'EOF'
# 什么是死锁

死锁是指两个或多个进程在执行过程中，因争夺资源而造成的互相等待的现象。

## 死锁的四个必要条件

1. 互斥条件：资源不能被共享
2. 请求与保持条件：进程因请求资源而阻塞时，对已获得的资源保持不放
3. 不可剥夺条件：进程已获得的资源，在未使用完之前，不能被强制剥夺
4. 循环等待条件：若干进程之间形成头尾相接的循环等待资源关系

## 死锁的预防

打破四个必要条件中的任意一个即可预防死锁。常见策略包括：
- 资源有序分配法
- 银行家算法
- 超时机制
EOF

# 上传文档
curl -s -X POST http://localhost:8000/api/v1/knowledge/upload \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@/tmp/test_knowledge.md" \
    -F "subject=Computer Science" \
    -F "category=操作系统" \
    -F "difficulty=MEDIUM" | jq '.'
```

**验收标准**：
- ✅ 返回 `code: 0`
- ✅ `data.ingested_count >= 3`（按 `#` / `##` 至少切分为 3 个章节）
- ✅ `data.source_file` 为 `test_knowledge.md`
- ✅ `data.ids` 为非空整数数组

**验证分块已可检索**：

```bash
curl -s -X POST http://localhost:8000/api/v1/knowledge/search \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"query": "死锁必要条件", "top_k": 3}' | jq '.data.results[] | {id, title, rerank_score}'
```

**验收标准**：
- ✅ 上传文档中的 "死锁的四个必要条件" 章节出现在搜索结果中
- ✅ 标题源自 Markdown 标题（如 "死锁的四个必要条件"）

### 19.6 测试四：TXT 文档上传

```bash
cat > /tmp/test_plain.txt << 'EOF'
快速排序（Quick Sort）是一种高效的排序算法，采用分治策略。
基本思想是选取一个基准元素，将数组分为较小和较大两部分，然后递归地对两部分分别排序。
平均时间复杂度为 O(n log n)，最坏情况下为 O(n²)。
空间复杂度为 O(log n)，是不稳定排序算法。
EOF

curl -s -X POST http://localhost:8000/api/v1/knowledge/upload \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@/tmp/test_plain.txt" \
    -F "subject=Computer Science" \
    -F "category=算法" | jq '.'
```

**验收标准**：
- ✅ 返回 `code: 0`
- ✅ `data.ingested_count >= 1`

### 19.7 测试五：上传校验（边界条件）

**不支持的文件类型**：

```bash
curl -s -X POST http://localhost:8000/api/v1/knowledge/upload \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@./docker-compose.yml" | jq '.'
```

**验收标准**：
- ✅ 返回错误，`code` 非 0
- ✅ `message` 包含 "unsupported file type"

**无鉴权请求**：

```bash
curl -s -X POST http://localhost:8000/api/v1/knowledge/upload \
    -F "file=@/tmp/test_plain.txt" | jq '.'
```

**验收标准**：
- ✅ 返回 401 或包含认证错误信息

### 19.8 测试六：RAG 问答覆盖上传文档

**目标**：验证上传的文档内容能被 RAG 问答链使用。

```bash
curl -s -X POST http://localhost:8000/api/v1/knowledge/ask \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"question": "死锁的四个必要条件分别是什么？"}' | jq '{answer: .data.answer, ref_count: (.data.references | length)}'
```

**验收标准**：
- ✅ `answer` 中提及互斥条件、请求与保持、不可剥夺、循环等待
- ✅ `references` 中包含来自上传文档的知识卡片
- ✅ `ref_count >= 1`

### 19.9 测试七：按来源删除上传文档分块

**目标**：验证 `source:<filename>` 标签可用于批量管理。

```bash
docker compose exec -T postgres psql -U postgres -d mianshibao -c \
    "SELECT id, title, tags FROM knowledge_point WHERE tags @> ARRAY['source:test_knowledge.md'] ORDER BY id;"
```

**验收标准**：
- ✅ 返回上传文档产生的所有分块记录
- ✅ 每条记录的 `tags` 列包含 `source:test_knowledge.md`

### 19.10 验收汇总

| # | 测试项 | 关键验收点 | 状态 |
|---|--------|-----------|------|
| 1 | jieba 中文分词检索 | "TCP三次握手" 精准命中对应卡片 | ✅ |
| 2 | 中文短语拆词 | "进程线程区别" 能拆词匹配 | ✅ |
| 3 | Reranker 精排 | rerank_score 降序排列且语义相关性合理 | ✅ |
| 4 | Reranker 降级 | gte-rerank API 正常工作，无降级日志 | ✅ |
| 5 | Markdown 上传分块 | 按标题切分 3 块，标题来自 MD 标题 | ✅ |
| 6 | 上传分块可检索 | "死锁必要条件" 命中上传内容（rank 1） | ✅ |
| 7 | TXT 上传 | 纯文本文件正常分块入库（1 chunk） | ✅ |
| 8 | 上传类型校验 | .yml 返回 400 + "unsupported file type" | ✅ |
| 9 | 上传鉴权保护 | 无 Token 请求返回 401 | ✅ |
| 10 | RAG 问答覆盖上传内容 | 问答引用上传文档，四个条件全部命中 | ✅ |
| 11 | 来源标签追踪 | `source:test_knowledge.md` 查到 3 条 | ✅ |
| 12 | FTS 重建脚本 | `reindex_knowledge_fts` 正常执行 | ✅ |

**全部 12/12 项通过，阶段 5.1 验收通过。** ✅

## 20. 阶段 6 交付说明（状态机驱动模拟面试）

本阶段已完成「模拟面试核心引擎」的后端落地，重点能力如下：

- 状态机面试流程：WELCOME → RESUME_DIG → TECH_QA → CANDIDATE_QUESTION → END
- WebSocket 流式交互：支持 token、message、state_change、report_ready、ping
- 面试会话与报告持久化：新增 interview_report 表，扩展 session/message 字段
- 人工介入预留接口：路由已提供，当前返回 501（符合预期）
- Docker 测试链路：新增 backend-test 容器服务，支持容器内迁移与 pytest

核心实现文件：

- `backend/app/services/interview_graph.py`
- `backend/app/services/interview_service.py`
- `backend/app/api/v1/endpoints/interview.py`
- `backend/app/api/v1/endpoints/interview_ws.py`
- `backend/app/schemas/interview.py`
- `backend/app/models/interview_session.py`
- `backend/app/models/interview_message.py`
- `backend/app/models/interview_report.py`
- `backend/alembic/versions/20260312_01_stage6_interview_engine.py`

## 21. 阶段 6 Docker 测试结论

已在 Docker 容器内完成如下验证：

1. 构建镜像并启动依赖服务成功
2. 执行迁移成功（包含阶段 6 新增表与字段）
3. 阶段 6 单测通过：3 passed
4. 后端健康检查通过：`/api/v1/health`
5. 面试相关 HTTP 路由已暴露：
    - `/api/v1/interview/sessions`
    - `/api/v1/interview/sessions/{session_id}/report`
    - `/api/v1/interview/{session_id}/human-intervention/*`

说明：WebSocket 路由不会出现在 OpenAPI 文档中，属于 FastAPI 正常行为。

## 22. 阶段 6 常见排障（已修复）

### 22.1 `create_demo_user` 报 `AmbiguousForeignKeysError`

原因：`interview_session` 新增 `human_operator_id` 后，与 `user` 之间存在两条外键路径，ORM 关系映射歧义。

修复：

- `InterviewSession.user` 显式绑定 `foreign_keys=[user_id]`
- 新增 `InterviewSession.human_operator` 并绑定 `foreign_keys=[human_operator_id]`
- `User.interview_sessions` 显式指定 `foreign_keys="InterviewSession.user_id"`

### 22.2 WebSocket 无法连接（URL 参数重复）

错误示例（不要使用）：

- `ws://localhost:8000/api/v1/interview/ws?session_id=2&session_id=<session_id>&user_id=1&user_id=<user_id>`

正确示例（只保留一组参数）：

- `ws://localhost:8000/api/v1/interview/ws?session_id=2&user_id=1`

### 22.3 PowerShell 下 `curl` 多行命令失败

建议优先使用单行命令，或改用 Postman / Apifox 进行接口与 WebSocket 调试。

## 23. 阶段 6 测试指南入口

完整测试步骤与验收清单见：

- `阶段六测试指南.md`

## 24. 阶段 7 交付说明（前端全页面开发）

本阶段完成前端所有功能页面的实现，覆盖简历分析、知识学习、模拟面试三大核心模块。

### 24.1 技术栈补充

在阶段 1 基础上新增：

| 依赖 | 版本 | 用途 |
|------|------|------|
| `recharts` | ^2.x | 简历评分 / 面试报告雷达图 |
| `react-markdown` | ^9.x | 面试对话 / 报告的 Markdown 渲染 |
| `react-use-websocket` | ^4.x | 面试对话 WebSocket 连接管理 |
| `@types/prop-types` | ^15.x | TypeScript 类型补全 |

### 24.2 设计系统

- **配色方案**：黑白灰米白（米白背景 `hsl(40 20% 98%)`，近黑主色 `hsl(0 0% 9%)`）
- **间距规范**：8pt 网格
- **Card 规范**：`rounded-xl border border-border/60 bg-card shadow-sm hover:shadow-md`
- **Button 变体**：`default`、`outline`、`ghost`

### 24.3 新增/修改文件清单

#### Shadcn UI 组件层 (`components/ui/`)

| 文件 | 状态 | 说明 |
|------|------|------|
| `button.tsx` | 修改 | 新增 `ghost` variant |
| `input.tsx` | 新增 | 文本输入组件 |
| `card.tsx` | 新增 | 卡片容器组件 |
| `badge.tsx` | 新增 | 标签组件（default/secondary/destructive/outline） |
| `progress.tsx` | 新增 | 进度条组件 |
| `slider.tsx` | 新增 | 滑块组件（支持 number 或 number[]） |
| `skeleton.tsx` | 新增 | 骨架屏加载占位组件 |
| `textarea.tsx` | 新增 | 多行文本输入组件 |
| `label.tsx` | 新增 | 表单标签组件 |
| `separator.tsx` | 新增 | 分隔线组件 |
| `select.tsx` | 新增 | 下拉选择组件 |
| `collapsible.tsx` | 新增 | 可折叠面板组件 |
| `toast.tsx` | 新增 | Toast 通知组件（Provider + useToast hook） |

#### 基础设施层

| 文件 | 状态 | 说明 |
|------|------|------|
| `app/globals.css` | 修改 | 黑白灰米白设计令牌 + Toast 动画关键帧 |
| `tailwind.config.ts` | 修改 | 新增 accent/destructive/card 色彩令牌 + borderRadius |
| `store/useAuthStore.ts` | 修改 | 新增 login()/logout()/hydrate() + JWT 解码 userId/username |
| `store/useInterviewStore.ts` | 修改 | 新增 ChatMessage 接口、消息列表、流式内容、阶段管理 |
| `hooks/useRequireAuth.ts` | 新增 | 路由守卫 Hook，未登录自动跳转 /login |
| `app/providers.tsx` | 新增 | 客户端 Provider 包装器（ToastProvider） |
| `app/layout.tsx` | 修改 | 包装 Providers 组件 |

#### 页面层

| 路由 | 文件 | 说明 |
|------|------|------|
| `/` | `app/page.tsx` | 入口重定向（有 token → /dashboard，无 → /login） |
| `/login` | `app/login/page.tsx` | 登录页 + 注册预留（toast 提示即将上线） |
| `/dashboard` | `app/dashboard/layout.tsx` | 顶部导航栏（品牌 + 用户名 + 登出） |
| `/dashboard` | `app/dashboard/page.tsx` | 主页三卡片入口（简历分析/知识学习/模拟面试） |
| `/resume` | `app/resume/layout.tsx` | 简历模块认证守卫 |
| `/resume` | `app/resume/page.tsx` | 简历上传 + 解析 + 雷达图评分 + AI 优化 + 下载 |
| `/knowledge` | `app/knowledge/layout.tsx` | 知识模块认证守卫 |
| `/knowledge` | `app/knowledge/page.tsx` | 知识学习入口（通用八股 / 岗位专业 双卡片） |
| `/knowledge/general` | `app/knowledge/general/page.tsx` | 通用八股文（左侧 sticky 目录 + 右侧 Card 网格 + IntersectionObserver 联动） |
| `/knowledge/position` | `app/knowledge/position/page.tsx` | 岗位专业知识（同构布局，scope=POSITION） |
| `/interview` | `app/interview/layout.tsx` | 面试模块认证守卫 |
| `/interview` | `app/interview/page.tsx` | 面试初始化表单（Collapsible 高级配置、Slider 参数） |
| `/interview/[sessionId]` | `app/interview/[sessionId]/page.tsx` | WebSocket 面试对话（流式打字机 + react-markdown + 计时器） |
| `/interview/report/[sessionId]` | `app/interview/report/[sessionId]/page.tsx` | 面试报告（雷达图 + 维度进度条 + 亮点/不足 + 逐题折叠 + Markdown 总结） |

### 24.4 页面功能详述

#### 简历分析 (`/resume`)

1. **拖拽上传区**：支持拖放或点击上传 PDF/DOCX，调用 `POST /resumes/upload`
2. **解析**：调用 `POST /resumes/{id}/parse`，展示结构化 JSON
3. **评分**：调用 `POST /resumes/{id}/score`，Recharts RadarChart 雷达图 + 维度分数明细
4. **AI 优化**：调用 `POST /resumes/{id}/optimize`
5. **下载**：调用 `GET /resumes/{id}/download-optimized`
6. 全程 Skeleton 骨架屏加载态

#### 知识学习 (`/knowledge/*`)

1. **入口页**：双卡片选择（通用八股 / 岗位专业）
2. **通用八股 / 岗位专业**：调用 `POST /knowledge/search` 获取知识点，按 subject → category 分组
3. **左侧目录**：`sticky top-20`，点击滚动到对应分组，`IntersectionObserver` 滚动联动高亮
4. **右侧内容**：Card 网格，显示科目名 + 题目数量
5. Card 点击预留（toast 提示"详细学习页面开发中"）

#### 模拟面试 (`/interview/*`)

1. **初始化页**：目标公司/岗位/JD 表单 + Collapsible 高级配置（题数 Slider、时长 Select）
2. **对话页**：
   - WebSocket 连接（`react-use-websocket`，自动重连、心跳 25s）
   - TOKEN 消息 → 流式打字机效果；MESSAGE 消息 → 完整气泡
   - 面试官消息左对齐 + `react-markdown` 渲染；候选人消息右对齐
   - 顶部状态栏：阶段标签 + 计时器 + 结束面试按钮
   - 底部输入：发送/跳过/语音预留，Enter 发送 + Shift+Enter 换行
   - STATE_CHANGE → 更新阶段；REPORT_READY → 弹窗跳转报告页
3. **报告页**：
   - 概览卡片（公司/岗位/时长/题数 + 综合大分）
   - Recharts RadarChart 五维雷达图
   - Progress 维度分数条
   - 亮点（绿点）/ 不足（橙点）双列卡片
   - 改进建议有序列表
   - 推荐复习知识点 Badge 标签
   - 逐题折叠评分（Collapsible）
   - Markdown 面试总结

### 24.5 构建结果

```
Route (app)                              Size     First Load JS
┌ ○ /                                    1.54 kB         110 kB
├ ○ /dashboard                           1.69 kB          89 kB
├ ○ /interview                           4.22 kB         120 kB
├ ƒ /interview/[sessionId]               11.4 kB         161 kB
├ ƒ /interview/report/[sessionId]        4.2 kB          239 kB
├ ○ /knowledge                           1.59 kB        88.9 kB
├ ○ /knowledge/general                   3.03 kB         119 kB
├ ○ /knowledge/position                  3.03 kB         119 kB
├ ○ /login                               4.2 kB          120 kB
└ ○ /resume                              4.13 kB         205 kB

○  (Static)   prerendered as static content
ƒ  (Dynamic)  server-rendered on demand
```

11 个路由全部编译通过，其中 9 个静态预渲染、2 个动态（含 `[sessionId]` 参数）。

### 24.6 前端启动

```bash
cd frontend
npm install
npm run dev
```

访问 `http://localhost:3000`，自动重定向至登录页。

### 24.7 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000/api/v1` | 后端 API 地址 |
| `NEXT_PUBLIC_WS_BASE_URL` | `ws://localhost:8000/api/v1` | WebSocket 地址 |

### 24.8 前后端联调测试步骤

1. 启动后端服务：

```bash
docker compose up -d postgres redis minio backend
docker compose exec backend alembic upgrade head
```

2. 创建测试用户（如未创建）：

```bash
docker compose exec backend python -m scripts.create_demo_user
```

3. 启动前端：

```bash
cd frontend
npm run dev
```

4. 打开 `http://localhost:3000`，使用 `demo / demo123` 登录
5. 依次测试：
   - **简历分析**：上传 PDF → 解析 → 评分（雷达图） → 优化 → 下载
   - **知识学习**：浏览通用八股 / 岗位专业知识分类
   - **模拟面试**：填写表单 → 开始面试 → WebSocket 对话 → 查看报告
