/** Hash-based router. One page module is mounted at a time with cleanup. */

import { closeAllModals } from "./components/modal.js";
import { refreshIcons } from "./components/icons.js";
import { setActiveNav } from "./components/layout.js";
import { errorPanel, pageLoading } from "./ui.js";

let routes = {};
let contentEl = null;
let currentRoute = null;
let currentDefinition = null;
let renderToken = 0;
let started = false;

function parseHash() {
  const raw = window.location.hash.replace(/^#\/?/, "");
  const [pathPart, queryPart = ""] = raw.split("?");
  const routeName = (pathPart.split("/")[0] || "dashboard").trim();
  const query = Object.fromEntries(new URLSearchParams(queryPart).entries());
  return { routeName, query };
}

function setDocumentTitle(definition, routeName) {
  const base = "StudyFlow";
  if (definition && definition.title) {
    document.title = `${definition.title} · ${base}`;
  } else if (routeName === "dashboard") {
    document.title = `${base} · AI 学习工作台`;
  } else {
    document.title = base;
  }
}

function notFoundMarkup(routeName) {
  return `<div class="route-missing">
    <div class="route-missing-code">404</div>
    <h1>找不到这个页面</h1>
    <p>“${escapeText(routeName)}” 不是一个有效的 StudyFlow 页面。</p>
    <a class="btn btn-primary" href="#/dashboard">返回首页</a>
  </div>`;
}

function escapeText(value) {
  return String(value || "").replace(/[<>&"]/g, (char) => {
    const map = { "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" };
    return map[char];
  });
}

async function renderCurrent({ preserveScroll = false } = {}) {
  if (!contentEl) return;
  const token = ++renderToken;
  const scrollY = preserveScroll ? window.scrollY : 0;
  closeAllModals();

  if (currentDefinition && typeof currentDefinition.cleanup === "function") {
    try {
      currentDefinition.cleanup();
    } catch (error) {
      console.warn("Page cleanup failed", error);
    }
  }

  const { routeName, query } = parseHash();
  currentRoute = routeName;
  const definition = routes[routeName];
  currentDefinition = definition || null;
  setActiveNav(definition ? routeName : "");
  setDocumentTitle(definition, routeName);

  const host = document.createElement("div");
  host.className = "route-page";
  contentEl.replaceChildren(host);

  if (!definition) {
    host.innerHTML = notFoundMarkup(routeName);
    refreshIcons(host);
    if (!preserveScroll) window.scrollTo({ top: 0, behavior: "auto" });
    return;
  }

  host.innerHTML = pageLoading({ label: `正在加载${definition.title || "页面"}…` });
  refreshIcons(host);

  try {
    await definition.render(host, { query, routeName });
    if (token !== renderToken) return;
    refreshIcons(host);
    document.body.dataset.pageReady = "true";
    if (!preserveScroll) {
      window.scrollTo({ top: 0, behavior: "auto" });
    } else {
      window.scrollTo({ top: scrollY, behavior: "auto" });
    }
  } catch (error) {
    if (token !== renderToken) return;
    console.error(`Failed to render ${routeName}`, error);
    const message =
      error && error.message ? error.message : "页面加载失败，请检查后端服务是否运行。";
    host.innerHTML = `<div class="container-narrow">${errorPanel(message)}</div>`;
    const retry = host.querySelector("#retry-button");
    if (retry) {
      retry.addEventListener("click", () => refreshCurrent());
    }
    refreshIcons(host);
  }
}

export function initRouter({ pageRoutes, container }) {
  routes = pageRoutes;
  contentEl = container;
  if (!started) {
    started = true;
    window.addEventListener("hashchange", () => renderCurrent());
    window.addEventListener("studyflow:navigate", (event) => {
      if (event.detail && event.detail.route) navigate(event.detail.route);
    });
    if (!window.location.hash) {
      history.replaceState(null, "", "#/dashboard");
    }
  }
  renderCurrent();
}

export function navigate(routeName) {
  const normalized = String(routeName || "dashboard").replace(/^#\/?/, "");
  if (window.location.hash === `#/${normalized}`) {
    renderCurrent();
  } else {
    window.location.hash = `#/${normalized}`;
  }
}

export function refreshCurrent({ preserveScroll = true } = {}) {
  return renderCurrent({ preserveScroll });
}

export function getCurrentRoute() {
  return currentRoute;
}
