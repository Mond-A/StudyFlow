/** Application shell: desktop sidebar, mobile drawer and shared chrome. */

import { icon, refreshIcons } from "./icons.js";
import { initials } from "../ui.js";

export const NAV_GROUPS = [
  {
    label: "学习总览",
    items: [
      { route: "dashboard", label: "首页", icon: "layout-dashboard" },
      { route: "planner", label: "学习规划", icon: "calendar-days" },
      { route: "analytics", label: "成绩分析", icon: "chart-line" },
      { route: "ai-toolbox", label: "AI 工具箱", icon: "sparkles" },
      { route: "notes", label: "智能笔记", icon: "notebook-pen" },
    ],
  },
  {
    label: "学习工具",
    items: [
      { route: "focus", label: "专注时钟", icon: "timer" },
      { route: "flashcards", label: "闪卡复习", icon: "layers" },
      { route: "errors", label: "错题本", icon: "clipboard-list" },
      { route: "reports", label: "学习报告", icon: "file-text" },
    ],
  },
];

const SETTINGS_ITEM = { route: "settings", label: "设置", icon: "settings" };

function navItem(item) {
  return `<a class="nav-item" href="#/${item.route}" data-route="${item.route}">
    <span class="nav-icon">${icon(item.icon)}</span>
    <span>${item.label}</span>
  </a>`;
}

function navGroup(group) {
  return `<div class="nav-group">
    <p class="nav-group-label">${group.label}</p>
    ${group.items.map(navItem).join("")}
  </div>`;
}

export function mountLayout(root) {
  root.innerHTML = `
    <a class="skip-link" href="#page-content">跳到主要内容</a>
    <div class="app-shell">
      <aside class="sidebar" id="app-sidebar" aria-label="主导航">
        <div class="sidebar-brand">
          <a href="#/dashboard" class="brand-link" aria-label="StudyFlow 首页">
            <span class="brand-mark">${icon("book-open-check")}</span>
            <span class="brand-copy">
              <strong>StudyFlow</strong>
              <span>AI 学习工作台</span>
            </span>
          </a>
          <button type="button" class="icon-button sidebar-close-mobile" id="sidebar-close" aria-label="关闭导航">${icon("x")}</button>
        </div>

        <div class="sidebar-ai js-sidebar-ai" data-state="loading" role="status" title="AI 服务状态">
          <span class="ai-status-dot"></span>
          <span class="js-ai-label">正在检查 AI 状态…</span>
          <span class="js-ai-detail"></span>
        </div>

        <nav class="sidebar-nav">
          ${NAV_GROUPS.map(navGroup).join("")}
        </nav>

        <div class="sidebar-bottom">
          <a class="nav-item nav-settings" href="#/settings" data-route="settings">
            <span class="nav-icon">${icon("settings")}</span><span>设置</span>
          </a>
          <a class="sidebar-user" href="#/settings" data-route="settings" aria-label="打开个人设置">
            <span class="avatar js-user-avatar">同学</span>
            <span class="sidebar-user-copy">
              <strong class="js-user-name">同学</strong>
              <span class="js-user-subtitle">本地学习空间</span>
            </span>
            ${icon("chevron-right", "sidebar-user-arrow")}
          </a>
          <p class="sidebar-version"><span class="js-app-version">StudyFlow</span> · MVP</p>
        </div>
      </aside>

      <div class="sidebar-backdrop" id="sidebar-backdrop" aria-hidden="true"></div>

      <div class="app-main">
        <header class="mobile-header">
          <button type="button" class="icon-button" id="sidebar-toggle" aria-label="打开导航" aria-expanded="false" aria-controls="app-sidebar">
            ${icon("menu")}
          </button>
          <a href="#/dashboard" class="mobile-brand">
            <span class="brand-mark brand-mark-sm">${icon("book-open-check")}</span>
            <strong>StudyFlow</strong>
          </a>
          <span class="mobile-ai js-mobile-ai" data-state="loading">${icon("bot")}<span>检查中</span></span>
        </header>

        <main id="page-content" class="page-content" tabindex="-1"></main>

        <footer class="app-footer">
          <span>StudyFlow · 专注每一个学习瞬间</span>
          <span class="footer-note">本地数据存储 · AI 结果需人工核对</span>
        </footer>
      </div>
    </div>
  `;
  bindShell(root);
  refreshIcons(root);
  return root.querySelector("#page-content");
}

function bindShell(root) {
  const sidebar = root.querySelector("#app-sidebar");
  const backdrop = root.querySelector("#sidebar-backdrop");
  const toggle = root.querySelector("#sidebar-toggle");
  const closeButton = root.querySelector("#sidebar-close");

  const setOpen = (open) => {
    document.body.classList.toggle("sidebar-open", open);
    sidebar.classList.toggle("is-open", open);
    backdrop.classList.toggle("is-open", open);
    toggle.setAttribute("aria-expanded", String(open));
  };

  toggle.addEventListener("click", () => setOpen(true));
  closeButton.addEventListener("click", () => setOpen(false));
  backdrop.addEventListener("click", () => setOpen(false));
  root.querySelectorAll(".sidebar a").forEach((link) => {
    link.addEventListener("click", () => setOpen(false));
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && document.body.classList.contains("sidebar-open")) {
      setOpen(false);
    }
  });
  window.addEventListener("resize", () => {
    if (window.innerWidth >= 1024) setOpen(false);
  });
}

export function setActiveNav(routeName) {
  document.querySelectorAll(".nav-item[data-route]").forEach((item) => {
    const active = item.dataset.route === routeName;
    item.classList.toggle("is-active", active);
    if (active) item.setAttribute("aria-current", "page");
    else item.removeAttribute("aria-current");
  });
  document.body.dataset.route = routeName || "";
}

export function applyMeta(meta) {
  if (!meta) return;
  const user = meta.user || {};
  const name = user.display_name || "同学";
  document.querySelectorAll(".js-user-name").forEach((node) => {
    node.textContent = name;
  });
  document.querySelectorAll(".js-user-avatar").forEach((node) => {
    node.textContent = initials(name);
    if (user.avatar_color) node.style.background = user.avatar_color;
  });
  const subtitle = document.querySelector(".js-user-subtitle");
  if (subtitle) subtitle.textContent = "本地学习空间";
  const version = document.querySelector(".js-app-version");
  if (version && meta.app) version.textContent = `${meta.app.name} ${meta.app.version.split("-")[0]}`;

  const ai = meta.ai;
  if (!ai) return;
  const textMode = ai.text?.effective_mode;
  const visionMode = ai.vision?.effective_mode;
  const modes = [textMode, visionMode];
  let state = "live";
  let label = "AI 已连接";
  let detail = "";
  if (modes.every((mode) => mode === "unavailable")) {
    state = "unavailable";
    label = "AI 未配置";
    detail = "配置密钥后启用";
  } else if (modes.includes("demo") || modes.includes("unavailable")) {
    state = "demo";
    label = "AI 演示模式";
    detail = "结果仅供体验";
  } else {
    label = "AI 已连接";
    detail = [ai.text?.provider, ai.vision?.provider].filter(Boolean).join(" / ");
  }
  const sidebar = document.querySelector(".js-sidebar-ai");
  if (sidebar) {
    sidebar.dataset.state = state;
    sidebar.title = `文本：${ai.text?.configured ? ai.text.provider : "未配置"} · 视觉：${
      ai.vision?.configured ? ai.vision.provider : "未配置"
    }`;
    sidebar.querySelector(".js-ai-label").textContent = label;
    sidebar.querySelector(".js-ai-detail").textContent = detail;
  }
  const mobile = document.querySelector(".js-mobile-ai");
  if (mobile) {
    mobile.dataset.state = state;
    mobile.querySelector("span").textContent =
      state === "live" ? "AI 在线" : state === "demo" ? "演示" : "未配置";
    mobile.title = label;
  }
}
