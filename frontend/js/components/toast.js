import { icon, refreshIcons } from "./icons.js";

let container = null;

function ensureContainer() {
  if (container && document.body.contains(container)) return container;
  container = document.createElement("div");
  container.className = "toast-container";
  container.setAttribute("aria-live", "polite");
  container.setAttribute("aria-atomic", "false");
  document.body.appendChild(container);
  return container;
}

const TYPE_META = {
  success: { icon: "check-circle-2", label: "成功" },
  error: { icon: "alert-circle", label: "错误" },
  warning: { icon: "triangle-alert", label: "注意" },
  info: { icon: "info", label: "提示" },
};

/**
 * Show a transient notification.
 * @param {string} message
 * @param {'success'|'error'|'warning'|'info'} type
 */
export function showToast(message, type = "success", { duration = 4200 } = {}) {
  if (!message) return null;
  const meta = TYPE_META[type] || TYPE_META.info;
  const host = ensureContainer();
  const el = document.createElement("div");
  el.className = `toast toast-${type}`;
  el.setAttribute("role", type === "error" ? "alert" : "status");
  el.innerHTML = `
    <span class="toast-icon">${icon(meta.icon)}</span>
    <span class="toast-message"></span>
    <button class="toast-close" type="button" aria-label="关闭提示">${icon("x")}</button>
  `;
  el.querySelector(".toast-message").textContent = message;
  const close = () => {
    el.classList.add("is-leaving");
    window.setTimeout(() => el.remove(), 180);
  };
  el.querySelector(".toast-close").addEventListener("click", close);
  host.appendChild(el);
  refreshIcons(el);
  if (duration > 0) {
    window.setTimeout(() => {
      if (el.isConnected) close();
    }, duration);
  }
  return el;
}

export function toastError(error, fallback = "操作失败，请稍后重试") {
  const message =
    (error && (error.message || error.error?.message)) || String(error || "") || fallback;
  return showToast(message, "error", { duration: 5600 });
}

export function toastSuccess(message) {
  return showToast(message, "success");
}

export function toastInfo(message) {
  return showToast(message, "info");
}
