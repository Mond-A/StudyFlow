import { api } from "../api.js";
import { icon, refreshIcons } from "../components/icons.js";
import { openConfirm, openModal } from "../components/modal.js";
import { aiBanner, aiModeBadge } from "../components/ai-display.js";
import { showToast, toastError } from "../components/toast.js";
import { createImageUploader } from "../components/upload.js";
import { refreshCurrent } from "../router.js";
import { getMeta, getSubjects } from "../services/store.js";
import { renderRichMarkdown } from "../markdown.js";
import {
  emptyState,
  escapeHTML,
  formatAgo,
  formatDate,
  formatDateTime,
  subjectBadge,
} from "../ui.js";

const state = {
  notes: [],
  selectedId: null,
  subject: "all",
  search: "",
  activeTab: "edit",
};

let pageController = null;
let auditController = null;
let graphController = null;
let currentNote = null;
let editor = null;
let fallbackTextarea = null;
let cytoscapeInstance = null;
let dirty = false;
let changeVersion = 0;
let savePromise = null;
let autoSaveTimer = null;
let pageRoot = null;
let beforeUnloadHandler = null;
let currentGraphData = null;

function getEditorMarkdown() {
  if (editor && typeof editor.getMarkdown === "function") return editor.getMarkdown();
  if (fallbackTextarea) return fallbackTextarea.value;
  return currentNote?.content_markdown || "";
}

function setEditorMarkdown(markdown, { silent = true } = {}) {
  if (editor && typeof editor.setMarkdown === "function") {
    editor.setMarkdown(markdown || "", false);
  } else if (fallbackTextarea) {
    fallbackTextarea.value = markdown || "";
  }
  if (silent) {
    dirty = false;
    updateSaveStatus("已保存");
  }
}

function filteredNotes() {
  return state.notes.filter((note) => {
    if (state.subject !== "all" && note.subject !== state.subject) return false;
    if (state.search) {
      const haystack = `${note.title} ${note.snippet} ${note.subject}`.toLowerCase();
      if (!haystack.includes(state.search.toLowerCase())) return false;
    }
    return true;
  });
}

function noteListItem(note) {
  return `<button type="button" class="note-list-item ${
    String(note.id) === String(state.selectedId) ? "is-active" : ""
  }" data-note-id="${note.id}">
    <div class="note-list-top">
      <strong>${escapeHTML(note.title)}</strong>
      ${subjectBadge(note.subject, { small: true })}
    </div>
    <p>${escapeHTML(note.snippet || "空白笔记")}</p>
    <div class="note-list-meta">
      <span>${icon("clock-3")}${formatAgo(note.updated_at)}</span>
      ${note.has_graph ? `<span class="note-mini-badge">${icon("git-branch")}图谱</span>` : ""}
      ${note.has_audit ? `<span class="note-mini-badge">${icon("shield-check")}已检查</span>` : ""}
    </div>
  </button>`;
}

function renderNoteList() {
  const listEl = pageRoot?.querySelector("#note-list");
  if (!listEl) return;
  const notes = filteredNotes();
  listEl.innerHTML = notes.length
    ? notes.map(noteListItem).join("")
    : emptyState({
        iconName: state.notes.length ? "search-x" : "notebook-pen",
        title: state.notes.length ? "没有匹配的笔记" : "还没有笔记",
        description: state.notes.length
          ? "试试其他关键词或学科。"
          : "新建一篇笔记，或上传手写笔记图片让 AI 帮你数字化。",
      });
  refreshIcons(listEl);
}

function noteSidebar() {
  const allSubjects = [...new Set(state.notes.map((note) => note.subject))].sort();
  return `<aside class="notes-sidebar card">
    <div class="notes-sidebar-head">
      <div><h2 class="card-title">${icon("library")} 我的笔记</h2><p class="card-subtitle">${state.notes.length} 篇 · 本地持久化</p></div>
      <button type="button" class="icon-button" data-new-note title="新建笔记" aria-label="新建笔记">${icon("plus")}</button>
    </div>
    <div class="notes-filter">
      <div class="search-box search-box-sm">${icon("search")}<input id="note-search" type="search" placeholder="搜索笔记…" value="${escapeHTML(
        state.search
      )}" aria-label="搜索笔记"></div>
      <select class="input input-sm" id="note-subject-filter" aria-label="按学科筛选笔记">
        <option value="all">全部学科</option>
        ${allSubjects
          .map(
            (subject) =>
              `<option value="${escapeHTML(subject)}" ${
                state.subject === subject ? "selected" : ""
              }>${escapeHTML(subject)}</option>`
          )
          .join("")}
      </select>
    </div>
    <div class="note-list" id="note-list">${filteredNotes().map(noteListItem).join("")}</div>
  </aside>`;
}

function noteEditorPanel() {
  if (!currentNote) {
    return `<section class="notes-editor card notes-empty">
      ${emptyState({
        iconName: "notebook-pen",
        title: "选择或创建一篇笔记",
        description: "用 Toast UI Editor 编辑 Markdown，用 KaTeX 渲染公式，AI 可以帮助识别、检查和整理知识点。",
        action: `<button type="button" class="btn btn-primary btn-sm" data-new-note>${icon("plus")} 新建笔记</button>`,
      })}
    </section>`;
  }
  const hasAudit = Boolean(currentNote.audit_report);
  return `<section class="notes-editor card" id="note-editor-card">
    <div class="note-editor-head">
      <div class="note-title-field">
        <span class="note-field-label">标题</span>
        <input class="note-title-input" id="note-title" maxlength="180" value="${escapeHTML(
          currentNote.title
        )}" aria-label="笔记标题">
      </div>
      <div class="note-head-actions">
        <span class="save-status" id="note-save-status"><span class="save-dot"></span>已保存</span>
        <button type="button" class="btn btn-primary btn-sm" data-save-note>${icon("save")} 保存</button>
      </div>
    </div>
    <div class="note-document-meta">
      <label class="inline-field">学科
        <input class="input input-sm inline-input" id="note-subject" list="note-subject-options" maxlength="30" value="${escapeHTML(
          currentNote.subject
        )}">
        <datalist id="note-subject-options">${getSubjects()
          .map((subject) => `<option value="${escapeHTML(subject)}"></option>`)
          .join("")}</datalist>
      </label>
      <span>${icon("clock-3")} 更新于 ${formatDateTime(currentNote.updated_at)}</span>
      ${
        currentNote.source_image
          ? `<a href="${escapeHTML(currentNote.source_image)}" target="_blank" rel="noopener" class="source-image-link">${icon("image")} 查看来源图片</a>`
          : ""
      }
    </div>
    <div class="note-toolbar">
      <div class="note-tabs" role="tablist" aria-label="笔记视图">
        <button type="button" class="note-tab ${state.activeTab === "edit" ? "is-active" : ""}" data-note-tab="edit" role="tab" aria-selected="${
          state.activeTab === "edit"
        }">${icon("pencil-line")} 编辑</button>
        <button type="button" class="note-tab ${state.activeTab === "preview" ? "is-active" : ""}" data-note-tab="preview" role="tab" aria-selected="${
          state.activeTab === "preview"
        }">${icon("eye")} 公式预览</button>
        <button type="button" class="note-tab ${state.activeTab === "graph" ? "is-active" : ""}" data-note-tab="graph" role="tab" aria-selected="${
          state.activeTab === "graph"
        }">${icon("git-branch")} 知识图谱 ${currentNote.knowledge_graph ? '<span class="tab-dot"></span>' : ""}</button>
      </div>
      <div class="note-toolbar-actions">
        ${hasAudit ? `<button type="button" class="btn btn-ghost btn-sm" data-view-audit>${icon("history")} 查看上次检查</button>` : ""}
        <button type="button" class="btn btn-secondary btn-sm" data-audit-note>${icon("shield-check")} AI 检查</button>
        <button type="button" class="icon-button danger" data-delete-note title="删除笔记" aria-label="删除笔记">${icon("trash-2")}</button>
      </div>
    </div>
    <div class="note-panes">
      <div class="note-pane ${state.activeTab === "edit" ? "is-active" : ""}" data-note-pane="edit">
        <div id="note-editor" class="note-editor-host"></div>
      </div>
      <div class="note-pane ${state.activeTab === "preview" ? "is-active" : ""}" data-note-pane="preview">
        <div class="preview-toolbar"><span>${icon("sigma")} KaTeX 公式已启用</span><span class="muted-note">行内 $...$ · 块级 $$...$$</span></div>
        <div class="markdown-body note-preview" id="note-preview"></div>
      </div>
      <div class="note-pane ${state.activeTab === "graph" ? "is-active" : ""}" data-note-pane="graph">
        <div class="graph-pane" id="note-graph-pane"></div>
      </div>
    </div>
    <div class="note-footer-hint">
      <span>${icon("info")} 笔记自动保存草稿（停止输入后），也可以手动保存。AI 检查不会自动改动原文。</span>
      <span class="char-count" id="note-char-count">${(currentNote.content_markdown || "").length} 字符</span>
    </div>
  </section>`;
}

function renderPage(container) {
  const meta = getMeta();
  container.innerHTML = `
    <div class="page-shell notes-page">
      <header class="page-header">
        <div class="page-heading">
          <h1>把知识整理成自己的结构</h1>
          <p class="page-subtitle">手写笔记数字化、AI 检查、公式渲染与知识点关系图，都在同一个工作区完成。</p>
        </div>
        <div class="page-actions">
          <button type="button" class="btn btn-secondary" data-recognize-note>${icon("scan-line")}<span>图片识别笔记</span></button>
          <button type="button" class="btn btn-primary" data-new-note>${icon("plus")}<span>新建笔记</span></button>
        </div>
      </header>
      <div class="notes-mode-bar">
        <div class="notes-mode-info">${aiModeBadge(meta?.ai, { small: true })}<span>AI 识别与检查都会明确标注来源；原笔记需要你确认后才会修改。</span></div>
        <span class="notes-count">${icon("notebook-pen")} ${state.notes.length} 篇笔记</span>
      </div>
      <div class="notes-layout">
        ${noteSidebar()}
        ${noteEditorPanel()}
      </div>
    </div>
  `;
  pageRoot = container;
  refreshIcons(container);
  renderNoteList();
  bindStaticEvents(container);
  if (currentNote) {
    initEditor();
    bindEditorEvents(container);
    activateTab(state.activeTab, { initial: true });
  }
}

function bindStaticEvents(container) {
  container.querySelectorAll("[data-new-note]").forEach((button) => {
    button.addEventListener("click", openNewNoteModal);
  });
  container.querySelectorAll("[data-recognize-note]").forEach((button) => {
    button.addEventListener("click", openNoteRecognitionModal);
  });
  const noteList = container.querySelector("#note-list");
  noteList?.addEventListener("click", (event) => {
    const item = event.target.closest("[data-note-id]");
    if (!item) return;
    selectNote(Number(item.dataset.noteId));
  });
  container.querySelector("#note-search")?.addEventListener("input", (event) => {
    state.search = event.target.value.trim();
    renderNoteList();
  });
  container.querySelector("#note-subject-filter")?.addEventListener("change", (event) => {
    state.subject = event.target.value;
    renderNoteList();
  });
}

async function selectNote(noteId) {
  if (String(noteId) === String(state.selectedId)) return;
  if (dirty) {
    const saved = await saveCurrentNote({ silent: true });
    if (!saved) return;
  }
  state.selectedId = noteId;
  state.activeTab = "edit";
  await refreshCurrent({ preserveScroll: true });
  // On tablet/mobile the list and editor are stacked. Selecting a note should
  // take the learner directly to the editor rather than making them hunt for it.
  if (window.innerWidth <= 900) {
    requestAnimationFrame(() => {
      pageRoot?.querySelector(".notes-editor, .notes-empty")?.scrollIntoView({
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
        block: "start",
      });
    });
  }
}

function initEditor() {
  destroyEditor();
  const host = document.querySelector("#note-editor");
  if (!host) return;
  const Editor = window.toastui && window.toastui.Editor;
  if (!Editor) {
    host.innerHTML = `<div class="editor-fallback">
      <p class="notice-box notice-warning">${icon("triangle-alert")} Toast UI Editor 资源未加载，已切换到基础 Markdown 编辑框。功能仍可使用。</p>
      <textarea id="note-editor-fallback" class="editor-fallback-textarea" rows="22"></textarea>
    </div>`;
    fallbackTextarea = host.querySelector("#note-editor-fallback");
    fallbackTextarea.value = currentNote.content_markdown || "";
    fallbackTextarea.addEventListener("input", () => {
      dirty = true;
      changeVersion += 1;
      updateCharCount();
      scheduleAutoSave();
    });
    return;
  }
  host.innerHTML = "";
  editor = new Editor({
    el: host,
    height: "520px",
    initialEditType: "markdown",
    previewStyle: "vertical",
    initialValue: currentNote.content_markdown || "",
    usageStatistics: false,
    hideModeSwitch: true,
    autofocus: false,
    placeholder: "用 Markdown 记录知识点。数学公式可写成 $x^2$ 或 $$\\frac{a}{b}$$…",
    toolbarItems: [
      ["heading", "bold", "italic", "strike"],
      ["hr", "quote"],
      ["ul", "ol", "task", "indent", "outdent"],
      ["table", "link"],
      ["code", "codeblock"],
    ],
  });
  editor.on("change", () => {
    dirty = true;
    changeVersion += 1;
    updateCharCount();
    updateSaveStatus("未保存");
    scheduleAutoSave();
  });
  dirty = false;
  updateSaveStatus("已保存");
  updateCharCount();
  beforeUnloadHandler = (event) => {
    if (dirty) {
      event.preventDefault();
      event.returnValue = "";
    }
  };
  window.addEventListener("beforeunload", beforeUnloadHandler);
}

function destroyEditor() {
  try {
    if (editor && typeof editor.destroy === "function") editor.destroy();
  } catch {
    // editor already detached
  }
  editor = null;
  fallbackTextarea = null;
  if (beforeUnloadHandler) {
    window.removeEventListener("beforeunload", beforeUnloadHandler);
    beforeUnloadHandler = null;
  }
  clearTimeout(autoSaveTimer);
  autoSaveTimer = null;
}

function bindEditorEvents(container) {
  container.querySelector("#note-title")?.addEventListener("input", markDirty);
  container.querySelector("#note-subject")?.addEventListener("change", markDirty);
  container.querySelector("[data-save-note]")?.addEventListener("click", () => saveCurrentNote({ silent: false }));
  container.querySelector("[data-audit-note]")?.addEventListener("click", runAudit);
  container.querySelector("[data-view-audit]")?.addEventListener("click", () => {
    if (currentNote?.audit_report) showAuditModal(currentNote.audit_report, null);
  });
  container.querySelector("[data-delete-note]")?.addEventListener("click", deleteCurrentNote);
  container.querySelectorAll("[data-note-tab]").forEach((tab) => {
    tab.addEventListener("click", () => activateTab(tab.dataset.noteTab));
  });
}

function markDirty() {
  dirty = true;
  changeVersion += 1;
  updateSaveStatus("未保存");
  scheduleAutoSave();
}

function scheduleAutoSave() {
  clearTimeout(autoSaveTimer);
  autoSaveTimer = window.setTimeout(() => {
    if (dirty) saveCurrentNote({ silent: true, autosave: true });
  }, 4000);
}

function updateSaveStatus(text) {
  const el = pageRoot?.querySelector("#note-save-status");
  if (!el) return;
  const isDirty = text !== "已保存";
  el.classList.toggle("is-dirty", isDirty);
  el.classList.toggle("is-saving", text === "保存中…");
  el.innerHTML = `<span class="save-dot"></span>${escapeHTML(text)}`;
}

function updateCharCount() {
  const el = pageRoot?.querySelector("#note-char-count");
  if (el) el.textContent = `${getEditorMarkdown().length} 字符`;
}

async function saveCurrentNote({ silent = true, autosave = false } = {}) {
  if (!currentNote) return false;
  if (savePromise) return savePromise;
  clearTimeout(autoSaveTimer);
  const version = changeVersion;
  const titleInput = pageRoot?.querySelector("#note-title");
  const subjectInput = pageRoot?.querySelector("#note-subject");
  const title = (titleInput?.value || currentNote.title || "未命名笔记").trim() || "未命名笔记";
  const subject = (subjectInput?.value || currentNote.subject || "综合").trim() || "综合";
  const markdown = getEditorMarkdown();
  if (titleInput) titleInput.value = title;
  if (!silent) updateSaveStatus("保存中…");
  savePromise = (async () => {
    try {
      const response = await api.put(`/notes/${currentNote.id}`, {
        title,
        subject,
        content_markdown: markdown,
      });
      currentNote = { ...currentNote, ...response.data };
      const listItem = state.notes.find((item) => item.id === currentNote.id);
      if (listItem) {
        Object.assign(listItem, {
          title: currentNote.title,
          subject: currentNote.subject,
          snippet: (markdown || "").replace(/[#*`>\[\]]/g, "").slice(0, 140),
          updated_at: currentNote.updated_at,
          content_length: markdown.length,
        });
      }
      if (version === changeVersion) {
        dirty = false;
        updateSaveStatus(autosave ? "已自动保存" : "已保存");
      } else {
        updateSaveStatus("未保存");
        scheduleAutoSave();
      }
      renderNoteList();
      if (!silent) showToast("笔记已保存");
      return true;
    } catch (error) {
      updateSaveStatus("保存失败");
      if (!silent) toastError(error);
      else console.warn("Autosave failed", error);
      return false;
    } finally {
      savePromise = null;
    }
  })();
  return savePromise;
}

function activateTab(tabName, { initial = false } = {}) {
  if (!currentNote) return;
  state.activeTab = tabName;
  document.querySelectorAll("[data-note-tab]").forEach((tab) => {
    const active = tab.dataset.noteTab === tabName;
    tab.classList.toggle("is-active", active);
    tab.setAttribute("aria-selected", String(active));
  });
  document.querySelectorAll("[data-note-pane]").forEach((pane) => {
    const active = pane.dataset.notePane === tabName;
    pane.classList.toggle("is-active", active);
    pane.hidden = !active;
  });
  if (tabName === "preview") {
    renderPreview();
  }
  if (tabName === "graph") {
    initGraphPane();
  }
  if (tabName === "edit" && editor) {
    requestAnimationFrame(() => {
      try {
        editor.layout();
      } catch {
        // noop
      }
    });
  }
  if (!initial) refreshIcons(document.querySelector(".note-toolbar") || document);
}

function renderPreview() {
  const el = document.querySelector("#note-preview");
  if (!el) return;
  const markdown = getEditorMarkdown();
  if (!markdown.trim()) {
    el.innerHTML = emptyState({
      iconName: "file-text",
      title: "笔记还是空白的",
      description: "回到编辑页写入内容后，这里会显示渲染结果。",
    });
    return;
  }
  renderRichMarkdown(el, markdown);
}

function graphShell(graphData) {
  return `<div class="graph-layout">
    <div class="graph-main">
      <div class="graph-toolbar">
        <div class="graph-legend">
          ${["概念", "公式", "定理", "方法", "应用"]
            .map((type) => `<span><i class="graph-legend-dot type-${type}"></i>${type}</span>`)
            .join("")}
        </div>
        <div class="graph-controls">
          <button type="button" class="icon-button" data-graph-action="zoom-in" title="放大" aria-label="放大">${icon("plus")}</button>
          <button type="button" class="icon-button" data-graph-action="zoom-out" title="缩小" aria-label="缩小">${icon("minus")}</button>
          <button type="button" class="icon-button" data-graph-action="fit" title="适应画布" aria-label="适应画布">${icon("maximize")}</button>
        </div>
      </div>
      <div class="graph-canvas" id="knowledge-graph" role="img" aria-label="知识点关系图"></div>
      <p class="graph-hint">${icon("move")} 拖动画布、滚轮缩放、拖动节点；点击节点查看知识点详情。</p>
    </div>
    <aside class="graph-detail" id="graph-node-detail">
      ${emptyState({
        iconName: "mouse-pointer-2",
        title: "选择知识点",
        description: "点击图谱中的节点，查看它的类型、说明和关联关系。",
      })}
    </aside>
  </div>
  <div class="graph-meta">
    <p>${escapeHTML(graphData.summary || "")}</p>
    ${
      graphData.warnings?.length
        ? `<div class="notice-box notice-warning">${graphData.warnings
            .map((warning) => `<p>${escapeHTML(warning)}</p>`)
            .join("")}</div>`
        : ""
    }
    <div class="graph-actions">
      <span class="muted-note">${graphData.generated_at ? `生成于 ${formatDateTime(graphData.generated_at)}` : "已保存的关系图"}</span>
      <button type="button" class="btn btn-secondary btn-sm" data-generate-graph>${icon("refresh-cw")} 重新生成</button>
    </div>
  </div>`;
}

function initGraphPane() {
  const pane = document.querySelector("#note-graph-pane");
  if (!pane) return;
  const graphData = currentGraphData || currentNote?.knowledge_graph;
  if (!graphData || !graphData.nodes?.length) {
    pane.innerHTML = `<div class="graph-empty-state">
      ${emptyState({
        iconName: "git-branch",
        title: "还没有知识关系图",
        description: "让 AI 从笔记中提取知识点、前置关系与从属结构，生成可交互的关系图。",
        action: `<button type="button" class="btn btn-primary btn-sm" data-generate-graph>${icon("sparkles")} 生成知识图谱</button>`,
      })}
      <p class="graph-ai-note">${icon("info")} 生成前会先保存当前笔记。AI 提取的节点与关系需人工核对。</p>
    </div>`;
    pane.querySelector("[data-generate-graph]")?.addEventListener("click", generateGraph);
    refreshIcons(pane);
    return;
  }
  currentGraphData = graphData;
  pane.innerHTML = graphShell(graphData);
  refreshIcons(pane);
  pane.querySelector("[data-generate-graph]")?.addEventListener("click", generateGraph);
  bindGraphControls(pane);
  requestAnimationFrame(() => mountCytoscape(graphData));
}

function mountCytoscape(graphData) {
  const container = document.querySelector("#knowledge-graph");
  if (!container) return;
  if (!window.cytoscape) {
    container.innerHTML = `<div class="inline-error">${icon("alert-circle")}<span>关系图库 Cytoscape.js 未加载，请查看浏览器控制台。</span></div>`;
    refreshIcons(container);
    return;
  }
  if (cytoscapeInstance) {
    cytoscapeInstance.destroy();
    cytoscapeInstance = null;
  }
  const colors = {
    概念: "#2563eb",
    公式: "#0d9488",
    定理: "#7c3aed",
    方法: "#d97706",
    应用: "#db2777",
  };
  const elements = [
    ...graphData.nodes.map((node) => ({
      data: {
        id: String(node.id),
        label: node.label,
        type: node.type,
        description: node.description || "",
        color: colors[node.type] || "#64748b",
      },
    })),
    ...graphData.edges.map((edge, index) => ({
      data: {
        id: `edge-${index}`,
        source: String(edge.source),
        target: String(edge.target),
        label: edge.label,
      },
    })),
  ];
  try {
    cytoscapeInstance = window.cytoscape({
      container,
      elements,
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "background-color": "data(color)",
            "background-opacity": 0.12,
            "border-width": 2,
            "border-color": "data(color)",
            color: "#0f172a",
            "font-size": 13,
            "font-weight": 600,
            "text-wrap": "wrap",
            "text-max-width": 120,
            "text-valign": "center",
            "text-halign": "center",
            shape: "round-rectangle",
            width: "label",
            height: 42,
            padding: "10px",
          },
        },
        {
          selector: "node:selected",
          style: {
            "background-opacity": 0.28,
            "border-width": 3,
            "overlay-color": "data(color)",
            "overlay-opacity": 0.08,
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.4,
            "line-color": "#cbd5e1",
            "target-arrow-color": "#94a3b8",
            "target-arrow-shape": "triangle",
            "arrow-scale": 0.8,
            "curve-style": "bezier",
            label: "data(label)",
            "font-size": 9,
            color: "#64748b",
            "text-rotation": "autorotate",
            "text-background-color": "#ffffff",
            "text-background-opacity": 0.88,
            "text-background-padding": 2,
          },
        },
        {
          selector: "edge:selected",
          style: { "line-color": "#2563eb", "target-arrow-color": "#2563eb", width: 2 },
        },
      ],
      layout: {
        name: "cose",
        animate: false,
        randomize: false,
        fit: true,
        padding: 36,
        idealEdgeLength: 105,
        nodeRepulsion: 14000,
        gravity: 0.35,
        numIter: 900,
      },
      minZoom: 0.35,
      maxZoom: 2.5,
      wheelSensitivity: 0.2,
      boxSelectionEnabled: false,
    });
    const showNodeDetail = (node) => {
      const outgoing = node.outgoers("edge");
      const incoming = node.incomers("edge");
      const relationships = [];
      outgoing.forEach((edge) => {
        const target = edge.target();
        relationships.push(
          `<li><span class="relation-tag">${escapeHTML(edge.data("label"))}</span><span>→ ${escapeHTML(
            target.data("label")
          )}</span></li>`
        );
      });
      incoming.forEach((edge) => {
        const source = edge.source();
        relationships.push(
          `<li><span class="relation-tag">${escapeHTML(edge.data("label"))}</span><span>${escapeHTML(
            source.data("label")
          )} →</span></li>`
        );
      });
      const detail = document.querySelector("#graph-node-detail");
      if (!detail) return;
      detail.innerHTML = `<div class="graph-detail-inner">
        <span class="node-type-badge node-type-${escapeHTML(node.data("type"))}">${escapeHTML(
          node.data("type")
        )}</span>
        <h3>${escapeHTML(node.data("label"))}</h3>
        <p>${escapeHTML(node.data("description") || "AI 未提供节点说明，请结合笔记核对。")}</p>
        <div class="node-relations"><h4>关联关系</h4>${
          relationships.length
            ? `<ul>${relationships.join("")}</ul>`
            : '<p class="muted-note">这个节点暂时没有关联边。</p>'
        }</div>
        <span class="graph-detail-hint">节点与关系由 AI 提取，仅供参考。</span>
      </div>`;
      refreshIcons(detail);
    };
    cytoscapeInstance.on("tap", "node", (event) => {
      showNodeDetail(event.target);
    });
    cytoscapeInstance.on("tap", (event) => {
      if (event.target !== cytoscapeInstance) return;
      cytoscapeInstance.nodes().unselect();
    });
    const firstNode = cytoscapeInstance.nodes().first();
    if (firstNode.nonempty()) {
      firstNode.select();
      showNodeDetail(firstNode);
    }
  } catch (error) {
    console.error("Knowledge graph rendering failed", error);
    container.innerHTML = `<div class="inline-error">${icon("alert-circle")}<span>关系图绘制失败，请尝试重新生成。</span></div>`;
    refreshIcons(container);
  }
}

function bindGraphControls(pane) {
  pane.querySelectorAll("[data-graph-action]").forEach((button) => {
    button.addEventListener("click", () => {
      if (!cytoscapeInstance) return;
      const action = button.dataset.graphAction;
      if (action === "zoom-in") cytoscapeInstance.zoom(cytoscapeInstance.zoom() * 1.2);
      if (action === "zoom-out") cytoscapeInstance.zoom(cytoscapeInstance.zoom() / 1.2);
      if (action === "fit") cytoscapeInstance.fit(undefined, 40);
    });
  });
}

async function generateGraph() {
  if (!currentNote) return;
  const buttons = document.querySelectorAll("[data-generate-graph]");
  buttons.forEach((button) => {
    button.disabled = true;
    button.innerHTML = `<span class="spinner"></span><span>生成中…</span>`;
  });
  if (dirty) {
    const saved = await saveCurrentNote({ silent: true });
    if (!saved) {
      buttons.forEach((button) => {
        button.disabled = false;
        button.innerHTML = `${icon("sparkles")} 生成知识图谱`;
      });
      return;
    }
  }
  graphController?.abort();
  graphController = new AbortController();
  const pane = document.querySelector("#note-graph-pane");
  if (pane) {
    pane.innerHTML = `<div class="graph-loading"><span class="spinner spinner-lg"></span><strong>正在提取知识点与关系…</strong><p>AI 返回结构化节点和边后再绘制关系图。</p></div>`;
  }
  try {
    const response = await api.post(
      `/notes/${currentNote.id}/graph`,
      {},
      { signal: graphController.signal, timeout: 120000 }
    );
    currentGraphData = response.data;
    currentNote = { ...currentNote, knowledge_graph: response.data };
    const listItem = state.notes.find((item) => item.id === currentNote.id);
    if (listItem) listItem.has_graph = true;
    state.activeTab = "graph";
    initGraphPane();
    const paneCheck = document.querySelector("[data-note-pane='graph']");
    if (paneCheck) {
      const ai = response.ai;
      if (ai?.mode === "demo") {
        const bannerHost = document.createElement("div");
        bannerHost.innerHTML = aiBanner(ai);
        paneCheck.prepend(bannerHost.firstElementChild);
        refreshIcons(paneCheck);
      }
    }
    showToast("知识关系图已生成");
    renderNoteList();
  } catch (error) {
    if (error.name === "AbortError") return;
    if (pane) {
      pane.innerHTML = `<div class="graph-empty-state"><div class="inline-error">${icon(
        "alert-circle"
      )}<span>${escapeHTML(error.message || "知识图生成失败")}</span></div>
      <button type="button" class="btn btn-secondary btn-sm" data-generate-graph>${icon(
        "refresh-cw"
      )} 再试一次</button></div>`;
      pane.querySelector("[data-generate-graph]")?.addEventListener("click", generateGraph);
      refreshIcons(pane);
    }
  } finally {
    buttons.forEach((button) => {
      if (button.isConnected) {
        button.disabled = false;
        button.innerHTML = `${icon("refresh-cw")} 重新生成`;
        refreshIcons(button);
      }
    });
  }
}

async function runAudit() {
  if (!currentNote) return;
  if (dirty) {
    const saved = await saveCurrentNote({ silent: true });
    if (!saved) return;
  }
  auditController?.abort();
  auditController = new AbortController();
  const button = document.querySelector("[data-audit-note]");
  const original = button?.innerHTML;
  if (button) {
    button.disabled = true;
    button.innerHTML = `<span class="spinner"></span><span>检查中…</span>`;
  }
  const body = document.createElement("div");
  body.innerHTML = `<div class="ai-loading"><span class="spinner spinner-lg"></span><strong>正在检查笔记…</strong><p>AI 会尝试发现知识性错误、公式问题与识别疑点，但不会自动修改原文。</p></div>`;
  const footer = document.createElement("div");
  footer.className = "modal-actions";
  footer.innerHTML = `<button type="button" class="btn btn-secondary" data-close-audit>关闭</button>`;
  const modal = openModal({
    title: "AI 笔记检查",
    subtitle: "只提供建议，原笔记保持不变。",
    body,
    footer,
    size: "lg",
    onMount: ({ close }) => {
      footer.querySelector("[data-close-audit]").addEventListener("click", close);
    },
  });
  try {
    const response = await api.post(
      `/notes/${currentNote.id}/audit`,
      {},
      { signal: auditController.signal, timeout: 120000 }
    );
    currentNote = { ...currentNote, audit_report: response.data };
    const listItem = state.notes.find((item) => item.id === currentNote.id);
    if (listItem) listItem.has_audit = true;
    body.innerHTML = renderAuditMarkup(response.data, response.ai);
    refreshIcons(body);
    refreshIcons(modal.dialog);
    renderNoteList();
  } catch (error) {
    if (error.name === "AbortError") return;
    body.innerHTML = `<div class="ai-error-panel">${icon("alert-circle")}<div><strong>检查没有完成</strong><p>${escapeHTML(
      error.message || "请稍后重试"
    )}</p></div></div>`;
    refreshIcons(body);
  } finally {
    if (button) {
      button.disabled = false;
      button.innerHTML = original;
      refreshIcons(button);
    }
  }
}

function showAuditModal(report, ai) {
  const body = document.createElement("div");
  body.innerHTML = renderAuditMarkup(report, ai);
  const footer = document.createElement("div");
  footer.className = "modal-actions";
  footer.innerHTML = `<button type="button" class="btn btn-secondary" data-close-audit>关闭</button>`;
  openModal({
    title: "上次笔记检查结果",
    subtitle: "已保存到笔记。原始内容未被自动修改。",
    body,
    footer,
    size: "lg",
    onMount: ({ close }) => {
      footer.querySelector("[data-close-audit]").addEventListener("click", close);
    },
  });
  refreshIcons(body);
}

function renderAuditMarkup(data, ai) {
  const corrections = data.corrections || [];
  const certain = corrections.filter((item) => item.certainty === "certain");
  const review = corrections.filter((item) => item.certainty !== "certain");
  const itemMarkup = (item) => `<article class="audit-correction">
    <div class="correction-meta">
      <span class="category-tag">${escapeHTML(item.category || "其他")}</span>
      ${item.location ? `<span class="location-tag">${escapeHTML(item.location)}</span>` : ""}
      <span class="certainty-tag ${item.certainty === "certain" ? "is-certain" : "is-review"}">${
        item.certainty === "certain" ? "确定错误" : "需要人工确认"
      }</span>
      ${
        item.confidence !== undefined && item.confidence !== null
          ? `<span class="confidence-tag">可信度 ${Math.round(Number(item.confidence) * 100)}%</span>`
          : ""
      }
    </div>
    <div class="audit-original"><span>原文</span><p>${escapeHTML(item.original || "—")}</p></div>
    <div class="audit-suggestion"><span>建议</span><p>${escapeHTML(item.suggested || "—")}</p></div>
    <p class="audit-reason">${escapeHTML(item.reason || "")}</p>
  </article>`;
  return `${ai ? aiBanner(ai) : ""}
    <div class="audit-summary">
      <div class="audit-summary-icon">${icon("shield-check")}</div>
      <div><h3>检查结论</h3><p>${escapeHTML(data.summary || "未提供结论。")}</p></div>
    </div>
    <div class="audit-warning-line">${icon("info")} 原笔记未被修改。确定错误与需确认内容已分开列出，请自行核对后再决定是否修改。</div>
    ${
      corrections.length
        ? `<div class="audit-groups">
            ${
              certain.length
                ? `<div class="audit-group"><div class="group-label"><span class="gen-dot is-certain"></span>确定问题 · ${certain.length}</div>${certain
                    .map(itemMarkup)
                    .join("")}</div>`
                : ""
            }
            ${
              review.length
                ? `<div class="audit-group"><div class="group-label"><span class="gen-dot is-review"></span>需要人工确认 · ${review.length}</div>${review
                    .map(itemMarkup)
                    .join("")}</div>`
                : ""
            }
          </div>`
        : `<div class="audit-clean">${icon("check-circle-2")}<div><strong>没有发现可自动确认的问题</strong><p>这不代表笔记完全正确，仅说明当前检查未找到明确依据。</p></div></div>`
    }
    ${
      data.coverage_note
        ? `<p class="audit-coverage">${icon("scan-search")} ${escapeHTML(data.coverage_note)}</p>`
        : ""
    }
    ${
      data.warnings?.length
        ? `<ul class="ai-warnings">${data.warnings
            .map((item) => `<li>${icon("info")}<span>${escapeHTML(item)}</span></li>`)
            .join("")}</ul>`
        : ""
    }
    <p class="ai-manual-check">${icon("shield-check")} 不自动应用修改。请对照教材和老师讲解逐条确认。</p>
  `;
}

async function deleteCurrentNote() {
  if (!currentNote) return;
  const confirmed = await openConfirm({
    title: "删除笔记",
    message: `确定删除「${currentNote.title}」吗？`,
    details: "笔记和保存的检查/图谱数据会被删除，关联闪卡会保留但解除关联。",
    confirmText: "删除笔记",
    danger: true,
  });
  if (!confirmed) return;
  try {
    await api.delete(`/notes/${currentNote.id}`);
    state.notes = state.notes.filter((note) => note.id !== currentNote.id);
    state.selectedId = state.notes[0]?.id || null;
    state.activeTab = "edit";
    showToast("笔记已删除");
    refreshCurrent({ preserveScroll: true });
  } catch (error) {
    toastError(error);
  }
}

function openNewNoteModal() {
  const subjects = getSubjects();
  const body = document.createElement("div");
  body.innerHTML = `<form id="new-note-form" class="form-stack">
    <label class="field"><span class="field-label">笔记标题 *</span><input class="input" name="title" maxlength="180" required placeholder="例如：二次函数复习" data-autofocus></label>
    <label class="field"><span class="field-label">学科</span><input class="input" name="subject" list="new-note-subjects" maxlength="30" value="数学"><datalist id="new-note-subjects">${subjects
      .map((subject) => `<option value="${escapeHTML(subject)}"></option>`)
      .join("")}</datalist></label>
    <label class="field"><span class="field-label">初始内容</span><textarea class="input textarea" name="content" rows="6" maxlength="200000" placeholder="可以先写下标题和关键词，稍后在编辑器中完善。"></textarea></label>
    <p class="form-error" id="new-note-error" role="alert" hidden></p>
  </form>`;
  const footer = document.createElement("div");
  footer.className = "modal-actions";
  footer.innerHTML = `<button type="button" class="btn btn-secondary" data-cancel>取消</button>
    <button type="submit" form="new-note-form" class="btn btn-primary" data-submit>${icon("plus")}<span>创建笔记</span></button>`;
  openModal({
    title: "新建笔记",
    subtitle: "用 Markdown 书写，保存后即可检查或生成知识图谱。",
    body,
    footer,
    onMount: ({ close }) => {
      const form = body.querySelector("#new-note-form");
      const errorEl = body.querySelector("#new-note-error");
      const submit = footer.querySelector("[data-submit]");
      footer.querySelector("[data-cancel]").addEventListener("click", close);
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const formData = new FormData(form);
        const title = String(formData.get("title") || "").trim();
        if (!title) {
          errorEl.textContent = "请填写笔记标题";
          errorEl.hidden = false;
          return;
        }
        submit.disabled = true;
        submit.innerHTML = `<span class="spinner"></span><span>创建中…</span>`;
        try {
          const response = await api.post("/notes", {
            title,
            subject: String(formData.get("subject") || "综合").trim() || "综合",
            content_markdown: String(formData.get("content") || ""),
          });
          state.selectedId = response.data.id;
          state.activeTab = "edit";
          close();
          showToast("笔记已创建");
          refreshCurrent({ preserveScroll: true });
        } catch (error) {
          errorEl.textContent = error.message || "创建失败";
          errorEl.hidden = false;
          submit.disabled = false;
          submit.innerHTML = `${icon("plus")}<span>创建笔记</span>`;
          refreshIcons(submit);
        }
      });
    },
  });
}

function openNoteRecognitionModal() {
  const meta = getMeta();
  const body = document.createElement("div");
  body.innerHTML = `<div class="note-recognition">
    <div class="modal-callout">${aiModeBadge(meta?.ai, { small: true })}<p>${
      meta?.ai?.vision?.effective_mode === "demo"
        ? "当前视觉模型未配置为真实调用。识别结果为演示数据，图片不会被真正读取，请勿作为学习材料。"
        : "上传清晰的手写/课本笔记图片。AI 会尽量保留标题、段落和公式结构，并输出 Markdown。"
    }</p></div>
    <div data-note-upload></div>
    <div class="form-grid form-grid-2 modal-form-section">
      <label class="field"><span class="field-label">标题提示（可选）</span><input class="input" id="note-recognize-title" maxlength="120" placeholder="例如：二次函数课堂笔记"></label>
    </div>
    <p class="form-error" id="note-recognize-error" role="alert" hidden></p>
    <button type="button" class="btn btn-primary" data-start-note-recognition>${icon("scan-line")}<span>上传并识别笔记</span></button>
  </div>
  <div class="note-recognition-result" hidden>
    <div class="result-toolbar">
      <button type="button" class="btn btn-secondary btn-sm" data-recognize-note-again>${icon("rotate-ccw")} 重新识别</button>
      <span class="muted-note">识别结果可先修改，再保存进入编辑器。</span>
    </div>
    <div class="recognize-note-ai-output"></div>
    <form id="recognized-note-form" class="form-stack">
      <div class="form-grid">
        <label class="field"><span class="field-label">标题</span><input class="input" name="title" maxlength="180" required></label>
        <label class="field"><span class="field-label">学科</span><input class="input" name="subject" maxlength="30" required></label>
        <label class="field field-span-2"><span class="field-label">Markdown 内容（可编辑）</span><textarea class="input textarea note-recognized-markdown" name="markdown" rows="15" maxlength="200000" required></textarea></label>
      </div>
      <div class="form-actions">
        <button type="submit" class="btn btn-primary" data-save-recognized>${icon("save")}<span>保存并进入编辑器</span></button>
        <span class="form-caption">保存后仍可继续编辑和检查。</span>
      </div>
    </form>
  </div>`;
  const uploader = createImageUploader({
    label: "上传笔记图片",
    hint: "支持 JPG / PNG / WebP，最大 8 MB。尽量正对纸张拍摄，减少阴影。",
  });
  body.querySelector("[data-note-upload]").appendChild(uploader.el);
  const footer = document.createElement("div");
  footer.className = "modal-actions";
  footer.innerHTML = `<button type="button" class="btn btn-secondary" data-close>关闭</button>`;
  let recognizedPayload = null;
  openModal({
    title: "图片识别笔记",
    subtitle: "识别结果先进入可编辑草稿，不会直接覆盖已有笔记。",
    body,
    footer,
    size: "lg",
    onMount: ({ close }) => {
      footer.querySelector("[data-close]").addEventListener("click", close);
      const startButton = body.querySelector("[data-start-note-recognition]");
      const errorEl = body.querySelector("#note-recognize-error");
      const stepOne = body.querySelector(".note-recognition");
      const resultPane = body.querySelector(".note-recognition-result");
      const aiOutput = body.querySelector(".recognize-note-ai-output");
      const form = body.querySelector("#recognized-note-form");
      startButton.addEventListener("click", async () => {
        const file = uploader.getFile();
        errorEl.hidden = true;
        if (!file) {
          errorEl.textContent = "请先选择一张笔记图片";
          errorEl.hidden = false;
          return;
        }
        startButton.disabled = true;
        startButton.innerHTML = `<span class="spinner"></span><span>上传图片中…</span>`;
        try {
          const uploadResponse = await api.upload(file);
          startButton.innerHTML = `<span class="spinner"></span><span>AI 识别中…</span>`;
          const response = await api.post(
            "/ai/notes/recognize",
            {
              image_url: uploadResponse.data.url,
              title_hint: body.querySelector("#note-recognize-title").value.trim() || null,
            },
            { timeout: 120000 }
          );
          recognizedPayload = { ...response.data, source_image: uploadResponse.data.url, ai: response.ai };
          stepOne.hidden = true;
          resultPane.hidden = false;
          aiOutput.innerHTML = `${aiBanner(response.ai)}
            ${
              response.data.warnings?.length
                ? `<div class="notice-box notice-warning">${response.data.warnings
                    .map((warning) => `<p>${escapeHTML(warning)}</p>`)
                    .join("")}</div>`
                : ""
            }
            <p class="field-hint">${icon("info")} 识别置信度：${Math.round(
              (response.data.confidence || 0) * 100
            )}%。请核对公式和易混淆文字后再保存。</p>`;
          form.elements.title.value = response.data.title || "识别笔记";
          form.elements.subject.value = response.data.subject || "综合";
          form.elements.markdown.value = response.data.markdown || "";
          refreshIcons(resultPane);
        } catch (error) {
          errorEl.textContent = error.message || "识别失败，请稍后重试";
          errorEl.hidden = false;
          startButton.disabled = false;
          startButton.innerHTML = `${icon("scan-line")}<span>上传并识别笔记</span>`;
          refreshIcons(startButton);
        }
      });
      body.querySelector("[data-recognize-note-again]").addEventListener("click", () => {
        stepOne.hidden = false;
        resultPane.hidden = true;
        uploader.clear();
        startButton.disabled = false;
        startButton.innerHTML = `${icon("scan-line")}<span>上传并识别笔记</span>`;
        refreshIcons(startButton);
      });
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const submit = form.querySelector("[data-save-recognized]");
        const formData = new FormData(form);
        const title = String(formData.get("title") || "").trim();
        const markdown = String(formData.get("markdown") || "").trim();
        if (!title || !markdown) {
          toastError(new Error("标题和笔记内容不能为空"));
          return;
        }
        submit.disabled = true;
        submit.innerHTML = `<span class="spinner"></span><span>保存中…</span>`;
        try {
          const response = await api.post("/notes", {
            title,
            subject: String(formData.get("subject") || "综合").trim() || "综合",
            content_markdown: markdown,
            source_image: recognizedPayload?.source_image || null,
          });
          state.selectedId = response.data.id;
          state.activeTab = "edit";
          close();
          showToast("识别笔记已保存，可以继续编辑");
          refreshCurrent({ preserveScroll: true });
        } catch (error) {
          toastError(error);
          submit.disabled = false;
          submit.innerHTML = `${icon("save")}<span>保存并进入编辑器</span>`;
          refreshIcons(submit);
        }
      });
    },
  });
}

async function render(container) {
  pageController?.abort();
  pageController = new AbortController();
  auditController?.abort();
  graphController?.abort();
  destroyEditor();
  cytoscapeInstance?.destroy();
  cytoscapeInstance = null;
  currentGraphData = null;
  try {
    const listResponse = await api.get("/notes", undefined, { signal: pageController.signal });
    state.notes = listResponse.data.notes || [];
    if (
      !state.selectedId ||
      !state.notes.some((note) => String(note.id) === String(state.selectedId))
    ) {
      state.selectedId = state.notes[0]?.id || null;
    }
    if (state.selectedId) {
      const detailResponse = await api.get(`/notes/${state.selectedId}`, undefined, {
        signal: pageController.signal,
      });
      currentNote = detailResponse.data;
      if (dirty) dirty = false;
    } else {
      currentNote = null;
    }
    renderPage(container);
  } catch (error) {
    if (error.name === "AbortError") return;
    currentNote = null;
    throw error;
  }
}

function cleanup() {
  // Best-effort flush when navigating away, so short autosave delays cannot
  // silently discard a change. Manual saves still surface errors normally.
  if (dirty && currentNote && !savePromise) {
    const title =
      (pageRoot?.querySelector("#note-title")?.value || currentNote.title || "未命名笔记").trim() ||
      "未命名笔记";
    const subject =
      (pageRoot?.querySelector("#note-subject")?.value || currentNote.subject || "综合").trim() ||
      "综合";
    api
      .put(`/notes/${currentNote.id}`, {
        title,
        subject,
        content_markdown: getEditorMarkdown(),
      })
      .catch(() => {});
  }
  pageController?.abort();
  auditController?.abort();
  graphController?.abort();
  pageController = null;
  auditController = null;
  graphController = null;
  clearTimeout(autoSaveTimer);
  autoSaveTimer = null;
  destroyEditor();
  try {
    cytoscapeInstance?.destroy();
  } catch {
    // noop
  }
  cytoscapeInstance = null;
  currentGraphData = null;
  currentNote = null;
  pageRoot = null;
  dirty = false;
}

export default {
  title: "智能笔记",
  render,
  cleanup,
};
