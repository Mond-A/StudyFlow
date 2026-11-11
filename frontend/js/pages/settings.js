import { api } from "../api.js";
import { icon, refreshIcons } from "../components/icons.js";
import { openConfirm } from "../components/modal.js";
import { aiBanner, aiModeBadge } from "../components/ai-display.js";
import { showToast, toastError } from "../components/toast.js";
import { refreshCurrent } from "../router.js";
import { applyMeta } from "../components/layout.js";
import { getMeta, loadMeta } from "../services/store.js";
import { copyText } from "../markdown.js";
import { escapeHTML, formatDate, initials, setButtonLoading } from "../ui.js";

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

let pageController = null;
let settingsData = null;

function engineCard(label, iconName, engine, envKey) {
  if (!engine) return "";
  const mode = engine.effective_mode || "unavailable";
  const modeLabel = mode === "live" ? "真实模型可用" : mode === "demo" ? "演示模式" : "未配置";
  return `<article class="engine-card engine-${mode}">
    <div class="engine-card-head">
      <span class="engine-card-icon">${icon(iconName)}</span>
      <div><strong>${escapeHTML(label)}</strong><span class="engine-state">${modeLabel}</span></div>
      <span class="engine-dot ${mode === "live" ? "is-live" : mode === "demo" ? "is-demo" : ""}"></span>
    </div>
    <dl class="engine-details">
      <div><dt>服务商</dt><dd>${escapeHTML(engine.provider || "—")}</dd></div>
      <div><dt>模型</dt><dd>${escapeHTML(engine.model || "—")}</dd></div>
      <div><dt>密钥状态</dt><dd>${engine.configured ? "已在服务端配置" : "未配置"}</dd></div>
      <div><dt>环境变量</dt><dd><code>${escapeHTML(envKey)}</code></dd></div>
    </dl>
  </article>`;
}

function renderPage(container) {
  const user = settingsData.user;
  const ai = settingsData.ai;
  const demo = settingsData.demo;
  const meta = getMeta();
  const version = meta?.app?.version || "MVP";
  const counts = demo.counts || {};
  const totalDemo = demo.total_records || 0;

  container.innerHTML = `
    <div class="page-shell settings-page">
      <header class="page-header">
        <div class="page-heading">
          <p class="eyebrow">SETTINGS · 设置</p>
          <h1>让 StudyFlow 更贴合你的节奏</h1>
          <p class="page-subtitle">管理个人偏好、查看 AI 服务状态与本地数据。你的 AI Key 永远不会出现在浏览器中。</p>
        </div>
        <div class="page-actions">
          <a class="btn btn-secondary" href="/api/health" target="_blank" rel="noopener">${icon("heart-pulse")}<span>API 健康检查</span></a>
        </div>
      </header>

      <div class="settings-layout">
        <div class="settings-main">
          <section class="card settings-card">
            <div class="card-header">
              <div><h2 class="card-title">${icon("user-round")} 个人资料</h2><p class="card-subtitle">用于首页问候和界面显示。</p></div>
            </div>
            <form id="profile-form" class="form-stack">
              <div class="profile-edit-row">
                <span class="avatar avatar-lg" id="settings-avatar" style="background:${escapeHTML(
                  user.avatar_color || "#2563eb"
                )}">${initials(user.display_name)}</span>
                <div class="form-grid form-grid-2 profile-fields">
                  <label class="field"><span class="field-label">显示名称</span><input class="input" name="display_name" maxlength="40" required value="${escapeHTML(
                    user.display_name || ""
                  )}"></label>
                  <label class="field"><span class="field-label">邮箱（可选）</span><input class="input" type="email" name="email" maxlength="120" value="${escapeHTML(
                    user.email || ""
                  )}" placeholder="用于标识，不会发送邮件"></label>
                  <label class="field"><span class="field-label">头像颜色</span><input class="input color-input" type="color" name="avatar_color" value="${escapeHTML(
                    user.avatar_color || "#2563eb"
                  )}"></label>
                  <div class="field"><span class="field-label">账号</span><span class="read-only-value">${escapeHTML(
                    user.username
                  )} · 单用户本地模式</span></div>
                </div>
              </div>
              <div class="form-actions">
                <button type="submit" class="btn btn-primary" data-submit>${icon("save")} 保存资料</button>
              </div>
            </form>
          </section>

          <section class="card settings-card">
            <div class="card-header">
              <div><h2 class="card-title">${icon("sliders-horizontal")} 学习偏好</h2><p class="card-subtitle">影响每日目标、番茄钟和休息时长。</p></div>
            </div>
            <form id="preferences-form" class="form-stack">
              <div class="form-grid form-grid-2">
                <label class="field"><span class="field-label">每日学习目标（分钟）</span><input class="input" type="number" name="daily_goal_minutes" min="15" max="720" step="5" value="${
                  user.daily_goal_minutes
                }"><span class="field-hint">首页目标环与报告会使用这个数值。</span></label>
                <label class="field"><span class="field-label">番茄钟时长（分钟）</span><input class="input" type="number" name="pomodoro_minutes" min="1" max="120" value="${
                  user.pomodoro_minutes
                }"></label>
                <label class="field"><span class="field-label">短休息（分钟）</span><input class="input" type="number" name="short_break_minutes" min="1" max="60" value="${
                  user.short_break_minutes
                }"></label>
                <label class="field"><span class="field-label">长休息（分钟）</span><input class="input" type="number" name="long_break_minutes" min="1" max="120" value="${
                  user.long_break_minutes
                }"></label>
              </div>
              <div class="form-actions">
                <button type="submit" class="btn btn-primary" data-submit>${icon("save")} 保存偏好</button>
              </div>
            </form>
          </section>

          <section class="card settings-card">
            <div class="card-header">
              <div><h2 class="card-title">${icon("bot")} AI 服务状态</h2><p class="card-subtitle">API Key 只存放在 Flask 后端环境变量中。</p></div>
              ${aiModeBadge(ai, { small: true })}
            </div>
            ${aiBanner(
              {
                mode:
                  ai.text?.effective_mode === "live" && ai.vision?.effective_mode === "live"
                    ? "live"
                    : "demo",
                provider: "服务端配置",
                notice:
                  ai.text?.effective_mode === "live" && ai.vision?.effective_mode === "live"
                    ? "文本与视觉模型均已连接真实 API。AI 输出仅供参考。"
                    : "至少一个 AI 能力处于演示或未配置状态。演示结果会被明确标记，不会伪装成真实模型输出。",
                disclaimer: ai.disclaimer,
              },
              { compact: true }
            )}
            <div class="engine-grid">
              ${engineCard("文本模型", "message-square-text", ai.text, "AI_TEXT_API_KEY")}
              ${engineCard("视觉模型", "image", ai.vision, "AI_VISION_API_KEY")}
            </div>
            <div class="ai-policy-row">
              <span>运行策略</span><code>AI_DEMO_MODE=${escapeHTML(ai.policy)}</code>
              <span class="muted-note">auto：有 Key 用真实模型，否则演示 · on：始终演示 · off：未配置时返回错误</span>
            </div>
            <details class="env-details">
              <summary>${icon("key-round")} 如何配置真实 AI？</summary>
              <div class="env-guide">
                <p>在项目根目录复制 <code>.env.example</code> 为 <code>.env</code>，填写密钥后重启 Flask。所有密钥只保留在服务端，前端不会收到。</p>
                <pre class="env-snippet">${escapeHTML(ENV_SNIPPET)}</pre>
                <div class="env-actions">
                  <button type="button" class="btn btn-secondary btn-sm" data-copy-env>${icon("copy")} 复制配置模板</button>
                  <span class="muted-note">修改后需要重启服务；演示模式不会发起外部请求。</span>
                </div>
              </div>
            </details>
          </section>

          <section class="card settings-card">
            <div class="card-header">
              <div><h2 class="card-title">${icon("flask-conical")} 演示数据与导出</h2><p class="card-subtitle">演示数据可随时清除，不会影响你自己创建的内容。</p></div>
            </div>
            <div class="demo-summary-box">
              <div>
                <strong>${totalDemo ? `已载入 ${totalDemo} 条演示记录` : "当前没有演示数据"}</strong>
                <p>${
                  totalDemo
                    ? "这些记录在演示时帮助你快速看到完整界面。清除时只会删除标记为演示的数据。"
                    : "如果界面还是空的，可以载入少量示例任务、成绩、笔记与学习记录。"
                }</p>
              </div>
              <span class="demo-badge ${totalDemo ? "is-loaded" : ""}">${totalDemo ? "演示数据已载入" : "干净空间"}</span>
            </div>
            ${
              Object.keys(counts).length
                ? `<div class="demo-count-grid">${Object.entries(counts)
                    .map(
                      ([key, count]) => `<div><strong>${count}</strong><span>${escapeHTML(
                        DEMO_LABELS[key] || key
                      )}</span></div>`
                    )
                    .join("")}</div>`
                : ""
            }
            <div class="settings-action-row">
              <button type="button" class="btn btn-secondary btn-sm" data-load-demo ${totalDemo ? "disabled" : ""}>${icon("sparkles")} 载入演示数据</button>
              <button type="button" class="btn btn-danger btn-sm" data-clear-demo ${totalDemo ? "" : "disabled"}>${icon("trash-2")} 清除演示数据</button>
              <a class="btn btn-secondary btn-sm" href="/api/export" download>${icon("download")} 导出全部数据 JSON</a>
            </div>
            <p class="field-hint">${icon("shield-check")} 导出文件包含任务、成绩、笔记、学习记录等个人数据，请妥善保管。</p>
          </section>
        </div>

        <aside class="settings-side">
          <section class="card settings-profile-card">
            <div class="avatar avatar-xl" id="settings-avatar-large" style="background:${escapeHTML(
              user.avatar_color || "#2563eb"
            )}">${initials(user.display_name)}</div>
            <h2>${escapeHTML(user.display_name || "同学")}</h2>
            <p>${escapeHTML(user.email || "本地学习空间")}</p>
            <div class="profile-since">${icon("calendar")} 自 ${formatDate(
              user.created_at?.slice(0, 10),
              { withYear: true }
            )} 开始使用</div>
            <div class="profile-stat-row">
              <div><strong>${user.daily_goal_minutes}m</strong><span>每日目标</span></div>
              <div><strong>${user.pomodoro_minutes}m</strong><span>番茄钟</span></div>
            </div>
          </section>

          <section class="card settings-info-card">
            <h3>${icon("info")} 关于 StudyFlow</h3>
            <dl>
              <div><dt>版本</dt><dd>${escapeHTML(version)}</dd></div>
              <div><dt>数据存储</dt><dd>SQLite 本地文件</dd></div>
              <div><dt>前端</dt><dd>原生 JS + Tailwind + Toast UI</dd></div>
              <div><dt>后端</dt><dd>Python Flask REST API</dd></div>
            </dl>
            <p class="muted-note">所有主要数据都会持久化到 SQLite。API Key 仅保存在服务端环境变量中。</p>
          </section>

          <section class="card settings-note-card">
            <span>${icon("lock")}</span>
            <div>
              <strong>关于隐私</strong>
              <p>学习数据默认保存在本机的 SQLite 数据库中。AI 请求会把必要的文本或上传图片发送给所配置的第三方模型服务；演示模式不发任何外部请求。</p>
            </div>
          </section>

          <section class="card settings-note-card">
            <span>${icon("file-code-2")}</span>
            <div>
              <strong>开发者接口</strong>
              <p>统一 REST API 前缀为 <code>/api</code>，完整接口说明见项目根目录 <code>docs/API.md</code>。</p>
            </div>
          </section>
        </aside>
      </div>
    </div>
  `;
  refreshIcons(container);
  bindForms(container);
  bindDataActions(container);
}

function bindForms(container) {
  const profileForm = container.querySelector("#profile-form");
  const profileColor = profileForm.querySelector('input[name="avatar_color"]');
  profileColor?.addEventListener("input", () => {
    const avatar = container.querySelector("#settings-avatar");
    const large = container.querySelector("#settings-avatar-large");
    if (avatar) avatar.style.background = profileColor.value;
    if (large) large.style.background = profileColor.value;
  });
  profileForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(profileForm);
    const button = profileForm.querySelector("[data-submit]");
    setButtonLoading(button, true, "保存中…");
    try {
      const response = await api.put("/settings", {
        display_name: String(formData.get("display_name") || "").trim(),
        email: String(formData.get("email") || "").trim(),
        avatar_color: formData.get("avatar_color"),
      });
      settingsData.user = response.data.user;
      const meta = await loadMeta({ force: true });
      applyMeta(meta);
      showToast("个人资料已保存");
      const avatar = container.querySelector("#settings-avatar");
      if (avatar) avatar.textContent = initials(response.data.user.display_name);
      const large = container.querySelector("#settings-avatar-large");
      if (large) large.textContent = initials(response.data.user.display_name);
    } catch (error) {
      toastError(error);
    } finally {
      setButtonLoading(button, false);
    }
  });

  const preferencesForm = container.querySelector("#preferences-form");
  preferencesForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(preferencesForm);
    const button = preferencesForm.querySelector("[data-submit]");
    setButtonLoading(button, true, "保存中…");
    try {
      const response = await api.put("/settings", {
        daily_goal_minutes: Number(formData.get("daily_goal_minutes")),
        pomodoro_minutes: Number(formData.get("pomodoro_minutes")),
        short_break_minutes: Number(formData.get("short_break_minutes")),
        long_break_minutes: Number(formData.get("long_break_minutes")),
      });
      settingsData.user = response.data.user;
      const meta = await loadMeta({ force: true });
      applyMeta(meta);
      showToast("学习偏好已保存");
    } catch (error) {
      toastError(error);
    } finally {
      setButtonLoading(button, false);
    }
  });

  container.querySelector("[data-copy-env]")?.addEventListener("click", async (event) => {
    try {
      await copyText(ENV_SNIPPET);
      showToast("配置模板已复制，请粘贴到服务端 .env");
      refreshIcons(event.currentTarget);
    } catch {
      toastError(new Error("复制失败，请手动选择配置文本"));
    }
  });
}

function bindDataActions(container) {
  container.querySelector("[data-load-demo]")?.addEventListener("click", async (event) => {
    const button = event.currentTarget;
    setButtonLoading(button, true, "载入中…");
    try {
      const response = await api.post("/demo/load", {});
      showToast(response.message || "演示数据已载入");
      refreshCurrent({ preserveScroll: true });
    } catch (error) {
      toastError(error);
      setButtonLoading(button, false);
    }
  });
  container.querySelector("[data-clear-demo]")?.addEventListener("click", async (event) => {
    const confirmed = await openConfirm({
      title: "清除演示数据",
      message: "确定清除所有标记为演示的记录吗？",
      details: "你手动创建的任务、成绩、笔记等不会被删除。此操作无法撤销。",
      confirmText: "清除演示数据",
      danger: true,
    });
    if (!confirmed) return;
    const button = event.currentTarget;
    setButtonLoading(button, true, "清除中…");
    try {
      const response = await api.delete("/demo/clear");
      showToast(response.message || "演示数据已清除");
      refreshCurrent({ preserveScroll: true });
    } catch (error) {
      toastError(error);
      setButtonLoading(button, false);
    }
  });
}

async function render(container) {
  pageController?.abort();
  pageController = new AbortController();
  try {
    const response = await api.get("/settings", undefined, { signal: pageController.signal });
    settingsData = response.data;
    renderPage(container);
  } catch (error) {
    if (error.name === "AbortError") return;
    throw error;
  }
}

function cleanup() {
  pageController?.abort();
  pageController = null;
}

export default {
  title: "设置",
  render,
  cleanup,
};
