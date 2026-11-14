/** Chart.js setup shared by the analytics dashboard. */

const CHART_FONT =
  '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif';

let defaultsApplied = false;

export const CHART_COLORS = [
  "#2563eb",
  "#0f766e",
  "#a16207",
  "#6d4bd8",
  "#be185d",
  "#0e7490",
  "#4d7c0f",
  "#c2410c",
  "#4f46e5",
  "#5d6775",
];

export function chartsAvailable() {
  return Boolean(window.Chart && typeof window.Chart === "function");
}

export function configureCharts() {
  if (!chartsAvailable() || defaultsApplied) return;
  const Chart = window.Chart;
  const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  Chart.defaults.font.family = CHART_FONT;
  Chart.defaults.font.size = 12;
  Chart.defaults.color = "#5d6775";
  Chart.defaults.borderColor = "rgba(104, 116, 131, 0.18)";
  Chart.defaults.animation = reduceMotion ? false : { duration: 320, easing: "easeOutQuart" };
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.boxWidth = 8;
  Chart.defaults.plugins.legend.labels.padding = 16;
  Chart.defaults.plugins.tooltip.backgroundColor = "#0f172a";
  Chart.defaults.plugins.tooltip.padding = 12;
  Chart.defaults.plugins.tooltip.cornerRadius = 8;
  Chart.defaults.plugins.tooltip.titleFont = { weight: "600", size: 12 };
  Chart.defaults.plugins.tooltip.bodyFont = { size: 12 };
  Chart.defaults.elements.line.tension = 0.32;
  Chart.defaults.elements.point.radius = 2.5;
  Chart.defaults.elements.point.hoverRadius = 4;
  defaultsApplied = true;
}

export function createChart(canvas, config) {
  if (!canvas || !chartsAvailable()) return null;
  const existing = window.Chart.getChart(canvas);
  if (existing) existing.destroy();
  const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const resolved = reduceMotion
    ? { ...config, options: { ...(config.options || {}), animation: false } }
    : config;
  return new window.Chart(canvas, resolved);
}

export function destroyCharts(charts) {
  (charts || []).forEach((chart) => {
    try {
      if (chart && typeof chart.destroy === "function") chart.destroy();
    } catch {
      // already destroyed
    }
  });
}

export function lineOptions({ yTitle = "得分率 (%)", showLegend = true, suggestedMax = 100 } = {}) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { display: showLegend, position: "top", align: "end" },
      tooltip: {
        callbacks: {
          label(context) {
            return `${context.dataset.label || ""}: ${context.formattedValue}%`;
          },
        },
      },
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { maxRotation: 0, autoSkipPadding: 18 },
      },
      y: {
        beginAtZero: false,
        suggestedMin: 40,
        suggestedMax,
        grid: { color: "rgba(148, 163, 184, 0.16)" },
        ticks: {
          callback(value) {
            return `${value}${yTitle.includes("%") ? "%" : ""}`;
          },
        },
      },
    },
  };
}

export function barOptions({ horizontal = false } = {}) {
  const valueScale = {
    beginAtZero: true,
    max: 100,
    grid: { color: "rgba(148, 163, 184, 0.16)" },
    ticks: { callback: (value) => `${value}%` },
  };
  return {
    responsive: true,
    maintainAspectRatio: false,
    indexAxis: horizontal ? "y" : "x",
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label(context) {
            return `平均得分率：${context.formattedValue}%`;
          },
        },
      },
    },
    scales: horizontal
      ? { x: valueScale, y: { grid: { display: false } } }
      : { x: { grid: { display: false } }, y: valueScale },
  };
}

export function hexToRgba(hex, alpha = 0.12) {
  if (!/^#[0-9a-f]{6}$/i.test(hex || "")) return `rgba(37, 99, 235, ${alpha})`;
  const value = parseInt(hex.slice(1), 16);
  const r = (value >> 16) & 255;
  const g = (value >> 8) & 255;
  const b = value & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
