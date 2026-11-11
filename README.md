# StudyFlow

> AI 智能学习管理平台 · MVP（约 70% 完成度）

StudyFlow 是一个面向中学生的全栈学习工作台：把作业规划、成绩分析、英语 AI 工具、笔记数字化、专注计时、闪卡复习和每日报告放进同一个轻量应用。

前端是原生 HTML / CSS / JavaScript（ES Modules）+ Tailwind 工具类，后端是 Python Flask + SQLite。项目不依赖 React、Vue、Next.js，也没有 Node 构建步骤。

![StudyFlow Dashboard](docs/screenshots/dashboard.png)

---

## 目录

- [当前完成度](#当前完成度)
- [功能总览](#功能总览)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [环境变量](#环境变量)
- [AI 配置与演示模式](#ai-配置与演示模式)
- [项目结构](#项目结构)
- [数据库设计](#数据库设计)
- [测试与验证](#测试与验证)
- [已知限制与未实测项](#已知限制与未实测项)
- [后续开发接口](#后续开发接口)
- [常见问题](#常见问题)
- [API 文档](docs/API.md)

---

## 当前完成度

这是可运行的核心 MVP，不是静态原型：

- ✅ 6 个主页面 + 专注/闪卡/错题/报告 4 个学习工具页面，真实 hash 导航
- ✅ 任务规划、AI 图片作业识别、本地透明排期、历史任务
- ✅ 成绩 CRUD、3 种 Chart.js 图表、科目/时间范围筛选、AI 成绩分析（含演示标识）
- ✅ 英语作文批改、表达润色、长难句、语法诊断、出题、阅卷
- ✅ 笔记 CRUD、Toast UI 编辑、图片识别草稿、AI 检查、KaTeX 预览、Cytoscape 知识图
- ✅ 番茄钟、手动学习记录、学习成就、闪卡生成与间隔复习、错题知识点归类、每日报告
- ✅ 统一 REST API / 统一 AI Service / JSON 校验 / 有限重试 / 明确错误语义
- ✅ SQLite 持久化、演示数据可载入/清除、JSON 导出
- ✅ 后端 pytest 测试、浏览器自动化联调（桌面 + 390px 移动端）
- ⚠️ 真实 Qwen/DeepSeek 外部 API 因本开发环境没有密钥而未实际调用，详见[已知限制](#已知限制与未实测项)

---

## 功能总览

| 页面 | 已经实现的核心能力 |
| --- | --- |
| **Dashboard 首页** | 问候语、今日日期、今日任务完成率、学习时长、7 天节奏、最近成绩、最近学习记录、快捷入口、成就、演示模式提示 |
| **Planner 学习规划** | 手动任务 CRUD、完成/重开/开始、历史任务、实际耗时、截止日期、难度/优先级、图片识别作业草稿、智能排期预览与应用 |
| **Analytics 成绩分析** | 成绩 CRUD、考试日期/分数/满分/备注、按学科与时间筛选、各科折线图、总成绩变化图、学科平均对比、AI 分析 |
| **AI Toolbox** | 作文批改（文本/图片）、表达润色（三版本）、长难句、语法诊断、AI 出题、AI 阅卷 |
| **Notes 智能笔记** | Markdown 笔记 CRUD、Toast UI Editor、图片笔记识别、AI 检查（确定/待确认/可信度）、KaTeX 预览、Cytoscape 交互知识图谱 |
| **Focus 专注时钟** | 自定义番茄钟、短/长休息、暂停/继续/重置、完成后自动记录学习时长、手动补录、今日记录、成就墙 |
| **Flashcards 闪卡** | 手动 CRUD、从笔记 AI 生成、翻面复习、1/3/5 评分、掌握度与下次复习日期、到期队列 |
| **Errors 错题本** | 错题 CRUD、知识点标签、掌握状态、答案/错因折叠、AI 学科与知识点归类建议 |
| **Reports 学习报告** | 按日期查看本地学习汇总、目标进度、任务回顾、学科投入、时间线、建议、打印 |
| **Settings 设置** | 昵称/邮箱/头像色、目标/番茄钟时长、AI 服务状态、环境变量说明、演示数据载入/清除、JSON 导出 |

### 页面预览

| 学习规划 | 成绩分析 |
| --- | --- |
| ![Planner](docs/screenshots/planner.png) | ![Analytics](docs/screenshots/analytics.png) |

| 智能笔记 + KaTeX | 知识关系图 |
| --- | --- |
| ![Notes](docs/screenshots/notes.png) | ![Knowledge graph](docs/screenshots/notes-graph.png) |

| AI 工具箱 | 移动端 |
| --- | --- |
| ![AI Toolbox](docs/screenshots/ai-toolbox.png) | ![Mobile](docs/screenshots/mobile-dashboard.png) |

---

## 技术栈

**前端**

- HTML5、CSS3 自定义设计变量、原生 JavaScript（ES Modules，无框架）
- Tailwind CSS 浏览器版本（已本地化到 `frontend/vendor/tailwind.min.js`，作为 utility 辅助；视觉组件由 `css/` 中的样式系统统一）
- Chart.js 4 —— 成绩图表
- Cytoscape.js 3 —— 知识图谱
- Toast UI Editor 3 —— Markdown 笔记编辑
- KaTeX —— 数学公式渲染（配合 marked + DOMPurify）
- Lucide —— 图标

**后端**

- Python 3.10+
- Flask 3 + flask-cors + python-dotenv
- SQLite（`sqlite3` 标准库，开启外键、索引、WAL）
- requests —— 调用 OpenAI-compatible 的 DeepSeek / Qwen 接口
- Pillow —— 上传图片真实性校验、压缩与元数据清理
- pytest —— API / AI 网关 / 演示数据测试

所有前端第三方库都已下载到 `frontend/vendor/`，运行时**不需要外网 CDN**（真实 AI 调用除外）。KaTeX 字体也已本地化。

---

## 快速开始

### 1. Python 环境

建议 Python **3.10 及以上**。在项目根目录执行：

**Windows（cmd / PowerShell）**

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python run.py
```

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python run.py
```

打开 <http://127.0.0.1:5000>。

如果不想手动敲命令，Windows 可双击/执行：

```bat
start.bat
```

macOS/Linux：

```bash
chmod +x start.sh
./start.sh
```

PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

> 启动脚本会优先使用 `.venv` 中已安装 Flask 的 Python，其次才尝试 `py -3` / `python`。如果依赖缺失，会给出安装命令提示，不会静默启动失败。

### 2. 数据库初始化

正常情况下不需要额外步骤：`run.py` 启动时会自动执行 `backend/schema.sql`，并确保默认用户存在。

也可以手动初始化（可查看表记录数）：

```bash
python scripts/init_db.py
```

可用参数：

```bash
python scripts/init_db.py --no-seed
python scripts/init_db.py --reload-demo
```

项目默认在第一次启动时载入少量演示数据（`SEED_DEMO=true`）。在 **设置 → 演示数据与导出** 中可一键清除；清除演示数据不会删除用户自己创建的内容。

### 3. 访问

| 地址 | 说明 |
| --- | --- |
| <http://127.0.0.1:5000> | 应用首页 |
| <http://127.0.0.1:5000/api/health> | 健康检查 |
| <http://127.0.0.1:5000/api/meta> | 应用与 AI 配置状态 |
| <http://127.0.0.1:5000/api/*> | REST API 前缀，见 [docs/API.md](docs/API.md) |

本地数据默认位于：

```text
data/studyflow.db
data/uploads/
```

---

## 环境变量

复制 `.env.example` 为 `.env`。后端在启动时读取 `.env`；前端无法读取这些值，API Key 永远不会发送到浏览器。

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `HOST` | `127.0.0.1` | Flask 监听地址 |
| `PORT` | `5000` | Flask 端口 |
| `FLASK_ENV` | `development` | `development` 会开启 Flask debug/reloader；部署时不要暴露 debug |
| `SECRET_KEY` | 开发占位值 | 生产部署前必须改成随机字符串 |
| `TIMEZONE` | `Asia/Shanghai` | 日期、今日统计使用 |
| `DATABASE_PATH` | `data/studyflow.db` | 相对项目根目录 |
| `UPLOAD_DIR` | `data/uploads` | 上传目录 |
| `SEED_DEMO` | `true` | 首次初始化是否写入演示数据 |
| `CORS_ORIGINS` | 空 | 需要跨域时填写允许的前端源，逗号分隔 |
| `AI_DEMO_MODE` | `auto` | `auto` / `on` / `off`，见下文 |
| `AI_TIMEOUT` | `60` | 请求 AI 的超时秒数 |
| `AI_MAX_RETRIES` | `2` | JSON/网络类错误的自动重试次数（不含首次） |

---

## AI 配置与演示模式

### 文本模型（DeepSeek 或任意 OpenAI 兼容接口）

```dotenv
AI_TEXT_PROVIDER=deepseek
AI_TEXT_API_KEY=your_key_here
AI_TEXT_BASE_URL=https://api.deepseek.com/v1
AI_TEXT_MODEL=deepseek-chat
```

### 视觉模型（Qwen-VL / 阿里云百炼，OpenAI 兼容模式）

```dotenv
AI_VISION_PROVIDER=qwen
AI_VISION_API_KEY=your_key_here
AI_VISION_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
AI_VISION_MODEL=qwen-vl-max
```

### 三种运行策略

| `AI_DEMO_MODE` | 行为 |
| --- | --- |
| `auto`（默认） | 有对应 Key → 调用真实模型；没有 → 明确标记的本地演示模式 |
| `on` | 始终演示；不发起任何外部 AI 请求 |
| `off` | 严格模式；没有 Key 时返回 `503 AI_NOT_CONFIGURED`，不偷偷演示 |

所有 AI 响应都包含 `ai.mode = live | demo`、真实或演示 provider、notice 与 disclaimer。前端在结果区显示「演示模式 · 非真实模型结果」或「真实 AI 分析」。

演示模式的行为是透明的：

- 不声称读取了图片：任务/笔记图片识别返回 `confidence: 0.0` 和警告；
- 对用户自己的文本（作文、语法、句子）使用本地启发式规则，并标注不是模型结果；
- 成绩分析和笔记检查会明确说明检查范围有限；
- 不会自动修改用户数据；所有应用/保存都需要用户确认。

### AI Service 设计

`backend/services/ai_service.py` 统一处理：

- 文本 / 视觉能力、model/base URL/key 的配置读取；
- OpenAI-compatible `/chat/completions` 请求；
- JSON 提取（支持代码围栏、前缀文本）、字段归一化回调校验；
- JSON 格式错误有限次重试及反馈；
- 超时、限流、5xx、鉴权、请求拒绝的语义化错误；
- 不把 Key 暴露到响应/日志/错误消息。

`backend/services/ai_features.py` 是业务门面：每个工具拥有独立的 prompt、输出归一化与演示实现。真实模型的异常输出不会直接进入前端，必须先过归一化。

---

## 项目结构

```text
studyflow/
├── backend/
│   ├── app.py                 # Flask factory、静态前端、API 错误处理、蓝图注册
│   ├── config.py              # 环境变量配置
│   ├── db.py                  # 连接、schema 初始化、默认用户、meta
│   ├── schema.sql             # SQLite 表结构 + 索引
│   ├── routes/
│   │   ├── meta.py            # health/meta/settings/demo/export
│   │   ├── dashboard.py
│   │   ├── tasks.py           # 任务 CRUD + 规划
│   │   ├── grades.py          # 成绩 CRUD + analytics
│   │   ├── notes.py           # 笔记 CRUD + audit + graph
│   │   ├── ai.py              # AI 工具箱与识别
│   │   ├── uploads.py
│   │   ├── study.py           # 学习记录与成就
│   │   ├── flashcards.py
│   │   ├── errors.py
│   │   └── reports.py
│   ├── services/
│   │   ├── ai_service.py      # 统一 AI 网关
│   │   ├── ai_prompts.py
│   │   ├── ai_features.py     # 归一化 + 业务调用
│   │   ├── demo_ai.py         # 明确标注的本地演示
│   │   ├── achievements.py
│   │   ├── analytics.py
│   │   ├── dashboard.py
│   │   ├── planner.py         # 透明本地排期规则
│   │   ├── reports.py
│   │   └── demo_data.py
│   ├── utils/                 # 校验、响应、序列化、上传、时区
│   └── tests/                 # pytest 测试
├── frontend/
│   ├── index.html
│   ├── css/                   # 设计变量、组件、页面、响应式、打印
│   ├── js/
│   │   ├── api.js             # 统一 fetch 封装
│   │   ├── app.js             # 启动
│   │   ├── router.js          # hash 路由 + 页面 cleanup
│   │   ├── markdown.js        # marked + DOMPurify + KaTeX
│   │   ├── ui.js              # 统一样式/格式化 helper
│   │   ├── components/        # 布局、弹窗、toast、上传、任务弹窗、AI 显示
│   │   ├── services/          # store、Chart.js 配置
│   │   └── pages/             # 10 个页面模块
│   ├── assets/
│   └── vendor/                # 已本地化的第三方库与字体
├── data/                      # SQLite 与上传文件（运行时创建）
├── docs/
│   ├── API.md
│   └── screenshots/
├── scripts/
│   └── init_db.py
├── .env.example
├── requirements.txt
├── pytest.ini
├── run.py
├── start.bat / start.ps1 / start.sh
└── README.md
```

> 前端路由使用 hash（例如 `/#/planner`），因此 Flask 只需要托管静态文件和 API，不需要为每个 SPA 路由准备服务器重写规则。

---

## 数据库设计

SQLite，所有时间字段文本化存储 ISO 时间，业务日期为 `YYYY-MM-DD`；开启 `PRAGMA foreign_keys = ON`。

| 表 | 关键字段 |
| --- | --- |
| `users` | 用户、显示名、每日目标、番茄钟/休息分钟、时区 |
| `tasks` | 标题、学科、说明、截止、预计/实际分钟、难度、优先级、状态、计划日期/开始/时长、来源、AI 元信息 |
| `grades` | 学科、考试、得分、满分、日期、备注 |
| `notes` | 标题、学科、Markdown、来源图片、检查结果 JSON、知识图 JSON |
| `study_sessions` | 学科、任务、分钟数、类型、开始/结束、备注 |
| `achievements` | code、标题、描述、图标、解锁时间，`(user_id, code)` 唯一 |
| `error_records` | 学科、题目、作答、正确答案、错因、知识点 JSON、掌握状态 |
| `flashcards` | 正面、背面、学科、笔记关联、掌握度、复习次数、下次复习日 |
| `demo_records` | 跟踪演示种子创建的记录，仅用于安全清除演示数据 |
| `app_meta` | 演示种子/清除标记等元数据 |

额外说明：

- 每张业务表都有 `user_id` 外键与级联删除，当前单用户 ID 固定为 `1`，但结构可以直接扩展多用户。
- 建立了任务状态/截止日期/计划日期、成绩日期/学科、学习记录日期、闪卡下次复习等索引。
- 当前没有认证系统；部署到公网前必须添加认证、鉴权和 CSRF 保护。

---

## 测试与验证

后端测试：

```bash
python -m pytest
```

测试覆盖：

- health/meta/settings/静态页面托管/统一错误结构
- 任务 CRUD、完成/重开、规划预览与应用
- 成绩 CRUD、得分率、筛选、图表数据
- 笔记 CRUD、来源图片校验、AI 检查、知识图持久化
- 学习记录、成就、每日报告
- 闪卡 CRUD/复习间隔、错题 CRUD
- 演示数据载入/清除、只清演示数据、JSON 导出
- 上传文件真实性与安全校验
- 所有 AI 工具的演示模式，以及严格模式 `AI_NOT_CONFIGURED`
- 使用 fake HTTP session 测试 AI 网关的 JSON 修复、有限重试、鉴权错误不泄露 Key（不是外部 API 实测）

本次开发还使用无头 Chrome + CDP 做了真实浏览器联调：

- 10 个页面全部加载，无 JavaScript 运行错误
- 任务创建/完成、成绩创建/删除、智能排期生成与应用
- AI 润色、文件上传预览、AI 成绩分析、笔记 AI 检查
- 笔记创建/保存/删除、KaTeX 预览、Cytoscape 知识图
- 闪卡翻面评分、从笔记生成并保存
- 专注计时开始/暂停/提前结束并写入学习记录
- 确认弹窗的取消路径
- 390px 移动视口下主要页面无横向溢出，移动抽屉导航正常

### 真实外部 AI 未实测声明

**本开发环境没有配置真实的 DeepSeek / Qwen API Key，因此没有实际发起外部模型调用。**  
已通过真实 HTTP 客户端接口的 fake-session 单元测试验证统一网关的请求构造、鉴权错误、JSON 解析和重试逻辑，并通过演示模式验证所有端点的完整数据流。配置 Key 后，仍建议用一张真实作业图片与一篇真实作文做一次端到端冒烟测试，确认真实模型返回符合提示词 schema。

---

## 已知限制与未实测项

1. **单用户、无登录**。所有 API 默认访问默认用户，适合本地个人使用与后续扩展，不适合直接公网部署。
2. **真实 Qwen/DeepSeek 调用未实测**（无密钥）。模型名称与 base URL 均可在 `.env` 修改；如果供应商接口有额外字段差异，需要在 `ai_service.py` 调整。
3. **演示模式不执行真实 OCR**。图片识别只返回明显标记的示例结构，不会假装已识别图片内容。
4. **无后台任务队列**。AI 请求是同步的，受浏览器 fetch 90 秒和模型自身超时限制；大型视觉请求可能较慢。
5. **番茄钟不跨页面持续计时**。离开 Focus 页面会停止当前计时，建议完成一轮后离开或使用手动补录。
6. **知识图谱与笔记 PDF 等高级能力未做**。当前支持 Markdown 图片识别、检查、KaTeX 与 Cytoscape 交互图。
7. **UI 已可日常使用，但不是最终视觉打磨版本**。项目目标即为 Codex 后续继续精修留出结构，详见下节。
8. **无自动备份计划**。可在设置页导出 JSON；SQLite 文件也可直接备份。

---

## 后续开发接口（给 Codex）

项目刻意避免“所有逻辑塞进一个文件”，进一步开发建议：

### 后端扩展点

- `backend/routes/*.py`：按领域新增路由；统一使用 `utils.responses.success` 与 `utils.exceptions.APIError`。
- `backend/services/ai_features.py`：新增 AI 工具时，先写 prompt 与字段归一化，再在 `routes/ai.py` 注册薄路由。
- `backend/services/ai_service.py`：统一模型网关；不要在前端直接请求模型。
- 多用户化：从 `get_current_user_id()` 注入真实认证身份；各表已有 `user_id`。
- 更丰富的分析：`services/analytics.py` 与 `services/reports.py` 接收 user_id，可扩展周/月报告、导出。
- 规划算法：`services/planner.py` 是纯本地、可测试的规则层，可进一步加入休息间隔、分天排期。

### 前端扩展点

- 页面模块位于 `frontend/js/pages/`，每个页面导出 `{ title, render(container), cleanup() }`；路由切换会自动调用 `cleanup`。
- 新增页面：在 `app.js` 注册 route，在 `components/layout.js` 的 `NAV_GROUPS` 添加导航项即可。
- 所有 API 必须走 `frontend/js/api.js`，错误结构统一。
- 通用组件：`components/modal.js`、`toast.js`、`upload.js`、`task-modal.js`、`ai-display.js`。
- 设计 token 位于 `frontend/css/base.css`；优先复用 `.card`、`.btn`、`.field`、`.badge` 等组件样式。
- Markdown 渲染统一走 `frontend/js/markdown.js`（已内置 DOMPurify 与 KaTeX）。
- AI 输出展示必须使用 `ai-display.js`，不要隐藏 `demo` 标识。

### 可访问性与体验

- 给新的自定义控件补齐 `aria-*`、键盘操作和 focus 样式。
- 不要在页面内联巨型 HTML 片段；继续拆成页面 helper / 组件。
- 移动端尽量复用现有响应式模式，注意避免横向溢出。

---

## 常见问题

### `ModuleNotFoundError: No module named 'flask'`

```bash
# 确认激活了正确的虚拟环境
python -m pip install -r requirements.txt
```

Windows 激活：

```bat
.venv\Scripts\activate
```

### 端口被占用

```dotenv
PORT=5001
```

或在 PowerShell 临时设置：

```powershell
$env:PORT=5001
python run.py
```

### 页面显示「AI 演示模式」

- 检查 `.env` 中对应 `AI_*_API_KEY` 是否填写；
- 保持 `AI_DEMO_MODE=auto`；
- 修改 `.env` 后重启 Flask；
- 到设置页查看两种能力（文本/视觉）各自的 `effective_mode`。

### 严格模式返回 `503 AI_NOT_CONFIGURED`

说明 `AI_DEMO_MODE=off` 且缺少 Key。填入 Key，或改为 `auto` / `on`；也可以在该次请求的 JSON 里显式传 `{"demo": true}`。

### 上传图片失败

- 只支持 JPG/PNG/WebP，单张最大 8 MB；
- 图片必须能被 Pillow 正常读取；
- 检查 `UPLOAD_DIR` 是否存在写权限；
- 上传后只能把返回的 `/uploads/...` URL 传给 AI，外部 URL 会被拒绝。

### 如何清空所有本地数据？

先备份，再停止服务，删除数据库文件：

```powershell
# Windows PowerShell（确认路径后执行）
Remove-Item .\data\studyflow.db*
Remove-Item .\data\uploads\* -Exclude .gitkeep
python run.py
```

下次启动会重新创建数据库，并按 `SEED_DEMO` 决定是否写入演示数据。

### 浏览器控制台出现 Tailwind CDN 提示

项目使用的是本地化的 Tailwind 浏览器运行包，其控制台提示属于开发期提示，不影响功能。生产环境如需正式 Tailwind 构建，可后续用 Tailwind CLI 生成编译产物替换 `frontend/vendor/tailwind.min.js`。

### API 文档在哪里？

见 [docs/API.md](docs/API.md)。

---

## License / 使用说明

这是学习管理场景的 MVP 源码，默认按本地个人学习工具使用。第三方前端库保留各自原始许可证；如需商用，请自行检查依赖许可证、数据合规和 AI 服务条款。
