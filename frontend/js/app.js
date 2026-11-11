/** StudyFlow front-end bootstrapping. */

import { applyMeta, mountLayout } from "./components/layout.js";
import { refreshIcons } from "./components/icons.js";
import { showToast } from "./components/toast.js";
import { initRouter } from "./router.js";
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

const root = document.getElementById("app");
const content = mountLayout(root);
refreshIcons(document);

loadMeta()
  .then((meta) => applyMeta(meta))
  .catch((error) => {
    console.error("Metadata load failed", error);
    showToast(
      "无法加载应用信息，请确认 Flask 后端正在运行。页面功能可能不可用。",
      "error",
      { duration: 7000 }
    );
  });

window.addEventListener("studyflow:meta", (event) => applyMeta(event.detail));

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

initRouter({ pageRoutes, container: content });
