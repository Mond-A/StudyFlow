# Fluent UI Web Components 集成验证

状态：**技术验证通过；十个生产页面已完成 Fluent 设计系统迁移。**

这是一个隔离的组件实验室，不是静态原型，也不替代现有 StudyFlow 页面。它用于验证微软 Fluent UI Web Components 在原生 HTML/CSS/JS 项目中的注册、主题、材质、表单事件和响应式行为。

测试地址：`/lab/fluent-lab.html`  
测试页源码：`frontend/lab/fluent-lab.html`

---

## 1. 选型与固定版本

| 依赖 | 固定版本 | 说明 |
| --- | --- | --- |
| `@fluentui/web-components` | `3.2.1` | 官方 Web Components，MIT |
| `@fluentui/tokens` | `1.0.0-alpha.24` | 官方 light/dark token 对象 |
| `@microsoft/fast-element` | `3.0.0` | peer；已包含在官方预构建 bundle 中 |
| `@microsoft/focusgroup-polyfill` | `1.5.0` | peer；已包含在官方预构建 bundle 中 |
| `tslib` | `2.8.1` | 运行时依赖；已包含在官方预构建 bundle 中 |

本地资源：

```text
frontend/vendor/fluent/3.2.1/
  web-components.min.js        # 官方 pre-bundled distribution, 266,811 bytes
  tokens/lib/**/*.js           # 官方 token ESM 文件
  fluent-entry.js              # 本地 ESM bridge
  VENDOR.md                    # 版本、来源、SHA-256、复现方式
  THIRD_PARTY_NOTICES.md
  LICENSE-*.txt
```

没有 React、Vue、构建步骤或 CDN。页面通过原生 ES Modules 加载本地 bundle。

### 为什么选择预构建 bundle

官方 `web-components.min.js` 已包含 42 个组件和 Fast Element 运行时。当前实验室阶段优先验证行为，因此使用单文件 bundle；正式迁移时建议改成按组件构建，减少首屏体积。当前 bundle 不是 tree-shaken。

---

## 2. 组件映射

Fluent UI Web Components v3 的命名和设计稿中的旧名称不完全一致。以下以实际 `customElements.get()` 验证结果为准：

| 设计需求 | 实际元素 | 状态 |
| --- | --- | --- |
| Button | `fluent-button` | 已验证 |
| Text Field | `fluent-text-input` + `fluent-field` | 已验证 |
| Checkbox | `fluent-checkbox` | 已验证 |
| Switch | `fluent-switch` | 已验证 |
| Select | `fluent-dropdown` + `fluent-listbox` + `fluent-option` | 已验证 |
| Dialog | `fluent-dialog` + `fluent-dialog-body` | 已验证 |
| Menu | `fluent-menu` + `fluent-menu-button` + `fluent-menu-list` + `fluent-menu-item` | 已验证 |
| Tooltip | `fluent-tooltip` | 已验证 |
| Progress Bar | `fluent-progress-bar` | 已验证 |
| Progress Ring | `fluent-spinner` | **替代实现** |
| Accordion | `fluent-accordion` + `fluent-accordion-item` | 已验证 |

### Progress Ring

`@fluentui/web-components@3.2.1` 不提供 `fluent-progress-ring`。当前使用 `fluent-spinner` 表示不确定加载；确定性进度使用 `fluent-progress-bar`。

如果产品必须保留圆形确定进度，需要选择：

1. 使用 Fluent token 驱动的自有 SVG 圆环组件，并明确它不是微软官方组件；
2. 或评估旧版 Fluent Web Components，但不建议混用大版本；
3. 或改成进度条 + 百分比文本。

这个决定不应在迁移真实页面时隐式做出。

---

## 3. 主题、Mica 与 Acrylic

### Fluent 2 tokens

运行时使用官方 `webLightTheme` / `webDarkTheme` 调用 `Fluent.setTheme()`，获得真实的 Fluent token 变量。

项目自己的 token 层位于：

`frontend/css/fluent/studyflow-fluent-tokens.css`

所有页面级样式只使用 `--sf-*` 变量，再映射到 Fluent 官方 token。包括：

- 字体、字号、行高；
- 4px 基础间距；
- 4 / 6 / 8 / 12 / 16px 圆角；
- 中性色、品牌色、状态色；
- 阴影、动效时长与曲线；
- light/dark 主题；
- Mica / Acrylic 材质参数。

### Mica

`.sf-mica` 使用：

- 近不透明底色；
- 多层低对比度径向色场；
- 轻微的纹理线性层次；
- 深色主题单独配比。

**没有**用 `backdrop-filter` 冒充 Mica。导航栏实测 `backdrop-filter: none`。

### Acrylic

`.sf-acrylic` 默认使用实色 fallback；仅在浏览器支持时增加半透明背景和 `backdrop-filter`。

已应用到实验室中的：

- Dialog；
- Menu popover；
- 临时浮层示例。

实测：

- 导航 `backdrop-filter: none`；
- Menu `blur(24px) saturate(1.2)`；
- Dialog `blur(28px) saturate(1.2)`。

这不是 Windows 原生 Mica API，只是 Web CSS 模拟。

---

## 4. 重要兼容性发现

这些是实际集成时需要带进生产迁移的约束：

1. **Checkbox 与 Switch 没有默认文本 slot。**  
   文本必须放在外部 `<label for="...">` 中，或通过 `fluent-field` 组合。直接写 `<fluent-checkbox>标签</fluent-checkbox>` 不会显示标签。
2. **Dropdown 的初始 `value` attribute 不会自动选中。**  
   用户点击 `fluent-option` 后可正常得到 `value` 和 `change`。不要在组件升级前同步设置 `.value`；测试中过早设置会触发 Fluent 内部错误。生产页面应在 options 连接完成后，按组件 API 或用户选择设置值。
3. **Dialog 使用 `show()` / `hide()`，不是 host 上的 `open` attribute。**  
   原生 dialog 的打开状态在 shadow root 内。
4. **Menu 依赖 Popover API 和 CSS anchor positioning。**  
   Chromium 157 通过；正式发布前必须测试 Edge、Firefox、Safari 的支持范围。
5. **Fluent Button 的 delegated focus 在 headless Chrome 中没有触发 Tooltip 的 focus 监听。**  
   测试页使用原生 `<button>` 作为 Tooltip anchor，并额外提供 `focusin` / `focusout` bridge。生产迁移时不能假设任意自定义按钮都能自动触发 Tooltip 键盘焦点行为。
6. **Fluent 元素的表单关联可用。**  
   `fluent-text-input`、`fluent-dropdown`、`fluent-checkbox`、`fluent-switch` 都通过标准 `FormData` 提交，已验证 6 个字段。
7. **样式隔离来自 Shadow DOM。**  
   现有页面的全局 CSS 不会进入组件 shadow tree，但字体、颜色、token 等继承属性仍会影响 host。生产迁移需要逐页加载真实 CSS 回归，而不是只依赖实验室页面。

---

## 5. 验证结果

### 组件行为

- Button 样式变体渲染正常；
- Text Input + Field 标签正常；
- Checkbox / Switch 外部 label 点击可切换；
- Dropdown 打开、选择、关闭正常；
- Dialog `show()` / `hide()` 正常；
- Menu 打开、选择、关闭正常；
- Tooltip hover 正常；
- Progress Bar 值更新 64 → 72；
- Accordion 展开正常；
- `FormData` 得到 6 个字段：

```json
{
  "display_name": "Mona",
  "email": "mona@example.com",
  "goal": "120",
  "note": "组件验证",
  "weekly_report": "yes",
  "focus_mode": "on"
}
```

### 响应式

| 视口 | 横向溢出 | 布局结果 |
| --- | --- | --- |
| 1920 × 1080 | 无 | 1560px 窗口，完整侧栏，双列卡片 |
| 1440 × 900 | 无 | 完整侧栏，双列卡片 |
| 1024 × 768 | 无 | 侧栏保留，卡片改为全宽两列表单 |
| 768 × 1024 | 无 | 顶部导航，单列卡片 |
| 390 × 844 | 无 | 顶部导航换行，单列 |
| 320 × 640 | 无 | 单列，导航换行，无横向滚动 |

另外测试了同一文档的连续宽度变化：

```text
1920 → 1366 → 1024 → 900 → 768 → 640 → 480 → 390 → 320 → 1440
```

全部无横向溢出，断点切换稳定。

### 浏览器与运行时

- Chrome 157 / Windows，桌面与移动 emulation；
- 控制台错误：0；
- 未捕获异常：0；
- 失败网络请求：0；
- 页面自身没有 CDN 依赖；
- 现有 StudyFlow 10 个页面在 1440 / 390 下各 20 次加载：全部通过，0 console error，0 横向溢出；
- 后端 pytest：28 passed。

> 注：测试环境的 Kaspersky 安全组件注入了一次外部请求；页面代码、HTML、CSS、JS 中没有第三方 CDN URL。

---

## 6. 尚未解决

- 十个生产页面已统一使用 Fluent tokens、Mica/Acrylic 与全站主题；
- 九个页面保留原生控件并套用 Fluent 几何/tokens，未逐控件替换 `fluent-*`；
- Progress Ring 没有官方实现，当前用 Spinner / Progress Bar 替代；
- 完整 bundle 含全部 42 个组件，尚未做按组件 tree-shaking；
- Menu 的 Popover / anchor positioning 需要跨浏览器验证；
- Fluent tokens 包为 `1.0.0-alpha.24`，升级需要重新跑实验室；
- 实验室不测试 AI、SQLite 或真实表单提交，只验证 UI 组件与事件。

全站迁移细节见 `docs/ALL_PAGES_FLUENT_MIGRATION.md`；Settings 基准见 `docs/SETTINGS_FLUENT_MIGRATION.md`。

---

## 7. 迁移状态

1. **确认实验室视觉和组件选择**（已完成）。
2. Settings 已完成并验收（已完成）。
3. Dashboard / Planner / Analytics / AI Toolbox / Notes / Focus / Flashcards / Errors / Reports 已完成视觉迁移（已完成）。
4. 全站主题、响应式、弹窗、图表和 Notes 编辑器回归（已完成）。
5. 后续工作：跨浏览器回归、按组件打包、逐步替换可选的原生控件。

全站业务 API、Flask 路由、SQLite schema 和 `.env` 未改动。

---

## 8. 本地验证方式

启动 Flask 后直接访问：

```text
http://127.0.0.1:5000/lab/fluent-lab.html
```

页面标记了 `noindex,nofollow`。它只使用测试值，不调用 `/api/*`，不读取或写入业务数据。

版本与资源清单见 `frontend/vendor/fluent/3.2.1/VENDOR.md`。
