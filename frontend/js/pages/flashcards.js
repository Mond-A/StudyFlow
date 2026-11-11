import { api } from "../api.js";
import { icon, refreshIcons } from "../components/icons.js";
import { openConfirm, openModal } from "../components/modal.js";
import { aiBanner, aiModeBadge } from "../components/ai-display.js";
import { showToast, toastError } from "../components/toast.js";
import { refreshCurrent } from "../router.js";
import { getMeta, getSubjects } from "../services/store.js";
import { renderRichMarkdown } from "../markdown.js";
import {
  emptyState,
  escapeHTML,
  formatDate,
  masteryLabel,
  subjectBadge,
} from "../ui.js";

const state = {
  cards: [],
  notes: [],
  queue: [],
  reviewed: 0,
  flipped: false,
  manageSubject: "all",
};

let pageController = null;
let pageRoot = null;
let keyboardHandler = null;
let ratingInFlight = false;

function dueCount() {
  return state.cards.filter((card) => card.is_due).length;
}

function masteredCount() {
  return state.cards.filter((card) => card.mastery_level >= 4).length;
}

function renderStats() {
  const host = pageRoot?.querySelector("#flashcard-stats");
  if (!host) return;
  host.innerHTML = `
    <div class="summary-chip"><span class="summary-icon violet">${icon("layers")}</span><div><strong>${state.cards.length}</strong><span>全部闪卡</span></div></div>
    <div class="summary-chip"><span class="summary-icon amber">${icon("alarm-clock")}</span><div><strong class="js-due-count">${dueCount()}</strong><span>今日待复习</span></div></div>
    <div class="summary-chip"><span class="summary-icon teal">${icon("badge-check")}</span><div><strong>${masteredCount()}</strong><span>已掌握</span></div></div>
    <div class="summary-chip"><span class="summary-icon blue">${icon("sparkles")}</span><div><strong>${state.notes.length}</strong><span>可生成来源笔记</span></div></div>
  `;
  refreshIcons(host);
}

function reviewQueueMarkup() {
  if (!state.queue.length) {
    return `<div class="review-complete">
      <span class="review-complete-icon">${icon("party-popper")}</span>
      <h3>${state.reviewed ? "本轮复习完成" : "今天没有到期闪卡"}</h3>
      <p>${
        state.reviewed
          ? `你刚刚复习了 ${state.reviewed} 张卡片。休息一下，或者去管理卡片继续补充。`
          : "所有闪卡都还没到复习时间。也可以到下方管理卡片，手动编辑或新建。"
      }</p>
      <div class="review-complete-actions">
        <a href="#/notes" class="btn btn-secondary btn-sm">${icon("notebook-pen")} 从笔记生成</a>
        <button type="button" class="btn btn-primary btn-sm" data-refresh-cards>${icon("refresh-cw")} 刷新列表</button>
      </div>
    </div>`;
  }
  const card = state.queue[0];
  const total = state.reviewed + state.queue.length;
  return `<div class="review-progress-row">
    <span>本轮进度</span>
    <div class="review-progress-bar"><span style="width:${Math.round(
      (state.reviewed / Math.max(1, total)) * 100
    )}%"></span></div>
    <strong>${state.reviewed + 1} / ${total}</strong>
  </div>
  <div class="review-card-meta">
    ${subjectBadge(card.subject, { small: true })}
    <span>${icon("layers")} 掌握度 ${masteryLabel(card.mastery_level)}</span>
    <span>已复习 ${card.review_count || 0} 次</span>
  </div>
  <button type="button" class="flashcard-face ${state.flipped ? "is-flipped" : ""}" data-flashcard-flip aria-label="${
    state.flipped ? "隐藏答案" : "显示答案"
  }">
    <span class="flashcard-side-label">${state.flipped ? "答案" : "问题"}</span>
    <div class="flashcard-content ${state.flipped ? "back-content" : "front-content"}" data-flashcard-content></div>
    <span class="flashcard-tap-hint">${state.flipped ? icon("rotate-ccw") + " 点击回到问题" : icon("eye") + " 点击显示答案"}</span>
  </button>
  <div class="review-rating ${state.flipped ? "is-visible" : ""}">
    <p>这张卡你记得怎么样？</p>
    <div class="rating-buttons">
      <button type="button" class="rating-button rating-again" data-rating="1" ${state.flipped ? "" : "disabled"}>
        <span>${icon("rotate-ccw")}</span><strong>没记住</strong><small>明天再来</small>
      </button>
      <button type="button" class="rating-button rating-fuzzy" data-rating="3" ${state.flipped ? "" : "disabled"}>
        <span>${icon("cloud")}</span><strong>有点模糊</strong><small>1 天后</small>
      </button>
      <button type="button" class="rating-button rating-good" data-rating="5" ${state.flipped ? "" : "disabled"}>
        <span>${icon("sun")}</span><strong>掌握了</strong><small>间隔拉长</small>
      </button>
    </div>
  </div>
  <div class="review-footer">
    <button type="button" class="btn btn-ghost btn-sm" data-skip-card>${icon("skip-forward")} 暂时跳过</button>
    <span class="muted-note">按空格翻面，按 1 / 3 / 5 评分</span>
  </div>`;
}

function renderReviewPanel() {
  const panel = pageRoot?.querySelector("#review-panel");
  if (!panel) return;
  const card = state.queue[0];
  panel.innerHTML = `
    <div class="card-header">
      <div><h2 class="card-title">${icon("brain")} 今日复习</h2><p class="card-subtitle">${
        state.queue.length
          ? `还剩 ${state.queue.length} 张 · 按记忆曲线安排`
          : "按记忆曲线安排复习"
      }</p></div>
      <span class="review-streak-badge">${icon("flame")} 已复习 ${state.reviewed}</span>
    </div>
    <div class="review-panel-body">
      ${reviewQueueMarkup()}
    </div>
  `;
  refreshIcons(panel);
  const content = panel.querySelector("[data-flashcard-content]");
  if (content && card) {
    renderRichMarkdown(content, state.flipped ? card.back : card.front);
  }
  panel.querySelector("[data-refresh-cards]")?.addEventListener("click", () => refreshCurrent({ preserveScroll: true }));
}

function renderManageList() {
  const list = pageRoot?.querySelector("#flashcard-manage-list");
  if (!list) return;
  const subject = state.manageSubject;
  const cards = state.cards.filter((card) => subject === "all" || card.subject === subject);
  list.innerHTML = cards.length
    ? cards
        .map(
          (card) => `<article class="manage-card" data-manage-card="${card.id}">
            <div class="manage-card-main">
              <div class="manage-card-head">${subjectBadge(card.subject, { small: true })}<span class="mastery-dots">${[
            1, 2, 3, 4, 5,
          ]
            .map((level) => `<i class="${card.mastery_level >= level ? "is-on" : ""}"></i>`)
            .join("")}</span><span class="manage-mastery-label">${masteryLabel(card.mastery_level)}</span></div>
              <strong class="manage-front">${escapeHTML(card.front)}</strong>
              <p class="manage-back">${escapeHTML(card.back)}</p>
            </div>
            <div class="manage-card-side">
              <span>${card.is_due ? "今天到期" : `下次 ${card.next_review_date ? formatDate(card.next_review_date) : "未安排"}`}</span>
              <div class="manage-actions">
                <button type="button" class="icon-button" data-card-action="edit" data-card-id="${card.id}" title="编辑闪卡" aria-label="编辑闪卡">${icon("pencil")}</button>
                <button type="button" class="icon-button danger" data-card-action="delete" data-card-id="${card.id}" title="删除闪卡" aria-label="删除闪卡">${icon("trash-2")}</button>
              </div>
            </div>
          </article>`
        )
        .join("")
    : emptyState({
        iconName: "layers",
        title: state.cards.length ? "这个学科还没有闪卡" : "还没有闪卡",
        description: state.cards.length ? "切换学科筛选，或新建一张卡片。" : "手写一张，或者从已有笔记中让 AI 提取复习卡。",
      });
  refreshIcons(list);
  const subjectSelect = pageRoot?.querySelector("#manage-subject");
  if (subjectSelect && subjectSelect.value !== state.manageSubject) subjectSelect.value = state.manageSubject;
}

function subjectsForFilter() {
  return [...new Set(state.cards.map((card) => card.subject))].sort();
}

function renderPage(container) {
  const meta = getMeta();
  const notes = state.notes;
  container.innerHTML = `
    <div class="page-shell">
      <header class="page-header">
        <div class="page-heading">
          <p class="eyebrow">FLASHCARDS · 闪卡复习</p>
          <h1>用主动回忆对抗遗忘</h1>
          <p class="page-subtitle">把笔记中的关键知识变成问题卡。先回忆，再翻面，最后诚实评估掌握程度。</p>
        </div>
        <div class="page-actions">
          <button type="button" class="btn btn-secondary" data-create-flashcard>${icon("plus")}<span>新建闪卡</span></button>
          <button type="button" class="btn btn-primary" data-generate-flashcards ${notes.length ? "" : "disabled title=\"请先创建笔记\""}>
            ${icon("sparkles")}<span>从笔记生成</span>
          </button>
        </div>
      </header>

      <section class="focus-summary-grid" id="flashcard-stats"></section>

      <div class="flashcards-layout">
        <section class="card review-card" id="review-panel"></section>

        <aside class="flashcards-side">
          <section class="card generate-card">
            <div class="card-header">
              <div><h2 class="card-title">${icon("sparkles")} AI 生成闪卡</h2><p class="card-subtitle">从笔记中抽取复习问题，生成结果会明确标注来源。</p></div>
              ${aiModeBadge(meta?.ai, { small: true })}
            </div>
            ${
              notes.length
                ? `<form id="generate-flashcards-form" class="form-stack">
                    <label class="field">
                      <span class="field-label">来源笔记</span>
                      <select class="input" name="note_id">${notes
                        .map(
                          (note) =>
                            `<option value="${note.id}">${escapeHTML(note.title)} · ${escapeHTML(
                              note.subject
                            )}</option>`
                        )
                        .join("")}</select>
                    </label>
                    <label class="field">
                      <span class="field-label">生成数量</span>
                      <select class="input" name="count">
                        <option value="3">3 张</option>
                        <option value="5" selected>5 张</option>
                        <option value="8">8 张</option>
                      </select>
                    </label>
                    <button type="submit" class="btn btn-primary btn-sm btn-full" data-generate-submit>${icon("wand-sparkles")} 生成复习卡</button>
                  </form>`
                : emptyState({
                    iconName: "notebook-pen",
                    title: "先准备一篇笔记",
                    description: "AI 会从你的笔记内容中提取闪卡。",
                    action: `<a href="#/notes" class="btn btn-secondary btn-sm">去创建笔记</a>`,
                  })
            }
          </section>

          <section class="card review-tips-card">
            <h3>${icon("lightbulb")} 有效的复习方式</h3>
            <ul>
              <li>先尝试完整回忆，再翻面看答案，不要一上来就翻。</li>
              <li>诚实选择掌握程度，间隔重复才有意义。</li>
              <li>用“为什么”“怎么用”替代单纯背诵关键词。</li>
            </ul>
          </section>
        </aside>
      </div>

      <section class="card flashcard-manage-card">
        <div class="card-header">
          <div><h2 class="card-title">${icon("gallery-vertical-end")} 管理全部闪卡</h2><p class="card-subtitle">${state.cards.length} 张 · 掌握度与下次复习时间</p></div>
          <select class="input input-sm" id="manage-subject" aria-label="按学科筛选闪卡">
            <option value="all">全部学科</option>
            ${subjectsForFilter()
              .map(
                (subject) =>
                  `<option value="${escapeHTML(subject)}" ${
                    state.manageSubject === subject ? "selected" : ""
                  }>${escapeHTML(subject)}</option>`
              )
              .join("")}
          </select>
        </div>
        <div id="flashcard-manage-list" class="manage-card-list"></div>
      </section>
    </div>
  `;
  pageRoot = container;
  refreshIcons(container);
  renderStats();
  renderReviewPanel();
  renderManageList();
  bindStaticEvents(container);
  bindKeyboard();
}

function bindStaticEvents(container) {
  container.querySelectorAll("[data-create-flashcard]").forEach((button) => {
    button.addEventListener("click", () => openCardModal());
  });
  container.querySelectorAll("[data-generate-flashcards]").forEach((button) => {
    button.addEventListener("click", generateFromNote);
  });
  container.querySelector("#generate-flashcards-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const noteId = Number(formData.get("note_id"));
    const count = Number(formData.get("count") || 5);
    await generateCards(noteId, count, event.currentTarget.querySelector("[data-generate-submit]"));
  });
  container.querySelector("#manage-subject")?.addEventListener("change", (event) => {
    state.manageSubject = event.target.value;
    renderManageList();
  });
  container.querySelector("#flashcard-manage-list")?.addEventListener("click", (event) => {
    const action = event.target.closest("[data-card-action]");
    if (!action) return;
    const card = state.cards.find((item) => String(item.id) === action.dataset.cardId);
    if (!card) return;
    if (action.dataset.cardAction === "edit") openCardModal(card);
    if (action.dataset.cardAction === "delete") deleteCard(card);
  });
  const reviewPanel = container.querySelector("#review-panel");
  reviewPanel?.addEventListener("click", (event) => {
    if (event.target.closest("[data-flashcard-flip]")) {
      state.flipped = !state.flipped;
      renderReviewPanel();
      return;
    }
    const ratingButton = event.target.closest("[data-rating]");
    if (ratingButton && state.flipped && !ratingInFlight) {
      rateCurrentCard(Number(ratingButton.dataset.rating));
      return;
    }
    if (event.target.closest("[data-skip-card]")) {
      if (state.queue.length <= 1) {
        showToast("这是本轮最后一张卡片，可以评分或稍后刷新。", "info");
        return;
      }
      state.queue.push(state.queue.shift());
      state.flipped = false;
      renderReviewPanel();
    }
  });
}

function bindKeyboard() {
  if (keyboardHandler) document.removeEventListener("keydown", keyboardHandler);
  keyboardHandler = (event) => {
    if (document.body.dataset.route !== "flashcards") return;
    const tag = document.activeElement?.tagName?.toLowerCase();
    if (["input", "textarea", "select", "button"].includes(tag)) return;
    if (document.querySelector(".modal-overlay")) return;
    if (event.code === "Space") {
      event.preventDefault();
      state.flipped = !state.flipped;
      renderReviewPanel();
    } else if (["1", "3", "5"].includes(event.key) && state.flipped) {
      event.preventDefault();
      rateCurrentCard(Number(event.key));
    }
  };
  document.addEventListener("keydown", keyboardHandler);
}

async function rateCurrentCard(rating) {
  const card = state.queue[0];
  if (!card || ratingInFlight) return;
  ratingInFlight = true;
  const panel = pageRoot?.querySelector("#review-panel");
  panel?.classList.add("is-rating");
  try {
    const response = await api.post(`/flashcards/${card.id}/review`, { rating });
    state.queue.shift();
    state.reviewed += 1;
    state.flipped = false;
    const updated = response.data.flashcard;
    state.cards = state.cards.map((item) => (item.id === updated.id ? updated : item));
    renderStats();
    renderReviewPanel();
    renderManageList();
    showToast(rating >= 4 ? "已标记为掌握，复习间隔已拉长" : "已记录本次复习");
  } catch (error) {
    toastError(error);
  } finally {
    ratingInFlight = false;
    pageRoot?.querySelector("#review-panel")?.classList.remove("is-rating");
  }
}

function openCardModal(card = null) {
  const subjects = [...new Set([...getSubjects(), card?.subject].filter(Boolean))];
  const body = document.createElement("div");
  body.innerHTML = `<form id="flashcard-form" class="form-stack">
    <label class="field"><span class="field-label">正面问题 *</span><textarea class="input textarea" name="front" rows="4" maxlength="1000" required placeholder="例如：二次函数对称轴公式是什么？" data-autofocus>${escapeHTML(
      card?.front || ""
    )}</textarea></label>
    <label class="field"><span class="field-label">背面答案 *</span><textarea class="input textarea" name="back" rows="5" maxlength="5000" required placeholder="支持 Markdown 与 LaTeX 公式">${escapeHTML(
      card?.back || ""
    )}</textarea></label>
    <label class="field"><span class="field-label">学科</span><input class="input" name="subject" list="flashcard-subjects" maxlength="30" value="${escapeHTML(
      card?.subject || "数学"
    )}"><datalist id="flashcard-subjects">${subjects
      .map((subject) => `<option value="${escapeHTML(subject)}"></option>`)
      .join("")}</datalist></label>
    <p class="form-error" id="flashcard-error" role="alert" hidden></p>
  </form>`;
  const footer = document.createElement("div");
  footer.className = "modal-actions";
  footer.innerHTML = `<button type="button" class="btn btn-secondary" data-cancel>取消</button>
    <button type="submit" form="flashcard-form" class="btn btn-primary" data-submit>${icon("save")}<span>${
      card ? "保存修改" : "创建闪卡"
    }</span></button>`;
  openModal({
    title: card ? "编辑闪卡" : "新建闪卡",
    subtitle: "主动回忆的问题比抄写答案更有效。",
    body,
    footer,
    onMount: ({ close }) => {
      const form = body.querySelector("#flashcard-form");
      const errorEl = body.querySelector("#flashcard-error");
      footer.querySelector("[data-cancel]").addEventListener("click", close);
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const formData = new FormData(form);
        const front = String(formData.get("front") || "").trim();
        const back = String(formData.get("back") || "").trim();
        if (!front || !back) {
          errorEl.textContent = "问题与答案都不能为空";
          errorEl.hidden = false;
          return;
        }
        const submit = footer.querySelector("[data-submit]");
        submit.disabled = true;
        submit.innerHTML = `<span class="spinner"></span><span>保存中…</span>`;
        try {
          const payload = {
            front,
            back,
            subject: String(formData.get("subject") || "综合").trim() || "综合",
          };
          if (card) await api.put(`/flashcards/${card.id}`, payload);
          else await api.post("/flashcards", payload);
          close();
          showToast(card ? "闪卡已更新" : "闪卡已创建");
          refreshCurrent({ preserveScroll: true });
        } catch (error) {
          errorEl.textContent = error.message || "保存失败";
          errorEl.hidden = false;
          submit.disabled = false;
          submit.innerHTML = `${icon("save")}<span>${card ? "保存修改" : "创建闪卡"}</span>`;
          refreshIcons(submit);
        }
      });
    },
  });
}

async function deleteCard(card) {
  const confirmed = await openConfirm({
    title: "删除闪卡",
    message: `确定删除这张闪卡吗？`,
    details: card.front,
    confirmText: "删除闪卡",
    danger: true,
  });
  if (!confirmed) return;
  try {
    await api.delete(`/flashcards/${card.id}`);
    showToast("闪卡已删除");
    refreshCurrent({ preserveScroll: true });
  } catch (error) {
    toastError(error);
  }
}

function generateFromNote() {
  if (!state.notes.length) {
    showToast("请先创建一篇笔记，再生成闪卡。", "info");
    return;
  }
  const body = document.createElement("div");
  body.innerHTML = `<form id="generate-modal-form" class="form-stack">
    <label class="field"><span class="field-label">来源笔记</span>
      <select class="input" name="note_id">${state.notes
        .map(
          (note) =>
            `<option value="${note.id}">${escapeHTML(note.title)} · ${escapeHTML(note.subject)}</option>`
        )
        .join("")}</select>
    </label>
    <label class="field"><span class="field-label">生成数量</span>
      <select class="input" name="count"><option value="3">3 张</option><option value="5" selected>5 张</option><option value="8">8 张</option></select>
    </label>
    <p class="field-hint">${icon("info")} 生成结果会先展示给你挑选，不会自动写入复习库。</p>
  </form>`;
  const footer = document.createElement("div");
  footer.className = "modal-actions";
  footer.innerHTML = `<button type="button" class="btn btn-secondary" data-cancel>取消</button>
    <button type="submit" form="generate-modal-form" class="btn btn-primary" data-submit>${icon("sparkles")}<span>生成闪卡</span></button>`;
  openModal({
    title: "从笔记生成闪卡",
    subtitle: "AI 提取问题与答案，由你决定是否保存。",
    body,
    footer,
    onMount: ({ close }) => {
      const form = body.querySelector("#generate-modal-form");
      footer.querySelector("[data-cancel]").addEventListener("click", close);
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const formData = new FormData(form);
        close();
        await generateCards(
          Number(formData.get("note_id")),
          Number(formData.get("count") || 5),
          null
        );
      });
    },
  });
}

async function generateCards(noteId, count, button) {
  const original = button?.innerHTML;
  if (button) {
    button.disabled = true;
    button.innerHTML = `<span class="spinner"></span><span>生成中…</span>`;
  }
  try {
    const response = await api.post(
      "/ai/flashcards/generate",
      { note_id: noteId, count },
      { timeout: 120000 }
    );
    showGeneratedCards(response.data, response.ai, noteId);
  } catch (error) {
    toastError(error);
  } finally {
    if (button) {
      button.disabled = false;
      button.innerHTML = original || `${icon("wand-sparkles")} 生成复习卡`;
      refreshIcons(button);
    }
  }
}

function showGeneratedCards(data, ai, noteId) {
  const selectedNote = state.notes.find((item) => String(item.id) === String(noteId));
  const cards = data.cards || [];
  if (!cards.length) {
    showToast("AI 没有生成可用的闪卡，请尝试内容更充实的笔记。", "warning");
    return;
  }
  const body = document.createElement("div");
  body.innerHTML = `${aiBanner(ai)}
    <p class="ai-summary-text">${escapeHTML(data.summary || "")}</p>
    ${
      data.warnings?.length
        ? `<div class="notice-box notice-warning">${data.warnings
            .map((warning) => `<p>${escapeHTML(warning)}</p>`)
            .join("")}</div>`
        : ""
    }
    <div class="generated-card-list">
      ${cards
        .map(
          (card, index) => `<label class="generated-card">
            <input type="checkbox" checked data-generated-index="${index}">
            <div><strong>${escapeHTML(card.front)}</strong><p>${escapeHTML(card.back)}</p>
              <span class="knowledge-point-tag">${icon("tag")} ${escapeHTML(
                card.knowledge_point || "未标注知识点"
              )}</span></div>
          </label>`
        )
        .join("")}
    </div>
    <div class="modal-inline-actions">
      <button type="button" class="btn btn-primary" data-save-generated>${icon("save")} 保存选中闪卡</button>
      <span class="muted-note">保存后会进入复习卡库。</span>
    </div>`;
  const footer = document.createElement("div");
  footer.className = "modal-actions";
  footer.innerHTML = `<button type="button" class="btn btn-secondary" data-close>关闭</button>`;
  openModal({
    title: "AI 生成的闪卡",
    subtitle: "请先核对卡片内容，取消勾选不准确的条目。",
    body,
    footer,
    size: "lg",
    closeOnBackdrop: false,
    onMount: ({ close }) => {
      footer.querySelector("[data-close]").addEventListener("click", close);
      body.querySelector("[data-save-generated]").addEventListener("click", async (event) => {
        const selected = [...body.querySelectorAll("[data-generated-index]")].filter(
          (input) => input.checked
        );
        if (!selected.length) {
          toastError(new Error("请至少选择一张闪卡"));
          return;
        }
        const subject = selectedNote?.subject || "综合";
        const button = event.currentTarget;
        const original = button.innerHTML;
        button.disabled = true;
        button.innerHTML = `<span class="spinner"></span><span>保存中…</span>`;
        let saved = 0;
        for (const input of selected) {
          const card = cards[Number(input.dataset.generatedIndex)];
          try {
            await api.post("/flashcards", {
              front: card.front,
              back: card.back,
              subject,
              note_id: noteId || null,
            });
            saved += 1;
          } catch (error) {
            console.error("Failed to save flashcard", error);
          }
        }
        if (saved) {
          showToast(`已保存 ${saved} 张闪卡`);
          close();
          refreshCurrent({ preserveScroll: true });
        } else {
          toastError(new Error("闪卡保存失败，请重试"));
          button.disabled = false;
          button.innerHTML = original;
          refreshIcons(button);
        }
      });
    },
  });
  refreshIcons(body);
}

async function render(container) {
  pageController?.abort();
  pageController = new AbortController();
  try {
    const [cardsResponse, notesResponse] = await Promise.all([
      api.get("/flashcards", { limit: 500 }, { signal: pageController.signal }),
      api.get("/notes", { limit: 200 }, { signal: pageController.signal }),
    ]);
    state.cards = cardsResponse.data.flashcards || [];
    state.notes = notesResponse.data.notes || [];
    state.queue = state.cards.filter((card) => card.is_due);
    state.reviewed = 0;
    state.flipped = false;
    state.manageSubject = "all";
    renderPage(container);
  } catch (error) {
    if (error.name === "AbortError") return;
    throw error;
  }
}

function cleanup() {
  pageController?.abort();
  pageController = null;
  if (keyboardHandler) {
    document.removeEventListener("keydown", keyboardHandler);
    keyboardHandler = null;
  }
  pageRoot = null;
}

export default {
  title: "闪卡复习",
  render,
  cleanup,
};
