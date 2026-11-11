/** Shared task create/edit and completion dialogs. */

import { api } from "../api.js";
import { escapeHTML } from "../ui.js";
import { icon } from "./icons.js";
import { openModal } from "./modal.js";
import { showToast, toastError } from "./toast.js";
import { setButtonLoading } from "../ui.js";
import { getSubjects } from "../services/store.js";

const DIFFICULTY_LABELS = {
  1: "1 · 很轻松",
  2: "2 · 较轻松",
  3: "3 · 中等",
  4: "4 · 有挑战",
  5: "5 · 很难",
};

function options(values, selected) {
  return values
    .map(
      (item) =>
        `<option value="${item.value}" ${String(item.value) === String(selected) ? "selected" : ""}>${escapeHTML(
          item.label
        )}</option>`
    )
    .join("");
}

function fieldShell(label, control, hint = "", className = "") {
  return `<label class="field ${className}">
    <span class="field-label">${escapeHTML(label)}</span>
    ${control}
    ${hint ? `<span class="field-hint">${escapeHTML(hint)}</span>` : ""}
  </label>`;
}

export function openTaskFormModal({ task = null, onSaved = () => {} } = {}) {
  const isEdit = Boolean(task);
  const subjects = [...new Set([...getSubjects(), task?.subject].filter(Boolean))];
  const subjectListId = `subject-list-${Date.now()}`;
  const body = document.createElement("div");
  body.innerHTML = `
    <form class="form-stack" id="task-form" novalidate>
      <div class="form-grid">
        ${fieldShell(
          "任务标题 *",
          `<input class="input" name="title" maxlength="180" required placeholder="例如：完成数学练习册 P42" value="${escapeHTML(
            task?.title || ""
          )}" data-autofocus>`,
          "",
          "field-span-2"
        )}
        ${fieldShell(
          "学科",
          `<input class="input" name="subject" list="${subjectListId}" maxlength="30" value="${escapeHTML(
            task?.subject || "数学"
          )}" placeholder="选择或输入学科">
           <datalist id="${subjectListId}">${subjects
             .map((subject) => `<option value="${escapeHTML(subject)}"></option>`)
             .join("")}</datalist>`
        )}
        ${fieldShell(
          "预计耗时（分钟）",
          `<input class="input" type="number" name="estimated_minutes" min="5" max="1440" step="5" value="${
            task?.estimated_minutes || 30
          }">`
        )}
        ${fieldShell(
          "截止日期",
          `<input class="input" type="date" name="due_date" value="${escapeHTML(
            task?.due_date || ""
          )}">`,
          "可留空，但设置截止日期后规划更准确"
        )}
        ${fieldShell(
          "难度",
          `<select class="input" name="difficulty">${options(
            Object.entries(DIFFICULTY_LABELS).map(([value, label]) => ({ value, label })),
            task?.difficulty || 3
          )}</select>`
        )}
        ${fieldShell(
          "优先级",
          `<select class="input" name="priority">${options(
            [
              { value: 1, label: "高优先级" },
              { value: 2, label: "正常" },
              { value: 3, label: "低优先级" },
            ],
            task?.priority || 2
          )}</select>`
        )}
        ${fieldShell(
          "计划日期",
          `<input class="input" type="date" name="planned_date" value="${escapeHTML(
            task?.planned_date || ""
          )}">`,
          "智能排期会写入计划日期与开始时间"
        )}
        ${fieldShell(
          "计划开始时间",
          `<input class="input" type="time" name="planned_start" value="${escapeHTML(
            task?.planned_start || ""
          )}">`
        )}
        ${fieldShell(
          "任务说明",
          `<textarea class="input textarea" name="description" rows="3" maxlength="3000" placeholder="补充要求、题目范围等">${escapeHTML(
            task?.description || ""
          )}</textarea>`,
          "",
          "field-span-2"
        )}
      </div>
      <p class="form-error" id="task-form-error" role="alert" hidden></p>
    </form>
  `;
  const footer = document.createElement("div");
  footer.className = "modal-actions";
  footer.innerHTML = `
    <button type="button" class="btn btn-secondary" data-modal-cancel>取消</button>
    <button type="submit" form="task-form" class="btn btn-primary" data-submit>
      ${icon(isEdit ? "save" : "plus")}<span>${isEdit ? "保存修改" : "创建任务"}</span>
    </button>
  `;

  const modal = openModal({
    title: isEdit ? "编辑任务" : "新建学习任务",
    subtitle: isEdit ? "AI 不会覆盖你在这里设置的内容。" : "把大目标拆成一个可以在今天完成的小任务。",
    body,
    footer,
    size: "lg",
    onMount: ({ close }) => {
      const form = body.querySelector("#task-form");
      const submit = footer.querySelector("[data-submit]");
      const errorEl = body.querySelector("#task-form-error");
      footer.querySelector("[data-modal-cancel]").addEventListener("click", close);
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        errorEl.hidden = true;
        const formData = new FormData(form);
        const title = String(formData.get("title") || "").trim();
        if (!title) {
          errorEl.textContent = "请填写任务标题";
          errorEl.hidden = false;
          form.elements.title.focus();
          return;
        }
        const payload = {
          title,
          subject: String(formData.get("subject") || "综合").trim() || "综合",
          description: String(formData.get("description") || "").trim(),
          due_date: String(formData.get("due_date") || "") || null,
          estimated_minutes: Number(formData.get("estimated_minutes") || 30),
          difficulty: Number(formData.get("difficulty") || 3),
          priority: Number(formData.get("priority") || 2),
          planned_date: String(formData.get("planned_date") || "") || null,
          planned_start: String(formData.get("planned_start") || "") || null,
        };
        setButtonLoading(submit, true, isEdit ? "保存中…" : "创建中…");
        try {
          const response = isEdit
            ? await api.put(`/tasks/${task.id}`, payload)
            : await api.post("/tasks", payload);
          showToast(response.message || (isEdit ? "任务已更新" : "任务已创建"), "success");
          close();
          onSaved(response.data);
        } catch (error) {
          errorEl.textContent = error.message || "保存失败";
          errorEl.hidden = false;
          setButtonLoading(submit, false);
        }
      });
    },
  });
  return modal;
}

export function openCompleteTaskModal(task, { onCompleted = () => {} } = {}) {
  const body = document.createElement("div");
  body.innerHTML = `
    <div class="completion-task-preview">
      <span class="completion-check">${icon("check")}</span>
      <div>
        <strong>${escapeHTML(task.title)}</strong>
        <span>${escapeHTML(task.subject)} · 预计 ${task.estimated_minutes} 分钟</span>
      </div>
    </div>
    <form id="complete-task-form" class="form-stack">
      ${fieldShell(
        "实际用了多久？（分钟）",
        `<input class="input" type="number" name="actual_minutes" min="0" max="1440" value="${
          task.actual_minutes || task.estimated_minutes || 30
        }" data-autofocus>`,
        "这个数字记录在任务本身。专注计时记录会同时计入学习时长统计。"
      )}
      <p class="inline-hint">${icon("info")} 完成后可在任务历史中重新打开。</p>
    </form>
  `;
  const footer = document.createElement("div");
  footer.className = "modal-actions";
  footer.innerHTML = `
    <button type="button" class="btn btn-secondary" data-modal-cancel>取消</button>
    <button type="submit" form="complete-task-form" class="btn btn-primary" data-submit>
      ${icon("check")}<span>完成任务</span>
    </button>
  `;
  openModal({
    title: "记录完成情况",
    subtitle: "给这次学习一个真实的收尾。",
    body,
    footer,
    size: "sm",
    onMount: ({ close }) => {
      const form = body.querySelector("#complete-task-form");
      const submit = footer.querySelector("[data-submit]");
      footer.querySelector("[data-modal-cancel]").addEventListener("click", close);
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const formData = new FormData(form);
        const actual = Number(formData.get("actual_minutes") || 0);
        setButtonLoading(submit, true, "记录中…");
        try {
          const response = await api.post(`/tasks/${task.id}/complete`, {
            actual_minutes: Math.max(0, Math.min(1440, Math.round(actual))),
          });
          close();
          showToast(response.message || "任务已完成", "success");
          const unlocked = response.data?.unlocked_achievements || [];
          if (unlocked.length) {
            window.setTimeout(
              () => showToast(`解锁成就：${unlocked.map((item) => item.title).join("、")}`, "info", { duration: 6000 }),
              350
            );
          }
          onCompleted(response.data);
        } catch (error) {
          toastError(error);
          setButtonLoading(submit, false);
        }
      });
    },
  });
}
