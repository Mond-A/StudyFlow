import {
  applyFluentTheme,
  webDarkTheme,
  webLightTheme,
} from "/vendor/fluent/3.2.1/fluent-entry.js";

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const THEME_KEY = "studyflow-fluent-lab-theme";

const eventLog = $("#lab-event-log");
const themeSwitch = $("#lab-theme-switch");
const form = $("#lab-form");
const formHint = $("#lab-form-hint");
const formOutput = $("#lab-form-output");
const progress = $("#lab-progress");
const progressValue = $("#lab-progress-value");
const dialog = $("#lab-dialog");
const menu = $("#lab-menu");

let themeMode = document.documentElement.dataset.theme === "dark" ? "dark" : "light";
let logCount = 0;

function logEvent(message) {
  const item = document.createElement("li");
  const time = document.createElement("time");
  const text = document.createElement("span");
  time.textContent = new Date().toLocaleTimeString("zh-CN", { hour12: false });
  text.textContent = message;
  item.append(time, text);
  eventLog.prepend(item);
  logCount += 1;
  while (eventLog.children.length > 40) {
    eventLog.lastElementChild?.remove();
  }
}

function setTheme(mode, { persist = true } = {}) {
  const next = mode === "dark" ? "dark" : "light";
  themeMode = next;
  document.documentElement.dataset.theme = next;
  applyFluentTheme(next === "dark" ? webDarkTheme : webLightTheme);

  if (themeSwitch) {
    themeSwitch.checked = next === "dark";
  }
  const themeColor = document.querySelector('meta[name="theme-color"]');
  if (themeColor) {
    themeColor.content = next === "dark" ? "#202020" : "#f3f2f1";
  }
  if (persist) {
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch (_) {}
  }
}

function readComponentRegistration() {
  const report = {};
  for (const row of $$("#lab-registry-body tr[data-tag]")) {
    const tag = row.dataset.tag;
    const status = row.querySelector(".lab-registry-status");
    const label = row.querySelector("td")?.textContent.trim() || tag;
    const fallback = label === "Progress Ring";
    const available = Boolean(customElements.get(tag));
    report[tag] = available;
    if (status) {
      status.dataset.state = available ? (fallback ? "warn" : "ok") : "error";
      status.textContent = available ? (fallback ? "替代实现" : "已注册") : "未注册";
    }
  }
  return report;
}

function collectFormData() {
  if (!form) return {};
  const data = {};
  for (const [key, value] of new FormData(form).entries()) {
    data[key] = value;
  }
  return data;
}

function initialiseTheme() {
  let saved = null;
  try {
    saved = localStorage.getItem(THEME_KEY);
  } catch (_) {}
  const initial = saved === "dark" || saved === "light" ? saved : "light";
  setTheme(initial, { persist: false });
  logEvent(`主题已应用：${initial === "dark" ? "深色" : "浅色"}`);
}

function initialiseThemeSwitch() {
  if (!themeSwitch) return;
  themeSwitch.checked = themeMode === "dark";
  themeSwitch.addEventListener("change", () => {
    const mode = themeSwitch.checked ? "dark" : "light";
    setTheme(mode);
    logEvent(`主题切换：${mode === "dark" ? "深色" : "浅色"}`);
  });
}

function initialiseForm() {
  if (!form) return;

  form.addEventListener("change", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement) || !target.name) return;
    const value = "checked" in target && typeof target.checked === "boolean"
      ? `${target.checked}`
      : String(target.value ?? "");
    logEvent(`表单值变更：${target.name} = ${value}`);
  });

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const data = collectFormData();
    formOutput.textContent = JSON.stringify(data, null, 2);
    formHint.textContent = `已提交 · ${Object.keys(data).length} 个字段`;
    logEvent(`表单提交：${Object.keys(data).length} 个字段`);
  });

  form.addEventListener("reset", () => {
    window.setTimeout(() => {
      formOutput.textContent = "表单已重置。";
      formHint.textContent = "尚未提交";
      logEvent("表单已重置");
    }, 0);
  });
}

function initialiseDialog() {
  const trigger = $("#lab-dialog-trigger");
  const close = $("#lab-dialog-close");
  if (!dialog || !trigger || !close) return;

  trigger.addEventListener("click", () => {
    dialog.show();
    logEvent("Dialog 已打开");
  });
  close.addEventListener("click", () => {
    dialog.hide();
    logEvent("Dialog 已关闭");
  });
  dialog.addEventListener("toggle", (event) => {
    logEvent(`Dialog toggle：${event.newState || (dialog.open ? "open" : "closed")}`);
  });
}

function initialiseMenu() {
  $$("#lab-menu fluent-menu-item").forEach((item) => {
    item.addEventListener("click", () => {
      logEvent(`菜单选择：${item.textContent.trim()}`);
    });
  });
}

function initialiseProgress() {
  const update = $("#lab-progress-update");
  if (!progress || !update) return;
  progressValue.textContent = String(progress.value ?? 0);
  update.addEventListener("click", () => {
    const next = Math.min(100, Number(progress.value || 0) + 8);
    progress.value = next;
    progressValue.textContent = String(next);
    logEvent(`进度更新：${next}%`);
    if (next >= 100) {
      update.disabled = true;
      update.textContent = "已完成";
    }
  });
}

function initialiseAccordion() {
  const accordion = $("#lab-accordion");
  if (!accordion) return;
  accordion.addEventListener("change", () => {
    const expanded = $$("#lab-accordion fluent-accordion-item")
      .filter((item) => item.expanded)
      .map((item) => item.querySelector('[slot="heading"]')?.textContent.trim())
      .filter(Boolean);
    logEvent(`Accordion 展开：${expanded.join(" / ") || "无"}`);
  });
}

function initialiseScrollSpy() {
  const sections = $$("#foundations, #form-controls, #overlays, #feedback, #registry");
  const links = new Map($$(".lab-nav-link").map((link) => [link.getAttribute("href")?.slice(1), link]));
  if (!sections.length) return;

  const setActive = (id) => {
    for (const [linkId, link] of links) {
      const active = linkId === id;
      link.classList.toggle("is-active", active);
      if (active) link.setAttribute("aria-current", "true");
      else link.removeAttribute("aria-current");
    }
  };

  let scheduled = false;
  const update = () => {
    scheduled = false;
    const marker = window.scrollY + Math.min(180, window.innerHeight * 0.28);
    let active = sections[0].id;
    for (const section of sections) {
      if (section.offsetTop <= marker) active = section.id;
    }
    setActive(active);
  };
  const schedule = () => {
    if (scheduled) return;
    scheduled = true;
    window.requestAnimationFrame(update);
  };

  window.addEventListener("scroll", schedule, { passive: true });
  window.addEventListener("resize", schedule);
  update();
}

function initialiseTooltipEvents() {
  $$("fluent-tooltip").forEach((tooltip) => {
    tooltip.addEventListener("toggle", (event) => {
      logEvent(`Tooltip toggle：${event.newState || "unknown"}`);
    });
    const anchor = tooltip.anchor ? document.getElementById(tooltip.anchor) : null;
    if (anchor) {
      // Fluent's button delegates focus into its shadow root. Listen to the
      // bubbling focusin/focusout phases so keyboard focus also opens the tooltip.
      anchor.addEventListener("focusin", () => tooltip.showTooltip(0));
      anchor.addEventListener("focusout", () => tooltip.hideTooltip(0));
    }
  });
}

async function initialiseRegistry() {
  const tags = [
    "fluent-button", "fluent-text-input", "fluent-field", "fluent-checkbox",
    "fluent-switch", "fluent-dropdown", "fluent-listbox", "fluent-option",
    "fluent-dialog", "fluent-dialog-body", "fluent-menu", "fluent-menu-button",
    "fluent-menu-list", "fluent-menu-item", "fluent-tooltip", "fluent-progress-bar",
    "fluent-spinner", "fluent-accordion", "fluent-accordion-item",
  ];
  await Promise.race([
    Promise.all(tags.map((tag) => customElements.whenDefined(tag))),
    new Promise((resolve) => window.setTimeout(resolve, 3000)),
  ]);
  const report = readComponentRegistration();
  const failCount = Object.values(report).filter((available) => !available).length;
  logEvent(`组件注册完成：${Object.keys(report).length} 项，失败 ${failCount} 项`);
  return report;
}

async function boot() {
  eventLog.replaceChildren();
  logEvent("Fluent lab 初始化");
  initialiseTheme();
  initialiseThemeSwitch();
  initialiseForm();
  initialiseDialog();
  initialiseMenu();
  initialiseAccordion();
  initialiseTooltipEvents();
  initialiseScrollSpy();

  let registry = {};
  try {
    registry = await initialiseRegistry();
  } catch (error) {
    logEvent(`组件注册异常：${error instanceof Error ? error.message : String(error)}`);
  }

  // Fluent properties are available after upgrade. Initialise the progress
  // label here so it reflects the upgraded component, not the pre-upgrade 0.
  initialiseProgress();

  window.__fluentLab = {
    ready: true,
    theme: themeMode,
    registry,
    formData: collectFormData(),
    version: "3.2.1",
  };
}

boot();
