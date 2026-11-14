# StudyFlow REST API

版本：`0.7.0-mvp`  
API 前缀：`/api`  
默认服务地址：`http://127.0.0.1:5000`

StudyFlow 是单管理员应用；业务数据归属于 `users.id = 1`（`username = student`）。除登录/登出外，所有 `/api/*`、页面和 `/uploads/*` 都需要管理员 Session。未登录 API 返回 HTTP `401` JSON（`AUTH_REQUIRED`），不会返回 HTML 登录页。

## 0. 认证

### `POST /api/auth/login`

请求：

```json
{"password": "管理员密码", "next": "/"}
```

成功响应会设置 `studyflow_session` Cookie（HttpOnly、SameSite=Lax，HTTPS 下可配置 Secure）：

```json
{"ok": true, "data": {"redirect": "/"}, "message": "登录成功"}
```

- 错误密码：HTTP `401`，`INVALID_CREDENTIALS`
- 频率限制：HTTP `429`，`LOGIN_RATE_LIMITED`，带 `Retry-After`
- 缺少密码：HTTP `400`

### `POST /api/auth/logout`

清除 Session，返回 `{"ok": true, "data": {"redirect": "/login"}}`。

登录页面是公开的 `/login`；登录成功后才可访问 SPA 和业务 API。认证相关的环境变量见 [部署说明](DEPLOY_DEBIAN_ARM64.md)。

---

## 1. 通用约定

### Content-Type

除图片上传外，请求和响应均使用 JSON：

```http
Content-Type: application/json
Accept: application/json
```

图片上传使用 `multipart/form-data`。

### 成功响应

```json
{
  "ok": true,
  "data": {},
  "message": "可选的人类可读消息"
}
```

AI 接口额外在顶层返回 `ai`：

```json
{
  "ok": true,
  "data": { "result": "..." },
  "ai": {
    "mode": "demo",
    "provider": "StudyFlow 本地演示",
    "model": "local-demo-v1",
    "notice": "当前为演示模式……",
    "disclaimer": "AI 输出仅供参考……",
    "analyzed_at": "2026-11-11T20:00:00+08:00"
  }
}
```

`ai.mode` 只会是：

- `live`：调用了真实的外部模型。
- `demo`：未调用外部模型，结果来自明确标记的本地演示/启发式逻辑。

前端会据此显示醒目徽标，不会把演示结果伪装成真实 AI。

### 错误响应

```json
{
  "ok": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "任务标题不能为空",
    "details": {}
  }
}
```

常见错误码：

| HTTP | code | 说明 |
| --- | --- | --- |
| 400 | `VALIDATION_ERROR` | 参数校验失败 |
| 400 | `INVALID_IMAGE_URL` | 图片地址不是本地上传路径 |
| 400 | `IMAGE_REQUIRED` | 视觉接口没有收到图片 |
| 400 | `IMAGE_FORMAT_ERROR` | 图片不是合法的 Base64 data URL（禁止把文件路径当图片文本发送） |
| 404 | `NOT_FOUND` | 资源不存在 |
| 413 | `FILE_TOO_LARGE` / `PAYLOAD_TOO_LARGE` | 文件或请求过大 |
| 415 | `UNSUPPORTED_FILE_TYPE` | 文件不是 JPG/PNG/WebP |
| 415 | `INVALID_CONTENT_TYPE` | 请求体不是 JSON |
| 502 | `AI_INVALID_RESPONSE` | 模型返回无法解析为约定的 JSON |
| 502 | `AI_AUTH_ERROR` | AI API Key 无效或无权限 |
| 502 | `AI_REQUEST_REJECTED` | 模型名称/接口地址/请求被拒绝 |
| 503 | `AI_NOT_CONFIGURED` | 严格模式下未配置 AI Key |
| 503 | `AI_CONFIG_ERROR` | 已配置 Key，但缺少 `AI_VISION_BASE_URL` 等必要设置；不会发起外部请求 |
| 503 | `AI_RATE_LIMIT` | 上游 AI 限流或额度不足 |

### 日期与时间

- 纯日期字段统一为 `YYYY-MM-DD`。
- 时间字段 `HH:MM`。
- 时间戳由后端按 `TIMEZONE`（默认 `Asia/Shanghai`）生成，带时区偏移，例如 `2026-11-11T20:00:00+08:00`。
- “今天”等统计以后端时区为准。

### 上传限制

- 支持内容和扩展名：JPG、PNG、WebP。
- 单张图片 ≤ 8 MB；整个 HTTP 请求 ≤ 12 MB。
- 文件内容会用 Pillow 重新校验、移除 EXIF 并限制最大边长为 2400px。
- 上传成功后返回 `/uploads/<文件名>`，只能把这个地址传给 AI 接口；禁止外部 URL 以避免 SSRF。

### 时间范围

`range` 支持 `30`、`90`、`180`、`all`。非法值按 90 天处理。

---

## 2. 系统、设置与数据

### `GET /api/health`

健康检查。

```json
{"ok":true,"data":{"status":"ok","app":"StudyFlow","version":"0.7.0-mvp","server_time":"..."}}
```

### `GET /api/meta`

应用元数据、当前用户、学科列表、AI 能力状态和演示数据摘要。

关键字段：

- `data.user`
- `data.subjects`
- `data.ai.policy`：`auto | on | off`
- `data.ai.text.effective_mode`：`live | demo | unavailable`
- `data.ai.vision.effective_mode`
- `data.ai.text.configured`：仅表示服务端是否配置了 Key，不返回 Key
- `data.demo.loaded`

### `GET /api/settings`

当前用户设置、AI 状态、演示数据摘要。

### `PUT|PATCH /api/settings`

可修改字段：

| 字段 | 类型 | 范围 |
| --- | --- | --- |
| `display_name` | string | 1-40 字符 |
| `email` | string/null | 合法邮箱或空 |
| `avatar_color` | string | `#RRGGBB` |
| `daily_goal_minutes` | int | 15-720 |
| `pomodoro_minutes` | int | 1-120 |
| `short_break_minutes` | int | 1-60 |
| `long_break_minutes` | int | 1-120 |

### 演示数据

- `GET /api/demo`：返回已载入的演示数据统计。
- `POST /api/demo/load`：载入演示数据；已经载入时返回 `already_loaded`。
- `DELETE /api/demo/clear`：只删除由演示种子写入的记录，随后根据用户自己的剩余数据重新计算成就。

演示数据首次启动可在 `.env` 中用 `SEED_DEMO=true/false` 开关。清除后不会在重启时自动重建；设置页可再次手动载入。

### `GET /api/export`

下载当前用户的完整 JSON 备份（任务、成绩、笔记、学习记录、成就、错题、闪卡）。不会导出 API Key。

---

## 3. Dashboard

### `GET /api/dashboard`

返回首页所需的一切数据：

- `greeting`、`date_label`、`weekday_label`
- `stats`：今日任务完成率、今日/本周学习分钟、连续天数、成就数、最近成绩均值等
- `today_tasks`
- `recent_grades`（每个学科最新一次，带 `delta`）
- `recent_sessions`
- `week_activity`：最近 7 天
- `achievements`
- `has_fallback_tasks`：今日无排期时是否展示了兜底的最近未完成任务

---

## 4. 任务与智能规划

### `GET /api/tasks`

Query：

| 参数 | 说明 |
| --- | --- |
| `status` | `all`（默认）、`open`、`pending`、`in_progress`、`completed`、`history` |
| `subject` | 学科筛选 |
| `q` | 标题/描述搜索 |
| `limit` | 1-300，默认 100 |

返回：

```json
{
  "ok": true,
  "data": {
    "tasks": [],
    "counts": {
      "total": 5,
      "pending": 2,
      "in_progress": 1,
      "completed": 2,
      "overdue": 0,
      "due_today": 2,
      "open_estimated_minutes": 120
    }
  }
}
```

### `POST /api/tasks`

```json
{
  "title": "完成数学练习册 P42",
  "subject": "数学",
  "description": "第 1-10 题",
  "due_date": "2026-11-12",
  "estimated_minutes": 40,
  "difficulty": 3,
  "priority": 1,
  "planned_date": "2026-11-11",
  "planned_start": "19:30",
  "planned_minutes": 40,
  "source": "manual",
  "ai_meta": null
}
```

必填：`title`。`estimated_minutes` 5-1440；`difficulty` 1-5；`priority` 1（高）-3（低）；`source` 为 `manual|ai|import`。

### `GET /api/tasks/<id>`

### `PUT|PATCH /api/tasks/<id>`

支持修改：`title`、`subject`、`description`、`due_date`、`estimated_minutes`、`actual_minutes`、`difficulty`、`priority`、`planned_date`、`planned_start`、`planned_minutes`。

### `DELETE /api/tasks/<id>`

### `POST /api/tasks/<id>/complete`

```json
{"actual_minutes": 35}
```

返回：`{task, unlocked_achievements}`。会写入 `actual_minutes`、`completed_at`。

### `POST /api/tasks/<id>/reopen`

重新变为待完成。

### `POST /api/tasks/<id>/start`

标记为进行中。

### `GET /api/tasks/history?limit=50`

已完成任务，按完成时间倒序。

### `POST /api/tasks/plan/preview`（别名 `/api/tasks/plan`）

```json
{
  "plan_date": "2026-11-11",
  "start_time": "19:00",
  "available_minutes": 120,
  "task_ids": [1, 2, 3]
}
```

系统使用本地透明规则（截止时间、优先级、难度、历史实际耗时/预计耗时）生成排期。返回 `schedule[]`、`unscheduled_tasks[]`、历史比例和说明。**不会自动写入任务。**

每项示例：

```json
{
  "task_id": 1,
  "title": "完成英语阅读",
  "start_time": "19:00",
  "end_time": "19:36",
  "planned_minutes": 36,
  "estimated_minutes": 30,
  "partial": false,
  "reason": "明天截止；根据历史实际耗时调整为约 36 分钟"
}
```

### `POST /api/tasks/plan/apply`

```json
{
  "plan_date": "2026-11-11",
  "schedule": [
    {"task_id": 1, "start_time": "19:00", "planned_minutes": 36}
  ]
}
```

只有用户应用后，计划时间才会写入任务。

---

## 5. 成绩

### `GET /api/grades/analytics`

Query：`subject`、`range`。

返回：

- `records`：最新在前
- `chart_records`：时间正序，用于图表
- `subject_series[]`：每科 `{subject,color,points,average,latest,delta,count}`
- `overall_series[]`：按日期合并的总得分率
- `subject_comparison[]`
- `kpis`
- `available_subjects`
- `data_range`

### `GET /api/grades`

是 analytics 的附带列表版本，包含 `grades`、`analytics`、`subjects`。

### `POST /api/grades`

```json
{
  "subject": "数学",
  "exam_name": "期中考试",
  "score": 91,
  "max_score": 100,
  "exam_date": "2026-11-08",
  "notes": "函数题有进步"
}
```

分数不能大于满分。`max_score` 必须 > 0。

### `PUT|PATCH /api/grades/<id>`

### `DELETE /api/grades/<id>`

---

## 6. 智能笔记

### `GET /api/notes?subject=&q=&limit=100`

返回摘要列表：

```json
{
  "notes": [{
    "id": 1,
    "title": "二次函数基础",
    "subject": "数学",
    "snippet": "...",
    "has_audit": true,
    "has_graph": true,
    "updated_at": "..."
  }],
  "subjects": ["数学", "英语"]
}
```

### `POST /api/notes`

```json
{
  "title": "二次函数基础",
  "subject": "数学",
  "content_markdown": "# ...\n$$x=-\\frac{b}{2a}$$",
  "source_image": "/uploads/abcdef....png"
}
```

`source_image` 只接受本地上传返回的 `/uploads/<32位hex>.(jpg|png|webp)`，防止链接注入。

### `GET /api/notes/<id>`

包含 `content_markdown`、`audit_report`、`knowledge_graph`。

### `PUT|PATCH /api/notes/<id>`、`DELETE /api/notes/<id>`

### `POST /api/notes/<id>/audit`

请求体可为空；也可传 `{"demo": true}` 强制演示模式。

不自动修改笔记内容，只把检查结果保存进 `audit_report`。返回：

```json
{
  "summary": "...",
  "corrections": [{
    "location": "公式部分",
    "original": "...",
    "suggested": "...",
    "reason": "...",
    "certainty": "certain|review",
    "confidence": 0.82,
    "category": "知识性错误|公式错误|概念混淆|逻辑矛盾|识别错误|其他"
  }],
  "coverage_note": "...",
  "warnings": []
}
```

### `POST /api/notes/<id>/graph`

让 AI 从已保存笔记提取节点和边，并把结果持久化到笔记。请求体可为空或 `{"demo": true}`。

```json
{
  "nodes": [
    {"id":"node-1","label":"二次函数","type":"概念","description":"..."}
  ],
  "edges": [
    {"source":"node-1","target":"node-2","label":"前置知识"}
  ],
  "summary": "...",
  "warnings": []
}
```

`type`：概念、公式、定理、方法、应用。  
`label`（关系）：前置知识、从属关系、相互关联、应用关系。

### `GET /api/notes/<id>/graph`

读取已保存的知识图；未生成时返回 404。

---

## 7. 学习时长、成就与报告

### `GET /api/study/sessions?date=YYYY-MM-DD&subject=&limit=50`

返回 `sessions`、`summary`（今日/本周/累计、按学科和 7 天活动）、filters。

### `POST /api/study/sessions`

```json
{
  "subject": "数学",
  "duration_minutes": 25,
  "session_type": "pomodoro",
  "task_id": 1,
  "started_at": "2026-11-11T20:00:00+08:00",
  "ended_at": "2026-11-11T20:25:00+08:00",
  "note": "完成练习"
}
```

`session_type`：`pomodoro|free|manual|task`。时长 1-720 分钟。返回 `session` 与 `unlocked_achievements`。

### `DELETE /api/study/sessions/<id>`

### `GET /api/study/stats`

聚合的今日/本周/累计统计，供专注页使用。

### `GET /api/achievements`

返回全部 12 个成就定义、解锁状态、解锁时间和进度统计。

### `GET /api/reports/daily?date=YYYY-MM-DD`

按本地数据生成每日报告。不能查询未来日期。返回任务、学习时长、学科分布、成绩/笔记/错题更新、成就、叙述建议。报告为本地数据汇总，不调用外部 AI。

---

## 8. 闪卡

### `GET /api/flashcards?due_only=true&subject=&limit=200`

返回 `flashcards`、`due_count`、`total`、`subjects`。

### `POST /api/flashcards`

```json
{
  "front": "二次函数对称轴公式？",
  "back": "$x=-\\frac{b}{2a}$",
  "subject": "数学",
  "note_id": 1
}
```

### `PUT|PATCH /api/flashcards/<id>`、`DELETE /api/flashcards/<id>`

### `POST /api/flashcards/<id>/review`

```json
{"rating": 5}
```

`rating` 0-5。评分会调整掌握度和下次复习日：

- ≥ 4：掌握度 +1，间隔拉长；
- 3：保持掌握度；
- ≤ 2：掌握度 -1，短期再复习。

返回更新后的闪卡和间隔天数。

---

## 9. 错题本

### `GET /api/errors?subject=&mastery=&q=&limit=100`

返回 `errors`、`counts`（总数/待复习/复习中/已掌握）、`subjects`。

### `POST /api/errors`

```json
{
  "subject": "数学",
  "question": "求二次函数顶点。",
  "student_answer": "直接代 x=0",
  "correct_answer": "使用顶点公式",
  "analysis": "概念混淆",
  "knowledge_points": ["二次函数", "顶点"],
  "mastery": "new"
}
```

### `PUT|PATCH /api/errors/<id>`、`DELETE /api/errors/<id>`

---

## 10. 上传

### `POST /api/uploads`

`multipart/form-data` 字段名：`image`（也接受 `file`）。

返回：

```json
{
  "filename": "32hex.png",
  "url": "/uploads/32hex.png",
  "mime_type": "image/png",
  "size_bytes": 234567,
  "width": 1200,
  "height": 1600,
  "original_name": "homework.png"
}
```

---

## 11. AI 接口

所有 AI 接口：

1. 只由后端读取环境变量并调用模型；
2. 返回顶层 `ai` 元数据；
3. 如果 `AI_DEMO_MODE=auto` 且对应能力未配置 Key，则进入**明确标记的**演示模式；
4. 如果 `AI_DEMO_MODE=off` 且未配置 Key，则返回 `503 AI_NOT_CONFIGURED`；
5. 可以在 JSON 请求体传 `"demo": true` 显式请求演示模式（即使已有 Key）。

### `GET /api/ai/status`

返回文本/视觉能力配置状态。不会返回 Key，也不会返回完整 Base URL。

```json
{
  "policy": "auto",
  "text": {
    "configured": true,
    "config_complete": true,
    "missing_env": [],
    "provider": "deepseek",
    "model": "deepseek-chat",
    "base_url_configured": true,
    "effective_mode": "live"
  },
  "vision": {
    "configured": true,
    "config_complete": true,
    "missing_env": [],
    "provider": "qwen",
    "model": "qwen3.8-flash",
    "base_url_configured": true,
    "effective_mode": "live"
  }
}
```

`missing_env` 会列出缺失的变量名，例如 `AI_VISION_API_KEY`、`AI_VISION_BASE_URL`。如果已配置 Key 但缺少 Base URL，视觉能力为 `unavailable`，实际请求会返回 `503 AI_CONFIG_ERROR`，不会偷偷切换到演示或使用硬编码地址。

### 视觉/结构化接口

| 方法 | 路径 | 主要字段 |
| --- | --- | --- |
| POST | `/api/ai/tasks/recognize` | `image_url`、`subject_hint?`、`due_date?` |
| POST | `/api/ai/notes/recognize` | `image_url`、`title_hint?` |

这些接口的 `image_url` 必须是 `/api/uploads` 返回的本地上传地址。后端读取文件后，将 PNG/JPG/WebP 编码为 data URL，并以 OpenAI 兼容的 `image_url` 内容块发送给 Qwen；不会把文件路径作为普通文本发送。

`tasks/recognize` 返回示例：

```json
{
  "image_summary": "...",
  "tasks": [{
    "title": "数学练习",
    "subject": "数学",
    "description": "图片中的作业要求",
    "question_count": 10,
    "difficulty": 4,
    "estimated_minutes": 45,
    "difficulty_reason": "题量较大且包含综合题",
    "confidence": 0.82,
    "due_date": "2026-11-12"
  }],
  "warnings": []
}
```

该结果只用于给用户确认，不会自动创建任务。

`notes/recognize` 返回：

```json
{"title":"...","subject":"数学","markdown":"...","confidence":0.8,"warnings":[]}
```

### 英语工具

| 方法 | 路径 | 请求 |
| --- | --- | --- |
| POST | `/api/ai/essay/review` | `text?`、`image_url?`（至少一个） |
| POST | `/api/ai/express/polish` | `text` |
| POST | `/api/ai/sentence/analyze` | `sentence` |
| POST | `/api/ai/grammar/check` | `sentence` |

### 出题与阅卷

`POST /api/ai/questions/generate`

```json
{
  "subject": "数学",
  "topic": "二次函数",
  "difficulty": "easy|medium|hard",
  "count": 3
}
```

`POST /api/ai/grading/assist`

```json
{
  "question": "说明浮力方向",
  "reference_answer": "浮力方向竖直向上。",
  "student_answer": "浮力向上。",
  "max_score": 10
}
```

### 成绩分析

`POST /api/ai/grades/analyze`

```json
{"subject": "all", "range": "90"}
```

服务端会读取真实成绩统计，交给模型生成谨慎的、非确定性的建议。返回包含 `trend`、`strengths`、`weaknesses`、`suggestions` 和 `disclaimer`。无数据时仍可返回无法判断。

### 错题知识点归类

`POST /api/ai/errors/classify`

```json
{
  "question": "...",
  "student_answer": "...",
  "subject_hint": "数学"
}
```

返回学科、知识点、原因、建议、置信度。前端需要用户点击应用才写回错题记录。

### 从笔记生成闪卡

`POST /api/ai/flashcards/generate`

```json
{"note_id": 1, "count": 5}
```

或使用未保存内容：

```json
{"title": "...", "subject": "数学", "markdown": "...", "count": 5}
```

生成结果只返回卡片草稿，由前端逐张保存到 `/api/flashcards`。

### 笔记检查 / 知识图

已在上文 Notes 部分说明。这两个接口也会返回 `ai` 元数据。

---

## 12. 前端页面路径

服务端同时托管前端静态资源，浏览器不是通过 API 访问页面，而是：

- `/`：SPA 入口
- `/#/dashboard`
- `/#/planner`
- `/#/analytics`
- `/#/ai-toolbox`
- `/#/notes`
- `/#/focus`
- `/#/flashcards`
- `/#/errors`
- `/#/reports`
- `/#/settings`

---

## 13. curl 示例

```bash
# 创建任务
curl -X POST http://127.0.0.1:5000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"title":"完成英语阅读","subject":"英语","estimated_minutes":30,"due_date":"2026-11-12"}'

# 上传图片
curl -X POST http://127.0.0.1:5000/api/uploads \
  -F "image=@homework.png"

# 在演示模式调用作文批改
curl -X POST http://127.0.0.1:5000/api/ai/essay/review \
  -H "Content-Type: application/json" \
  -d '{"text":"I think this book is very good.","demo":true}'

# 生成计划
curl -X POST http://127.0.0.1:5000/api/tasks/plan/preview \
  -H "Content-Type: application/json" \
  -d '{"available_minutes":120,"start_time":"19:00"}'
```

---

## 14. AI 演示与真实模式

演示模式**不会**：

- 请求任何外部 AI URL；
- 声称读取了图片内容；
- 把本地规则结果标记为 `live`。

演示模式会：

- 返回结构完整的样例数据，或在用户文本上用透明启发式规则生成结果；
- 在 `ai.notice`、`ai.mode` 和前端结果卡片上醒目标注；
- 在图片识别任务/笔记中以 `0.0` 置信度和警告说明图片没有被读取。

配置真实模型需在 `.env` 设置：

```dotenv
AI_TEXT_API_KEY=...
AI_TEXT_BASE_URL=https://api.deepseek.com/v1
AI_TEXT_MODEL=deepseek-chat

AI_VISION_PROVIDER=qwen
AI_VISION_API_KEY=...
AI_VISION_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
AI_VISION_MODEL=qwen3.8-flash
AI_DEMO_MODE=auto
```

修改 `.env` 后需重启 Flask。`AI_VISION_BASE_URL` 必须由环境变量提供，后端没有硬编码默认地址；API Key 绝不能写进前端或提交到 Git。

真实调用可通过可选的连通性脚本验证。脚本先检查 Qwen 端点/鉴权/模型，成功后才发送内嵌测试图片：

```bash
python scripts/test_ai_connection.py --capability vision
python scripts/test_ai_connection.py --capability all
```

未配置 Key 时脚本返回 `2 (SKIPPED)`，不会发起请求或伪造成功。

本次已使用真实 `.env` 凭据完成实测：

- Qwen 请求/响应模型均为 `qwen3.8-flash`，纯文本连通性和 Base64 图片多模态输入均通过；
- 应用级 `POST /api/ai/tasks/recognize` 返回 `ai.mode=live`，识别出作业任务；
- DeepSeek 请求配置为 `deepseek-chat`，连通性通过，上游返回的响应模型为 `deepseek-flash`；
- 应用级 `POST /api/ai/express/polish` 返回 `ai.mode=live`。

测试没有打印、返回或提交任何 API Key。测试上传图片在验证后已删除。
