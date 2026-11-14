import { api } from "../api.js";
import { icon, refreshIcons } from "../components/icons.js";
import { openConfirm, openModal } from "../components/modal.js";
import { aiBanner, aiModeBadge } from "../components/ai-display.js";
import { showToast, toastError } from "../components/toast.js";
import { refreshCurrent } from "../router.js";
import { getMeta, getSubjects } from "../services/store.js";
import {
  barOptions,
  configureCharts,
  createChart,
  destroyCharts,
  hexToRgba,
  lineOptions,
} from "../services/charts.js";
import {
  emptyState,
  escapeHTML,
  formatDate,
  subjectBadge,
  todayISO,
} from "../ui.js";

const state = {
  subject: "all",
  range: "90",
  analytics: null,
  aiResult: null,
  aiInfo: null,
};

let controller = null;
let charts = [];
let analysisRequest = null;

const RANGES = [
  { value: "30", label: "近 30 天" },
  { value: "90", label: "近 90 天" },
  { value: "180", label: "近 180 天" },
  { value: "all", label: "全部记录" },
];

function kpiCard({ label, value, suffix = "", foot = "", iconName = "chart-line", tone = "blue" }) {
  return `<article class="kpi-card kpi-${tone}">
    <div class="kpi-top"><span class="kpi-icon">${icon(iconName)}</span><span>${escapeHTML(label)}</span></div>
    <div class="kpi-value">${escapeHTML(value)}${suffix ? `<small>${escapeHTML(suffix)}</small>` : ""}</div>
    <div class="kpi-foot">${foot}</div>
  </article>`;
}

function deltaMarkup(value, { suffix = "%" } = {}) {
  if (value === null || value === undefined) {
    return '<span class="delta delta-flat">暂无对比</span>';
  }
  const positive = value >= 0;
  return `<span class="delta ${positive ? "delta-up" : "delta-down"}">${icon(
    positive ? "trending-up" : "trending-down"
  )}${positive ? "+" : ""}${Number(value).toFixed(1)}${suffix}</span>`;
}

function chartShell({ id, title, subtitle, empty = false, emptyText = "当前筛选范围内暂无数据" }) {
  return `<section class="card chart-card">
    <div class="card-header">
      <div><h2 class="card-title">${title}</h2><p class="card-subtitle">${subtitle}</p></div>
    </div>
    <div class="chart-canvas-wrap ${empty ? "is-empty" : ""}">
      <canvas id="${id}" aria-label="${escapeHTML(title)}，图表"></canvas>
      ${
        empty
          ? `<div class="chart-empty"><span>${icon("chart-no-axes-column")}</span><p>${escapeHTML(
              emptyText
            )}</p></div>`
          : ""
      }
    </div>
  </section>`;
}

function buildPage(container, analytics) {
  const kpis = analytics.kpis;
  const best = kpis.best_subject;
  const records = analytics.records || [];
  const hasRecords = records.length > 0;
  const emptyChart = !hasRecords;
  container.innerHTML = `
    <div class="page-shell">
      <header class="page-header">
        <div class="page-heading">
          <h1>看见趋势，而不只是分数</h1>
          <p class="page-subtitle">整理考试记录，观察各科变化，用数据找到下一步值得投入的方向。</p>
        </div>
        <div class="page-actions">
          <button type="button" class="btn btn-secondary" data-ai-grades ${hasRecords ? "" : "disabled title='请先录入成绩'"}>
            ${icon("sparkles")}<span>AI 成绩分析</span>
          </button>
          <button type="button" class="btn btn-primary" data-add-grade>${icon("plus")}<span>录入成绩</span></button>
        </div>
      </header>

      <div class="analytics-filterbar">
        <div class="filter-group">
          <span class="filter-label">${icon("filter")} 筛选</span>
          <select class="input input-sm" id="grade-subject-filter" aria-label="选择学科">
            <option value="all">全部学科</option>
            ${(analytics.available_subjects || [])
              .map(
                (subject) =>
                  `<option value="${escapeHTML(subject)}" ${
                    state.subject === subject ? "selected" : ""
                  }>${escapeHTML(subject)}</option>`
              )
              .join("")}
          </select>
        </div>
        <div class="segmented-control" role="group" aria-label="时间范围">
          ${RANGES.map(
            (range) =>
              `<button type="button" class="segment ${state.range === range.value ? "is-active" : ""}" data-range="${
                range.value
              }">${range.label}</button>`
          ).join("")}
        </div>
        <span class="filter-summary">${records.length} 条记录${
          analytics.data_range?.first ? ` · 数据范围 ${formatDate(analytics.data_range.first)} 起` : ""
        }</span>
      </div>

      ${
        !hasRecords
          ? `<div class="analytics-empty-banner">
              ${emptyState({
                iconName: "chart-no-axes-column-increasing",
                title: "从第一条成绩开始",
                description: "录入考试分数后，这里会自动生成折线图、学科对比和总分变化。",
                action: `<button type="button" class="btn btn-primary btn-sm" data-add-grade>${icon("plus")} 录入成绩</button>`,
              })}
            </div>`
          : ""
      }

      <section class="kpi-grid">
        ${kpiCard({
          label: "平均得分率",
          value: kpis.average_percentage === null ? "—" : `${kpis.average_percentage}`,
          suffix: kpis.average_percentage === null ? "" : "%",
          foot: `<span>共 ${kpis.exam_count} 条记录 · ${kpis.subject_count} 个学科</span>`,
          iconName: "gauge",
          tone: "blue",
        })}
        ${kpiCard({
          label: "最近一次得分率",
          value: kpis.latest_percentage === null ? "—" : `${kpis.latest_percentage}`,
          suffix: kpis.latest_percentage === null ? "" : "%",
          foot: deltaMarkup(kpis.change_from_previous),
          iconName: "activity",
          tone: "violet",
        })}
        ${kpiCard({
          label: "当前优势学科",
          value: best ? best.subject : "—",
          suffix: best ? `${best.average}%` : "",
          foot: best ? `<span>基于范围内平均值</span>` : `<span>录入更多成绩后显示</span>`,
          iconName: "trophy",
          tone: "teal",
        })}
        ${kpiCard({
          label: "需要关注",
          value: kpis.weakest_subject ? kpis.weakest_subject.subject : "—",
          suffix: kpis.weakest_subject ? `${kpis.weakest_subject.average}%` : "",
          foot: kpis.weakest_subject
            ? "<span>仅表示当前数据中的相对位置，不是能力评价</span>"
            : "<span>暂无足够数据</span>",
          iconName: "target",
          tone: "amber",
        })}
      </section>

      <div class="analytics-main-grid">
        ${chartShell({
          id: "chart-subjects-line",
          title: `${icon("chart-line")} 各科成绩趋势`,
          subtitle: "纵轴为得分率，已将不同满分统一折算为百分比。",
          empty: emptyChart,
        })}
        ${chartShell({
          id: "chart-overall-line",
          title: `${icon("activity")} 总成绩变化`,
          subtitle: "同一天的多科考试合并计算总得分率。",
          empty: emptyChart,
          emptyText: "至少录入一条成绩记录后显示",
        })}
      </div>

      <div class="analytics-bottom-grid">
        ${chartShell({
          id: "chart-subjects-bar",
          title: `${icon("chart-no-axes-column")} 学科平均得分率对比`,
          subtitle: "用于观察相对位置，样本较少时请谨慎解读。",
          empty: emptyChart,
        })}
        <section class="card analytics-notes-card">
          <div class="card-header">
            <div><h2 class="card-title">${icon("book-open-check")} 如何读这张表</h2><p class="card-subtitle">不把简单趋势当成确定性结论。</p></div>
          </div>
          <ul class="insight-list">
            <li><span>1</span><p>得分率把不同满分折算到同一尺度，适合跨考试比较；原始分数仍可在表格中查看。</p></li>
            <li><span>2</span><p>试卷难度、考试范围和状态都会影响分数，趋势只能描述已记录的数据。</p></li>
            <li><span>3</span><p>AI 分析只提供观察角度，不预测下一次考试，也不替代老师反馈。</p></li>
          </ul>
          <div class="note-pill">${aiModeBadge(getMeta()?.ai, { small: true })} <span>AI 分析会明确标注结果来源</span></div>
        </section>
      </div>

      <section class="card grade-table-card">
        <div class="card-header">
          <div>
            <h2 class="card-title">${icon("table-2")} 成绩记录</h2>
            <p class="card-subtitle">最新考试在前，支持编辑和删除。</p>
          </div>
          <button type="button" class="btn btn-secondary btn-sm" data-add-grade>${icon("plus")} 新增记录</button>
        </div>
        ${
          hasRecords
            ? `<div class="table-scroll">
                <table class="data-table">
                  <thead><tr><th>学科</th><th>考试</th><th>日期</th><th>分数</th><th>得分率</th><th>水平</th><th class="table-actions-col">操作</th></tr></thead>
                  <tbody>
                    ${records
                      .map(
                        (record) => `<tr>
                          <td>${subjectBadge(record.subject, { small: true })}</td>
                          <td><strong>${escapeHTML(record.exam_name)}</strong>${
                            record.notes ? `<span class="table-note">${escapeHTML(record.notes)}</span>` : ""
                          }</td>
                          <td class="nowrap">${formatDate(record.exam_date, { withYear: true })}</td>
                          <td><strong>${record.score}</strong><span class="muted-inline"> / ${record.max_score}</span></td>
                          <td><span class="score-pill">${record.percentage}%</span></td>
                          <td><span class="level-tag">${escapeHTML(record.level)}</span></td>
                          <td class="table-actions-col">
                            <button type="button" class="icon-button" data-grade-action="edit" data-grade-id="${record.id}" title="编辑成绩" aria-label="编辑成绩">${icon("pencil")}</button>
                            <button type="button" class="icon-button danger" data-grade-action="delete" data-grade-id="${record.id}" title="删除成绩" aria-label="删除成绩">${icon("trash-2")}</button>
                          </td>
                        </tr>`
                      )
                      .join("")}
                  </tbody>
                </table>
              </div>`
            : `<div class="card-empty">${emptyState({
                iconName: "clipboard-list",
                title: "还没有成绩记录",
                description: "记录最近一次考试，建立你的第一组数据。",
              })}</div>`
        }
      </section>

      <section class="card ai-analysis-card" id="ai-analysis-panel">
        <div class="card-header">
          <div>
            <h2 class="card-title">${icon("sparkles")} AI 成绩分析</h2>
            <p class="card-subtitle">结合当前筛选范围，梳理变化、优势与可执行的下一步。</p>
          </div>
          <button type="button" class="btn btn-primary btn-sm" data-ai-grades ${hasRecords ? "" : "disabled"}>
            ${icon("wand-sparkles")}<span>生成分析</span>
          </button>
        </div>
        <div class="ai-analysis-body" data-ai-body>
          ${
            state.aiResult
              ? renderAIAnalysisMarkup(state.aiResult, state.aiInfo)
              : `<div class="ai-placeholder">
                  <span>${icon("bot")}</span>
                  <div><strong>等待你的数据</strong><p>点击 AI 分析后，这里会显示基于当前记录的观察与建议。所有结论均需结合老师讲解与原始试卷核对。</p></div>
                </div>`
          }
        </div>
      </section>
    </div>
  `;
  refreshIcons(container);
  bindEvents(container);
  requestAnimationFrame(() => drawCharts(analytics));
}

function drawCharts(analytics) {
  if (!window.Chart || !analytics) return;
  configureCharts();
  // Import-time direct call is intentionally avoided; these canvases are new.
  const chartsToCreate = [];
  const subjectCanvas = document.getElementById("chart-subjects-line");
  const overallCanvas = document.getElementById("chart-overall-line");
  const barCanvas = document.getElementById("chart-subjects-bar");
  try {
    if (subjectCanvas && analytics.chart_records?.length) {
      const allDates = [...new Set(analytics.chart_records.map((item) => item.exam_date))].sort();
      const datasets = (analytics.subject_series || []).map((series) => {
        const byDate = new Map();
        series.points.forEach((point) => byDate.set(point.date, point.percentage));
        return {
          label: series.subject,
          data: allDates.map((date) => byDate.get(date) ?? null),
          borderColor: series.color,
          backgroundColor: hexToRgba(series.color, 0.1),
          pointBackgroundColor: series.color,
          pointBorderColor: "#ffffff",
          pointBorderWidth: 2,
          borderWidth: 2.2,
          spanGaps: true,
          tension: 0.3,
          fill: false,
        };
      });
      chartsToCreate.push(
        createChart(subjectCanvas, {
          type: "line",
          data: {
            labels: allDates.map((date) => formatDate(date)),
            datasets,
          },
          options: lineOptions({ showLegend: true }),
        })
      );
    }
    if (overallCanvas && analytics.overall_series?.length) {
      chartsToCreate.push(
        createChart(overallCanvas, {
          type: "line",
          data: {
            labels: analytics.overall_series.map((item) => formatDate(item.date)),
            datasets: [
              {
                label: "合并得分率",
                data: analytics.overall_series.map((item) => item.percentage),
                borderColor: "#2563eb",
                backgroundColor: "rgba(37, 99, 235, 0.12)",
                fill: true,
                borderWidth: 2.5,
                pointBackgroundColor: "#2563eb",
                pointBorderColor: "#ffffff",
                pointBorderWidth: 2,
                tension: 0.32,
              },
            ],
          },
          options: lineOptions({ showLegend: false }),
        })
      );
    }
    if (barCanvas && analytics.subject_comparison?.length) {
      chartsToCreate.push(
        createChart(barCanvas, {
          type: "bar",
          data: {
            labels: analytics.subject_comparison.map((item) => item.subject),
            datasets: [
              {
                label: "平均得分率",
                data: analytics.subject_comparison.map((item) => item.average),
                backgroundColor: analytics.subject_comparison.map((item) => hexToRgba(item.color, 0.72)),
                borderColor: analytics.subject_comparison.map((item) => item.color),
                borderWidth: 1,
                borderRadius: 6,
                maxBarThickness: 42,
              },
            ],
          },
          options: barOptions(),
        })
      );
    }
  } catch (error) {
    console.error("Chart rendering failed", error);
  }
  charts = chartsToCreate.filter(Boolean);
}

function bindEvents(container) {
  container.querySelectorAll("[data-add-grade]").forEach((button) => {
    button.addEventListener("click", () => openGradeModal());
  });
  container.querySelectorAll("[data-ai-grades]").forEach((button) => {
    button.addEventListener("click", () => requestAIAnalysis(container, button));
  });
  container.querySelector("#grade-subject-filter")?.addEventListener("change", (event) => {
    state.subject = event.target.value;
    state.aiResult = null;
    state.aiInfo = null;
    refreshCurrent({ preserveScroll: true });
  });
  container.querySelectorAll("[data-range]").forEach((button) => {
    button.addEventListener("click", () => {
      if (button.dataset.range === state.range) return;
      state.range = button.dataset.range;
      state.aiResult = null;
      state.aiInfo = null;
      refreshCurrent({ preserveScroll: true });
    });
  });
  container.querySelectorAll("[data-grade-action]").forEach((button) => {
    button.addEventListener("click", () => {
      const record = (state.analytics?.records || []).find(
        (item) => String(item.id) === button.dataset.gradeId
      );
      if (!record) return;
      if (button.dataset.gradeAction === "edit") openGradeModal(record);
      if (button.dataset.gradeAction === "delete") deleteGrade(record);
    });
  });
}

function gradeFormBody(record) {
  const subjects = [...new Set([...getSubjects(), record?.subject].filter(Boolean))];
  return `<form class="form-stack" id="grade-form">
    <div class="form-grid">
      <label class="field">
        <span class="field-label">学科 *</span>
        <input class="input" name="subject" list="grade-subject-list" maxlength="30" required value="${escapeHTML(
          record?.subject || ""
        )}" placeholder="例如：数学" data-autofocus>
        <datalist id="grade-subject-list">${subjects
          .map((subject) => `<option value="${escapeHTML(subject)}"></option>`)
          .join("")}</datalist>
      </label>
      <label class="field">
        <span class="field-label">考试名称 *</span>
        <input class="input" name="exam_name" maxlength="120" required value="${escapeHTML(
          record?.exam_name || ""
        )}" placeholder="例如：期中考试">
      </label>
      <label class="field">
        <span class="field-label">考试日期 *</span>
        <input class="input" type="date" name="exam_date" required value="${escapeHTML(
          record?.exam_date || todayISO()
        )}">
      </label>
      <div class="form-grid form-grid-2">
        <label class="field">
          <span class="field-label">得分 *</span>
          <input class="input" type="number" name="score" min="0" step="0.1" required value="${
            record?.score ?? ""
          }" placeholder="例如：86">
        </label>
        <label class="field">
          <span class="field-label">满分 *</span>
          <input class="input" type="number" name="max_score" min="0.1" step="0.1" required value="${
            record?.max_score ?? 100
          }">
        </label>
      </div>
      <label class="field field-span-2">
        <span class="field-label">备注</span>
        <textarea class="input textarea" name="notes" rows="2" maxlength="2000" placeholder="失分主要在哪里？考试范围是什么？">${escapeHTML(
          record?.notes || ""
        )}</textarea>
      </label>
    </div>
    <p class="form-error" id="grade-form-error" role="alert" hidden></p>
  </form>`;
}

function openGradeModal(record = null) {
  const body = document.createElement("div");
  body.innerHTML = gradeFormBody(record);
  const footer = document.createElement("div");
  footer.className = "modal-actions";
  footer.innerHTML = `<button type="button" class="btn btn-secondary" data-modal-cancel>取消</button>
    <button type="submit" form="grade-form" class="btn btn-primary" data-submit>${icon("save")}<span>${
      record ? "保存修改" : "保存成绩"
    }</span></button>`;
  openModal({
    title: record ? "编辑成绩记录" : "录入成绩",
    subtitle: "分数会自动折算为得分率。AI 不会修改你录入的数据。",
    body,
    footer,
    onMount: ({ close }) => {
      const form = body.querySelector("#grade-form");
      const errorEl = body.querySelector("#grade-form-error");
      const submit = footer.querySelector("[data-submit]");
      footer.querySelector("[data-modal-cancel]").addEventListener("click", close);
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const formData = new FormData(form);
        const score = Number(formData.get("score"));
        const maxScore = Number(formData.get("max_score"));
        if (score > maxScore) {
          errorEl.textContent = "得分不能大于满分";
          errorEl.hidden = false;
          return;
        }
        const payload = {
          subject: String(formData.get("subject") || "").trim(),
          exam_name: String(formData.get("exam_name") || "").trim(),
          exam_date: String(formData.get("exam_date") || ""),
          score,
          max_score: maxScore,
          notes: String(formData.get("notes") || "").trim(),
        };
        submit.disabled = true;
        submit.innerHTML = `<span class="spinner"></span><span>保存中…</span>`;
        try {
          const response = record
            ? await api.put(`/grades/${record.id}`, payload)
            : await api.post("/grades", payload);
          close();
          showToast(response.message || "成绩已保存");
          state.aiResult = null;
          state.aiInfo = null;
          refreshCurrent({ preserveScroll: true });
        } catch (error) {
          errorEl.textContent = error.message || "保存失败";
          errorEl.hidden = false;
          submit.disabled = false;
          submit.innerHTML = `${icon("save")}<span>${record ? "保存修改" : "保存成绩"}</span>`;
          refreshIcons(submit);
        }
      });
    },
  });
}

async function deleteGrade(record) {
  const confirmed = await openConfirm({
    title: "删除成绩记录",
    message: `确定删除「${record.subject} · ${record.exam_name}」吗？`,
    details: "删除后图表和统计会立即更新，此操作无法撤销。",
    confirmText: "删除记录",
    danger: true,
  });
  if (!confirmed) return;
  try {
    await api.delete(`/grades/${record.id}`);
    showToast("成绩记录已删除");
    state.aiResult = null;
    refreshCurrent({ preserveScroll: true });
  } catch (error) {
    toastError(error);
  }
}

async function requestAIAnalysis(container, triggerButton) {
  if (!state.analytics?.records?.length) {
    showToast("先录入至少一条成绩记录，再进行 AI 分析。", "info");
    return;
  }
  const panel = container.querySelector("#ai-analysis-panel");
  const body = panel?.querySelector("[data-ai-body]");
  if (!body) return;
  analysisRequest?.abort();
  analysisRequest = new AbortController();
  const original = triggerButton.innerHTML;
  triggerButton.disabled = true;
  triggerButton.innerHTML = `<span class="spinner"></span><span>分析中…</span>`;
  body.innerHTML = `<div class="ai-loading"><span class="spinner spinner-lg"></span><p>正在整理成绩区间与趋势数据…</p></div>`;
  try {
    const response = await api.post(
      "/ai/grades/analyze",
      { subject: state.subject, range: state.range },
      { signal: analysisRequest.signal }
    );
    state.aiResult = response.data;
    state.aiInfo = response.ai;
    body.innerHTML = renderAIAnalysisMarkup(response.data, response.ai);
    refreshIcons(body);
    panel.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    if (error.name !== "AbortError") {
      body.innerHTML = `<div class="inline-error">${icon("alert-circle")}<span>${escapeHTML(
        error.message || "AI 分析失败，请稍后重试"
      )}</span></div>`;
      refreshIcons(body);
    }
  } finally {
    triggerButton.disabled = false;
    triggerButton.innerHTML = original;
    refreshIcons(triggerButton);
  }
}

function renderAIAnalysisMarkup(data, ai) {
  const strengths = data.strengths || [];
  const weaknesses = data.weaknesses || [];
  const suggestions = data.suggestions || [];
  return `${aiBanner(ai)}
    <p class="ai-summary-text">${escapeHTML(data.summary || "")}</p>
    <div class="ai-trend-block">
      <span class="ai-trend-label">趋势观察</span>
      <strong>${escapeHTML(data.trend?.direction || "暂时无法判断")}</strong>
      <p>${escapeHTML(data.trend?.explanation || "")}</p>
      <p class="muted-note">${escapeHTML(data.trend?.limitations || "")}</p>
    </div>
    <div class="ai-insight-columns">
      <div class="ai-insight-block">
        <h4>${icon("trending-up")} 有数据支撑的优势</h4>
        ${
          strengths.length
            ? strengths
                .map(
                  (item) => `<div class="ai-insight-item"><strong>${escapeHTML(item.subject || "—")}</strong><p>${escapeHTML(
                    item.evidence || item.observation
                  )}</p></div>`
                )
                .join("")
            : '<p class="muted-note">当前数据不足以判断优势学科。</p>'
        }
      </div>
      <div class="ai-insight-block">
        <h4>${icon("target")} 值得关注的方面</h4>
        ${
          weaknesses.length
            ? weaknesses
                .map(
                  (item) => `<div class="ai-insight-item"><strong>${escapeHTML(item.subject || "—")}</strong><p>${escapeHTML(
                    item.evidence || item.observation
                  )}</p></div>`
                )
                .join("")
            : '<p class="muted-note">当前没有明显需要单独标记的学科。</p>'
        }
      </div>
    </div>
    <div class="ai-suggestion-block">
      <h4>${icon("lightbulb")} 可执行的下一步</h4>
      ${
        suggestions.length
          ? `<ul>${suggestions
              .map(
                (item) => `<li><span class="priority-tag priority-${escapeHTML(
                  item.priority || "中"
                )}">${escapeHTML(item.priority || "中")}</span><div><strong>${escapeHTML(
                  item.title
                )}</strong><p>${escapeHTML(item.detail)}</p></div></li>`
              )
              .join("")}</ul>`
          : '<p class="muted-note">暂无建议。</p>'
      }
    </div>
    <p class="ai-disclaimer-line">${icon("shield-check")} ${escapeHTML(
      data.disclaimer || "本分析仅基于有限成绩记录，仅供参考，不构成预测。"
    )}${data.warnings?.length ? ` ${escapeHTML(data.warnings[0])}` : ""}</p>
  `;
}

async function render(container) {
  controller?.abort();
  analysisRequest?.abort();
  controller = new AbortController();
  destroyCharts(charts);
  charts = [];
  try {
    const response = await api.get(
      "/grades/analytics",
      { subject: state.subject, range: state.range },
      { signal: controller.signal }
    );
    state.analytics = response.data;
    if (
      state.subject !== "all" &&
      !(response.data.available_subjects || []).includes(state.subject)
    ) {
      state.subject = "all";
    }
    buildPage(container, response.data);
  } catch (error) {
    if (error.name === "AbortError") return;
    throw error;
  }
}

function cleanup() {
  controller?.abort();
  analysisRequest?.abort();
  controller = null;
  analysisRequest = null;
  destroyCharts(charts);
  charts = [];
}

export default {
  title: "成绩分析",
  render,
  cleanup,
};
