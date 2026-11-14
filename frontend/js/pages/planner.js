import { api } from "../api.js";
import { icon, refreshIcons } from "../components/icons.js";
import { openModal, openConfirm } from "../components/modal.js";
import { aiBanner, aiModeBadge } from "../components/ai-display.js";
import { showToast, toastError } from "../components/toast.js";
import { openCompleteTaskModal, openTaskFormModal } from "../components/task-modal.js";
import { createImageUploader } from "../components/upload.js";
import { refreshCurrent } from "../router.js";
import { getMeta, getSubjects } from "../services/store.js";
import {
  difficultyDots,
  dueLabel,
  dueTone,
  emptyState,
  escapeHTML,
  formatDate,
  formatMinutes,
  formatTime,
  progressBar,
  relativeDay,
  subjectBadge,
  todayISO,
} from "../ui.js";

const state = {
  tasks: [],
  counts: {},
  filter: "all",
  subject: "all",
  search: "",
  planResult: null,
};

let controller = null;
let taskListElement = null;

function filteredTasks() {
  return state.tasks.filter((task) => {
    if (state.filter === "open" && task.status === "completed") return false;
    if (["pending", "in_progress", "completed"].includes(state.filter) && task.status !== state.filter) {
      return false;
    }
    if (state.subject !== "all" && task.subject !== state.subject) return false;
    if (state.search) {
      const haystack = `${task.title} ${task.description} ${task.subject}`.toLowerCase();
      if (!haystack.includes(state.search.toLowerCase())) return false;
    }
    return true;
  });
}

function tabCount(filter) {
  const counts = state.counts;
  if (filter === "all") return counts.total || 0;
  if (filter === "open") return (counts.pending || 0) + (counts.in_progress || 0);
  return counts[filter] || 0;
}

function renderTabs() {
  const tabs = [
    { key: "all", label: "全部" },
    { key: "open", label: "待完成" },
    { key: "in_progress", label: "进行中" },
    { key: "completed", label: "已完成" },
  ];
  return tabs
    .map(
      (tab) =>
        `<button type="button" class="tab-button ${state.filter === tab.key ? "is-active" : ""}" data-task-tab="${
          tab.key
        }">${tab.label}<span>${tabCount(tab.key)}</span></button>`
    )
    .join("");
}

function taskActions(task) {
  if (task.status === "completed") {
    return `<div class="task-actions">
      <button type="button" class="icon-button" data-task-action="reopen" title="重新打开任务" aria-label="重新打开任务">${icon("rotate-ccw")}</button>
      <button type="button" class="icon-button danger" data-task-action="delete" title="删除任务" aria-label="删除任务">${icon("trash-2")}</button>
    </div>`;
  }
  return `<div class="task-actions">
    ${task.status === "pending" ? `<button type="button" class="icon-button" data-task-action="start" title="标记为进行中" aria-label="开始任务">${icon("play")}</button>` : ""}
    <button type="button" class="icon-button" data-task-action="edit" title="编辑任务" aria-label="编辑任务">${icon("pencil")}</button>
    <button type="button" class="icon-button danger" data-task-action="delete" title="删除任务" aria-label="删除任务">${icon("trash-2")}</button>
  </div>`;
}

function taskCard(task) {
  const isCompleted = task.status === "completed";
  const sourceBadge =
    task.source === "ai"
      ? `<span class="source-badge">${icon("sparkles")} AI 录入</span>`
      : "";
  const planned =
    task.planned_date
      ? `<span class="meta-chip">${icon("calendar-clock")}${escapeHTML(relativeDay(task.planned_date))}${
          task.planned_start ? ` ${escapeHTML(task.planned_start)}` : ""
        }${task.planned_minutes ? ` · ${task.planned_minutes} 分钟` : ""}</span>`
      : "";
  return `<article class="task-card ${isCompleted ? "is-completed" : ""}" data-task-id="${task.id}">
    <div class="task-card-leading">
      ${
        isCompleted
          ? `<span class="task-check is-checked">${icon("check")}</span>`
          : `<button type="button" class="task-check" data-task-action="complete" aria-label="完成任务">${icon("circle")}</button>`
      }
      <span class="task-timeline" aria-hidden="true"></span>
    </div>
    <div class="task-card-main">
      <div class="task-card-title-row">
        <h3>${escapeHTML(task.title)}</h3>
        ${subjectBadge(task.subject, { small: true })}
        ${sourceBadge}
        ${
          task.status === "in_progress"
            ? '<span class="status-badge status-progress"><span class="status-dot"></span>进行中</span>'
            : ""
        }
      </div>
      ${task.description ? `<p class="task-description">${escapeHTML(task.description)}</p>` : ""}
      <div class="task-meta-row">
        <span class="due-text due-${dueTone(task)}">${icon("calendar")} ${escapeHTML(dueLabel(task))}</span>
        <span class="meta-chip">${icon("hourglass")}预计 ${task.estimated_minutes} 分钟</span>
        ${task.actual_minutes ? `<span class="meta-chip">${icon("check-check")}实际 ${task.actual_minutes} 分钟</span>` : ""}
        ${difficultyDots(task.difficulty)}
        ${planned}
      </div>
      ${
        isCompleted
          ? `<div class="task-complete-note">${icon("check-circle-2")} 已完成${task.completed_at ? ` · ${formatTime(task.completed_at)}` : ""}</div>`
          : `<div class="task-mini-progress">${progressBar(
              Math.min(100, Math.round(((task.actual_minutes || 0) / Math.max(1, task.estimated_minutes)) * 100)),
              { tone: "teal" }
            )}<span>${task.actual_minutes || 0} / ${task.estimated_minutes} 分钟</span></div>`
      }
    </div>
    ${taskActions(task)}
  </article>`;
}

function renderTaskList() {
  if (!taskListElement) return;
  const tasks = filteredTasks();
  taskListElement.innerHTML = tasks.length
    ? tasks.map(taskCard).join("")
    : emptyState({
        iconName: state.tasks.length ? "search-x" : "clipboard-list",
        title: state.tasks.length ? "没有匹配的任务" : "还没有学习任务",
        description: state.tasks.length
          ? "试试更换筛选条件或搜索关键词。"
          : "手动添加一个任务，或者用 AI 识别一张作业图片。",
        action: state.tasks.length
          ? `<button type="button" class="btn btn-secondary btn-sm" data-reset-filters>清除筛选</button>`
          : `<button type="button" class="btn btn-primary btn-sm" data-create-task>添加第一个任务</button>`,
      });
  refreshIcons(taskListElement);
  const resetButton = taskListElement.querySelector("[data-reset-filters]");
  if (resetButton) {
    resetButton.addEventListener("click", () => {
      state.filter = "all";
      state.subject = "all";
      state.search = "";
      const search = document.querySelector("#task-search");
      if (search) search.value = "";
      const subject = document.querySelector("#task-subject-filter");
      if (subject) subject.value = "all";
      document.querySelectorAll("[data-task-tab]").forEach((tab) => {
        tab.classList.toggle("is-active", tab.dataset.taskTab === "all");
      });
      renderTaskList();
    });
  }
  taskListElement.querySelector("[data-create-task]")?.addEventListener("click", openCreateTask);
}

function renderPage(container) {
  const counts = state.counts || {};
  const subjects = [...new Set(state.tasks.map((task) => task.subject))].sort();
  const meta = getMeta();
  const overdues = state.tasks.filter((task) => task.is_overdue && task.status !== "completed");
  container.innerHTML = `
    <div class="page-shell">
      <header class="page-header">
        <div class="page-heading">
          <h1>把任务变成可执行的计划</h1>
          <p class="page-subtitle">记录作业、估算耗时，再用 AI 辅助识别与本地透明规则排期。你的修改始终优先。</p>
        </div>
        <div class="page-actions">
          <button type="button" class="btn btn-secondary" data-ai-recognize>${icon("scan-line")}<span>图片识别作业</span></button>
          <button type="button" class="btn btn-primary" data-create-task>${icon("plus")}<span>新建任务</span></button>
        </div>
      </header>

      <section class="summary-strip planner-summary" aria-label="任务统计">
        <div class="summary-chip"><span class="summary-icon blue">${icon("list-checks")}</span><div><strong>${counts.pending || 0}</strong><span>待完成</span></div></div>
        <div class="summary-chip"><span class="summary-icon amber">${icon("timer")}</span><div><strong>${formatMinutes(counts.open_estimated_minutes || 0, { compact: true })}</strong><span>待投入时间</span></div></div>
        <div class="summary-chip"><span class="summary-icon red">${icon("triangle-alert")}</span><div><strong>${counts.overdue || 0}</strong><span>已逾期</span></div></div>
        <div class="summary-chip"><span class="summary-icon teal">${icon("check-check")}</span><div><strong>${counts.completed || 0}</strong><span>累计完成</span></div></div>
      </section>

      <div class="planner-layout">
        <section class="card planner-task-panel">
          <div class="card-header planner-list-header">
            <div>
              <h2 class="card-title">${icon("layers-2")} 我的任务</h2>
              <p class="card-subtitle">${counts.total || 0} 个任务 · ${overdues.length ? `${overdues.length} 个已逾期` : "目前没有逾期任务"}</p>
            </div>
            <div class="search-box">
              ${icon("search")}
              <input id="task-search" type="search" placeholder="搜索任务…" value="${escapeHTML(state.search)}" aria-label="搜索任务">
            </div>
          </div>
          <div class="task-filter-row">
            <div class="tabs" role="tablist" aria-label="任务筛选">${renderTabs()}</div>
            <select id="task-subject-filter" class="input input-sm" aria-label="按学科筛选">
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
          </div>
          <div id="task-list" class="task-list"></div>
        </section>

        <aside class="planner-side">
          <section class="card plan-card">
            <div class="card-header">
              <div>
                <h2 class="card-title">${icon("wand-sparkles")} 智能排期</h2>
                <p class="card-subtitle">综合截止时间、优先级、难度和历史实际耗时。</p>
              </div>
              <span class="local-rule-badge">本地规则</span>
            </div>
            <form id="plan-form" class="plan-form">
              <div class="form-grid form-grid-2">
                <label class="field">
                  <span class="field-label">计划日期</span>
                  <input class="input" type="date" name="plan_date" value="${todayISO()}">
                </label>
                <label class="field">
                  <span class="field-label">开始时间</span>
                  <input class="input" type="time" name="start_time" value="19:00">
                </label>
                <label class="field field-span-2">
                  <span class="field-label">可用学习时间（分钟）</span>
                  <input class="input" type="number" name="available_minutes" min="10" max="720" step="5" value="${
                    meta?.user?.daily_goal_minutes || 120
                  }">
                </label>
              </div>
              <button type="submit" class="btn btn-primary btn-full" data-plan-submit>
                ${icon("sparkles")}<span>生成智能排期</span>
              </button>
              <p class="field-hint">${icon("info")} 排期建议不会自动覆盖任务；你确认后才会写入计划时间。</p>
            </form>
            <div id="plan-result" class="plan-result"></div>
          </section>

          <section class="card urgency-card">
            <div class="card-header">
              <div>
                <h2 class="card-title">${icon("flame")} 今天优先</h2>
                <p class="card-subtitle">按截止时间与优先级筛出</p>
              </div>
            </div>
            ${
              overdues.length || state.tasks.filter((task) => task.due_date === todayISO() && task.status !== "completed").length
                ? `<ul class="urgency-list">
                  ${[...overdues, ...state.tasks.filter((task) => task.due_date === todayISO() && task.status !== "completed" && !task.is_overdue)]
                    .slice(0, 4)
                    .map(
                      (task) => `<li><span class="urgency-marker"></span><div><strong>${escapeHTML(task.title)}</strong><span>${escapeHTML(
                        task.subject
                      )} · ${escapeHTML(dueLabel(task))}</span></div></li>`
                    )
                    .join("")}
                </ul>`
                : `<p class="muted-note">${icon("check-circle-2")} 当前没有逾期或今天截止的任务。</p>`
            }
          </section>
        </aside>
      </div>
    </div>
  `;
  refreshIcons(container);
  taskListElement = container.querySelector("#task-list");
  renderTaskList();
  bindPageEvents(container);
  if (state.planResult) {
    renderPlanResult(container.querySelector("#plan-result"), state.planResult);
  }
}

function bindPageEvents(container) {
  container.querySelectorAll("[data-create-task]").forEach((button) => {
    button.addEventListener("click", openCreateTask);
  });
  container.querySelector("[data-ai-recognize]")?.addEventListener("click", openRecognitionModal);

  container.querySelectorAll("[data-task-tab]").forEach((tab) => {
    tab.addEventListener("click", () => {
      state.filter = tab.dataset.taskTab;
      container.querySelectorAll("[data-task-tab]").forEach((item) => {
        item.classList.toggle("is-active", item === tab);
      });
      renderTaskList();
    });
  });
  container.querySelector("#task-search")?.addEventListener("input", (event) => {
    state.search = event.target.value.trim();
    renderTaskList();
  });
  container.querySelector("#task-subject-filter")?.addEventListener("change", (event) => {
    state.subject = event.target.value;
    renderTaskList();
  });
  taskListElement?.addEventListener("click", (event) => {
    const actionButton = event.target.closest("[data-task-action]");
    if (!actionButton) return;
    const taskCardEl = actionButton.closest("[data-task-id]");
    if (!taskCardEl) return;
    const task = state.tasks.find((item) => String(item.id) === taskCardEl.dataset.taskId);
    if (!task) return;
    const action = actionButton.dataset.taskAction;
    if (action === "complete") openCompleteTaskModal(task, { onCompleted: refreshAfterChange });
    if (action === "edit") openEditTask(task);
    if (action === "delete") deleteTask(task);
    if (action === "reopen") reopenTask(task);
    if (action === "start") startTask(task);
  });
  container.querySelector("#plan-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    generatePlan(event.currentTarget, container);
  });
}

function openCreateTask() {
  openTaskFormModal({ onSaved: refreshAfterChange });
}

function openEditTask(task) {
  openTaskFormModal({ task, onSaved: refreshAfterChange });
}

async function startTask(task) {
  try {
    const response = await api.post(`/tasks/${task.id}/start`, {});
    showToast(response.message || "任务已开始");
    refreshAfterChange();
  } catch (error) {
    toastError(error);
  }
}

async function reopenTask(task) {
  const confirmed = await openConfirm({
    title: "重新打开任务",
    message: `确定将“${task.title}”重新标记为待完成吗？`,
    confirmText: "重新打开",
  });
  if (!confirmed) return;
  try {
    await api.post(`/tasks/${task.id}/reopen`, {});
    showToast("任务已重新打开");
    refreshAfterChange();
  } catch (error) {
    toastError(error);
  }
}

async function deleteTask(task) {
  const confirmed = await openConfirm({
    title: "删除任务",
    message: `确定删除“${task.title}”吗？`,
    details: "删除后无法恢复，关联的学习计时记录会保留。",
    confirmText: "删除任务",
    danger: true,
  });
  if (!confirmed) return;
  try {
    await api.delete(`/tasks/${task.id}`);
    showToast("任务已删除");
    refreshAfterChange();
  } catch (error) {
    toastError(error);
  }
}

function refreshAfterChange() {
  state.planResult = null;
  refreshCurrent({ preserveScroll: true });
}

async function generatePlan(form, container) {
  const button = form.querySelector("[data-plan-submit]");
  const formData = new FormData(form);
  const resultHost = container.querySelector("#plan-result");
  const original = button.innerHTML;
  button.disabled = true;
  button.innerHTML = `<span class="spinner"></span><span>正在排期…</span>`;
  try {
    const response = await api.post("/tasks/plan/preview", {
      plan_date: formData.get("plan_date"),
      start_time: formData.get("start_time"),
      available_minutes: Number(formData.get("available_minutes") || 120),
    });
    state.planResult = response.data;
    renderPlanResult(resultHost, response.data);
  } catch (error) {
    toastError(error);
  } finally {
    button.disabled = false;
    button.innerHTML = original;
    refreshIcons(button);
  }
}

function renderPlanResult(host, plan) {
  if (!host) return;
  const schedule = plan.schedule || [];
  host.innerHTML = `
    <div class="plan-result-header">
      <div>
        <strong>${escapeHTML(formatDate(plan.plan_date, { weekday: true }))} · ${escapeHTML(plan.start_time)} 开始</strong>
        <span>排入 ${formatMinutes(plan.scheduled_minutes)} / 可用 ${formatMinutes(plan.available_minutes)}</span>
      </div>
      ${plan.schedule.length ? `<button type="button" class="btn btn-primary btn-sm" data-apply-plan>${icon("check")} 应用计划</button>` : ""}
    </div>
    ${
      schedule.length
        ? `<ol class="plan-timeline">
            ${schedule
              .map(
                (item) => `<li class="plan-slot">
                  <div class="plan-slot-time"><strong>${escapeHTML(item.start_time)}</strong><span>${escapeHTML(item.end_time)}</span></div>
                  <div class="plan-slot-dot" style="--dot:${subjectColor(item.subject)}"></div>
                  <div class="plan-slot-body">
                    <div class="plan-slot-title">${escapeHTML(item.title)}</div>
                    <div class="plan-slot-meta">${escapeHTML(item.subject)} · ${item.planned_minutes} 分钟${
                      item.partial ? "（部分）" : ""
                    }</div>
                    <p>${escapeHTML(item.reason)}</p>
                  </div>
                </li>`
              )
              .join("")}
          </ol>`
        : `<div class="plan-empty">${emptyState({
            iconName: "calendar-x",
            title: plan.schedule.length === 0 && state.tasks.length === 0 ? "没有可排期的任务" : "本次排期为空",
            description: plan.summary || "增加可用时间或先添加任务。",
          })}</div>`
    }
    ${
      plan.unscheduled_tasks?.length
        ? `<div class="plan-unscheduled"><strong>未排入本次计划</strong><ul>${plan.unscheduled_tasks
            .map(
              (task) =>
                `<li><span>${escapeHTML(task.title)}</span><em>${escapeHTML(task.reason)}</em></li>`
            )
            .join("")}</ul></div>`
        : ""
    }
    <p class="plan-notice">${icon("info")} ${escapeHTML(plan.notice || "")}</p>
    <p class="plan-summary">${escapeHTML(plan.summary || "")}${
      plan.beyond_midnight ? " 可用时间已自动限制在当天结束前。" : ""
    }</p>
  `;
  refreshIcons(host);
  host.querySelector("[data-apply-plan]")?.addEventListener("click", (event) => {
    applyPlan(host, plan, event.currentTarget);
  });
}

async function applyPlan(host, plan, button) {
  const original = button.innerHTML;
  button.disabled = true;
  button.innerHTML = `<span class="spinner"></span><span>应用中…</span>`;
  try {
    const response = await api.post("/tasks/plan/apply", {
      plan_date: plan.plan_date,
      schedule: plan.schedule.map((item) => ({
        task_id: item.task_id,
        start_time: item.start_time,
        planned_minutes: item.planned_minutes,
      })),
    });
    showToast(response.message || "智能排期已应用", "success");
    state.planResult = null;
    refreshAfterChange();
  } catch (error) {
    toastError(error);
    button.disabled = false;
    button.innerHTML = original;
    refreshIcons(button);
  }
}

function subjectColor(subject) {
  const colors = {
    语文: "#d97706",
    数学: "#2563eb",
    英语: "#7c3aed",
    物理: "#0d9488",
    化学: "#db2777",
    生物: "#16a34a",
  };
  return colors[subject] || "#64748b";
}

function openRecognitionModal() {
  const meta = getMeta();
  const uploadMount = document.createElement("div");
  uploadMount.className = "modal-upload-mount";
  const body = document.createElement("div");
  body.innerHTML = `
    <div class="ai-recognition-step">
      <div class="modal-callout">
        ${aiModeBadge(meta?.ai, { small: true })}
        <p>${
          meta?.ai?.vision?.effective_mode === "demo"
            ? "当前视觉模型处于演示/未配置状态。识别结果会是明确的演示数据，不会假装读取了图片内容。"
            : "上传清晰的作业图片，AI 将尝试提取学科、题目数量、难度和预计完成时间。"
        }</p>
      </div>
      <div data-upload-mount></div>
      <div class="form-grid form-grid-2 modal-form-section">
        <label class="field">
          <span class="field-label">学科提示（可选）</span>
          <input class="input" id="recognize-subject" list="planner-subject-options" placeholder="例如：数学" maxlength="30">
          <datalist id="planner-subject-options">${getSubjects()
            .map((item) => `<option value="${escapeHTML(item)}"></option>`)
            .join("")}</datalist>
        </label>
        <label class="field">
          <span class="field-label">截止日期提示（可选）</span>
          <input class="input" type="date" id="recognize-due-date">
        </label>
      </div>
      <p class="field-hint">${icon("shield-check")} 图片仅保存在本机 StudyFlow 上传目录，不会发送给前端第三方服务。</p>
      <p class="form-error" id="recognize-error" role="alert" hidden></p>
      <button type="button" class="btn btn-primary" data-start-recognition>
        ${icon("scan-line")}<span>上传并识别作业</span>
      </button>
    </div>
    <div class="ai-recognition-result" hidden>
      <div class="result-toolbar">
        <button type="button" class="btn btn-secondary btn-sm" data-recognize-again>${icon("rotate-ccw")} 重新上传</button>
        <span class="muted-note">识别结果先由你确认，才会创建任务。</span>
      </div>
      <div class="recognize-ai-output"></div>
      <div class="recognized-task-list"></div>
      <div class="recognize-action-row">
        <button type="button" class="btn btn-primary" data-add-recognized>${icon("plus")} 添加选中任务</button>
      </div>
    </div>
  `;
  const uploader = createImageUploader({
    label: "上传作业图片",
    hint: "支持 JPG / PNG / WebP，最大 8 MB；建议拍摄清晰、端正。",
  });
  body.querySelector("[data-upload-mount]").appendChild(uploader.el);

  const footer = document.createElement("div");
  footer.className = "modal-actions";
  footer.innerHTML = `<button type="button" class="btn btn-secondary" data-close-modal>关闭</button>`;

  let recognitionState = null;
  const modal = openModal({
    title: "AI 识别作业图片",
    subtitle: "视觉识别只生成任务草稿，不会直接覆盖你的数据。",
    body,
    footer,
    size: "lg",
    onMount: ({ close }) => {
      footer.querySelector("[data-close-modal]").addEventListener("click", close);
      const errorEl = body.querySelector("#recognize-error");
      const startButton = body.querySelector("[data-start-recognition]");
      const stepOne = body.querySelector(".ai-recognition-step");
      const resultPane = body.querySelector(".ai-recognition-result");
      const output = body.querySelector(".recognize-ai-output");
      const taskList = body.querySelector(".recognized-task-list");

      startButton.addEventListener("click", async () => {
        const file = uploader.getFile();
        errorEl.hidden = true;
        if (!file) {
          errorEl.textContent = "请先选择一张作业图片";
          errorEl.hidden = false;
          return;
        }
        startButton.disabled = true;
        startButton.innerHTML = `<span class="spinner"></span><span>上传图片中…</span>`;
        try {
          const uploadResponse = await api.upload(file);
          startButton.innerHTML = `<span class="spinner"></span><span>AI 分析中，请稍候…</span>`;
          const response = await api.post("/ai/tasks/recognize", {
            image_url: uploadResponse.data.url,
            subject_hint: body.querySelector("#recognize-subject").value.trim() || null,
            due_date: body.querySelector("#recognize-due-date").value || null,
          });
          recognitionState = { ...response.data, ai: response.ai, image: uploadResponse.data };
          stepOne.hidden = true;
          resultPane.hidden = false;
          renderRecognitionResult(output, taskList, recognitionState, close);
          refreshIcons(resultPane);
        } catch (error) {
          errorEl.textContent = error.message || "识别失败，请稍后重试";
          errorEl.hidden = false;
          startButton.disabled = false;
          startButton.innerHTML = `${icon("scan-line")}<span>上传并识别作业</span>`;
          refreshIcons(startButton);
        }
      });

      body.querySelector("[data-recognize-again]").addEventListener("click", () => {
        stepOne.hidden = false;
        resultPane.hidden = true;
        uploader.clear();
        startButton.disabled = false;
        startButton.innerHTML = `${icon("scan-line")}<span>上传并识别作业</span>`;
        refreshIcons(startButton);
      });
    },
  });
  return modal;
}

function renderRecognitionResult(output, taskList, recognition, closeModal) {
  const tasks = recognition.tasks || [];
  output.innerHTML = `
    ${aiBanner(recognition.ai)}
    <p class="image-summary">${escapeHTML(recognition.image_summary || "未提供图片概述。")}</p>
    ${
      recognition.warnings?.length
        ? `<div class="notice-box notice-warning">${recognition.warnings
            .map((warning) => `<p>${escapeHTML(warning)}</p>`)
            .join("")}</div>`
        : ""
    }
    <p class="field-hint">在添加前检查并修改每个任务，AI 的预计时间只是建议。</p>
  `;
  if (!tasks.length) {
    taskList.innerHTML = emptyState({
      iconName: "scan-search",
      title: "没有识别出可添加的作业",
      description: "换一张更清晰的图片，或手动创建任务。",
    });
    return;
  }
  taskList.innerHTML = tasks
    .map(
      (task, index) => `<div class="recognized-task" data-recognized-task data-index="${index}">
        <label class="checkbox-row recognized-check">
          <input type="checkbox" checked data-recognized-check>
          <span>添加到任务列表</span>
          <span class="confidence-badge" title="模型置信度">置信度 ${Math.round(
            (task.confidence || 0) * 100
          )}%</span>
        </label>
        <div class="form-grid form-grid-4">
          <label class="field field-span-2">
            <span class="field-label">任务标题</span>
            <input class="input" data-field="title" maxlength="180" value="${escapeHTML(task.title)}">
          </label>
          <label class="field">
            <span class="field-label">学科</span>
            <input class="input" data-field="subject" maxlength="30" value="${escapeHTML(task.subject)}">
          </label>
          <label class="field">
            <span class="field-label">截止日期</span>
            <input class="input" type="date" data-field="due_date" value="${escapeHTML(task.due_date || "")}">
          </label>
          <label class="field">
            <span class="field-label">预计分钟</span>
            <input class="input" type="number" min="5" max="1440" step="5" data-field="estimated_minutes" value="${
              task.estimated_minutes
            }">
          </label>
          <label class="field">
            <span class="field-label">难度（1-5）</span>
            <input class="input" type="number" min="1" max="5" data-field="difficulty" value="${task.difficulty}">
          </label>
          <label class="field">
            <span class="field-label">题目数量</span>
            <input class="input" type="number" min="0" max="999" data-field="question_count" value="${
              task.question_count ?? ""
            }" placeholder="未知">
          </label>
          <div class="field recognition-reason">
            <span class="field-label">难度依据</span>
            <p>${escapeHTML(task.difficulty_reason || "未说明")}</p>
          </div>
          <label class="field field-span-4">
            <span class="field-label">任务说明</span>
            <textarea class="input textarea" rows="2" data-field="description" maxlength="3000">${escapeHTML(
              task.description || ""
            )}</textarea>
          </label>
        </div>
      </div>`
    )
    .join("");
  const addButton = taskList.parentElement.querySelector("[data-add-recognized]");
  addButton.addEventListener("click", async () => {
    const selected = [...taskList.querySelectorAll("[data-recognized-task]")].filter(
      (card) => card.querySelector("[data-recognized-check]").checked
    );
    if (!selected.length) {
      toastError(new Error("请至少选择一个任务"));
      return;
    }
    const original = addButton.innerHTML;
    addButton.disabled = true;
    addButton.innerHTML = `<span class="spinner"></span><span>正在添加…</span>`;
    let added = 0;
    let failed = 0;
    for (const card of selected) {
      if (!card.querySelector('[data-field="title"]').value.trim()) {
        failed += 1;
        continue;
      }
      const field = (name) => card.querySelector(`[data-field="${name}"]`)?.value ?? "";
      try {
        await api.post("/tasks", {
          title: field("title").trim(),
          subject: field("subject").trim() || "综合",
          description: field("description").trim(),
          due_date: field("due_date") || null,
          estimated_minutes: Number(field("estimated_minutes") || 30),
          difficulty: Math.max(1, Math.min(5, Number(field("difficulty") || 3))),
          priority: 2,
          source: "ai",
          ai_meta: {
            confidence: recognition.tasks[Number(card.dataset.index)]?.confidence ?? null,
            difficulty_reason: recognition.tasks[Number(card.dataset.index)]?.difficulty_reason || "",
            question_count: field("question_count") ? Number(field("question_count")) : null,
            image_summary: recognition.image_summary,
            ai_mode: recognition.ai?.mode,
            provider: recognition.ai?.provider,
          },
        });
        added += 1;
      } catch (error) {
        failed += 1;
        console.error("Failed to add recognized task", error);
      }
    }
    if (added) {
      showToast(`已添加 ${added} 个任务${failed ? `，${failed} 个失败` : ""}`, failed ? "warning" : "success");
      closeModal();
      refreshAfterChange();
    } else {
      toastError(new Error("任务添加失败，请重试"));
      addButton.disabled = false;
      addButton.innerHTML = original;
      refreshIcons(addButton);
    }
  });
}

async function render(container) {
  controller?.abort();
  controller = new AbortController();
  try {
    const response = await api.get(
      "/tasks",
      { status: "all", limit: 300 },
      { signal: controller.signal }
    );
    state.tasks = response.data.tasks || [];
    state.counts = response.data.counts || {};
    if (state.subject !== "all" && !state.tasks.some((task) => task.subject === state.subject)) {
      state.subject = "all";
    }
    renderPage(container);
  } catch (error) {
    if (error.name === "AbortError") return;
    throw error;
  }
}

function cleanup() {
  controller?.abort();
  controller = null;
  taskListElement = null;
}

export default {
  title: "学习规划",
  render,
  cleanup,
};
