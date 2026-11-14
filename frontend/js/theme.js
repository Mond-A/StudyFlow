/** Global light/dark preference bridge for the Fluent app shell. */

const THEME_KEY = "studyflow.settings.theme";
const FOLLOW_SYSTEM_KEY = "studyflow.settings.follow-system";
let media = null;
let listening = false;

function systemTheme() {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyTheme(mode) {
  const dark = mode === "dark";
  if (dark) document.documentElement.dataset.theme = "dark";
  else document.documentElement.removeAttribute("data-theme");
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.content = dark ? "#202020" : "#f3f2f1";
}

function resolveSavedTheme() {
  let follow = true;
  let stored = null;
  try {
    const followRaw = localStorage.getItem(FOLLOW_SYSTEM_KEY);
    follow = followRaw === null ? true : followRaw !== "false";
    stored = localStorage.getItem(THEME_KEY);
  } catch (_) {}
  if (follow) return systemTheme();
  return stored === "dark" ? "dark" : "light";
}

function syncSystemTheme() {
  let follow = true;
  try {
    const followRaw = localStorage.getItem(FOLLOW_SYSTEM_KEY);
    follow = followRaw === null ? true : followRaw !== "false";
  } catch (_) {}
  if (follow) applyTheme(systemTheme());
}

export function initGlobalTheme() {
  applyTheme(resolveSavedTheme());
  if (!media) media = window.matchMedia?.("(prefers-color-scheme: dark)");
  if (media && !listening) {
    listening = true;
    media.addEventListener?.("change", syncSystemTheme);
  }
}

export function getGlobalTheme() {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}
