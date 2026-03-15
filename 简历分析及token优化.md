已压缩对话正在优化工具选择...

搜索与 `**/backend/**/resume*.py` 匹配的文件，5 匹配项

读取 [](file:///d%3A/mianshibao/backend/app/api/v1/endpoints/resume.py)

读取 [](file:///d%3A/mianshibao/backend/app/services/resume_service.py#1-1)，行 1 到 100

搜索匹配 `**/backend/**/ai*.py` 的文件，1 个匹配项

读取 [](file:///d%3A/mianshibao/backend/app/utils/file_parser.py#1-1)，行 1 到 100

读取 [](file:///d%3A/mianshibao/backend/app/models/resume.py)

读取 [](file:///d%3A/mianshibao/backend/app/services/resume_service.py#100-100)，行 100 到 130

读取 [](file:///d%3A/mianshibao/backend/app/services/resume_service.py#130-130)，行 130 到 200

读取 [](file:///d%3A/mianshibao/backend/app/providers/llm_factory.py)

针对目前简历分析部分性能过差、Token 消耗过高的问题，结合未来 Web 端多用户并发场景，我为您制定了以下优化方案。

---

### 一、 架构与性能优化方案 (针对卡顿与并发)

目前最大的性能瓶颈在于 **同步阻塞式处理** 和 **重复计算**。只要用户点击"预览"或"分析"，后端就会重新进行文件转换或 OCR 识别，这在多用户场景下是不可接受的。

#### 1. 引入异步任务队列 (Asynchronous Task Queue)
*   **现状**：用户上传简历后，前端等待 `api.post('/parse')`，后端同步执行 PDF 解析、OCR（可能耗时 10s+）和 LLM 请求。由于 HTTP 超时限制，大文件极易失败。
*   **优化**：
    *   引入 **Celery** 或 **Redis Queue (RQ)** 处理耗时任务。
    *   **流程变更**：
        1.  前端 `POST /upload` -> 后端保存文件 -> 立即返回 `task_id`，状态为 `processing`。
        2.  后台 Worker 异步执行：文件转 PDF -> OCR/文本提取 -> LLM 解析 -> 存入数据库。
        3.  前端轮询 `GET /tasks/{task_id}` 或通过 **WebSocket** 接收完成通知。
    *   **效果**：接口响应时间降至 <100ms，消除页面假死，支持高并发任务排队。

#### 2. 静态资源持久化缓存 (Persistent Caching)
*   **现状**：每次调用 `GET /preview-pdf`，后端都会运行 `soffice` 或 `reportlab` 重新生成 PDF。LibreOffice 启动极慢且消耗大量 CPU。
*   **优化**：
    *   **生成即存储**：首次生成预览 PDF 后，将其上传至 MinIO 的 `previews/` 目录。
    *   **读取优先**：`preview_resume_pdf` 接口先检查 MinIO 是否存在缓存文件，存在则直接返回流，不存在再生成。
    *   **数据库标记**：在 `Resume` 表中增加 `preview_file_url` 字段。

#### 3. 数据库结构优化
*   **现状**：`parse_resume` 提取的纯文本 (Raw Text) 可能未被持久化，后续 `score` 和 `optimize` 可能需要重新从文件读取或依赖 LLM 解析后的 JSON（可能丢失细节）。
*   **优化**：
    *   **修改 `Resume` 模型**：增加 `raw_text` (Text) 字段。
    *   **一次解析，多次使用**：仅仅在上传时进行一次 OCR/文本提取并存入 `raw_text`。后续的评分、优化直接从数据库读取文本，**完全省去文件 IO 和 OCR 开销**。

---

### 二、 Token 节省与成本控制方案

#### 1. 模型分级策略 (Model Tiering)
不要用同一个昂贵的模型处理所有任务。
*   **文本结构化 (Parsing)**：使用 **Qwen-Turbo** 或 **GPT-3.5-Turbo**。此任务只需按格式提取信息（姓名、学历、时间），不需要复杂的逻辑推理，小模型完全够用，成本降低 10 倍。
*   **评分与优化 (Scoring/Optimization)**：使用 **Qwen-Max** 或 **GPT-4**。这需要理解上下文和职场逻辑，使用大模型保证质量。

#### 2. Token 输入压缩 (Prompt Engineering)
*   **只传必要字段**：
    *   **评分时**：不需要传入用户的手机号、邮箱、家庭住址等隐私信息，也不需要传入纯装饰性的自我介绍。只传入 `项目经历`、`工作经历`、`教育背景`。
    *   **优化时**：如果是优化“项目经历”，则 **只截取该项目的文本** 发送给 LLM，而不是整份简历。这能减少 50%-70% 的 Token 消耗。
*   **JSON Mode 优化**：目前的 Prompt 中包含大量 `format_instructions`（Pydantic 输出的 Schema 往往很长）。
    *   **优化**：简化 Prompt 中的 JSON 示例，改用 One-shot 示例："请输出 JSON，包含 keys: ['score', 'advice']..."，能显著减少 Prompt Token。

#### 3. 预处理与过滤
*   **使用非 LLM 提取基础信息**：
    *   **正则提取**：邮箱、电话、甚至部分日期，使用 Python 正则表达式提取，**0 Token 消耗**。
    *   **关键词匹配**：技能标签（Java, Python）可以先用关键词库匹配，LLM 仅用于补充未匹配项。

---

### 三、 具体的开发实施步骤

为了验证上述方案，我们不再大幅重构所有代码，而是针对当前瓶颈进行**即刻失效**的改进：

#### 步骤 1：数据库与缓存改造 (优先实施)
修改 resume.py，增加字段以支持缓存。

```python
# backend/app/models/resume.py

class Resume(Base, BaseModelMixin):
    # ... 原有字段
    # 新增字段：只有在第一次解析时写入，后续直接读取
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True) 
    # 新增字段：预览图地址，避免重复生成 PDF
    preview_file_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
```

#### 步骤 2：改造 Service 层逻辑
修改 resume_service.py：
1.  **Parse**: 解析后填充 `raw_text`。
2.  **Score/Optimize**: 优先读取 `resume.raw_text`，不再读取 MinIO 文件。
3.  **Preview**: 检查 `resume.preview_file_url`，有则直接下载，无则生成并上传 MinIO。

#### 步骤 3：前端轮询机制 (针对 Web 体验)
虽然暂时不引入 Celery (架构改动大)，但可以在前端模拟优化的交互：
1.  用户上传后，前端显示 "正在深度解析..." 进度条 (伪进度或估算时间)。
2.  若 API 超过 10 秒未返回，前端捕获超时并提示 "服务器正忙，请稍后在历史记录中查看"，避免用户以为应用崩溃。

---

### 总结
1.  **架构优化**：**Preview 缓存** 是当务之急，能直接解决 `preview-pdf` 卡顿问题。
2.  **Token 优化**：在 `config.py` 中分离 `PARSING_MODEL` (低成本) 和 `OPTIMIZE_MODEL` (高质量)，并存储 `raw_text` 避免重复解析。

您觉得这个方案是否符合您对未来的预期？如果同意，我可以先为您实现 **"预览 PDF 缓存"** 和 **"Raw Text 持久化"** 这两个最立竿见影的功能。