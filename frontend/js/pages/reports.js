import { api } from "../api.js";
import { icon, refreshIcons } from "../components/icons.js";
import { refreshCurrent } from "../router.js";
import { getMeta } from "../services/store.js";
import {
  emptyState,
  escapeHTML,
  formatDate,
  formatDateTime,
  formatMinutes,
  formatTime,
  progressBar,
  progressRing,
  subjectBadge,
  todayISO,
} from "../ui.js";

const state = {
  date: todayISO(),
  report: null,
};

let pageController = null;

function shiftDate(days) {
  const date = new Date(`${state.date}T00:00:00`);
  date.setDate(date.getDate() + days);
  const offset = date.getTimezoneOffset() * 60000;
  const iso = new Date(date.getTime() - offset).toISOString().slice(0, 10);
  if (iso > todayISO()) return;
  state.date = iso;
  refreshCurrent({ preserveScroll: true });
}

function metricCard({ iconName, label, value, suffix = "", foot = "", tone = "blue" }) {
  return `<article class="report-metric report-metric-${tone}">
    <span class="report-metric-icon">${icon(iconName)}</span>
    <span class="report-metric-label">${escapeHTML(label)}</span>
    <strong>${escapeHTML(value)}${suffix ? `<small>${escapeHTML(suffix)}</small>` : ""}</strong>
    <p>${foot}</p>
  </article>`;
}

function renderPage(container) {
  const report = state.report;
  const user = getMeta()?.user;
  const name = report.user?.display_name || user?.display_name || "同学";
  const goal = report.goal;
  const tasks = report.tasks;
  const study = report.study;
  const targetReached = goal.progress >= 100;
  const hasActivity =
    study.total_minutes > 0 ||
    tasks.total > 0 ||
    report.grades.length > 0 ||
    report.notes.length > 0 ||
    report.errors.length > 0 ||
    report.achievements.length > 0;

  container.innerHTML = `
    <div class="page-shell report-page">
      <header class="page-header">
        <div class="page-heading">
          <h1>${escapeHTML(report.date_label)} · ${escapeHTML(report.weekday)}</h1>
          <p class="page-subtitle">${report.is_today ? "今天的学习轨迹还在继续。" : "回看已发生的学习，找到可以调整的节奏。"} 本报告由本地学习数据自动汇总。</p>
        </div>
        <div class="page-actions report-actions">
          <div class="report-date-nav">
            <button type="button" class="icon-button" data-date-shift="-1" title="前一天" aria-label="前一天">${icon("chevron-left")}</button>
            <input class="input input-sm" type="date" id="report-date" value="${escapeHTML(
              state.date
            )}" max="${todayISO()}" aria-label="选择报告日期">
            <button type="button" class="icon-button" data-date-shift="1" title="后一天" aria-label="后一天" ${
              state.date >= todayISO() ? "disabled" : ""
            }>${icon("chevron-right")}</button>
          </div>
          <button type="button" class="btn btn-secondary" data-print-report>${icon("printer")}<span>打印报告</span></button>
        </div>
      </header>

      <section class="report-hero">
        <div class="report-hero-copy">
          <span class="report-hero-kicker">${icon("sunrise")} ${escapeHTML(name)}的学习小结</span>
          <h2>${targetReached ? "今天的专注目标已经达成。" : hasActivity ? "今天已经留下了这些学习痕迹。" : "今天还是一张白纸，可以从 25 分钟开始。"}</h2>
          <p>${escapeHTML(report.narrative[0] || "")}</p>
          <div class="report-hero-tags">
            <span>${icon("timer")} ${formatMinutes(study.total_minutes)}</span>
            <span>${icon("check-check")} ${tasks.completed}/${tasks.total} 个任务</span>
            <span>${icon("layers")} ${report.flashcards_reviewed} 张闪卡复习</span>
          </div>
        </div>
        <div class="report-goal-ring">
          ${progressRing(goal.progress, { size: 130, stroke: 10, label: "学习目标" })}
          <span>每日目标 ${formatMinutes(goal.target_minutes)}</span>
        </div>
      </section>

      <section class="report-metrics">
        ${metricCard({
          iconName: "timer",
          label: "专注时长",
          value: formatMinutes(study.total_minutes, { compact: true }),
          foot: `${study.session_count} 次学习记录 · ${study.pomodoros} 个番茄钟`,
          tone: "teal",
        })}
        ${metricCard({
          iconName: "list-checks",
          label: "任务完成率",
          value: String(tasks.completion_rate),
          suffix: "%",
          foot: `${tasks.completed} 个已完成 · ${tasks.pending} 个未完成`,
          tone: "blue",
        })}
        ${metricCard({
          iconName: "target",
          label: "目标完成度",
          value: String(goal.progress),
          suffix: "%",
          foot: targetReached ? "达成每日目标" : `距离目标还差 ${formatMinutes(
              Math.max(0, goal.target_minutes - study.total_minutes)
            )}`,
          tone: "amber",
        })}
        ${metricCard({
          iconName: "award",
          label: "今日成就",
          value: String(report.achievements.length),
          suffix: "枚",
          foot: report.achievements.length ? "新解锁成就" : "继续积累即可解锁",
          tone: "violet",
        })}
      </section>

      <div class="report-layout">
        <div class="report-main">
          <section class="card">
            <div class="card-header">
              <div><h2 class="card-title">${icon("book-open")} 学习投入</h2><p class="card-subtitle">按学科统计今天的学习时间。</p></div>
            </div>
            ${
              study.subjects.length
                ? `<div class="subject-minute-list">
                    ${study.subjects
                      .map(
                        (item) => `<div class="subject-minute-row">
                          <div class="subject-minute-label">${subjectBadge(item.subject, { small: true })}<strong>${formatMinutes(
                            item.minutes
                          )}</strong></div>
                          ${progressBar(
                            Math.round((item.minutes / Math.max(1, study.total_minutes)) * 100),
                            { tone: "teal" }
                          )}
                        </div>`
                      )
                      .join("")}
                  </div>`
                : emptyState({
                    iconName: "timer",
                    title: "今天还没有专注记录",
                    description: "去完成一个番茄钟，明天的报告会更有内容。",
                    action: `<a href="#/focus" class="btn btn-secondary btn-sm">${icon("timer")} 开始专注</a>`,
                  })
            }
          </section>

          <section class="card">
            <div class="card-header">
              <div><h2 class="card-title">${icon("check-square")} 任务回顾</h2><p class="card-subtitle">今天相关任务与完成情况。</p></div>
              <a href="#/planner" class="text-link">打开规划 ${icon("arrow-right")}</a>
            </div>
            ${
              tasks.items.length
                ? `<ul class="report-task-list">
                    ${tasks.items
                      .map(
                        (task) => `<li class="${task.status === "completed" ? "is-done" : ""}">
                          <span class="report-task-check">${icon(task.status === "completed" ? "check" : "circle")}</span>
                          <div><strong>${escapeHTML(task.title)}</strong><span>${escapeHTML(
                            task.subject
                          )}</span></div>
                          <span class="report-task-status">${
                            task.status === "completed" ? "已完成" : "未完成"
                          }</span>
                        </li>`
                      )
                      .join("")}
                  </ul>`
                : emptyState({
                    iconName: "clipboard-list",
                    title: "今天没有安排任务",
                    description: "没有任务也可以专注于复习和整理。",
                  })
            }
          </section>

          <section class="card">
            <div class="card-header">
              <div><h2 class="card-title">${icon("history")} 学习时间线</h2><p class="card-subtitle">每一次专注都算数。</p></div>
            </div>
            ${
              study.sessions.length
                ? `<ol class="report-timeline">
                    ${study.sessions
                      .map(
                        (session) => `<li>
                          <span class="timeline-time">${formatTime(session.started_at)}</span>
                          <span class="timeline-dot" style="--dot:${session.session_type === "manual" ? "#94a3b8" : "#0d9488"}"></span>
                          <div><strong>${escapeHTML(session.subject)}</strong><span>${
                            session.session_type === "manual" ? "手动记录" : "专注计时"
                          } · ${formatMinutes(session.duration_minutes)}</span></div>
                        </li>`
                      )
                      .join("")}
                  </ol>`
                : `<p class="muted-note">今天没有学习计时记录。</p>`
            }
          </section>

          ${
            report.notes.length || report.grades.length || report.errors.length || report.achievements.length
              ? `<div class="report-updates-grid">
                  ${
                    report.notes.length
                      ? `<section class="card mini-report-card"><h3>${icon("notebook-pen")} 今日笔记</h3>${report.notes
                          .map(
                            (note) => `<div class="mini-report-row"><div><strong>${escapeHTML(
                              note.title
                            )}</strong>${subjectBadge(note.subject, { small: true })}</div></div>`
                          )
                          .join("")}</section>`
                      : ""
                  }
                  ${
                    report.grades.length
                      ? `<section class="card mini-report-card"><h3>${icon("chart-line")} 今日成绩</h3>${report.grades
                          .map(
                            (grade) => `<div class="mini-report-row"><div><strong>${escapeHTML(
                              grade.subject
                            )} · ${escapeHTML(grade.exam_name)}</strong><span>${grade.percentage}%</span></div></div>`
                          )
                          .join("")}</section>`
                      : ""
                  }
                  ${
                    report.errors.length
                      ? `<section class="card mini-report-card"><h3>${icon("clipboard-list")} 新增错题</h3>${report.errors
                          .map(
                            (error) => `<div class="mini-report-row"><div><strong>${escapeHTML(
                              error.subject
                            )}</strong><span>${escapeHTML(
                              (error.knowledge_points || []).join(" · ") || "未标注知识点"
                            )}</span></div></div>`
                          )
                          .join("")}</section>`
                      : ""
                  }
                  ${
                    report.achievements.length
                      ? `<section class="card mini-report-card"><h3>${icon("award")} 解锁成就</h3>${report.achievements
                          .map(
                            (item) => `<div class="mini-report-row"><div><strong>${escapeHTML(
                              item.title
                            )}</strong><span>${formatDateTime(item.unlocked_at)}</span></div></div>`
                          )
                          .join("")}</section>`
                      : ""
                  }
                </div>`
              : ""
          }
        </div>

        <aside class="report-side">
          <section class="card suggestions-card">
            <div class="card-header">
              <div><h2 class="card-title">${icon("lightbulb")} 明日调整建议</h2><p class="card-subtitle">温和、具体，不追求一次改变很多。</p></div>
            </div>
            <ul class="suggestion-list">
              ${report.suggestions
                .map(
                  (suggestion, index) => `<li><span class="suggestion-number">${index + 1}</span><p>${escapeHTML(
                    suggestion
                  )}</p></li>`
                )
                .join("")}
            </ul>
          </section>
          <section class="card report-narrative-card">
            <h2>${icon("align-left")} 今日小结</h2>
            ${report.narrative
              .map((paragraph) => `<p>${escapeHTML(paragraph)}</p>`)
              .join("")}
            <span class="report-generated">${icon("clock-3")} 生成于 ${formatDateTime(
              report.generated_at
            )}</span>
          </section>
          <section class="card report-note-card">
            <p>${icon("info")} ${escapeHTML(report.notice)}</p>
            <a class="btn btn-secondary btn-sm btn-full" href="#/settings">${icon("download")} 在设置中导出数据</a>
          </section>
        </aside>
      </div>
    </div>
  `;
  refreshIcons(container);
  bindEvents(container);
}

function bindEvents(container) {
  container.querySelector("#report-date")?.addEventListener("change", (event) => {
    const value = event.target.value;
    if (!value) return;
    if (value > todayISO()) {
      event.target.value = todayISO();
      return;
    }
    state.date = value;
    refreshCurrent({ preserveScroll: true });
  });
  container.querySelectorAll("[data-date-shift]").forEach((button) => {
    button.addEventListener("click", () => shiftDate(Number(button.dataset.dateShift)));
  });
  container.querySelector("[data-print-report]")?.addEventListener("click", () => {
    window.print();
  });
}

async function render(container) {
  pageController?.abort();
  pageController = new AbortController();
  if (state.date > todayISO()) state.date = todayISO();
  try {
    const response = await api.get(
      "/reports/daily",
      { date: state.date },
      { signal: pageController.signal }
    );
    state.report = response.data;
    state.date = response.data.date;
    renderPage(container);
  } catch (error) {
    if (error.name === "AbortError") return;
    throw error;
  }
}

function cleanup() {
  pageController?.abort();
  pageController = null;
}

export default {
  title: "学习报告",
  render,
  cleanup,
};
