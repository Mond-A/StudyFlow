import { api } from "../api.js";
import { icon, refreshIcons } from "../components/icons.js";
import { openConfirm, openModal } from "../components/modal.js";
import { aiBanner, aiModeBadge } from "../components/ai-display.js";
import { showToast, toastError } from "../components/toast.js";
import { refreshCurrent } from "../router.js";
import { getMeta, getSubjects } from "../services/store.js";
import {
  emptyState,
  escapeHTML,
  formatDate,
  subjectBadge,
} from "../ui.js";

const state = {
  errors: [],
  counts: {},
  subject: "all",
  mastery: "all",
  search: "",
};

let pageController = null;
let pageRoot = null;

const MASTERY = {
  new: { label: "待复习", className: "mastery-new" },
  reviewing: { label: "复习中", className: "mastery-reviewing" },
  mastered: { label: "已掌握", className: "mastery-mastered" },
};

function filteredErrors() {
  return state.errors.filter((item) => {
    if (state.subject !== "all" && item.subject !== state.subject) return false;
    if (state.mastery !== "all" && item.mastery !== state.mastery) return false;
    if (state.search) {
      const haystack = `${item.question} ${item.analysis} ${(item.knowledge_points || []).join(
        " "
      )}`.toLowerCase();
      if (!haystack.includes(state.search.toLowerCase())) return false;
    }
    return true;
  });
}

function masteryTag(mastery) {
  const meta = MASTERY[mastery] || MASTERY.new;
  return `<span class="mastery-tag ${meta.className}"><span class="mastery-dot"></span>${meta.label}</span>`;
}

function errorCard(item) {
  const knowledge = item.knowledge_points || [];
  return `<article class="error-card" data-error-id="${item.id}">
    <div class="error-card-head">
      <div class="error-card-badges">${subjectBadge(item.subject, { small: true })}${masteryTag(
        item.mastery
      )}<span class="error-date">${icon("calendar")} ${formatDate(item.created_at?.slice(0, 10) || item.created_at, {
        withYear: true,
      })}</span></div>
      <div class="error-card-actions">
        ${
          item.mastery !== "mastered"
            ? `<button type="button" class="btn btn-ghost btn-sm" data-error-action="master" data-error-id="${item.id}">${icon("check")} 标记已掌握</button>`
            : `<button type="button" class="btn btn-ghost btn-sm" data-error-action="review" data-error-id="${item.id}">${icon("rotate-ccw")} 重新复习</button>`
        }
        <button type="button" class="btn btn-secondary btn-sm" data-error-action="classify" data-error-id="${item.id}">${icon("sparkles")} AI 归类</button>
        <button type="button" class="icon-button" data-error-action="edit" data-error-id="${item.id}" title="编辑错题" aria-label="编辑错题">${icon("pencil")}</button>
        <button type="button" class="icon-button danger" data-error-action="delete" data-error-id="${item.id}" title="删除错题" aria-label="删除错题">${icon("trash-2")}</button>
      </div>
    </div>
    <p class="error-question">${escapeHTML(item.question)}</p>
    <div class="knowledge-tags">
      ${
        knowledge.length
          ? knowledge
              .map((point) => `<span class="knowledge-tag">${icon("tag")} ${escapeHTML(point)}</span>`)
              .join("")
          : `<span class="knowledge-tag is-empty">${icon("tag")} 尚未标注知识点</span>`
      }
    </div>
    <details class="error-details">
      <summary>${icon("notebook-text")} 展开答案与错因分析</summary>
      <div class="error-answer-grid">
        <div class="error-answer-block"><span>我的答案</span><p>${escapeHTML(
          item.student_answer || "未填写"
        )}</p></div>
        <div class="error-answer-block is-correct"><span>正确答案 / 思路</span><p>${escapeHTML(
          item.correct_answer || "未填写"
        )}</p></div>
      </div>
      ${
        item.analysis
          ? `<div class="error-analysis"><span>${icon("lightbulb")} 错因分析</span><p>${escapeHTML(item.analysis)}</p></div>`
          : ""
      }
    </details>
  </article>`;
}

function renderList() {
  const list = pageRoot?.querySelector("#error-list");
  if (!list) return;
  const errors = filteredErrors();
  list.innerHTML = errors.length
    ? errors.map(errorCard).join("")
    : emptyState({
        iconName: state.errors.length ? "search-x" : "clipboard-list",
        title: state.errors.length ? "没有匹配的错题" : "错题本还是空的",
        description: state.errors.length
          ? "调整筛选条件，或清空搜索关键词。"
          : "把真正做错的题记录下来，比重复刷已会的题更有价值。",
        action: state.errors.length
          ? `<button type="button" class="btn btn-secondary btn-sm" data-reset-error-filter>清除筛选</button>`
          : `<button type="button" class="btn btn-primary btn-sm" data-add-error>添加第一道错题</button>`,
      });
  refreshIcons(list);
  list.querySelector("[data-add-error]")?.addEventListener("click", () => openErrorModal());
  list.querySelector("[data-reset-error-filter]")?.addEventListener("click", () => {
    state.subject = "all";
    state.mastery = "all";
    state.search = "";
    pageRoot.querySelector("#error-search").value = "";
    pageRoot.querySelector("#error-subject").value = "all";
    pageRoot.querySelectorAll("[data-mastery-tab]").forEach((tab) => {
      tab.classList.toggle("is-active", tab.dataset.masteryTab === "all");
    });
    renderList();
  });
}

function renderPage(container) {
  const meta = getMeta();
  const subjects = [...new Set(state.errors.map((item) => item.subject))].sort();
  container.innerHTML = `
    <div class="page-shell">
      <header class="page-header">
        <div class="page-heading">
          <p class="eyebrow">ERROR BOOK · 错题本</p>
          <h1>把错误变成下一次的得分点</h1>
          <p class="page-subtitle">记录错题、正确答案和错因，按知识点归类并安排复习。重点不是抄题，而是弄清楚为什么错。</p>
        </div>
        <div class="page-actions">
          <button type="button" class="btn btn-primary" data-add-error>${icon("plus")}<span>记录错题</span></button>
        </div>
      </header>

      <section class="focus-summary-grid">
        <div class="summary-chip"><span class="summary-icon red">${icon("clipboard-list")}</span><div><strong>${state.counts.total || 0}</strong><span>错题总数</span></div></div>
        <div class="summary-chip"><span class="summary-icon amber">${icon("circle-alert")}</span><div><strong>${state.counts.new || 0}</strong><span>待复习</span></div></div>
        <div class="summary-chip"><span class="summary-icon blue">${icon("refresh-cw")}</span><div><strong>${state.counts.reviewing || 0}</strong><span>复习中</span></div></div>
        <div class="summary-chip"><span class="summary-icon teal">${icon("badge-check")}</span><div><strong>${state.counts.mastered || 0}</strong><span>已掌握</span></div></div>
      </section>

      <section class="error-filterbar card">
        <div class="error-filter-tabs" role="tablist" aria-label="按掌握程度筛选">
          ${[
            { value: "all", label: "全部" },
            { value: "new", label: "待复习" },
            { value: "reviewing", label: "复习中" },
            { value: "mastered", label: "已掌握" },
          ]
            .map(
              (tab) => `<button type="button" class="tab-button ${
                state.mastery === tab.value ? "is-active" : ""
              }" data-mastery-tab="${tab.value}">${tab.label}<span>${
                tab.value === "all" ? state.counts.total || 0 : state.counts[tab.value] || 0
              }</span></button>`
            )
            .join("")}
        </div>
        <div class="error-filter-controls">
          <div class="search-box search-box-sm">${icon("search")}<input id="error-search" type="search" placeholder="搜索错题或知识点…" value="${escapeHTML(
            state.search
          )}" aria-label="搜索错题"></div>
          <select class="input input-sm" id="error-subject" aria-label="按学科筛选错题">
            <option value="all">全部学科</option>
            ${subjects
              .map(
                (subject) =>
                  `<option value="${escapeHTML(subject)}" ${
                    state.subject === subject ? "selected" : ""
                  }>${escapeHTML(subject)}</option>`
              )
              .join("")}
          </select>
          <span class="ai-classify-hint">${aiModeBadge(meta?.ai, { small: true })}<span>AI 归类需人工确认</span></span>
        </div>
      </section>

      <div class="error-list" id="error-list"></div>

      <div class="error-page-tip">
        ${icon("lightbulb")}
        <p><strong>如何用好错题本？</strong> 记录时写清错误原因；复习时遮住答案独立重做；连续两次独立做对后，再标记为“已掌握”。</p>
      </div>
    </div>
  `;
  pageRoot = container;
  refreshIcons(container);
  renderList();
  bindEvents(container);
}

function bindEvents(container) {
  container.querySelectorAll("[data-add-error]").forEach((button) => {
    button.addEventListener("click", () => openErrorModal());
  });
  container.querySelectorAll("[data-mastery-tab]").forEach((tab) => {
    tab.addEventListener("click", () => {
      state.mastery = tab.dataset.masteryTab;
      container.querySelectorAll("[data-mastery-tab]").forEach((item) => {
        item.classList.toggle("is-active", item === tab);
      });
      renderList();
    });
  });
  container.querySelector("#error-subject")?.addEventListener("change", (event) => {
    state.subject = event.target.value;
    renderList();
  });
  container.querySelector("#error-search")?.addEventListener("input", (event) => {
    state.search = event.target.value.trim();
    renderList();
  });
  container.querySelector("#error-list")?.addEventListener("click", (event) => {
    const action = event.target.closest("[data-error-action]");
    if (!action) return;
    const item = state.errors.find((error) => String(error.id) === action.dataset.errorId);
    if (!item) return;
    if (action.dataset.errorAction === "edit") openErrorModal(item);
    if (action.dataset.errorAction === "delete") deleteError(item);
    if (action.dataset.errorAction === "classify") classifyError(item);
    if (action.dataset.errorAction === "master") updateMastery(item, "mastered");
    if (action.dataset.errorAction === "review") updateMastery(item, "reviewing");
  });
}

function errorFormBody(item = null) {
  const subjects = [...new Set([...getSubjects(), item?.subject].filter(Boolean))];
  return `<form id="error-form" class="form-stack">
    <div class="form-grid">
      <label class="field"><span class="field-label">学科 *</span><input class="input" name="subject" list="error-subjects" maxlength="30" required value="${escapeHTML(
        item?.subject || ""
      )}" placeholder="例如：数学" data-autofocus><datalist id="error-subjects">${subjects
        .map((subject) => `<option value="${escapeHTML(subject)}"></option>`)
        .join("")}</datalist></label>
      <label class="field"><span class="field-label">掌握程度</span><select class="input" name="mastery">${Object.entries(
        MASTERY
      )
        .map(
          ([value, meta]) =>
            `<option value="${value}" ${(item?.mastery || "new") === value ? "selected" : ""}>${meta.label}</option>`
        )
        .join("")}</select></label>
      <label class="field field-span-2"><span class="field-label">题目 *</span><textarea class="input textarea" name="question" rows="4" maxlength="10000" required placeholder="粘贴或输入错题题干">${escapeHTML(
        item?.question || ""
      )}</textarea></label>
      <label class="field"><span class="field-label">我的答案</span><textarea class="input textarea" name="student_answer" rows="4" maxlength="10000" placeholder="我当时是怎么做的">${escapeHTML(
        item?.student_answer || ""
      )}</textarea></label>
      <label class="field"><span class="field-label">正确答案 / 解题思路</span><textarea class="input textarea" name="correct_answer" rows="4" maxlength="10000" placeholder="正确解法或关键步骤">${escapeHTML(
        item?.correct_answer || ""
      )}</textarea></label>
      <label class="field field-span-2"><span class="field-label">知识点</span><input class="input" name="knowledge_points" maxlength="500" placeholder="用逗号分隔，例如：二次函数, 判别式" value="${escapeHTML(
        (item?.knowledge_points || []).join(", ")
      )}"><span class="field-hint">知识点标签会用于筛选和复习回顾；可以稍后用 AI 建议修改。</span></label>
      <label class="field field-span-2"><span class="field-label">错因分析</span><textarea class="input textarea" name="analysis" rows="3" maxlength="10000" placeholder="是概念没理解、审题失误、计算错误，还是步骤不完整？">${escapeHTML(
        item?.analysis || ""
      )}</textarea></label>
    </div>
    <p class="form-error" id="error-form-error" role="alert" hidden></p>
  </form>`;
}

function openErrorModal(item = null) {
  const body = document.createElement("div");
  body.innerHTML = errorFormBody(item);
  const footer = document.createElement("div");
  footer.className = "modal-actions";
  footer.innerHTML = `<button type="button" class="btn btn-secondary" data-cancel>取消</button>
    <button type="submit" form="error-form" class="btn btn-primary" data-submit>${icon("save")}<span>${
      item ? "保存修改" : "保存错题"
    }</span></button>`;
  openModal({
    title: item ? "编辑错题" : "记录一道错题",
    subtitle: "记录真实错误，才能做有价值的复盘。",
    body,
    footer,
    size: "lg",
    onMount: ({ close }) => {
      const form = body.querySelector("#error-form");
      const errorEl = body.querySelector("#error-form-error");
      footer.querySelector("[data-cancel]").addEventListener("click", close);
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const formData = new FormData(form);
        const subject = String(formData.get("subject") || "").trim();
        const question = String(formData.get("question") || "").trim();
        if (!subject || !question) {
          errorEl.textContent = "学科和题目不能为空";
          errorEl.hidden = false;
          return;
        }
        const payload = {
          subject,
          question,
          student_answer: String(formData.get("student_answer") || "").trim(),
          correct_answer: String(formData.get("correct_answer") || "").trim(),
          analysis: String(formData.get("analysis") || "").trim(),
          knowledge_points: String(formData.get("knowledge_points") || "")
            .split(/[,，]/)
            .map((point) => point.trim())
            .filter(Boolean),
          mastery: formData.get("mastery"),
        };
        const submit = footer.querySelector("[data-submit]");
        submit.disabled = true;
        submit.innerHTML = `<span class="spinner"></span><span>保存中…</span>`;
        try {
          if (item) await api.put(`/errors/${item.id}`, payload);
          else await api.post("/errors", payload);
          close();
          showToast(item ? "错题已更新" : "错题已保存");
          refreshCurrent({ preserveScroll: true });
        } catch (error) {
          errorEl.textContent = error.message || "保存失败";
          errorEl.hidden = false;
          submit.disabled = false;
          submit.innerHTML = `${icon("save")}<span>${item ? "保存修改" : "保存错题"}</span>`;
          refreshIcons(submit);
        }
      });
    },
  });
}

async function deleteError(item) {
  const confirmed = await openConfirm({
    title: "删除错题",
    message: "确定把这道错题从错题本删除吗？",
    details: item.question.slice(0, 100),
    confirmText: "删除错题",
    danger: true,
  });
  if (!confirmed) return;
  try {
    await api.delete(`/errors/${item.id}`);
    showToast("错题已删除");
    refreshCurrent({ preserveScroll: true });
  } catch (error) {
    toastError(error);
  }
}

async function updateMastery(item, mastery) {
  try {
    await api.put(`/errors/${item.id}`, { mastery });
    showToast(mastery === "mastered" ? "已标记为掌握" : "已放回复习中");
    refreshCurrent({ preserveScroll: true });
  } catch (error) {
    toastError(error);
  }
}

async function classifyError(item) {
  const body = document.createElement("div");
  body.innerHTML = `<div class="ai-loading"><span class="spinner spinner-lg"></span><strong>正在分析知识点…</strong><p>AI 会尝试根据题目内容归类学科和知识点。这不会自动修改你的错题。</p></div>`;
  const footer = document.createElement("div");
  footer.className = "modal-actions";
  footer.innerHTML = `<button type="button" class="btn btn-secondary" data-close>关闭</button>`;
  let classified = null;
  const modal = openModal({
    title: "AI 错题归类",
    subtitle: "建议需人工确认，你决定是否应用。",
    body,
    footer,
    size: "md",
    onMount: ({ close }) => {
      footer.querySelector("[data-close]").addEventListener("click", close);
    },
  });
  try {
    const response = await api.post(
      "/ai/errors/classify",
      {
        question: item.question,
        student_answer: item.student_answer || "",
        subject_hint: item.subject,
      },
      { timeout: 120000 }
    );
    classified = response.data;
    body.innerHTML = `${aiBanner(response.ai)}
      <div class="classify-result">
        <div class="classify-row"><span>建议学科</span><strong>${escapeHTML(
          classified.subject || item.subject
        )}</strong></div>
        <div class="classify-row"><span>知识点</span><div class="knowledge-tags">${
          classified.knowledge_points?.length
            ? classified.knowledge_points
                .map((point) => `<span class="knowledge-tag">${icon("tag")} ${escapeHTML(point)}</span>`)
                .join("")
            : '<span class="knowledge-tag is-empty">未能可靠识别，请手动填写</span>'
        }</div></div>
        <div class="classify-row"><span>可能原因</span><p>${escapeHTML(classified.analysis || "")}</p></div>
        <div class="classify-row"><span>建议复习</span><p>${escapeHTML(classified.suggested_review || "")}</p></div>
        <div class="classify-row"><span>置信度</span><strong>${escapeHTML(
          { high: "较高", medium: "中等", low: "低" }[classified.confidence] || classified.confidence || "低"
        )}</strong></div>
      </div>
      ${
        classified.warnings?.length
          ? `<ul class="ai-warnings">${classified.warnings
              .map((warning) => `<li>${icon("info")}<span>${escapeHTML(warning)}</span></li>`)
              .join("")}</ul>`
          : ""
      }
      <div class="modal-inline-actions">
        <button type="button" class="btn btn-primary" data-apply-classification>${icon("check")} 应用学科与知识点</button>
        <span class="muted-note">不会自动修改你的错因分析。</span>
      </div>`;
    refreshIcons(body);
    body.querySelector("[data-apply-classification]").addEventListener("click", async (event) => {
      const points = [
        ...new Set([...(item.knowledge_points || []), ...(classified.knowledge_points || [])]),
      ];
      const button = event.currentTarget;
      button.disabled = true;
      button.innerHTML = `<span class="spinner"></span><span>应用中…</span>`;
      try {
        await api.put(`/errors/${item.id}`, {
          subject: classified.subject || item.subject,
          knowledge_points: points,
        });
        modal.close();
        showToast("已应用 AI 建议的学科与知识点");
        refreshCurrent({ preserveScroll: true });
      } catch (error) {
        toastError(error);
        button.disabled = false;
        button.innerHTML = `${icon("check")} 应用学科与知识点`;
        refreshIcons(button);
      }
    });
    refreshIcons(modal.dialog);
  } catch (error) {
    body.innerHTML = `<div class="ai-error-panel">${icon("alert-circle")}<div><strong>归类没有完成</strong><p>${escapeHTML(
      error.message || "请稍后重试"
    )}</p></div></div>`;
    refreshIcons(body);
  }
}

async function render(container) {
  pageController?.abort();
  pageController = new AbortController();
  try {
    const response = await api.get("/errors", { limit: 300 }, { signal: pageController.signal });
    state.errors = response.data.errors || [];
    state.counts = response.data.counts || {};
    renderPage(container);
  } catch (error) {
    if (error.name === "AbortError") return;
    throw error;
  }
}

function cleanup() {
  pageController?.abort();
  pageController = null;
  pageRoot = null;
}

export default {
  title: "错题本",
  render,
  cleanup,
};
