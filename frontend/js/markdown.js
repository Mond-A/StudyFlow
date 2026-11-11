/** Markdown + KaTeX rendering for previews, notes and AI output. */

import { escapeHTML } from "./ui.js";

function parseMarkdown(markdown) {
  if (window.marked && typeof window.marked.parse === "function") {
    try {
      return window.marked.parse(markdown || "", {
        gfm: true,
        breaks: true,
        headerIds: false,
        mangle: false,
      });
    } catch {
      // fall through to safe plain text
    }
  }
  return `<p>${escapeHTML(markdown || "").replace(/\n/g, "<br>")}</p>`;
}

export function renderMath(element) {
  if (!element || typeof window.renderMathInElement !== "function") return false;
  try {
    window.renderMathInElement(element, {
      delimiters: [
        { left: "$$", right: "$$", display: true },
        { left: "\\[", right: "\\]", display: true },
        { left: "$", right: "$", display: false },
        { left: "\\(", right: "\\)", display: false },
      ],
      ignoredTags: ["script", "noscript", "style", "textarea", "pre", "code", "option"],
      throwOnError: false,
      errorColor: "#dc2626",
      strict: "ignore",
      trust: false,
    });
    return true;
  } catch (error) {
    console.warn("KaTeX rendering failed", error);
    return false;
  }
}

export function markdownToHTML(markdown) {
  const raw = parseMarkdown(markdown);
  if (window.DOMPurify && typeof window.DOMPurify.sanitize === "function") {
    return window.DOMPurify.sanitize(raw, {
      USE_PROFILES: { html: true },
      ADD_ATTR: ["target", "rel"],
    });
  }
  return raw;
}

export function renderRichMarkdown(target, markdown) {
  if (!target) return;
  target.innerHTML = markdownToHTML(markdown);
  target.querySelectorAll("a").forEach((link) => {
    link.setAttribute("target", "_blank");
    link.setAttribute("rel", "noopener noreferrer nofollow");
  });
  target.querySelectorAll("table").forEach((table) => {
    const wrapper = document.createElement("div");
    wrapper.className = "markdown-table-wrap";
    table.parentNode.insertBefore(wrapper, table);
    wrapper.appendChild(table);
  });
  renderMath(target);
  return target;
}

export function markdownPreviewElement(markdown, className = "markdown-body") {
  const el = document.createElement("div");
  el.className = className;
  renderRichMarkdown(el, markdown);
  return el;
}

export async function copyText(text) {
  const value = String(text ?? "");
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(value);
    return true;
  }
  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  const ok = document.execCommand("copy");
  textarea.remove();
  return ok;
}
