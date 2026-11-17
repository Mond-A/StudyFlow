/** StudyFlow front-end bootstrapping. */

import { applyMeta, mountLayout } from "./components/layout.js";
import { refreshIcons } from "./components/icons.js";
import { showToast } from "./components/toast.js";
import { initRouter } from "./router.js";
import { initGlobalTheme } from "./theme.js";
import { loadMeta } from "./services/store.js";
import { api } from "./api.js";

import dashboardPage from "./pages/dashboard.js";
import plannerPage from "./pages/planner.js";
import analyticsPage from "./pages/analytics.js";
import aiToolboxPage from "./pages/ai-toolbox.js";
import notesPage from "./pages/notes.js";
import focusPage from "./pages/focus.js";
import flashcardsPage from "./pages/flashcards.js";
import errorsPage from "./pages/errors.js";
import reportsPage from "./pages/reports.js";
import settingsPage from "./pages/settings.js";

const pageRoutes = {
  dashboard: dashboardPage,
  planner: plannerPage,
  analytics: analyticsPage,
  "ai-toolbox": aiToolboxPage,
  notes: notesPage,
  focus: focusPage,
  flashcards: flashcardsPage,
  errors: errorsPage,
  reports: reportsPage,
  settings: settingsPage,
};

initGlobalTheme();
const root = document.getElementById("app");
const content = mountLayout(root);
refreshIcons(document);

window.addEventListener("studyflow:meta", (event) => applyMeta(event.detail));

// Do not mount the first page before metadata is available. Pages such as
// AI Toolbox read AI configuration during their initial render; mounting
// early used to leave “未配置” pills on screen even when both models were live.
loadMeta()
  .then((meta) => {
    applyMeta(meta);
    initRouter({ pageRoutes, container: content });
    if (!window.__STUDYFLOW_GUEST__) maybeOfferGuestImport();
  })
  .catch((error) => {
    console.error("Metadata load failed", error);
    showToast(
      "无法加载应用信息，请确认 Flask 后端正在运行。页面功能可能不可用。",
      "error",
      { duration: 7000 }
    );
    initRouter({ pageRoutes, container: content });
  });

async function maybeOfferGuestImport() {
  if (window.sessionStorage.getItem("studyflow.guest-import-dismissed") === "1") return;
  let summary;
  try {
    const module = await import("./guest-store.js");
    summary = await module.guestImportSummary();
  } catch (error) {
    console.warn("Guest storage is unavailable", error);
    return;
  }
  if (!summary.total) return;
  const labels = {
    tasks: "任务",
    grades: "成绩",
    notes: "笔记",
    sessions: "学习记录",
    flashcards: "闪卡",
    errors: "错题",
  };
  const rows = Object.entries(summary.counts)
    .filter(([, count]) => count > 0)
    .map(([key, count]) => `<li><span>${labels[key] || key}</span><strong>${count}</strong></li>`)
    .join("");
  const overlay = document.createElement("div");
  overlay.className = "guest-import-overlay";
  overlay.innerHTML = `
    <section class="guest-import-dialog" role="dialog" aria-modal="true" aria-labelledby="guest-import-title">
      <p class="guest-import-eyebrow">当前设备有访客数据</p>
      <h2 id="guest-import-title">是否将访客数据同步到当前账户？</h2>
      <p class="guest-import-copy">这些数据目前只保存在本机。只有你确认后才会提交到当前登录账户；账户中原有的数据不会被覆盖。</p>
      <ul class="guest-import-counts">${rows}</ul>
      <div class="guest-import-actions">
        <button type="button" class="btn btn-secondary" data-guest-import-cancel>暂不同步</button>
        <button type="button" class="btn btn-primary" data-guest-import-confirm>同步本地数据</button>
      </div>
      <p class="guest-import-error" data-guest-import-error hidden></p>
    </section>`;
  document.body.appendChild(overlay);
  const close = () => {
    try { window.sessionStorage.setItem("studyflow.guest-import-dismissed", "1"); } catch {}
    overlay.remove();
  };
  overlay.querySelector("[data-guest-import-cancel]").addEventListener("click", close);
  overlay.querySelector("[data-guest-import-confirm]").addEventListener("click", async (event) => {
    const button = event.currentTarget;
    const errorBox = overlay.querySelector("[data-guest-import-error]");
    button.disabled = true;
    button.textContent = "正在导入…";
    errorBox.hidden = true;
    try {
      const module = await import("./guest-store.js");
      const batchId = (window.crypto && crypto.randomUUID)
        ? crypto.randomUUID()
        : `guest-import-${Date.now()}`;
      const payload = await module.guestImportPayload(batchId);
      const response = await api.post("/guest/import", payload);
      button.textContent = "导入完成";
      showToast(
        response?.data?.total_imported
          ? `已导入 ${response.data.total_imported} 条访客数据，本地数据仍保留。`
          : "访客数据已处理。",
        "success",
        { duration: 5000 }
      );
      window.sessionStorage.setItem("studyflow.guest-import-dismissed", "1");
      window.setTimeout(() => window.location.reload(), 700);
    } catch (error) {
      errorBox.textContent = error?.message || "导入失败，请稍后重试。本地访客数据仍然保留。";
      errorBox.hidden = false;
      button.disabled = false;
      button.textContent = "同步本地数据";
    }
  });
}

window.addEventListener("offline", () => {
  showToast("网络已断开。本地数据仍保存在服务端，恢复连接后请刷新。", "warning", {
    duration: 6000,
  });
});

window.addEventListener("unhandledrejection", (event) => {
  if (event.reason && event.reason.name === "AbortError") {
    event.preventDefault();
    return;
  }
  console.error("Unhandled promise rejection", event.reason);
});
