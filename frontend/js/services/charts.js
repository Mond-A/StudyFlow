/** Chart.js setup shared by the analytics dashboard. */

const CHART_FONT =
  '"Segoe UI Variable Text", "Segoe UI", -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif';

export const CHART_COLORS = [
  "#3b82f6",
  "#0d9488",
  "#d97706",
  "#8b5cf6",
  "#e11d48",
  "#0891b2",
  "#65a30d",
  "#ea580c",
  "#6366f1",
  "#64748b",
];

function cssColor(name, fallback) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

function chartGridColor() {
  return document.documentElement.dataset.theme === "dark"
    ? "rgba(173, 173, 173, 0.16)"
    : "rgba(97, 97, 97, 0.14)";
}

export function chartsAvailable() {
  return Boolean(window.Chart && typeof window.Chart === "function");
}

export function configureCharts() {
  if (!chartsAvailable()) return;
  const Chart = window.Chart;
  const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  Chart.defaults.font.family = cssColor("--sf-font-family-base", CHART_FONT);
  Chart.defaults.font.size = 12;
  Chart.defaults.color = cssColor("--sf-color-text-3", "#616161");
  Chart.defaults.borderColor = chartGridColor();
  Chart.defaults.animation = reduceMotion ? false : { duration: 320, easing: "easeOutQuart" };
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.boxWidth = 8;
  Chart.defaults.plugins.legend.labels.padding = 16;
  Chart.defaults.plugins.tooltip.backgroundColor = cssColor("--sf-color-text", "#242424");
  Chart.defaults.plugins.tooltip.titleColor = cssColor("--sf-color-surface", "#ffffff");
  Chart.defaults.plugins.tooltip.bodyColor = cssColor("--sf-color-surface", "#ffffff");
  Chart.defaults.plugins.tooltip.padding = 12;
  Chart.defaults.plugins.tooltip.cornerRadius = 8;
  Chart.defaults.plugins.tooltip.titleFont = { weight: "600", size: 12 };
  Chart.defaults.plugins.tooltip.bodyFont = { size: 12 };
  Chart.defaults.elements.line.tension = 0.32;
  Chart.defaults.elements.point.radius = 2.5;
  Chart.defaults.elements.point.hoverRadius = 4;
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
        grid: { color: chartGridColor() },
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
    grid: { color: chartGridColor() },
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
