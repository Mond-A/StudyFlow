/** Shared formatting and rendering helpers used across pages. */

import { icon } from "./components/icons.js";

export const SUBJECT_COLORS = {
  语文: "#d97706",
  数学: "#2563eb",
  英语: "#7c3aed",
  物理: "#0d9488",
  化学: "#db2777",
  生物: "#16a34a",
  政治: "#b91c1c",
  历史: "#92400e",
  地理: "#0891b2",
  综合: "#64748b",
};

const FALLBACK_COLORS = ["#2563eb", "#0d9488", "#7c3aed", "#d97706", "#db2777", "#16a34a"];

export function escapeHTML(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

export function truncate(value, max = 120) {
  const text = String(value ?? "");
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

export function getSubjectColor(subject) {
  if (SUBJECT_COLORS[subject]) return SUBJECT_COLORS[subject];
  let hash = 0;
  for (const char of String(subject || "综合")) hash = (hash * 31 + char.charCodeAt(0)) % 997;
  return FALLBACK_COLORS[hash % FALLBACK_COLORS.length];
}

export function subjectBadge(subject, { dot = true, small = false } = {}) {
  const safe = escapeHTML(subject || "综合");
  const color = getSubjectColor(subject);
  return `<span class="subject-badge ${small ? "subject-badge-sm" : ""}" style="--subject-color:${color}">
    ${dot ? '<span class="subject-dot"></span>' : ""}${safe}
  </span>`;
}

export function parseDateOnly(value) {
  if (!value) return null;
  const match = String(value).match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
  }
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
}

export function todayISO() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

export function dateDiffDays(fromISO, toISO = todayISO()) {
  const from = parseDateOnly(fromISO);
  const to = parseDateOnly(toISO);
  if (!from || !to) return null;
  return Math.round((from.getTime() - to.getTime()) / 86400000);
}

export function formatDate(value, { withYear = false, weekday = false } = {}) {
  const date = parseDateOnly(value);
  if (!date) return "—";
  const options = { month: "short", day: "numeric" };
  if (withYear) options.year = "numeric";
  if (weekday) options.weekday = "short";
  return new Intl.DateTimeFormat("zh-CN", options).format(date);
}

export function formatDateLong(value) {
  const date = parseDateOnly(value);
  if (!date) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  }).format(date);
}

export function formatTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

export function formatDateTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

export function formatAgo(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  const seconds = Math.round((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return "刚刚";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟前`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} 小时前`;
  if (seconds < 86400 * 7) return `${Math.floor(seconds / 86400)} 天前`;
  return formatDate(value, { withYear: true });
}

export function relativeDay(value) {
  const diff = dateDiffDays(value);
  if (diff === null) return "—";
  if (diff === 0) return "今天";
  if (diff === 1) return "明天";
  if (diff === 2) return "后天";
  if (diff === -1) return "昨天";
  if (diff < -1) return `逾期 ${-diff} 天`;
  return formatDate(value, { weekday: true });
}

export function dueLabel(task) {
  if (!task) return "";
  if (!task.due_date) return task.planned_date ? `计划 ${relativeDay(task.planned_date)}` : "未设截止";
  const days = task.days_until_due;
  if (task.status === "completed") return `截止 ${formatDate(task.due_date)}`;
  if (days === null || days === undefined) return `截止 ${formatDate(task.due_date)}`;
  if (days < 0) return `已逾期 ${Math.abs(days)} 天`;
  if (days === 0) return "今天截止";
  if (days === 1) return "明天截止";
  if (days <= 7) return `${days} 天后截止`;
  return `截止 ${formatDate(task.due_date)}`;
}

export function dueTone(task) {
  if (!task || task.status === "completed") return "muted";
  if (task.is_overdue) return "danger";
  if (task.days_until_due === 0) return "warning";
  return "muted";
}

export function formatMinutes(minutes, { compact = false } = {}) {
  const value = Math.max(0, Math.round(Number(minutes) || 0));
  if (compact) {
    if (value < 60) return `${value}m`;
    const hours = value / 60;
    return Number.isInteger(hours) ? `${hours}h` : `${hours.toFixed(1)}h`;
  }
  if (value < 60) return `${value} 分钟`;
  const hours = Math.floor(value / 60);
  const remainder = value % 60;
  return remainder ? `${hours} 小时 ${remainder} 分钟` : `${hours} 小时`;
}

export function formatClock(totalSeconds) {
  const safe = Math.max(0, Math.round(Number(totalSeconds) || 0));
  const minutes = Math.floor(safe / 60);
  const seconds = safe % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

export function formatScore(score, max = 100) {
  const value = Number(score);
  if (Number.isNaN(value)) return "—";
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

export function initials(name) {
  const text = String(name || "同学").trim();
  if (!text) return "同";
  if (/[\u4e00-\u9fff]/.test(text)) return text.slice(-2);
  const words = text.split(/\s+/).filter(Boolean);
  return words.length > 1
    ? `${words[0][0]}${words[1][0]}`.toUpperCase()
    : text.slice(0, 2).toUpperCase();
}

export function percent(part, total, fallback = 0) {
  const numerator = Number(part) || 0;
  const denominator = Number(total) || 0;
  if (!denominator) return fallback;
  return Math.round((numerator / denominator) * 100);
}

export function statusBadge(status) {
  const map = {
    pending: { label: "待完成", className: "status-pending" },
    in_progress: { label: "进行中", className: "status-progress" },
    completed: { label: "已完成", className: "status-completed" },
  };
  const meta = map[status] || map.pending;
  return `<span class="status-badge ${meta.className}"><span class="status-dot"></span>${meta.label}</span>`;
}

export function masteryLabel(level) {
  const value = Number(level) || 0;
  if (value >= 5) return "已掌握";
  if (value >= 3) return "熟悉";
  if (value >= 1) return "学习中";
  return "新卡片";
}

export function difficultyDots(level, { withLabel = false } = {}) {
  const value = Math.max(1, Math.min(5, Number(level) || 3));
  const dots = Array.from({ length: 5 }, (_, index) => {
    return `<span class="difficulty-dot ${index < value ? "is-on" : ""}"></span>`;
  }).join("");
  return `<span class="difficulty" title="难度 ${value}/5">${dots}${
    withLabel ? `<span class="difficulty-label">难度 ${value}</span>` : ""
  }</span>`;
}

export function progressBar(percentValue, { tone = "primary", showLabel = false, label = "" } = {}) {
  const safe = Math.max(0, Math.min(100, Number(percentValue) || 0));
  return `<div class="progress-wrap">
    <div class="progress-track" role="progressbar" aria-valuenow="${safe}" aria-valuemin="0" aria-valuemax="100" aria-label="${escapeHTML(label || "完成度")}">
      <span class="progress-fill progress-${escapeHTML(tone)}" style="width:${safe}%"></span>
    </div>
    ${showLabel ? `<span class="progress-label">${safe}%</span>` : ""}
  </div>`;
}

export function progressRing(percentValue, { size = 96, stroke = 8, label = "" } = {}) {
  const safe = Math.max(0, Math.min(100, Number(percentValue) || 0));
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - safe / 100);
  return `<div class="progress-ring" style="width:${size}px;height:${size}px">
    <svg viewBox="0 0 ${size} ${size}" role="img" aria-label="${escapeHTML(label || `完成 ${safe}%`)}">
      <circle class="progress-ring-track" cx="${size / 2}" cy="${size / 2}" r="${radius}" fill="none" stroke-width="${stroke}"></circle>
      <circle class="progress-ring-value" cx="${size / 2}" cy="${size / 2}" r="${radius}" fill="none" stroke-width="${stroke}"
        stroke-dasharray="${circumference.toFixed(1)}" stroke-dashoffset="${offset.toFixed(1)}"
        stroke-linecap="round" transform="rotate(-90 ${size / 2} ${size / 2})"></circle>
    </svg>
    <div class="progress-ring-label"><strong>${safe}%</strong><span>${escapeHTML(label)}</span></div>
  </div>`;
}

export function weeklyBars(activity, { maxHeight = 96 } = {}) {
  const max = Math.max(1, ...(activity || []).map((item) => Number(item.minutes) || 0));
  return `<div class="weekly-bars" role="img" aria-label="最近七天学习时长">
    ${(activity || [])
      .map((item) => {
        const height = Math.max(4, Math.round(((Number(item.minutes) || 0) / max) * maxHeight));
        return `<div class="weekly-bar-col ${item.is_today ? "is-today" : ""}" title="${escapeHTML(
          `${item.date}：${formatMinutes(item.minutes)}`
        )}">
          <span class="weekly-bar-value">${item.minutes ? formatMinutes(item.minutes, { compact: true }) : ""}</span>
          <span class="weekly-bar-track"><span class="weekly-bar-fill" style="height:${height}px"></span></span>
          <span class="weekly-bar-label">${escapeHTML(item.weekday || "")}</span>
        </div>`;
      })
      .join("")}
  </div>`;
}

export function emptyState({ iconName = "inbox", title = "暂无内容", description = "", action = "" } = {}) {
  return `<div class="empty-state">
    <div class="empty-icon">${icon(iconName)}</div>
    <h3>${escapeHTML(title)}</h3>
    ${description ? `<p>${escapeHTML(description)}</p>` : ""}
    ${action ? `<div class="empty-action">${action}</div>` : ""}
  </div>`;
}

export function skeletonBlock({ lines = 3, className = "" } = {}) {
  return `<div class="skeleton-block ${className}" aria-hidden="true">
    ${Array.from({ length: lines }, (_, index) => `<span class="skeleton-line" style="width:${
      index === lines - 1 ? 62 : 100
    }%"></span>`).join("")}
  </div>`;
}

export function pageLoading({ label = "正在加载数据…" } = {}) {
  return `<div class="page-loading" role="status">
    <span class="spinner spinner-lg"></span>
    <p>${escapeHTML(label)}</p>
  </div>`;
}

export function errorPanel(message, { retryId = "retry-button" } = {}) {
  return `<div class="error-panel" role="alert">
    <div class="error-panel-icon">${icon("cloud-off")}</div>
    <div>
      <h3>内容加载失败</h3>
      <p>${escapeHTML(message || "请稍后重试")}</p>
    </div>
    <button type="button" class="btn btn-secondary btn-sm" id="${escapeHTML(retryId)}">${icon(
      "refresh-cw"
    )}<span>重试</span></button>
  </div>`;
}

export function setButtonLoading(button, loading, loadingText = "处理中…") {
  if (!button) return;
  if (loading) {
    if (!button.dataset.originalHtml) button.dataset.originalHtml = button.innerHTML;
    button.disabled = true;
    button.classList.add("is-loading");
    button.innerHTML = `<span class="spinner"></span><span>${escapeHTML(loadingText)}</span>`;
  } else {
    button.disabled = false;
    button.classList.remove("is-loading");
    if (button.dataset.originalHtml) {
      button.innerHTML = button.dataset.originalHtml;
      delete button.dataset.originalHtml;
    }
  }
}

export function setFormBusy(form, busy) {
  if (!form) return;
  form.querySelectorAll("input, select, textarea, button").forEach((field) => {
    field.disabled = busy;
  });
}

export function debounce(fn, wait = 250) {
  let timer;
  return (...args) => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => fn(...args), wait);
  };
}

export function valueOrDash(value) {
  if (value === null || value === undefined || value === "") return "—";
  return escapeHTML(value);
}

export function nl2br(value) {
  return escapeHTML(value).replace(/\n/g, "<br>");
}

export function formatFileSize(bytes) {
  if (!bytes) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function parseJsonSafe(value, fallback = null) {
  if (value === null || value === undefined) return fallback;
  if (typeof value === "object") return value;
  try {
    return JSON.parse(value);
  } catch {
    return fallback;
  }
}

export function uniqueBy(items, keyFn) {
  const seen = new Set();
  return (items || []).filter((item) => {
    const key = keyFn(item);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export function isAbort(error) {
  return Boolean(error && error.name === "AbortError");
}
