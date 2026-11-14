/** StudyFlow front-end bootstrapping. */

import { applyMeta, mountLayout } from "./components/layout.js";
import { refreshIcons } from "./components/icons.js";
import { showToast } from "./components/toast.js";
import { initRouter } from "./router.js";
import { initGlobalTheme } from "./theme.js";
import { loadMeta } from "./services/store.js";

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
