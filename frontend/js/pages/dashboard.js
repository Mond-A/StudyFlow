import { api } from "../api.js";
import { icon, refreshIcons } from "../components/icons.js";
import { openCompleteTaskModal } from "../components/task-modal.js";
import { showToast, toastError } from "../components/toast.js";
import { aiModeBadge } from "../components/ai-display.js";
import { refreshCurrent } from "../router.js";
import { getMeta } from "../services/store.js";
import {
  difficultyDots,
  dueLabel,
  dueTone,
  emptyState,
  escapeHTML,
  formatAgo,
  formatDate,
  formatMinutes,
  formatTime,
  initials,
  percent,
  progressBar,
  progressRing,
  relativeDay,
  subjectBadge,
  weeklyBars,
} from "../ui.js";

let abortController = null;
let dashboardData = null;

function statsCard({ iconName, label, value, suffix, foot, accent = "blue" }) {
  return `<article class="stat-card stat-${accent}">
    <div class="stat-top">
      <span class="stat-icon">${icon(iconName)}</span>
      <span class="stat-label">${escapeHTML(label)}</span>
    </div>
    <div class="stat-value">${escapeHTML(value)}${suffix ? `<span>${escapeHTML(suffix)}</span>` : ""}</div>
    <div class="stat-foot">${foot}</div>
  </article>`;
}

function taskItem(task) {
  const completed = task.status === "completed";
  const timeBits = [];
  if (task.planned_start) timeBits.push(`<span>${icon("clock-3")}计划 ${task.planned_start}</span>`);
  timeBits.push(`<span>${icon("hourglass")}预计 ${task.estimated_minutes} 分钟</span>`);
  return `<li class="today-task ${completed ? "is-completed" : ""}">
    ${
      completed
        ? `<span class="task-check is-checked" aria-label="已完成">${icon("check")}</span>`
        : `<button type="button" class="task-check" data-complete-task="${task.id}" aria-label="完成 ${escapeHTML(
            task.title
          )}">${icon("circle")}</button>`
    }
    <div class="today-task-body">
      <div class="today-task-title-row">
        <span class="today-task-title">${escapeHTML(task.title)}</span>
        ${subjectBadge(task.subject, { small: true })}
      </div>
      <div class="today-task-meta">
        <span class="due-text due-${dueTone(task)}">${escapeHTML(dueLabel(task))}</span>
        ${timeBits.join("")}
        ${difficultyDots(task.difficulty)}
      </div>
    </div>
    ${task.status === "in_progress" ? '<span class="status-badge status-progress"><span class="status-dot"></span>进行中</span>' : ""}
  </li>`;
}

function renderDashboard(container, data) {
  const meta = getMeta();
  const ai = meta?.ai;
  const userName = data.user?.display_name || "同学";
  const s = data.stats;
  const aiNeedsAttention = ai && [ai.text?.effective_mode, ai.vision?.effective_mode].some(
    (mode) => mode === "demo" || mode === "unavailable"
  );
  const latestGradeDelta =
    data.recent_grades.length && data.recent_grades[0].delta !== null
      ? data.recent_grades[0].delta
      : null;
  const deltaMarkup = (() => {
    if (latestGradeDelta === null) return "";
    const positive = latestGradeDelta >= 0;
    return `<span class="delta ${positive ? "delta-up" : "delta-down"}">${icon(
      positive ? "arrow-up-right" : "arrow-down-right"
    )}${Math.abs(latestGradeDelta).toFixed(1)}</span>`;
  })();

  container.innerHTML = `
    <div class="page-shell">
      <header class="page-header">
        <div class="page-heading">
          <h1>${escapeHTML(data.greeting)}，${escapeHTML(userName)}</h1>
          <p class="page-subtitle">${escapeHTML(data.date_label)} · ${escapeHTML(
            data.weekday_label
          )}。${s.today_tasks_total ? `今天有 ${s.today_tasks_total} 个任务，先完成最重要的一件。` : "今天还没有排期，给自己安排一个清晰的小目标吧。"}</p>
        </div>
        <div class="page-actions">
          <a class="btn btn-secondary" href="#/reports">${icon("file-text")}<span>学习报告</span></a>
          <a class="btn btn-primary" href="#/planner">${icon("calendar-plus")}<span>规划今天</span></a>
        </div>
      </header>

      ${
        aiNeedsAttention
          ? `<div class="dashboard-ai-note">
              <span>${aiModeBadge(ai)}</span>
              <p>AI 分析尚未全部连接真实模型，AI 功能会显示明确的演示标识。你可以在设置页查看配置状态。</p>
              <a href="#/settings" class="text-link">检查 AI 配置 ${icon("arrow-right")}</a>
            </div>`
          : ""
      }

      <section class="stats-grid" aria-label="今日学习概览">
        ${statsCard({
          iconName: "list-checks",
          label: "今日任务",
          value: `${s.today_tasks_completed}/${s.today_tasks_total}`,
          foot: `${progressBar(s.today_completion_rate, { tone: "primary" })}<span class="stat-foot-note">完成率 ${s.today_completion_rate}%</span>`,
          accent: "blue",
        })}
        ${statsCard({
          iconName: "timer",
          label: "今日专注",
          value: formatMinutes(s.today_focus_minutes, { compact: true }),
          foot: `<span class="stat-foot-main">${s.today_sessions} 次专注记录</span><span class="stat-foot-note">目标 ${formatMinutes(
            s.daily_goal_minutes,
            { compact: true }
          )}</span>`,
          accent: "teal",
        })}
        ${statsCard({
          iconName: "flame",
          label: "连续学习",
          value: String(s.streak_days),
          suffix: "天",
          foot: `<span class="stat-foot-main">${s.study_days} 个学习日</span><span class="stat-foot-note">保持节奏比时长更重要</span>`,
          accent: "amber",
        })}
        ${statsCard({
          iconName: "chart-line",
          label: "最近成绩",
          value: s.recent_average === null ? "—" : `${s.recent_average}%`,
          foot: `<span class="stat-foot-main">${
            s.recent_average === null ? "还没有成绩记录" : "最近各科得分率均值"
          }</span>${deltaMarkup}`,
          accent: "violet",
        })}
      </section>

      <div class="dashboard-grid">
        <div class="dashboard-main">
          <section class="card dashboard-tasks-card">
            <div class="card-header">
              <div>
                <h2 class="card-title">${icon("sun")} 今日任务</h2>
                <p class="card-subtitle">${data.has_fallback_tasks ? "今日暂无排期，以下是最值得优先处理的任务。" : "按计划与优先级排序，完成一个就划掉一个。"}</p>
              </div>
              <a href="#/planner" class="text-link">全部任务 ${icon("arrow-right")}</a>
            </div>
            <div class="card-toolbar">
              <div class="mini-progress">
                <div class="mini-progress-numbers"><strong>${s.today_completion_rate}%</strong><span>今日完成率</span></div>
                ${progressBar(s.today_completion_rate, { tone: s.today_completion_rate >= 100 ? "success" : "primary" })}
              </div>
              <span class="muted-note">${icon("clock")} 已投入 ${formatMinutes(s.today_focus_minutes)}</span>
            </div>
            ${
              data.today_tasks.length
                ? `<ul class="today-task-list">${data.today_tasks.slice(0, 7).map(taskItem).join("")}</ul>`
                : `<div class="card-empty">${emptyState({
                    iconName: "calendar-plus",
                    title: "今天还没有任务",
                    description: "把作业拆成小任务，或者让 AI 帮你识别一张作业图片。",
                    action: `<a href="#/planner" class="btn btn-primary btn-sm">${icon("plus")} 添加任务</a>`,
                  })}</div>`
            }
            ${
              data.today_tasks.length > 7
                ? `<a class="card-more-link" href="#/planner">还有 ${data.today_tasks.length - 7} 个任务 ${icon("arrow-right")}</a>`
                : ""
            }
          </section>

          <section class="card dashboard-week-card">
            <div class="card-header">
              <div>
                <h2 class="card-title">${icon("activity")} 最近 7 天学习节奏</h2>
                <p class="card-subtitle">共 ${formatMinutes(s.week_focus_minutes)} · ${s.week_sessions} 次专注</p>
              </div>
              <a href="#/focus" class="text-link">去专注 ${icon("arrow-right")}</a>
            </div>
            ${weeklyBars(data.week_activity)}
          </section>

          <section class="card">
            <div class="card-header">
              <div>
                <h2 class="card-title">${icon("history")} 最近学习记录</h2>
                <p class="card-subtitle">来自番茄钟与手动补录的专注时间。</p>
              </div>
              <a href="#/focus" class="text-link">查看全部 ${icon("arrow-right")}</a>
            </div>
            ${
              data.recent_sessions.length
                ? `<ul class="session-list compact">
                    ${data.recent_sessions
                      .slice(0, 4)
                      .map(
                        (session) => `<li class="session-row">
                          <span class="session-color" style="background:${escapeHTML(
                            session.session_type === "manual" ? "#94a3b8" : "#0d9488"
                          )}"></span>
                          <div class="session-copy">
                            <strong>${escapeHTML(session.task_title || session.subject)}</strong>
                            <span>${escapeHTML(session.subject)} · ${formatAgo(session.started_at)}</span>
                          </div>
                          <span class="session-duration">${formatMinutes(session.duration_minutes)}</span>
                        </li>`
                      )
                      .join("")}
                  </ul>`
                : `<div class="card-empty">${emptyState({
                    iconName: "timer",
                    title: "还没有学习记录",
                    description: "从一个 25 分钟番茄钟开始，记录真实的学习时间。",
                    action: `<a href="#/focus" class="btn btn-secondary btn-sm">${icon("timer")} 开始计时</a>`,
                  })}</div>`
            }
          </section>
        </div>

        <aside class="dashboard-side">
          <section class="card goal-card">
            <div class="card-header">
              <div>
                <h2 class="card-title">${icon("target")} 今日学习目标</h2>
                <p class="card-subtitle">${formatMinutes(s.today_focus_minutes)} / ${formatMinutes(s.daily_goal_minutes)}</p>
              </div>
            </div>
            <div class="goal-ring-row">
              ${progressRing(s.goal_progress, { size: 116, stroke: 9, label: "今日目标" })}
              <div class="goal-copy">
                <strong>${s.goal_progress >= 100 ? "目标达成" : s.goal_progress >= 50 ? "进度过半" : "刚刚起步"}</strong>
                <p>${s.goal_progress >= 100 ? "很棒，记得留出休息与复盘时间。" : `还需要 ${formatMinutes(Math.max(0, s.daily_goal_minutes - s.today_focus_minutes))} 专注时间。`}</p>
                <a href="#/focus" class="btn btn-secondary btn-sm">${icon("play")} 开始番茄钟</a>
              </div>
            </div>
            <div class="goal-stats">
              <div><span>本周专注</span><strong>${formatMinutes(s.week_focus_minutes)}</strong></div>
              <div><span>累计学习</span><strong>${formatMinutes(s.total_study_minutes)}</strong></div>
            </div>
          </section>

          <section class="card">
            <div class="card-header">
              <div>
                <h2 class="card-title">${icon("chart-no-axes-column")} 最近成绩</h2>
                <p class="card-subtitle">每个学科的最新一次记录</p>
              </div>
              <a href="#/analytics" class="text-link">分析 ${icon("arrow-right")}</a>
            </div>
            ${
              data.recent_grades.length
                ? `<ul class="grade-mini-list">
                    ${data.recent_grades
                      .map((grade) => {
                        const positive = (grade.delta || 0) >= 0;
                        return `<li>
                          <span class="grade-subject-dot" style="background:${escapeHTML(
                            grade ? subjectColor(grade.subject) : "#2563eb"
                          )}"></span>
                          <div class="grade-mini-copy">
                            <strong>${escapeHTML(grade.subject)}</strong>
                            <span>${escapeHTML(grade.exam_name)} · ${formatDate(grade.exam_date)}</span>
                          </div>
                          <div class="grade-mini-score">
                            <strong>${grade.percentage}%</strong>
                            ${
                              grade.delta === null
                                ? '<span class="delta delta-flat">首次</span>'
                                : `<span class="delta ${positive ? "delta-up" : "delta-down"}">${positive ? "+" : ""}${grade.delta}%</span>`
                            }
                          </div>
                        </li>`;
                      })
                      .join("")}
                  </ul>`
                : `<div class="card-empty">${emptyState({
                    iconName: "chart-line",
                    title: "还没有成绩记录",
                    description: "记录一次考试，开始观察自己的学习趋势。",
                    action: `<a href="#/analytics" class="btn btn-secondary btn-sm">录入成绩</a>`,
                  })}</div>`
            }
          </section>

          <section class="card">
            <div class="card-header">
              <div>
                <h2 class="card-title">${icon("zap")} 快捷入口</h2>
              </div>
            </div>
            <div class="quick-grid">
              <a href="#/ai-toolbox" class="quick-tile"><span class="quick-icon blue">${icon("sparkles")}</span><span><strong>AI 工具箱</strong><small>作文、长难句、出题</small></span></a>
              <a href="#/notes" class="quick-tile"><span class="quick-icon violet">${icon("notebook-pen")}</span><span><strong>智能笔记</strong><small>识别、纠错、图谱</small></span></a>
              <a href="#/flashcards" class="quick-tile"><span class="quick-icon teal">${icon("layers")}</span><span><strong>闪卡复习</strong><small>按记忆曲线复习</small></span></a>
              <a href="#/errors" class="quick-tile"><span class="quick-icon amber">${icon("clipboard-list")}</span><span><strong>错题本</strong><small>归纳薄弱知识点</small></span></a>
            </div>
          </section>

          <section class="card achievements-mini-card">
            <div class="card-header">
              <div>
                <h2 class="card-title">${icon("award")} 学习成就</h2>
                <p class="card-subtitle">已解锁 ${s.achievements_unlocked} / ${s.achievements_total}</p>
              </div>
              <a href="#/focus" class="text-link">全部 ${icon("arrow-right")}</a>
            </div>
            ${
              data.achievements.length
                ? `<div class="achievement-strip">
                    ${data.achievements
                      .map(
                        (item) => `<div class="achievement-chip" title="${escapeHTML(item.description)}">
                          <span>${icon(item.icon || "award")}</span>
                          <strong>${escapeHTML(item.title)}</strong>
                        </div>`
                      )
                      .join("")}
                  </div>`
                : `<p class="muted-note">完成第一个任务或专注记录，就能点亮第一枚成就。</p>`
            }
          </section>
        </aside>
      </div>
    </div>
  `;

  refreshIcons(container);

  container.querySelectorAll("[data-complete-task]").forEach((button) => {
    button.addEventListener("click", () => {
      const task = dashboardData.today_tasks.find(
        (item) => String(item.id) === button.dataset.completeTask
      );
      if (!task) return;
      openCompleteTaskModal(task, {
        onCompleted: () => refreshCurrent(),
      });
    });
  });
}

function subjectColor(subject) {
  const colors = {
    语文: "#d97706",
    数学: "#2563eb",
    英语: "#7c3aed",
    物理: "#0d9488",
    化学: "#db2777",
    生物: "#16a34a",
    政治: "#b91c1c",
    历史: "#92400e",
    地理: "#0891b2",
    综合: "#64748b",
  };
  return colors[subject] || "#64748b";
}

async function render(container) {
  abortController?.abort();
  abortController = new AbortController();
  try {
    const response = await api.get("/dashboard", undefined, {
      signal: abortController.signal,
    });
    dashboardData = response.data;
    renderDashboard(container, response.data);
  } catch (error) {
    if (error.name === "AbortError") return;
    throw error;
  }
}

function cleanup() {
  if (abortController) {
    abortController.abort();
    abortController = null;
  }
}

export default {
  title: "首页",
  render,
  cleanup,
};
