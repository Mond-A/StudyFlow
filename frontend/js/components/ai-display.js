/** Consistent display of AI mode, provider, notices and warnings. */

import { icon } from "./icons.js";
import { escapeHTML, formatDateTime, uniqueBy } from "../ui.js";

/**
 * AI responses include a top-level `mode`, while /api/meta describes the two
 * capability engines separately. Normalize both shapes so a status badge can
 * never accidentally claim a demo response is live.
 */
export function resolveAIMode(ai) {
  if (!ai) return "unknown";
  if (ai.mode === "live" || ai.mode === "demo") return ai.mode;
  const modes = [ai.text?.effective_mode, ai.vision?.effective_mode].filter(Boolean);
  if (!modes.length) return "unknown";
  if (modes.every((mode) => mode === "live")) return "live";
  if (modes.every((mode) => mode === "unavailable")) return "unavailable";
  return "demo";
}

export function aiModeBadge(ai, { small = false } = {}) {
  if (!ai) return "";
  const mode = resolveAIMode(ai);
  const demo = mode !== "live";
  const label =
    mode === "unavailable" ? "AI 未配置" : mode === "demo" ? "演示模式" : "AI 实时分析";
  return `<span class="ai-mode-badge ${
    mode === "unavailable" ? "ai-mode-unavailable" : demo ? "ai-mode-demo" : "ai-mode-live"
  } ${small ? "ai-mode-badge-sm" : ""}">
    ${icon(mode === "unavailable" ? "plug-zap" : demo ? "flask-conical" : "sparkles")}
    ${label}
  </span>`;
}

export function aiBanner(ai, { compact = false } = {}) {
  if (!ai) return "";
  const demo = resolveAIMode(ai) !== "live";
  const notice = ai.notice || (demo ? "当前未调用外部模型。" : "AI 生成内容，请核对原文。");
  return `<div class="ai-banner ${demo ? "is-demo" : "is-live"} ${compact ? "is-compact" : ""}">
    <span class="ai-banner-icon">${icon(demo ? "flask-conical" : "sparkles")}</span>
    <div class="ai-banner-copy">
      <div class="ai-banner-title">
        ${demo ? "演示模式 · 非真实模型结果" : "真实 AI 分析"}
        <span class="ai-provider">${escapeHTML(ai.provider || "")}${
          ai.model ? ` · ${escapeHTML(ai.model)}` : ""
        }</span>
      </div>
      <p>${escapeHTML(notice)}</p>
      ${!compact && ai.disclaimer ? `<p class="ai-disclaimer">${escapeHTML(ai.disclaimer)}</p>` : ""}
    </div>
    ${
      ai.analyzed_at
        ? `<span class="ai-time">${escapeHTML(formatDateTime(ai.analyzed_at))}</span>`
        : ""
    }
  </div>`;
}

export function warningList(warnings, { exclude = [] } = {}) {
  const filtered = uniqueBy(
    (Array.isArray(warnings) ? warnings : []).filter(
      (warning) => warning && !exclude.includes(warning)
    ),
    (warning) => String(warning)
  );
  if (!filtered.length) return "";
  return `<ul class="ai-warnings">
    ${filtered
      .map(
        (warning) =>
          `<li>${icon("info")}<span>${escapeHTML(warning)}</span></li>`
      )
      .join("")}
  </ul>`;
}

export function aiResultFooter(ai, { warnings = [] } = {}) {
  if (!ai) return "";
  const exclude = [ai.notice, ai.disclaimer].filter(Boolean);
  return `<div class="ai-result-meta">
    ${warningList(warnings, { exclude })}
    <p class="ai-manual-check">${icon("shield-check")} ${
      ai.mode === "demo"
        ? "以上内容由本地演示逻辑生成，不能替代老师讲解或真实 AI 分析。"
        : "AI 输出仅供参考，请结合教材与原文核对。"
    }</p>
  </div>`;
}

export function aiEmptyHint(ai) {
  if (!ai) return "";
  if (ai.mode === "demo") {
    return `<p class="inline-hint demo-hint">${icon("flask-conical")} 当前为演示模式。配置服务端 API Key 后，可在设置页查看真实模型状态。</p>`;
  }
  return "";
}
