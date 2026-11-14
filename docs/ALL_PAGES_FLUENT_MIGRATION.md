# StudyFlow 全站 Fluent 迁移

状态：**Dashboard / Planner / Analytics / AI Toolbox / Notes / Focus / Flashcards / Errors / Reports 已完成迁移，等待验收。**

Settings 保持已验收版本，仅把主题偏好从“页面内主题”提升为全站主题；没有重写 Settings 的结构和组件规范。

## 设计基准

- Fluent UI Web Components `3.2.1`（本地固定资源）
- Fluent 2 Design Tokens + 项目 `--sf-*` 映射
- Mica 全页背景（分层色场，不以模糊冒充 Mica）
- Acrylic 临时浮层：共享 Modal、Toast、Settings Dialog / Dropdown
- 统一 Segoe UI / 微软雅黑字体栈
- 统一 6px 控件圆角、12px 卡片圆角、1px 描边、克制阴影
- 统一页面标题、页面操作、侧栏、移动端顶栏、页脚
- 完整浅色 / 深色主题
- `prefers-reduced-motion: reduce` 全站生效

## 九个页面的布局

没有把页面改成同一个卡片模板，原有信息架构和交互结构保留：

| 页面 | 保留并强化的布局 |
| --- | --- |
| Dashboard | 4 个 KPI + 今日任务主区 + 目标/最近成绩/快捷入口右栏 |
| Planner | 任务列表主面板 + 智能排期/今天优先右栏；保留弹窗表单 |
| Analytics | 筛选条 + KPI 条 + 双图表 + 学科对比 + 成绩表格 + AI 分析 |
| AI Toolbox | 工具导航栏 + 输入工作区 + 结果区 |
| Notes | 笔记列表 + Markdown/预览双栏 + 工具栏 + 知识图谱入口 |
| Focus | 中央计时器为视觉中心 + 右侧节奏/补录/记录 |
| Flashcards | 中央复习卡 + 右侧生成/方法 + 下方卡片管理 |
| Errors | 筛选 + 错题列表 + 折叠详情 + 底部方法提示 |
| Reports | 日期导航 + 学习摘要 Hero + 指标条 + 报告正文/建议栏 |

## 迁移前后截图

每页提供 1440×900 和 390×844 的迁移前后图；另有完整深色主题截图。

### Dashboard

- [迁移前 1440](screenshots/migration-before-dashboard-1440.png) / [迁移后 1440](screenshots/migration-after-dashboard-1440.png)
- [迁移前 390](screenshots/migration-before-dashboard-390.png) / [迁移后 390](screenshots/migration-after-dashboard-390.png)

### Planner

- [迁移前 1440](screenshots/migration-before-planner-1440.png) / [迁移后 1440](screenshots/migration-after-planner-1440.png)
- [迁移前 390](screenshots/migration-before-planner-390.png) / [迁移后 390](screenshots/migration-after-planner-390.png)

### Analytics

- [迁移前 1440](screenshots/migration-before-analytics-1440.png) / [迁移后 1440](screenshots/migration-after-analytics-1440.png)
- [迁移前 390](screenshots/migration-before-analytics-390.png) / [迁移后 390](screenshots/migration-after-analytics-390.png)

### AI Toolbox

- [迁移前 1440](screenshots/migration-before-ai-toolbox-1440.png) / [迁移后 1440](screenshots/migration-after-ai-toolbox-1440.png)
- [迁移前 390](screenshots/migration-before-ai-toolbox-390.png) / [迁移后 390](screenshots/migration-after-ai-toolbox-390.png)

### Notes

- [迁移前 1440](screenshots/migration-before-notes-1440.png) / [迁移后 1440](screenshots/migration-after-notes-1440.png)
- [迁移前 390](screenshots/migration-before-notes-390.png) / [迁移后 390](screenshots/migration-after-notes-390.png)
- [深色笔记工作区](screenshots/migration-after-notes-dark-1440.png)

### Focus

- [迁移前 1440](screenshots/migration-before-focus-1440.png) / [迁移后 1440](screenshots/migration-after-focus-1440.png)
- [迁移前 390](screenshots/migration-before-focus-390.png) / [迁移后 390](screenshots/migration-after-focus-390.png)

### Flashcards

- [迁移前 1440](screenshots/migration-before-flashcards-1440.png) / [迁移后 1440](screenshots/migration-after-flashcards-1440.png)
- [迁移前 390](screenshots/migration-before-flashcards-390.png) / [迁移后 390](screenshots/migration-after-flashcards-390.png)

### Errors

- [迁移前 1440](screenshots/migration-before-errors-1440.png) / [迁移后 1440](screenshots/migration-after-errors-1440.png)
- [迁移前 390](screenshots/migration-before-errors-390.png) / [迁移后 390](screenshots/migration-after-errors-390.png)

### Reports

- [迁移前 1440](screenshots/migration-before-reports-1440.png) / [迁移后 1440](screenshots/migration-after-reports-1440.png)
- [迁移前 390](screenshots/migration-before-reports-390.png) / [迁移后 390](screenshots/migration-after-reports-390.png)

### 深色主题与浮层

每页 1440 深色截图：

- [Dashboard](screenshots/migration-after-dashboard-dark-1440.png)
- [Planner](screenshots/migration-after-planner-dark-1440.png)
- [Analytics](screenshots/migration-after-analytics-dark-1440.png)
- [AI Toolbox](screenshots/migration-after-ai-toolbox-dark-1440.png)
- [Notes](screenshots/migration-after-notes-dark-1440.png)
- [Focus](screenshots/migration-after-focus-dark-1440.png)
- [Flashcards](screenshots/migration-after-flashcards-dark-1440.png)
- [Errors](screenshots/migration-after-errors-dark-1440.png)
- [Reports](screenshots/migration-after-reports-dark-1440.png)

其他：

- [Planner Acrylic Modal · 1440](screenshots/migration-planner-modal-1440.png)
- [Planner Modal · 390](screenshots/migration-planner-modal-390.png)
- [Analytics 深色成绩表格](screenshots/migration-analytics-table-dark-1440.png)
- [Settings 全站主题 · 浅色](screenshots/migration-settings-light-1440.png)
- [Settings 全站主题 · 深色](screenshots/migration-settings-dark-1440.png)

## 主题实现

- 首屏由 `index.html` 的极小内联脚本在 CSS 前读取偏好，避免深色闪白。
- `frontend/js/theme.js` 负责全站主题初始化、`meta[theme-color]` 和系统主题变化监听。
- Settings 的外观控件仍是主题入口：
  - `studyflow.settings.theme`
  - `studyflow.settings.follow-system`
  - `studyflow.settings.reduce-motion`
- 在 Settings 选择深色后离开页面，主题不再被 `cleanup()` 重置；Dashboard 等页面继续使用深色。
- Settings 重新进入时会从相同偏好恢复 Dropdown / Switch 状态。
- 深色 token 显式写入 `--sf-*`，即使当前页面没有加载 Fluent 组件 bundle，也能完整使用深色调色板。
- 图表在每次渲染时读取当前 Fluent token，深色下切换文字、网格、Tooltip 背景色。
- 系统的 `prefers-reduced-motion` 在九页全站生效。

## Fluent 组件使用情况

**Settings（已验收）**

- `fluent-button`
- `fluent-text-input` / `fluent-field`
- `fluent-dropdown` / `fluent-listbox` / `fluent-option`
- `fluent-switch`
- `fluent-checkbox`
- `fluent-tooltip`
- `fluent-dialog` / `fluent-dialog-body`

**其余九页**

- 使用 Fluent 2 tokens、`--sf-*` 变量、Mica/Acrylic、Fluent 控件几何与排版；
- 保留原生表单/按钮/Modal 元素，以保持原有事件绑定、表单验证、状态反馈和兼容性；
- **没有在九个页面重复加载 Fluent Web Components bundle**；Dashboard 等页面网络请求中没有 Fluent vendor；
- 这是本轮的明确兼容取舍：视觉与 token 已统一，但不是把每个原生控件替换成 `fluent-*` custom element。

如验收必须要求九页所有按钮/输入都成为 Fluent custom elements，需要下一轮逐页重建事件绑定，本轮未做，以避免破坏既有功能。

## CSS / 兼容性处理

- 新增 `fluent-global.css`，在旧样式之后加载，统一 shell、页面标题、按钮、输入、卡片、Tabs、Modal、Toast 和深色 surface。
- 所有页面原有布局网格、断点和业务 DOM 保留。
- `.card` surface 统一为 Fluent 12px 圆角，但不强制统一页面内部结构。
- 修复旧 `design-system.css` 中始终显示 `.sidebar-backdrop` 导致 320px 页面宽度增加的问题，关闭时不再参与布局。
- 修复 Errors 页 320px 下筛选 Tab 强制宽度导致页面横向溢出，改为内部横向滚动。
- 深色下单独处理：Dashboard/Reports 进度环、Notes Toast UI 编辑器、错误知识点标签、Analytics 表格、Charts、Modal。
- Acrylic 使用 `backdrop-filter` + `@supports` fallback；不支持时回到不透明 surface。
- 不依赖 Popover API 或 CSS Anchor Positioning；移动导航和 Modal 均沿用原有可靠实现。

## 测试结果

### 响应式矩阵

9 个页面 × 6 个视口 = **54 次加载**：

| 视口 | 结果 |
| --- | --- |
| 1920 × 1080 | 无横向溢出 |
| 1440 × 900 | 无横向溢出 |
| 1024 × 768 | 无横向溢出 |
| 768 × 1024 | 无横向溢出 |
| 390 × 844 | 无横向溢出 |
| 320 × 640 | 无横向溢出 |

- 移动顶栏在 ≤1180px 显示，>1180px 隐藏。
- 移动侧栏抽屉打开/关闭正常；关闭后 backdrop 不占布局。
- 图表 Canvas 宽度不超过父容器。
- 320px Errors 筛选条改为内部滚动，根页面无横向溢出。
- 390px Planner Modal 完整落在视口内，内容可滚动。

### 主题

- Settings 浅色 → 深色：通过
- 离开 Settings 后 Dashboard 保持深色：通过
- Dashboard 卡片/侧栏/页面背景深色：通过
- 返回 Settings 仍显示深色 Dropdown 和关闭的跟随系统：通过
- 打开跟随系统后回到浅色：通过
- Notes 在浅色下恢复正常：通过
- 深色 Notes Toast UI 正文/工具栏可见：通过
- 深色 Analytics 图表文字与表格可读：通过
- 深色 Modal：Acrylic `rgba(44,44,44,0.8)` + `blur(28px)`：通过

### 交互 / 功能

- Planner 新建任务 Modal 打开/关闭：通过
- Analytics 时间范围筛选切换：通过（3 个 Canvas 宽度均匹配父容器）
- Flashcards 翻面与评分按钮显示：通过
- Errors 详情展开：通过
- Settings 主题控件：通过
- 页面导航、移动抽屉：通过
- 页面级业务 JS 未改动（除 Charts 主题读取）；原有 API 请求和表单处理未改动

### 错误统计

- Console errors：**0**
- Uncaught exceptions：**0**
- Failed requests：**0**
- Dashboard 初始加载 Fluent vendor 请求：**0**
- 后端 pytest：**28 passed**

## 修改文件

- `frontend/index.html`（主题首屏脚本、全局 Fluent token/global CSS）
- `frontend/css/fluent/fluent-global.css`（新增）
- `frontend/css/fluent/studyflow-fluent-tokens.css`（显式深色 `--sf-*`）
- `frontend/js/theme.js`（新增全站主题 bridge）
- `frontend/js/app.js`（初始化全站主题）
- `frontend/js/services/charts.js`（Fluent token / 深色图表）
- `frontend/js/pages/settings.js`（主题改为全站保留；不再重复加载 token CSS）
- `docs/ALL_PAGES_FLUENT_MIGRATION.md`
- `docs/FLUENT_UI_INTEGRATION.md`
- `docs/SETTINGS_FLUENT_MIGRATION.md`
- `README.md`
- `docs/screenshots/migration-*.png`

没有修改：

- 后端 `.py`、API、SQLite schema、`.env`
- 九个页面的业务 JS
- 现有数据库内容
- 现有页面 DOM 结构与事件绑定

## 已知问题与限制

1. **九个页面没有逐控件替换成 Fluent Web Components**。它们使用 Fluent tokens、几何、Mica/Acrylic 和统一 CSS；原生控件保留是为了兼容现有事件、验证和反馈。Settings 使用完整 Fluent 组件。
2. 主题入口目前在 Settings；没有在侧栏新增全局主题按钮。
3. 如果系统主题在 Analytics 页面打开期间变化，已有 Chart.js 实例不会立即重绘；重新进入页面后会使用新主题。
4. 深色 Notes 依赖对 Toast UI 的 CSS 覆盖；升级 Toast UI 后需要重新检查。
5. 当前仅验证 Chrome 157；Edge/Firefox/Safari 未做跨浏览器回归。
6. Fluent bundle 仍为全量 42 组件（约 267 KB），但只在 Settings 加载。
7. 共享 Modal 保留原有可访问性实现，使用 Acrylic CSS，而不是 Fluent Dialog；Settings 清除演示数据 Dialog 使用 Fluent Dialog。
8. 手动“减少动画”偏好仍主要影响 Settings；系统级 `prefers-reduced-motion` 在全站生效。
9. Reports 保持 1400px 阅读宽度，以便长文阅读；其余页面在 1920 下使用最多 1600px。
