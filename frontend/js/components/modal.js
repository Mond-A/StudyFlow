/** Accessible single-modal helper shared by every page. */

import { icon, refreshIcons } from "./icons.js";

let active = null;
let lastFocused = null;

function normalizeNode(content) {
  if (content instanceof Node) return content;
  const wrapper = document.createElement("div");
  wrapper.innerHTML = content == null ? "" : String(content);
  return wrapper;
}

function createHeader(title, subtitle, onClose) {
  const header = document.createElement("div");
  header.className = "modal-header";
  const text = document.createElement("div");
  text.className = "modal-heading";
  const heading = document.createElement("h2");
  heading.id = "modal-title";
  heading.textContent = title || "对话框";
  text.appendChild(heading);
  if (subtitle) {
    const sub = document.createElement("p");
    sub.className = "modal-subtitle";
    sub.textContent = subtitle;
    text.appendChild(sub);
  }
  const closeButton = document.createElement("button");
  closeButton.type = "button";
  closeButton.className = "icon-button modal-close";
  closeButton.setAttribute("aria-label", "关闭对话框");
  closeButton.innerHTML = icon("x");
  closeButton.addEventListener("click", onClose);
  header.append(text, closeButton);
  return header;
}

export function openModal({
  title = "",
  subtitle = "",
  body = "",
  footer = "",
  size = "md",
  closeOnBackdrop = true,
  onMount = null,
  onClose = null,
  className = "",
} = {}) {
  closeAllModals();
  lastFocused = document.activeElement;

  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.setAttribute("role", "presentation");
  const dialog = document.createElement("section");
  dialog.className = `modal modal-${size} ${className}`.trim();
  dialog.setAttribute("role", "dialog");
  dialog.setAttribute("aria-modal", "true");
  dialog.setAttribute("aria-labelledby", "modal-title");

  const close = () => {
    if (!overlay.isConnected) return;
    overlay.classList.remove("is-open");
    document.body.classList.remove("modal-open");
    document.removeEventListener("keydown", onKeydown);
    window.setTimeout(() => overlay.remove(), 160);
    if (active && active.overlay === overlay) active = null;
    if (lastFocused && typeof lastFocused.focus === "function") {
      lastFocused.focus({ preventScroll: true });
    }
    if (typeof onClose === "function") {
      try {
        onClose();
      } catch (error) {
        console.error("Modal onClose failed", error);
      }
    }
  };

  dialog.appendChild(createHeader(title, subtitle, close));
  const bodyEl = document.createElement("div");
  bodyEl.className = "modal-body";
  bodyEl.appendChild(normalizeNode(body));
  dialog.appendChild(bodyEl);

  let footerEl = null;
  if (footer !== "" && footer !== null && footer !== undefined) {
    footerEl = document.createElement("div");
    footerEl.className = "modal-footer";
    footerEl.appendChild(normalizeNode(footer));
    dialog.appendChild(footerEl);
  }

  overlay.appendChild(dialog);
  if (closeOnBackdrop) {
    overlay.addEventListener("mousedown", (event) => {
      if (event.target === overlay) close();
    });
  }

  function onKeydown(event) {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      return;
    }
    if (event.key !== "Tab") return;
    const focusable = dialog.querySelectorAll(
      'button:not([disabled]), [href], input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  document.body.appendChild(overlay);
  document.body.classList.add("modal-open");
  document.addEventListener("keydown", onKeydown);
  requestAnimationFrame(() => {
    overlay.classList.add("is-open");
    const target = dialog.querySelector(
      "[data-autofocus], input:not([type=hidden]), textarea, select, button.btn-primary"
    );
    if (target) target.focus({ preventScroll: true });
  });
  refreshIcons(overlay);

  active = { overlay, dialog, close };
  if (typeof onMount === "function") {
    try {
      onMount({ overlay, dialog, body: bodyEl, footer: footerEl, close });
    } catch (error) {
      console.error("Modal onMount failed", error);
    }
  }
  refreshIcons(overlay);
  return {
    overlay,
    dialog,
    body: bodyEl,
    footer: footerEl,
    close,
  };
}

export function closeAllModals() {
  if (active) active.close();
  document.querySelectorAll(".modal-overlay").forEach((node) => node.remove());
  document.body.classList.remove("modal-open");
  active = null;
}

export function openConfirm({
  title = "确认操作",
  message = "此操作无法撤销，是否继续？",
  confirmText = "确认",
  cancelText = "取消",
  danger = false,
  details = "",
} = {}) {
  return new Promise((resolve) => {
    const body = document.createElement("div");
    body.className = "confirm-body";
    const text = document.createElement("p");
    text.className = "confirm-message";
    text.textContent = message;
    body.appendChild(text);
    if (details) {
      const note = document.createElement("p");
      note.className = "confirm-details";
      note.textContent = details;
      body.appendChild(note);
    }
    let settled = false;
    let closeModal = null;
    const resolveOnce = (value) => {
      if (settled) return;
      settled = true;
      resolve(value);
    };
    const finish = (value) => {
      resolveOnce(value);
      if (closeModal) closeModal();
    };
    const footer = document.createElement("div");
    footer.className = "modal-actions";
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "btn btn-secondary";
    cancel.textContent = cancelText;
    const confirm = document.createElement("button");
    confirm.type = "button";
    confirm.className = `btn ${danger ? "btn-danger" : "btn-primary"}`;
    confirm.textContent = confirmText;
    footer.append(cancel, confirm);

    openModal({
      title,
      body,
      footer,
      size: "sm",
      onMount: ({ close }) => {
        closeModal = close;
        cancel.addEventListener("click", () => finish(false));
        confirm.addEventListener("click", () => finish(true));
      },
      onClose: () => resolveOnce(false),
    });
  });
}
