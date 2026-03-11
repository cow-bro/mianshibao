# 数据库设计文档

本文件用于记录 PostgreSQL + pgvector 的数据模型设计与索引策略。

## 当前状态

- 已完成阶段 2 的核心 7 张表建模
- 已集成 Alembic 迁移与 pgvector extension 初始化
- 已配置 `knowledge_point.embedding` 的 HNSW 向量索引

## 核心表

1. `user`
2. `resume`
3. `resume_template`
4. `knowledge_point`
5. `interview_session`
6. `interview_message`
7. `wrong_question`

所有表统一包含 `id`, `created_at`, `updated_at`。

## 向量字段

- 字段: `knowledge_point.embedding`
- 类型: `Vector(1536)`
- 依赖: `pgvector.sqlalchemy.Vector`

## 迁移关键点

- 启用扩展:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

- HNSW 索引:

```sql
CREATE INDEX IF NOT EXISTS ix_knowledge_point_embedding_hnsw
ON knowledge_point
USING hnsw (embedding vector_cosine_ops);
```

## 迁移命令

在 `backend/` 目录执行:

```bash
alembic upgrade head
```
