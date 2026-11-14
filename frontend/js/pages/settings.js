import { api } from "../api.js";
import { icon, refreshIcons } from "../components/icons.js";
import { showToast, toastError } from "../components/toast.js";
import { refreshCurrent } from "../router.js";
import { applyMeta } from "../components/layout.js";
import { getMeta, loadMeta } from "../services/store.js";
import { copyText } from "../markdown.js";
import { escapeHTML, formatDate, initials } from "../ui.js";

const DEMO_LABELS = {
  tasks: "任务",
  grades: "成绩",
  notes: "笔记",
  study_sessions: "学习记录",
  achievements: "成就",
  error_records: "错题",
  flashcards: "闪卡",
};

const ENV_SNIPPET = `# 服务端 .env
AI_DEMO_MODE=auto
AI_TEXT_PROVIDER=deepseek
AI_TEXT_API_KEY=your_text_key
AI_TEXT_BASE_URL=https://api.deepseek.com/v1
AI_TEXT_MODEL=deepseek-chat

AI_VISION_PROVIDER=qwen
AI_VISION_API_KEY=your_vision_key
AI_VISION_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
AI_VISION_MODEL=qwen-vl-max`;

const FLUENT_STYLES = [
  "/css/fluent/studyflow-fluent-tokens.css",
  "/css/settings-fluent.css",
];
const THEME_KEY = "studyflow.settings.theme";
const FOLLOW_SYSTEM_KEY = "studyflow.settings.follow-system";
const REDUCE_MOTION_KEY = "studyflow.settings.reduce-motion";
const FLUENT_ENTRY = "../../vendor/fluent/3.2.1/fluent-entry.js";

let pageController = null;
let pageEvents = null;
let settingsData = null;
let fluentApi = null;
let fluentPromise = null;
let stylePromise = null;
let themeMedia = null;
let motionMedia = null;
let systemThemeListener = null;
let followSystem = true;
let themeMode = "light";
let reduceMotion = false;

function loadStyles() {
  if (stylePromise) return stylePromise;
  stylePromise = Promise.all(FLUENT_STYLES.map((href) => new Promise((resolve, reject) => {
    const absolute = new URL(href, window.location.href).href;
    const existing = [...document.querySelectorAll("link[data-settings-fluent]")]
      .find((link) => link.href === absolute);
    if (existing) {
      if (existing.sheet) resolve();
      else {
        existing.addEventListener("load", resolve, { once: true });
        existing.addEventListener("error", () => reject(new Error(`无法加载 ${href}`)), { once: true });
      }
      return;
    }
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = href;
    link.dataset.settingsFluent = "true";
    link.addEventListener("load", resolve, { once: true });
    link.addEventListener("error", () => reject(new Error(`无法加载 ${href}`)), { once: true });
    document.head.append(link);
  }))).then(() => undefined);
  return stylePromise;
}

function loadFluent() {
  if (fluentPromise) return fluentPromise;
  fluentPromise = import(FLUENT_ENTRY).then((module) => {
    fluentApi = module;
    return module;
  });
  return fluentPromise;
}

async function ensureFluentAssets() {
  await Promise.all([loadStyles(), loadFluent()]);
  const tags = [
    "fluent-button", "fluent-text-input", "fluent-field", "fluent-dropdown",
    "fluent-listbox", "fluent-option", "fluent-switch", "fluent-checkbox",
    "fluent-dialog", "fluent-dialog-body", "fluent-tooltip",
  ];
  await Promise.all(tags.map((tag) => customElements.whenDefined(tag)));
  return fluentApi;
}

function systemTheme() {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function readThemePreferences() {
  themeMedia = window.matchMedia?.("(prefers-color-scheme: dark)");
  motionMedia = window.matchMedia?.("(prefers-reduced-motion: reduce)");
  let storedFollow = null;
  let storedTheme = null;
  let storedMotion = null;
  try {
    storedFollow = localStorage.getItem(FOLLOW_SYSTEM_KEY);
    storedTheme = localStorage.getItem(THEME_KEY);
    storedMotion = localStorage.getItem(REDUCE_MOTION_KEY);
  } catch (_) {}
  followSystem = storedFollow === null ? true : storedFollow === "true";
  themeMode = followSystem
    ? systemTheme()
    : storedTheme === "dark" || storedTheme === "light"
      ? storedTheme
      : systemTheme();
  reduceMotion = storedMotion === null ? Boolean(motionMedia?.matches) : storedMotion === "true";
}

function applyTheme(mode) {
  themeMode = mode === "dark" ? "dark" : "light";
  document.documentElement.dataset.theme = themeMode;
  if (fluentApi) {
    fluentApi.applyFluentTheme(themeMode === "dark" ? fluentApi.webDarkTheme : fluentApi.webLightTheme);
  }
  const themeMeta = document.querySelector('meta[name="theme-color"]');
  if (themeMeta) {
    themeMeta.content = themeMode === "dark" ? "#202020" : "#f3f2f1";
  }
}

function applyReducedMotion(enabled) {
  reduceMotion = Boolean(enabled);
  document.body.classList.toggle("sfl-reduce-motion", reduceMotion);
  document.documentElement.toggleAttribute("data-settings-reduce-motion", reduceMotion);
  const durations = {
    "--durationFaster": "1ms",
    "--durationFast": "1ms",
    "--durationNormal": "1ms",
    "--durationGentle": "1ms",
    "--durationSlow": "1ms",
  };
  for (const [token, value] of Object.entries(durations)) {
    if (reduceMotion) document.documentElement.style.setProperty(token, value);
    else document.documentElement.style.removeProperty(token);
  }
}

function persistThemePreferences() {
  try {
    localStorage.setItem(FOLLOW_SYSTEM_KEY, String(followSystem));
    localStorage.setItem(THEME_KEY, themeMode);
    localStorage.setItem(REDUCE_MOTION_KEY, String(reduceMotion));
  } catch (_) {}
}

function updateThemeSummary() {
  const summary = document.querySelector("#sfl-theme-summary");
  if (!summary) return;
  summary.textContent = followSystem
    ? `当前跟随系统 · ${themeMode === "dark" ? "深色" : "浅色"}`
    : `当前手动选择 · ${themeMode === "dark" ? "深色" : "浅色"}`;
}

function nextPaint() {
  return new Promise((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(resolve));
  });
}

async function setDropdownValue(dropdown, value) {
  if (!dropdown) return;
  await customElements.whenDefined("fluent-dropdown");
  await dropdown.updateComplete;
  await nextPaint();
  const index = (dropdown.options || []).findIndex((option) => option.value === value);
  if (index < 0) return;
  try {
    dropdown.selectOption(index, false);
  } catch (error) {
    console.warn("Fluent dropdown default selection failed", error);
  }
}

function getDropdownValue(dropdown) {
  if (!dropdown) return "";
  return dropdown.value
    || dropdown.selectedOptions?.[0]?.value
    || dropdown.querySelector("fluent-option[selected]")?.value
    || "";
}

function setButtonBusy(button, busy, text = "处理中…") {
  if (!button) return;
  if (busy) {
    if (!button.dataset.sflOriginalText) {
      button.dataset.sflOriginalText = button.textContent.trim();
    }
    button.disabled = true;
    button.textContent = text;
  } else {
    button.disabled = false;
    if (button.dataset.sflOriginalText) {
      button.textContent = button.dataset.sflOriginalText;
      delete button.dataset.sflOriginalText;
    }
  }
}

function engineCard(label, iconName, engine, envKey) {
  if (!engine) return "";
  const mode = engine.effective_mode || "unavailable";
  const modeLabel = mode === "live" ? "真实模型可用" : mode === "demo" ? "演示模式" : "未配置";
  return `<article class="sfl-engine sfl-engine-${mode}">
    <div class="sfl-engine-head">
      <span class="sfl-engine-icon">${icon(iconName)}</span>
      <div class="sfl-engine-title"><strong>${escapeHTML(label)}</strong><span>${modeLabel}</span></div>
      <span class="sfl-status-dot sfl-status-dot-${mode}" aria-hidden="true"></span>
    </div>
    <dl class="sfl-engine-details">
      <div><dt>服务商</dt><dd>${escapeHTML(engine.provider || "—")}</dd></div>
      <div><dt>模型</dt><dd>${escapeHTML(engine.model || "—")}</dd></div>
      <div><dt>密钥状态</dt><dd>${engine.configured ? "已在服务端配置" : "未配置"}</dd></div>
      <div><dt>环境变量</dt><dd><code>${escapeHTML(envKey)}</code></dd></div>
    </dl>
  </article>`;
}

function sectionHead(id, title, description, number) {
  return `<header class="sfl-section-head">
    <div>
      <h2 id="${id}-title">${title}</h2>
      <p>${description}</p>
    </div>
    <span class="sfl-section-number" aria-hidden="true">${number}</span>
  </header>`;
}

function navButton(target, iconName, label) {
  return `<button type="button" class="sfl-section-link" data-settings-target="${target}">
    <span class="sfl-section-link-icon">${icon(iconName)}</span>
    <span>${label}</span>
  </button>`;
}

function renderPage(container) {
  const user = settingsData.user;
  const ai = settingsData.ai || {};
  const demo = settingsData.demo || {};
  const meta = getMeta();
  const version = meta?.app?.version?.split("-")[0] || "0.7.0";
  const counts = demo.counts || {};
  const totalDemo = demo.total_records || 0;
  const textLive = ai.text?.effective_mode === "live";
  const visionLive = ai.vision?.effective_mode === "live";
  const live = textLive && visionLive;
  const aiState = live ? "live" : "demo";

  container.innerHTML = `
    <div class="page-shell sfl-settings-page">
      <header class="sfl-page-header">
        <div class="sfl-page-heading">
          <h1>设置</h1>
          <p>管理个人资料、学习偏好、外观与 AI 服务。设置只影响本地这份 StudyFlow 数据。</p>
        </div>
        <div class="sfl-page-actions">
          <a class="sfl-action-link" href="/api/health" target="_blank" rel="noopener">
            ${icon("heart-pulse")}<span>API 健康检查</span>
          </a>
        </div>
      </header>

      <div class="sfl-settings-layout">
        <nav class="sfl-section-nav" aria-label="设置分类">
          <p class="sfl-section-nav-label">设置分类</p>
          ${navButton("sfl-profile", "user-round", "个人资料")}
          ${navButton("sfl-preferences", "sliders-horizontal", "学习偏好")}
          ${navButton("sfl-appearance", "sun-moon", "外观")}
          ${navButton("sfl-ai", "bot", "AI 服务")}
          ${navButton("sfl-data", "database", "数据与导出")}
          ${navButton("sfl-about", "info", "关于")}
        </nav>

        <div class="sfl-settings-content">
          <section class="sfl-section" id="sfl-profile" aria-labelledby="sfl-profile-title">
            ${sectionHead("sfl-profile", "个人资料", "用于首页问候、界面显示和本地账号标识。", "01")}
            <div class="sfl-profile-layout">
              <aside class="sfl-profile-preview" aria-label="个人资料预览">
                <span class="sfl-avatar" id="sfl-avatar" style="background:${escapeHTML(user.avatar_color || "#2563eb")}">${initials(user.display_name)}</span>
                <strong id="sfl-profile-name">${escapeHTML(user.display_name || "同学")}</strong>
                <span id="sfl-profile-email">${escapeHTML(user.email || "本地学习空间")}</span>
                <span class="sfl-profile-since" title="加入日期">${icon("calendar")} ${formatDate(user.created_at?.slice(0, 10), { withYear: true })}</span>
                <div class="sfl-profile-stats">
                  <div><strong>${user.daily_goal_minutes}m</strong><span>每日目标</span></div>
                  <div><strong>${user.pomodoro_minutes}m</strong><span>番茄钟</span></div>
                </div>
              </aside>

              <form id="profile-form" class="sfl-form">
                <div class="sfl-field-grid">
                  <fluent-field class="sfl-field">
                    <label slot="label" for="sfl-display-name">显示名称</label>
                    <fluent-text-input slot="input" id="sfl-display-name" name="display_name" value="${escapeHTML(user.display_name || "")}" maxlength="40" required></fluent-text-input>
                  </fluent-field>
                  <fluent-field class="sfl-field">
                    <label slot="label" for="sfl-email">邮箱（可选）</label>
                    <fluent-text-input slot="input" id="sfl-email" name="email" type="email" value="${escapeHTML(user.email || "")}" maxlength="120" placeholder="用于标识，不会发送邮件"></fluent-text-input>
                  </fluent-field>
                  <fluent-field class="sfl-field">
                    <label slot="label" for="sfl-avatar-color">头像颜色</label>
                    <div slot="input" class="sfl-color-control">
                      <input id="sfl-avatar-color" name="avatar_color" type="color" value="${escapeHTML(user.avatar_color || "#2563eb")}">
                      <span id="sfl-avatar-color-value">${escapeHTML(user.avatar_color || "#2563eb")}</span>
                    </div>
                  </fluent-field>
                  <div class="sfl-readonly-field">
                    <span>账号</span>
                    <strong>${escapeHTML(user.username)} · 单用户本地模式</strong>
                  </div>
                </div>
                <div class="sfl-form-actions">
                  <fluent-button id="sfl-save-profile" type="submit" appearance="primary">保存资料</fluent-button>
                  <span class="sfl-form-status" id="sfl-profile-status" role="status"></span>
                </div>
              </form>
            </div>
          </section>

          <section class="sfl-section" id="sfl-preferences" aria-labelledby="sfl-preferences-title">
            ${sectionHead("sfl-preferences", "学习偏好", "影响首页目标、番茄钟和报告中的时间计算。", "02")}
            <form id="preferences-form" class="sfl-form">
              <div class="sfl-field-grid sfl-field-grid-4">
                <fluent-field class="sfl-field">
                  <label slot="label" for="sfl-daily-goal">每日学习目标（分钟）</label>
                  <fluent-text-input slot="input" id="sfl-daily-goal" name="daily_goal_minutes" type="number" value="${user.daily_goal_minutes}" inputmode="numeric"></fluent-text-input>
                  <span slot="message">15–720 分钟</span>
                </fluent-field>
                <fluent-field class="sfl-field">
                  <label slot="label" for="sfl-pomodoro">番茄钟时长（分钟）</label>
                  <fluent-text-input slot="input" id="sfl-pomodoro" name="pomodoro_minutes" type="number" value="${user.pomodoro_minutes}" inputmode="numeric"></fluent-text-input>
                  <span slot="message">1–120 分钟</span>
                </fluent-field>
                <fluent-field class="sfl-field">
                  <label slot="label" for="sfl-short-break">短休息（分钟）</label>
                  <fluent-text-input slot="input" id="sfl-short-break" name="short_break_minutes" type="number" value="${user.short_break_minutes}" inputmode="numeric"></fluent-text-input>
                  <span slot="message">1–60 分钟</span>
                </fluent-field>
                <fluent-field class="sfl-field">
                  <label slot="label" for="sfl-long-break">长休息（分钟）</label>
                  <fluent-text-input slot="input" id="sfl-long-break" name="long_break_minutes" type="number" value="${user.long_break_minutes}" inputmode="numeric"></fluent-text-input>
                  <span slot="message">1–120 分钟</span>
                </fluent-field>
              </div>
              <div class="sfl-form-actions">
                <fluent-button id="sfl-save-preferences" type="submit" appearance="primary">保存偏好</fluent-button>
                <span class="sfl-form-status" id="sfl-preferences-status" role="status"></span>
              </div>
            </form>
          </section>

          <section class="sfl-section" id="sfl-appearance" aria-labelledby="sfl-appearance-title">
            ${sectionHead("sfl-appearance", "外观", "主题与动效偏好只保存在当前浏览器，不写入 SQLite。", "03")}
            <div class="sfl-appearance-grid">
              <fluent-field class="sfl-field">
                <label slot="label" for="sfl-theme-dropdown">主题</label>
                <fluent-dropdown slot="input" id="sfl-theme-dropdown" placeholder="选择主题">
                  <fluent-listbox class="sfl-acrylic-popover">
                    <fluent-option value="light">浅色</fluent-option>
                    <fluent-option value="dark">深色</fluent-option>
                  </fluent-listbox>
                </fluent-dropdown>
                <span slot="message" id="sfl-theme-summary">当前跟随系统</span>
              </fluent-field>
              <div class="sfl-toggle-row">
                <div><strong>跟随系统主题</strong><p>自动跟随 Windows 或浏览器的深浅色设置。</p></div>
                <label class="sfl-inline-label" for="sfl-follow-system">
                  <fluent-switch id="sfl-follow-system"></fluent-switch>
                  <span>跟随系统</span>
                </label>
              </div>
              <div class="sfl-toggle-row">
                <div><strong>减少动画效果</strong><p>降低页面切换、卡片和控件的动效。</p></div>
                <label class="sfl-inline-label" for="sfl-reduce-motion">
                  <fluent-checkbox id="sfl-reduce-motion"></fluent-checkbox>
                  <span>减少动画</span>
                </label>
              </div>
            </div>
          </section>

          <section class="sfl-section" id="sfl-ai" aria-labelledby="sfl-ai-title">
            ${sectionHead("sfl-ai", "AI 服务", "API Key 只存放在 Flask 后端环境变量中。", "04")}
            <div class="sfl-section-tools">
              <span class="sfl-status-pill sfl-status-${aiState}">
                <span class="sfl-status-dot sfl-status-dot-${aiState}" aria-hidden="true"></span>
                ${live ? "真实模型可用" : "演示或未配置"}
              </span>
              <button type="button" class="sfl-help-button" id="sfl-api-help" aria-label="API Key 保存位置说明">${icon("circle-help")}</button>
              <fluent-tooltip anchor="sfl-api-help" delay="140">API Key 只保存在服务端环境变量中，浏览器不会收到。</fluent-tooltip>
            </div>
            <div class="sfl-infobar sfl-infobar-${aiState}">
              <span class="sfl-infobar-icon">${icon(live ? "sparkles" : "flask-conical")}</span>
              <div>
                <strong>${live ? "真实 AI 分析" : "演示模式 · 非真实模型结果"}</strong>
                <p>${live ? "文本与视觉模型均已连接真实 API。AI 输出仅供参考。" : "至少一个 AI 能力处于演示或未配置状态；演示结果会明确标记。"}</p>
              </div>
            </div>
            <div class="sfl-engine-grid">
              ${engineCard("文本模型", "message-square-text", ai.text, "AI_TEXT_API_KEY")}
              ${engineCard("视觉模型", "image", ai.vision, "AI_VISION_API_KEY")}
            </div>
            <div class="sfl-policy-row">
              <span>运行策略</span><code>AI_DEMO_MODE=${escapeHTML(ai.policy || "auto")}</code>
              <span class="sfl-muted">auto：有 Key 用真实模型，否则演示 · on：始终演示 · off：未配置时返回错误</span>
            </div>
            <details class="sfl-details">
              <summary>${icon("key-round")} 如何配置真实 AI？</summary>
              <div class="sfl-details-body">
                <p>在项目根目录复制 <code>.env.example</code> 为 <code>.env</code>，填写密钥后重启 Flask。所有密钥只保留在服务端，前端不会收到。</p>
                <pre>${escapeHTML(ENV_SNIPPET)}</pre>
                <div class="sfl-inline-actions">
                  <fluent-button id="sfl-copy-env" appearance="outline" size="small">复制配置模板</fluent-button>
                  <span class="sfl-muted">修改后需要重启服务；演示模式不会发起外部请求。</span>
                </div>
              </div>
            </details>
          </section>

          <section class="sfl-section" id="sfl-data" aria-labelledby="sfl-data-title">
            ${sectionHead("sfl-data", "数据与导出", "演示数据可随时清除，不会影响你自己创建的内容。", "05")}
            <div class="sfl-demo-summary">
              <div>
                <strong>${totalDemo ? `已载入 ${totalDemo} 条演示记录` : "当前没有演示数据"}</strong>
                <p>${totalDemo ? "清除时只会删除标记为演示的数据，真实数据会保留。" : "如果需要完整界面示例，可以载入少量任务、成绩、笔记与学习记录。"}</p>
              </div>
              <span class="sfl-demo-badge ${totalDemo ? "is-loaded" : ""}">${totalDemo ? "演示数据已载入" : "干净空间"}</span>
            </div>
            ${Object.keys(counts).length ? `<div class="sfl-demo-counts">${Object.entries(counts).map(([key, count]) => `<div><strong>${count}</strong><span>${escapeHTML(DEMO_LABELS[key] || key)}</span></div>`).join("")}</div>` : ""}
            <div class="sfl-action-row">
              <fluent-button id="sfl-load-demo" appearance="outline" ${totalDemo ? "disabled" : ""}>载入演示数据</fluent-button>
              <fluent-button id="sfl-clear-demo" appearance="outline" class="sfl-danger-button" ${totalDemo ? "" : "disabled"}>清除演示数据</fluent-button>
              <a class="sfl-action-link sfl-action-link-small" href="/api/export" download>${icon("download")}<span>导出全部数据 JSON</span></a>
            </div>
            <p class="sfl-fineprint">${icon("shield-check")} 导出文件包含任务、成绩、笔记、学习记录等个人数据，请妥善保管。</p>
          </section>

          <section class="sfl-section" id="sfl-about" aria-labelledby="sfl-about-title">
            ${sectionHead("sfl-about", "关于 StudyFlow", "本地运行的产品信息与数据边界。", "06")}
            <div class="sfl-about-grid">
              <article class="sfl-about-card">
                <h3>系统信息</h3>
                <dl>
                  <div><dt>版本</dt><dd>${escapeHTML(version)}</dd></div>
                  <div><dt>数据存储</dt><dd>SQLite 本地文件</dd></div>
                  <div><dt>前端</dt><dd>原生 JS + Fluent Web Components</dd></div>
                  <div><dt>后端</dt><dd>Python Flask REST API</dd></div>
                </dl>
              </article>
              <article class="sfl-about-card">
                <h3>${icon("lock")} 隐私</h3>
                <p>学习数据默认保存在本机 SQLite。AI 请求会把必要的文本或图片发送给配置的第三方模型服务；演示模式不发起外部请求。</p>
              </article>
              <article class="sfl-about-card">
                <h3>${icon("file-code-2")} 开发者接口</h3>
                <p>REST API 前缀为 <code>/api</code>。完整接口说明见项目根目录 <code>docs/API.md</code>，本页面不会修改 API。</p>
              </article>
            </div>
          </section>
        </div>
      </div>
    </div>

    <fluent-dialog id="sfl-clear-dialog" class="sfl-dialog" aria-labelledby="sfl-clear-title">
      <fluent-dialog-body>
        <h2 slot="title" id="sfl-clear-title">清除演示数据</h2>
        <p>确定清除所有标记为演示的记录吗？你手动创建的任务、成绩、笔记等不会被删除。此操作无法撤销。</p>
        <fluent-button slot="action" id="sfl-clear-cancel" appearance="outline">取消</fluent-button>
        <fluent-button slot="action" id="sfl-clear-confirm" appearance="primary">清除演示数据</fluent-button>
      </fluent-dialog-body>
    </fluent-dialog>
  `;

  refreshIcons(container);
  bindProfileForm(container);
  bindPreferencesForm(container);
  bindDataActions(container);
  bindSectionNav(container);
}

function bindProfileForm(container) {
  const form = container.querySelector("#profile-form");
  const colorInput = form.querySelector('input[name="avatar_color"]');
  const colorValue = form.querySelector("#sfl-avatar-color-value");
  colorInput?.addEventListener("input", () => {
    const avatar = container.querySelector("#sfl-avatar");
    if (avatar) avatar.style.background = colorInput.value;
    if (colorValue) colorValue.textContent = colorInput.value;
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(form);
    const button = form.querySelector("#sfl-save-profile");
    const status = form.querySelector("#sfl-profile-status");
    setButtonBusy(button, true, "保存中…");
    if (status) status.textContent = "正在保存到本地 SQLite…";
    try {
      const response = await api.put("/settings", {
        display_name: String(formData.get("display_name") || "").trim(),
        email: String(formData.get("email") || "").trim(),
        avatar_color: formData.get("avatar_color"),
      });
      settingsData.user = response.data.user;
      const meta = await loadMeta({ force: true });
      applyMeta(meta);
      const avatar = container.querySelector("#sfl-avatar");
      if (avatar) {
        avatar.textContent = initials(response.data.user.display_name);
        avatar.style.background = response.data.user.avatar_color || "#2563eb";
      }
      const name = container.querySelector("#sfl-profile-name");
      if (name) name.textContent = response.data.user.display_name;
      const email = container.querySelector("#sfl-profile-email");
      if (email) email.textContent = response.data.user.email || "本地学习空间";
      if (status) status.textContent = "资料已保存";
      showToast("个人资料已保存");
    } catch (error) {
      if (status) status.textContent = "";
      toastError(error);
    } finally {
      setButtonBusy(button, false);
    }
  });
}

function bindPreferencesForm(container) {
  const form = container.querySelector("#preferences-form");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(form);
    const values = {
      daily_goal_minutes: Number(formData.get("daily_goal_minutes")),
      pomodoro_minutes: Number(formData.get("pomodoro_minutes")),
      short_break_minutes: Number(formData.get("short_break_minutes")),
      long_break_minutes: Number(formData.get("long_break_minutes")),
    };
    const ranges = {
      daily_goal_minutes: [15, 720, "每日学习目标"],
      pomodoro_minutes: [1, 120, "番茄钟时长"],
      short_break_minutes: [1, 60, "短休息"],
      long_break_minutes: [1, 120, "长休息"],
    };
    for (const [key, [minimum, maximum, label]] of Object.entries(ranges)) {
      if (!Number.isInteger(values[key]) || values[key] < minimum || values[key] > maximum) {
        showToast(`${label}必须是 ${minimum}–${maximum} 之间的整数分钟`, "error");
        return;
      }
    }
    const button = form.querySelector("#sfl-save-preferences");
    const status = form.querySelector("#sfl-preferences-status");
    setButtonBusy(button, true, "保存中…");
    if (status) status.textContent = "正在保存到本地 SQLite…";
    try {
      const response = await api.put("/settings", values);
      settingsData.user = response.data.user;
      const meta = await loadMeta({ force: true });
      applyMeta(meta);
      if (status) status.textContent = "偏好已保存";
      showToast("学习偏好已保存");
    } catch (error) {
      if (status) status.textContent = "";
      toastError(error);
    } finally {
      setButtonBusy(button, false);
    }
  });
}

function bindDataActions(container) {
  const loadButton = container.querySelector("#sfl-load-demo");
  const clearButton = container.querySelector("#sfl-clear-demo");
  const clearDialog = container.querySelector("#sfl-clear-dialog");
  const clearCancel = container.querySelector("#sfl-clear-cancel");
  const clearConfirm = container.querySelector("#sfl-clear-confirm");

  loadButton?.addEventListener("click", async () => {
    setButtonBusy(loadButton, true, "载入中…");
    try {
      const response = await api.post("/demo/load", {});
      showToast(response.message || "演示数据已载入");
      refreshCurrent({ preserveScroll: true });
    } catch (error) {
      toastError(error);
      setButtonBusy(loadButton, false);
    }
  });

  clearButton?.addEventListener("click", () => {
    clearDialog?.show();
  });
  clearCancel?.addEventListener("click", () => {
    clearDialog?.hide();
  });
  clearConfirm?.addEventListener("click", async () => {
    clearDialog?.hide();
    setButtonBusy(clearButton, true, "清除中…");
    try {
      const response = await api.delete("/demo/clear");
      showToast(response.message || "演示数据已清除");
      refreshCurrent({ preserveScroll: true });
    } catch (error) {
      toastError(error);
      setButtonBusy(clearButton, false);
    }
  });

  container.querySelector("#sfl-copy-env")?.addEventListener("click", async () => {
    try {
      await copyText(ENV_SNIPPET);
      showToast("配置模板已复制，请粘贴到服务端 .env");
    } catch {
      toastError(new Error("复制失败，请手动选择配置文本"));
    }
  });
}

function bindSectionNav(container) {
  const buttons = [...container.querySelectorAll("[data-settings-target]")];
  const sections = buttons
    .map((button) => container.querySelector(`#${button.dataset.settingsTarget}`))
    .filter(Boolean);
  if (!buttons.length || !sections.length) return;

  const setActive = (id) => {
    for (const button of buttons) {
      const active = button.dataset.settingsTarget === id;
      button.classList.toggle("is-active", active);
      if (active) button.setAttribute("aria-current", "true");
      else button.removeAttribute("aria-current");
    }
  };

  const updateFromScroll = () => {
    const marker = window.scrollY + Math.min(320, Math.max(220, window.innerHeight * 0.35));
    let active = sections[0]?.id;
    for (const section of sections) {
      const top = section.getBoundingClientRect().top + window.scrollY;
      if (top <= marker) active = section.id;
    }
    setActive(active);
  };

  let scheduled = false;
  const onScroll = () => {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      updateFromScroll();
    });
  };
  window.addEventListener("scroll", onScroll, { passive: true, signal: pageEvents.signal });
  window.addEventListener("resize", onScroll, { signal: pageEvents.signal });

  for (const button of buttons) {
    button.addEventListener("click", () => {
      const section = container.querySelector(`#${button.dataset.settingsTarget}`);
      if (!section) return;
      section.scrollIntoView({
        behavior: reduceMotion ? "auto" : "smooth",
        block: "start",
      });
      setActive(button.dataset.settingsTarget);
    });
  }
  updateFromScroll();
}

async function hydrateFluentControls(container) {
  const themeDropdown = container.querySelector("#sfl-theme-dropdown");
  const followSwitch = container.querySelector("#sfl-follow-system");
  const motionCheckbox = container.querySelector("#sfl-reduce-motion");
  const tooltip = container.querySelector("#sfl-api-tooltip") || container.querySelector("fluent-tooltip");
  const helpButton = container.querySelector("#sfl-api-help");

  await setDropdownValue(themeDropdown, themeMode);
  if (followSwitch) followSwitch.checked = followSystem;
  if (motionCheckbox) motionCheckbox.checked = reduceMotion;
  updateThemeSummary();

  themeDropdown?.addEventListener("change", () => {
    // Choosing a concrete theme is an explicit override of system following.
    if (followSystem) {
      followSystem = false;
      if (followSwitch) followSwitch.checked = false;
    }
    const next = getDropdownValue(themeDropdown) === "dark" ? "dark" : "light";
    applyTheme(next);
    applyReducedMotion(reduceMotion);
    persistThemePreferences();
    updateThemeSummary();
  });

  followSwitch?.addEventListener("change", async () => {
    followSystem = Boolean(followSwitch.checked);
    persistThemePreferences();
    const next = followSystem ? systemTheme() : themeMode;
    applyTheme(next);
    applyReducedMotion(reduceMotion);
    await setDropdownValue(themeDropdown, next);
    updateThemeSummary();
  });

  motionCheckbox?.addEventListener("change", () => {
    applyReducedMotion(Boolean(motionCheckbox.checked));
    persistThemePreferences();
  });

  if (themeMedia && !systemThemeListener) {
    systemThemeListener = () => {
      if (!followSystem) return;
      const next = systemTheme();
      applyTheme(next);
      applyReducedMotion(reduceMotion);
      setDropdownValue(themeDropdown, next);
      updateThemeSummary();
    };
    themeMedia.addEventListener?.("change", systemThemeListener);
  }

  if (tooltip && helpButton) {
    // Native anchors keep keyboard focus reliable; mirror it to the Fluent tooltip.
    helpButton.addEventListener("focusin", () => tooltip.showTooltip(0));
    helpButton.addEventListener("focusout", () => tooltip.hideTooltip(0));
  }
}

function cleanup() {
  pageController?.abort();
  pageController = null;
  pageEvents?.abort();
  pageEvents = null;
  if (themeMedia && systemThemeListener) {
    themeMedia.removeEventListener?.("change", systemThemeListener);
    systemThemeListener = null;
  }
  themeMedia = null;
  motionMedia = null;
  document.documentElement.removeAttribute("data-theme");
  document.documentElement.removeAttribute("data-settings-reduce-motion");
  document.body.classList.remove("sfl-reduce-motion");
  const durations = ["--durationFaster", "--durationFast", "--durationNormal", "--durationGentle", "--durationSlow"];
  for (const token of durations) document.documentElement.style.removeProperty(token);
  if (fluentApi) {
    fluentApi.applyFluentTheme(fluentApi.webLightTheme);
  }
  const themeMeta = document.querySelector('meta[name="theme-color"]');
  if (themeMeta) themeMeta.content = "#f3f2f1";
}

async function render(container) {
  cleanup();
  pageController = new AbortController();
  pageEvents = new AbortController();
  try {
    const [response] = await Promise.all([
      api.get("/settings", undefined, { signal: pageController.signal }),
      ensureFluentAssets(),
    ]);
    if (pageController.signal.aborted) return;
    settingsData = response.data;
    readThemePreferences();
    applyTheme(themeMode);
    applyReducedMotion(reduceMotion);
    renderPage(container);
    refreshIcons(container);
    await hydrateFluentControls(container);
  } catch (error) {
    if (error.name === "AbortError") return;
    throw error;
  }
}

export default {
  title: "设置",
  render,
  cleanup,
};
