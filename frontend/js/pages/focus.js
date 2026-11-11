import { api } from "../api.js";
import { icon, refreshIcons } from "../components/icons.js";
import { openConfirm } from "../components/modal.js";
import { showToast, toastError } from "../components/toast.js";
import { refreshCurrent } from "../router.js";
import { getMeta, getSubjects } from "../services/store.js";
import {
  emptyState,
  escapeHTML,
  formatClock,
  formatDate,
  formatMinutes,
  formatTime,
  progressBar,
  weeklyBars,
} from "../ui.js";

const state = {
  sessions: [],
  summary: null,
  openTasks: [],
  achievements: null,
};

let pageController = null;
let timer = null;

function buildTimer(user) {
  const focusMinutes = Number(user?.pomodoro_minutes) || 25;
  const shortMinutes = Number(user?.short_break_minutes) || 5;
  const longMinutes = Number(user?.long_break_minutes) || 15;
  return {
    mode: "focus",
    durations: { focus: focusMinutes, short: shortMinutes, long: longMinutes },
    durationSeconds: focusMinutes * 60,
    remainingSeconds: focusMinutes * 60,
    running: false,
    intervalId: null,
    endsAt: null,
    startedAt: null,
    recording: false,
  };
}

function resetTimer(seconds = timer?.durationSeconds) {
  if (!timer) return;
  clearInterval(timer.intervalId);
  timer.intervalId = null;
  timer.running = false;
  timer.recording = false;
  timer.remainingSeconds = seconds;
  timer.endsAt = null;
  timer.startedAt = null;
}

function modeLabel(mode) {
  return { focus: "专注", short: "短休息", long: "长休息" }[mode] || "专注";
}

function renderPage(container) {
  const meta = getMeta();
  const user = meta?.user;
  const sessions = state.sessions || [];
  const summary = state.summary || {};
  const achievements = state.achievements;
  const unlocked = (achievements?.items || []).filter((item) => item.unlocked);
  const locked = (achievements?.items || []).filter((item) => !item.unlocked);
  const subjects = getSubjects();
  const todayLabel = summary.today_minutes;
  const activeMode = timer.mode;
  const duration = timer.durationSeconds;
  const minutesValue = Math.floor(timer.remainingSeconds / 60);
  const secondsValue = timer.remainingSeconds % 60;
  const circumference = 2 * Math.PI * 126;
  const progress = duration ? timer.remainingSeconds / duration : 1;
  const dashOffset = circumference * (1 - progress);

  container.innerHTML = `
    <div class="page-shell">
      <header class="page-header">
        <div class="page-heading">
          <p class="eyebrow">FOCUS · 专注时钟</p>
          <h1>一次只做一件事</h1>
          <p class="page-subtitle">用番茄钟建立专注节奏，完成后自动记录学习时长。离开页面会结束当前计时。</p>
        </div>
        <div class="page-actions">
          <a class="btn btn-secondary" href="#/reports">${icon("file-text")}<span>今日报告</span></a>
          <a class="btn btn-primary" href="#/planner">${icon("calendar-days")}<span>查看计划</span></a>
        </div>
      </header>

      <section class="focus-summary-grid">
        <div class="summary-chip"><span class="summary-icon teal">${icon("timer")}</span><div><strong>${formatMinutes(summary.today_minutes || 0)}</strong><span>今日专注 · ${summary.today_sessions || 0} 次</span></div></div>
        <div class="summary-chip"><span class="summary-icon blue">${icon("calendar-days")}</span><div><strong>${formatMinutes(summary.week_minutes || 0)}</strong><span>近 7 天 · ${summary.week_sessions || 0} 次</span></div></div>
        <div class="summary-chip"><span class="summary-icon amber">${icon("flame")}</span><div><strong>${summary.study_days || 0} 天</strong><span>累计学习天数</span></div></div>
        <div class="summary-chip"><span class="summary-icon violet">${icon("clock-3")}</span><div><strong>${formatMinutes(summary.total_minutes || 0)}</strong><span>累计学习时长</span></div></div>
      </section>

      <div class="focus-layout">
        <section class="card timer-card">
          <div class="timer-modes" role="group" aria-label="计时模式">
            <button type="button" class="timer-mode ${activeMode === "focus" ? "is-active" : ""}" data-timer-mode="focus">${icon("brain")} 专注</button>
            <button type="button" class="timer-mode ${activeMode === "short" ? "is-active" : ""}" data-timer-mode="short">${icon("coffee")} 短休息</button>
            <button type="button" class="timer-mode ${activeMode === "long" ? "is-active" : ""}" data-timer-mode="long">${icon("sofa")} 长休息</button>
          </div>
          <div class="timer-context">
            <label class="timer-context-field">
              <span>学科</span>
              <select class="input input-sm" id="timer-subject" ${timer.running ? "disabled" : ""}>
                ${subjects
                  .map(
                    (subject) =>
                      `<option value="${escapeHTML(subject)}" ${
                        (timer.subject || "数学") === subject ? "selected" : ""
                      }>${escapeHTML(subject)}</option>`
                  )
                  .join("")}
              </select>
            </label>
            <label class="timer-context-field">
              <span>关联任务</span>
              <select class="input input-sm" id="timer-task" ${timer.running ? "disabled" : ""}>
                <option value="">不关联任务</option>
                ${state.openTasks
                  .map(
                    (task) =>
                      `<option value="${task.id}" ${String(timer.taskId || "") === String(task.id) ? "selected" : ""}>${escapeHTML(
                        task.title
                      )}</option>`
                  )
                  .join("")}
              </select>
            </label>
            ${
              activeMode === "focus"
                ? `<label class="timer-context-field timer-duration-field"><span>时长（分钟）</span><input class="input input-sm" id="timer-focus-minutes" type="number" min="5" max="120" value="${
                    timer.durations.focus
                  }" ${timer.running ? "disabled" : ""}></label>`
                : ""
            }
          </div>

          <div class="timer-stage">
            <div class="timer-ring-wrap">
              <svg class="timer-ring" viewBox="0 0 300 300" aria-hidden="true">
                <circle class="timer-ring-track" cx="150" cy="150" r="126"></circle>
                <circle class="timer-ring-progress" cx="150" cy="150" r="126"
                  stroke-dasharray="${circumference.toFixed(1)}"
                  stroke-dashoffset="${dashOffset.toFixed(1)}"></circle>
              </svg>
              <div class="timer-display">
                <span class="timer-mode-label">${escapeHTML(modeLabel(activeMode))}</span>
                <strong id="timer-clock">${formatClock(timer.remainingSeconds)}</strong>
                <span id="timer-status">${timer.running ? "保持专注，别切换页面" : timer.remainingSeconds < duration ? "已暂停" : "准备好就开始"}</span>
              </div>
            </div>
          </div>

          <div class="timer-controls">
            <button type="button" class="btn btn-secondary timer-reset" data-timer-reset ${timer.running ? "" : "disabled"}>${icon("rotate-ccw")} 重置</button>
            <button type="button" class="btn btn-primary btn-lg timer-toggle" data-timer-toggle>
              ${icon(timer.running ? "pause" : "play")}
              <span>${timer.running ? "暂停" : timer.remainingSeconds === duration ? (activeMode === "focus" ? "开始专注" : "开始休息") : "继续"}</span>
            </button>
            <button type="button" class="btn btn-secondary timer-finish" data-timer-finish ${timer.running || timer.remainingSeconds < duration ? "" : "disabled"}>
              ${icon("check")} 结束并记录
            </button>
          </div>
          <p class="timer-note">${icon("info")} 专注结束后会自动记录本次时长${
            activeMode === "focus" ? "；休息计时不会计入学习数据" : ""
          }。离开页面会中断当前计时。</p>
        </section>

        <aside class="focus-side">
          <section class="card">
            <div class="card-header">
              <div><h2 class="card-title">${icon("activity")} 本周节奏</h2><p class="card-subtitle">共 ${formatMinutes(summary.week_minutes || 0)}</p></div>
            </div>
            ${weeklyBars((summary.week_activity || []).map((item) => ({ ...item, weekday: item.weekday })))}
          </section>

          <section class="card manual-session-card">
            <div class="card-header">
              <div><h2 class="card-title">${icon("plus")} 手动补录</h2><p class="card-subtitle">忘记计时？补上真实学习时间。</p></div>
            </div>
            <form id="manual-session-form" class="form-stack">
              <div class="form-grid form-grid-2">
                <label class="field"><span class="field-label">学科</span><select class="input input-sm" name="subject">${subjects
                  .map((subject) => `<option value="${escapeHTML(subject)}">${escapeHTML(subject)}</option>`)
                  .join("")}</select></label>
                <label class="field"><span class="field-label">分钟数</span><input class="input input-sm" type="number" name="duration_minutes" min="1" max="720" value="30" required></label>
              </div>
              <label class="field"><span class="field-label">备注</span><input class="input input-sm" name="note" maxlength="200" placeholder="例如：复习英语单词"></label>
              <button type="submit" class="btn btn-secondary btn-sm btn-full">${icon("save")} 记录学习时间</button>
            </form>
          </section>

          <section class="card">
            <div class="card-header">
              <div><h2 class="card-title">${icon("history")} 今日记录</h2><p class="card-subtitle">${todayLabel ? "今天已经留下学习痕迹" : "完成一次专注后会出现在这里"}</p></div>
            </div>
            ${
              sessions.length
                ? `<ul class="session-list">
                    ${sessions
                      .slice(0, 5)
                      .map(
                        (session) => `<li class="session-row">
                          <span class="session-color" style="background:${
                            session.session_type === "manual" ? "#94a3b8" : "#0d9488"
                          }"></span>
                          <div class="session-copy"><strong>${escapeHTML(
                            session.task_title || session.subject
                          )}</strong><span>${escapeHTML(session.subject)} · ${formatTime(
                            session.started_at
                          )}</span></div>
                          <span class="session-duration">${session.duration_minutes}m</span>
                          <button type="button" class="icon-button danger session-delete" data-delete-session="${
                            session.id
                          }" aria-label="删除这条学习记录" title="删除记录">${icon("x")}</button>
                        </li>`
                      )
                      .join("")}
                  </ul>`
                : emptyState({
                    iconName: "timer",
                    title: "今天还没有学习记录",
                    description: "开始一个番茄钟，让今天的专注有迹可循。",
                  })
            }
          </section>
        </aside>
      </div>

      <section class="card achievements-card">
        <div class="card-header">
          <div><h2 class="card-title">${icon("award")} 学习成就</h2><p class="card-subtitle">已解锁 ${unlocked.length} / ${achievements?.total || 0} · 每个小进步都值得记录</p></div>
        </div>
        <div class="achievement-grid">
          ${(achievements?.items || [])
            .map(
              (item) => `<article class="achievement-tile ${item.unlocked ? "is-unlocked" : "is-locked"}">
                <span class="achievement-icon">${icon(item.icon || "award")}</span>
                <div><strong>${escapeHTML(item.title)}</strong><p>${escapeHTML(item.description)}</p>${
                  item.unlocked
                    ? `<span class="achievement-date">${formatDate(item.unlocked_at, { withYear: true })} 解锁</span>`
                    : '<span class="achievement-locked-label">尚未解锁</span>'
                }</div>
              </article>`
            )
            .join("")}
        </div>
        ${
          locked.length
            ? `<p class="achievement-footnote">继续完成任务、专注学习、写笔记或添加闪卡，更多成就会自动解锁。</p>`
            : ""
        }
      </section>
    </div>
  `;
  refreshIcons(container);
  bindTimer(container);
  bindManualForm(container);
  bindSessionDeletes(container);
}

function bindTimer(container) {
  const toggle = container.querySelector("[data-timer-toggle]");
  const reset = container.querySelector("[data-timer-reset]");
  const finish = container.querySelector("[data-timer-finish]");
  const subjectSelect = container.querySelector("#timer-subject");
  const taskSelect = container.querySelector("#timer-task");
  const customMinutes = container.querySelector("#timer-focus-minutes");

  container.querySelectorAll("[data-timer-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      if (timer.running) return;
      setMode(button.dataset.timerMode, container);
    });
  });

  subjectSelect?.addEventListener("change", () => {
    timer.subject = subjectSelect.value;
  });
  taskSelect?.addEventListener("change", () => {
    timer.taskId = taskSelect.value || null;
  });
  customMinutes?.addEventListener("change", () => {
    if (timer.running) return;
    const value = Math.max(5, Math.min(120, Number(customMinutes.value) || 25));
    customMinutes.value = String(value);
    timer.durations.focus = value;
    if (timer.mode === "focus") {
      timer.durationSeconds = value * 60;
      timer.remainingSeconds = value * 60;
      updateTimerUI(container);
    }
  });

  toggle.addEventListener("click", () => {
    if (timer.running) pauseTimer(container);
    else startTimer(container);
  });
  reset.addEventListener("click", () => {
    resetTimer();
    updateTimerUI(container);
    updateTimerButtons(container);
  });
  finish.addEventListener("click", () => {
    finishTimer(container, { early: true });
  });
  timer.subject = subjectSelect?.value || timer.subject || "数学";
  timer.taskId = taskSelect?.value || null;
  updateTimerUI(container);
  updateTimerButtons(container);
}

function setMode(mode, container) {
  resetTimer();
  timer.mode = mode;
  const minutes = timer.durations[mode];
  timer.durationSeconds = minutes * 60;
  timer.remainingSeconds = minutes * 60;
  container.querySelectorAll("[data-timer-mode]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.timerMode === mode);
  });
  const durationField = container.querySelector(".timer-duration-field");
  if (durationField) durationField.hidden = mode !== "focus";
  updateTimerUI(container);
  updateTimerButtons(container);
}

function startTimer(container) {
  if (timer.recording) return;
  if (timer.remainingSeconds <= 0) resetTimer();
  clearInterval(timer.intervalId);
  timer.running = true;
  if (!timer.startedAt) timer.startedAt = new Date().toISOString();
  timer.endsAt = Date.now() + timer.remainingSeconds * 1000;
  timer.intervalId = window.setInterval(() => {
    const secondsLeft = Math.max(0, Math.ceil((timer.endsAt - Date.now()) / 1000));
    timer.remainingSeconds = secondsLeft;
    updateTimerUI(container);
    if (secondsLeft <= 0) {
      clearInterval(timer.intervalId);
      timer.intervalId = null;
      timer.running = false;
      finishTimer(container, { early: false });
    }
  }, 250);
  updateTimerUI(container);
  updateTimerButtons(container);
}

function pauseTimer(container) {
  if (!timer.running) return;
  timer.remainingSeconds = Math.max(0, Math.ceil((timer.endsAt - Date.now()) / 1000));
  clearInterval(timer.intervalId);
  timer.intervalId = null;
  timer.running = false;
  updateTimerUI(container);
  updateTimerButtons(container);
}

function updateTimerUI(container) {
  const clock = container.querySelector("#timer-clock");
  const status = container.querySelector("#timer-status");
  const ring = container.querySelector(".timer-ring-progress");
  if (!clock) return;
  clock.textContent = formatClock(timer.remainingSeconds);
  status.textContent = timer.running
    ? "保持专注，别切换页面"
    : timer.remainingSeconds < timer.durationSeconds
    ? "已暂停，准备好后继续"
    : modeLabel(timer.mode) === "专注"
    ? "准备好就开始"
    : "休息一下，放松眼睛";
  const circumference = 2 * Math.PI * 126;
  const progress = timer.durationSeconds ? timer.remainingSeconds / timer.durationSeconds : 1;
  if (ring) ring.setAttribute("stroke-dashoffset", `${(circumference * (1 - progress)).toFixed(1)}`);
  const subjectSelect = container.querySelector("#timer-subject");
  const taskSelect = container.querySelector("#timer-task");
  const customMinutes = container.querySelector("#timer-focus-minutes");
  if (subjectSelect) subjectSelect.disabled = timer.running;
  if (taskSelect) taskSelect.disabled = timer.running;
  if (customMinutes) customMinutes.disabled = timer.running;
  container.querySelectorAll("[data-timer-mode]").forEach((button) => {
    button.disabled = timer.running;
  });
}

function updateTimerButtons(container) {
  const toggle = container.querySelector("[data-timer-toggle]");
  const reset = container.querySelector("[data-timer-reset]");
  const finish = container.querySelector("[data-timer-finish]");
  if (!toggle) return;
  const label = timer.running
    ? "暂停"
    : timer.remainingSeconds === timer.durationSeconds
    ? timer.mode === "focus"
      ? "开始专注"
      : "开始休息"
    : "继续";
  toggle.innerHTML = `${icon(timer.running ? "pause" : "play")}<span>${label}</span>`;
  toggle.disabled = timer.recording;
  reset.disabled = timer.recording || (!timer.running && timer.remainingSeconds === timer.durationSeconds);
  finish.disabled =
    timer.recording || (!timer.running && timer.remainingSeconds === timer.durationSeconds);
  refreshIcons(toggle);
  refreshIcons(reset);
  refreshIcons(finish);
}

function playCompletionSound() {
  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return;
    const context = new AudioContext();
    [0, 0.18, 0.36].forEach((offset, index) => {
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.frequency.value = [660, 880, 1046][index];
      oscillator.type = "sine";
      gain.gain.setValueAtTime(0.0001, context.currentTime + offset);
      gain.gain.exponentialRampToValueAtTime(0.12, context.currentTime + offset + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + offset + 0.25);
      oscillator.connect(gain);
      gain.connect(context.destination);
      oscillator.start(context.currentTime + offset);
      oscillator.stop(context.currentTime + offset + 0.3);
    });
    window.setTimeout(() => context.close(), 1200);
  } catch {
    // Browsers may block audio; visual notification still works.
  }
}

async function finishTimer(container, { early = false } = {}) {
  if (timer.recording) return;
  clearInterval(timer.intervalId);
  timer.intervalId = null;
  timer.running = false;
  const elapsedMinutes = Math.max(
    1,
    Math.round((timer.durationSeconds - timer.remainingSeconds) / 60)
  );
  const completedFully = timer.remainingSeconds <= 0;
  if (timer.mode !== "focus") {
    playCompletionSound();
    showToast("休息结束，可以开始下一轮专注了。", "info");
    resetTimer();
    setMode("focus", container);
    return;
  }
  if (!early && !completedFully) {
    // Timer was interrupted unusually; do not invent a full session.
    updateTimerUI(container);
    updateTimerButtons(container);
    return;
  }
  const minutes = early
    ? elapsedMinutes
    : Math.max(1, Math.round(timer.durationSeconds / 60));
  playCompletionSound();
  timer.recording = true;
  updateTimerButtons(container);
  const startedAt = timer.startedAt || new Date(Date.now() - minutes * 60000).toISOString();
  const subject = timer.subject || "综合";
  const taskId = timer.taskId || null;
  try {
    const response = await api.post("/study/sessions", {
      subject,
      task_id: taskId,
      duration_minutes: minutes,
      session_type: "pomodoro",
      started_at: startedAt,
      ended_at: new Date().toISOString(),
      note: early ? "提前结束并记录" : "番茄钟完成",
    });
    const unlocked = response.data?.unlocked_achievements || [];
    showToast(`专注完成，已记录 ${minutes} 分钟`);
    if (unlocked.length) {
      window.setTimeout(
        () => showToast(`解锁成就：${unlocked.map((item) => item.title).join("、")}`, "info", { duration: 6000 }),
        300
      );
    }
    refreshCurrent({ preserveScroll: true });
  } catch (error) {
    timer.recording = false;
    updateTimerButtons(container);
    toastError(error);
  }
}

function bindManualForm(container) {
  const form = container.querySelector("#manual-session-form");
  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(form);
    const duration = Number(formData.get("duration_minutes") || 0);
    if (!duration || duration < 1 || duration > 720) {
      toastError(new Error("学习时长需在 1 到 720 分钟之间"));
      return;
    }
    const button = form.querySelector("button[type=submit]");
    const original = button.innerHTML;
    button.disabled = true;
    button.innerHTML = `<span class="spinner"></span><span>记录中…</span>`;
    try {
      const response = await api.post("/study/sessions", {
        subject: formData.get("subject"),
        duration_minutes: duration,
        session_type: "manual",
        note: String(formData.get("note") || "").trim(),
      });
      showToast(response.message || "学习时间已记录");
      refreshCurrent({ preserveScroll: true });
    } catch (error) {
      toastError(error);
      button.disabled = false;
      button.innerHTML = original;
      refreshIcons(button);
    }
  });
}

function bindSessionDeletes(container) {
  container.querySelectorAll("[data-delete-session]").forEach((button) => {
    button.addEventListener("click", async () => {
      const confirmed = await openConfirm({
        title: "删除学习记录",
        message: "确定删除这条学习记录吗？统计数据会同步更新。",
        confirmText: "删除记录",
        danger: true,
      });
      if (!confirmed) return;
      try {
        await api.delete(`/study/sessions/${button.dataset.deleteSession}`);
        showToast("学习记录已删除");
        refreshCurrent({ preserveScroll: true });
      } catch (error) {
        toastError(error);
      }
    });
  });
}

async function render(container) {
  pageController?.abort();
  pageController = new AbortController();
  clearInterval(timer?.intervalId);
  try {
    const [sessionsResponse, statsResponse, tasksResponse, achievementsResponse] = await Promise.all([
      api.get("/study/sessions", { date: todayForApi(), limit: 100 }, { signal: pageController.signal }),
      api.get("/study/stats", undefined, { signal: pageController.signal }),
      api.get("/tasks", { status: "open", limit: 100 }, { signal: pageController.signal }),
      api.get("/achievements", undefined, { signal: pageController.signal }),
    ]);
    state.sessions = sessionsResponse.data.sessions || [];
    state.summary = statsResponse.data;
    state.openTasks = tasksResponse.data.tasks || [];
    state.achievements = achievementsResponse.data;
    if (!timer) {
      timer = buildTimer(getMeta()?.user);
    } else {
      timer.recording = false;
      timer.durationSeconds = timer.durations[timer.mode] * 60;
      timer.remainingSeconds = timer.durationSeconds;
    }
    timer.subject = state.sessions[0]?.subject || getSubjects()[1] || "综合";
    renderPage(container);
  } catch (error) {
    if (error.name === "AbortError") return;
    throw error;
  }
}

function todayForApi() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

function cleanup() {
  pageController?.abort();
  pageController = null;
  if (timer) {
    clearInterval(timer.intervalId);
    timer.intervalId = null;
    timer.running = false;
  }
}

export default {
  title: "专注时钟",
  render,
  cleanup,
};
