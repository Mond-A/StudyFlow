/**
 * Local-first guest storage.
 *
 * Guest business data lives only in IndexedDB. This module is an API-shaped
 * adapter used by api.js while window.__STUDYFLOW_GUEST__ is true; it never
 * calls a server endpoint for guest data.
 */

const DB_NAME = "studyflow-guest";
const DB_VERSION = 1;
const STORE_NAMES = ["meta", "tasks", "grades", "notes", "sessions", "flashcards", "errors", "uploads"];
const GUEST_PROFILE_KEY = "profile";
const GUEST_DEVICE_KEY = "studyflow.guest.device";
const SUBJECTS = ["语文", "数学", "英语", "物理", "化学", "生物", "政治", "历史", "地理", "综合"];
const ACHIEVEMENTS = [
  ["first_task", "第一步", "完成第一个学习任务", "check"],
  ["focus_25", "专注起步", "累计专注 25 分钟", "timer"],
  ["focus_300", "专注积累", "累计专注 300 分钟", "timer"],
  ["notes_3", "笔记新芽", "创建 3 篇笔记", "notebook-pen"],
  ["grades_3", "记录成长", "记录 3 次成绩", "chart-line"],
  ["cards_5", "复习卡片", "创建 5 张闪卡", "layers"],
];

let dbPromise = null;

export class GuestError extends Error {
  constructor(message, code = "GUEST_ERROR", status = 400) {
    super(message);
    this.name = "GuestError";
    this.code = code;
    this.status = status;
  }
}

function uid() {
  if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
  return `guest-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function nowIso() {
  return new Date().toISOString();
}

function todayIso() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function dayLabel(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : `${date.getMonth() + 1}月${date.getDate()}日`;
}

function openDb() {
  if (dbPromise) return dbPromise;
  dbPromise = new Promise((resolve, reject) => {
    if (!window.indexedDB) {
      reject(new GuestError("当前浏览器不支持本地访客存储", "IDB_UNAVAILABLE", 0));
      return;
    }
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains("meta")) db.createObjectStore("meta", { keyPath: "key" });
      for (const name of ["tasks", "grades", "notes", "sessions", "flashcards", "errors", "uploads"]) {
        if (!db.objectStoreNames.contains(name)) {
          const store = db.createObjectStore(name, { keyPath: "id", autoIncrement: true });
          store.createIndex("updated_at", "updated_at", { unique: false });
        }
      }
      // Future versions add stores/indexes here. Existing object stores are
      // never deleted, so an upgrade cannot discard the guest's data.
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(new GuestError("无法打开本地访客存储", "IDB_OPEN_FAILED", 0));
  });
  return dbPromise;
}

function requestResult(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new GuestError("本地存储操作失败", "IDB_FAILED", 0));
  });
}

function transactionDone(transaction) {
  return new Promise((resolve, reject) => {
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error || new Error("IndexedDB transaction failed"));
    transaction.onabort = () => reject(transaction.error || new Error("IndexedDB transaction aborted"));
  });
}

async function rawGet(storeName, key) {
  const db = await openDb();
  const transaction = db.transaction(storeName, "readonly");
  const store = transaction.objectStore(storeName);
  return requestResult(store.get(key));
}

async function rawAll(storeName) {
  const db = await openDb();
  const transaction = db.transaction(storeName, "readonly");
  return requestResult(transaction.objectStore(storeName).getAll());
}

async function rawPut(storeName, value) {
  const db = await openDb();
  const transaction = db.transaction(storeName, "readwrite");
  const store = transaction.objectStore(storeName);
  const result = storeName === "meta" || value.id !== undefined
    ? await requestResult(store.put(value))
    : await requestResult(store.add(value));
  await transactionDone(transaction);
  return result;
}

async function rawDelete(storeName, id) {
  const db = await openDb();
  const transaction = db.transaction(storeName, "readwrite");
  transaction.objectStore(storeName).delete(id);
  await transactionDone(transaction);
}

async function metaGet(key) {
  const row = await rawGet("meta", key);
  return row ? row.value : null;
}

async function metaSet(key, value) {
  await rawPut("meta", { key, value });
}

async function profile() {
  let value = await metaGet(GUEST_PROFILE_KEY);
  if (!value) {
    value = {
      id: 1,
      username: "guest",
      display_name: "访客同学",
      email: null,
      avatar_color: "#0d9488",
      daily_goal_minutes: 120,
      pomodoro_minutes: 25,
      short_break_minutes: 5,
      long_break_minutes: 15,
      timezone: "Asia/Shanghai",
      created_at: nowIso(),
    };
    await metaSet(GUEST_PROFILE_KEY, value);
  }
  return value;
}

function deviceId() {
  try {
    let value = localStorage.getItem(GUEST_DEVICE_KEY);
    if (!value) {
      value = uid();
      localStorage.setItem(GUEST_DEVICE_KEY, value);
    }
    return value;
  } catch {
    return "guest-device";
  }
}

function guestUser() {
  return { ...(profileCache || {}), ...(!profileCache ? { display_name: "访客同学" } : {}) };
}

let profileCache = null;

async function loadProfile() {
  profileCache = await profile();
  return profileCache;
}

function envelope(data, message) {
  const result = { ok: true, data };
  if (message) result.message = message;
  return result;
}

function requireTitle(value, label = "标题") {
  const text = String(value || "").trim();
  if (!text) throw new GuestError(`请输入${label}`, "VALIDATION_ERROR", 400);
  return text;
}

function num(value, fallback = 0) {
  const result = Number(value);
  return Number.isFinite(result) ? result : fallback;
}

function taskSerialize(row) {
  const today = todayIso();
  let days = null;
  let overdue = false;
  if (row.due_date) {
    days = Math.round((new Date(`${row.due_date}T00:00:00`) - new Date(`${today}T00:00:00`)) / 86400000);
    overdue = row.status !== "completed" && days < 0;
  }
  return {
    id: row.id,
    title: row.title,
    subject: row.subject,
    description: row.description || "",
    due_date: row.due_date || null,
    estimated_minutes: row.estimated_minutes || 30,
    actual_minutes: row.actual_minutes || 0,
    difficulty: row.difficulty || 3,
    status: row.status || "pending",
    priority: row.priority || 2,
    planned_date: row.planned_date || null,
    planned_start: row.planned_start || null,
    planned_minutes: row.planned_minutes || null,
    source: row.source || "manual",
    ai_meta: row.ai_meta || null,
    completed_at: row.completed_at || null,
    created_at: row.created_at,
    updated_at: row.updated_at,
    is_overdue: overdue,
    days_until_due: days,
  };
}

function gradeSerialize(row) {
  const percentage = row.max_score ? Math.round((row.score / row.max_score) * 1000) / 10 : 0;
  return {
    id: row.id,
    subject: row.subject,
    exam_name: row.exam_name,
    score: row.score,
    max_score: row.max_score,
    percentage,
    level: percentage >= 90 ? "优秀" : percentage >= 80 ? "良好" : percentage >= 60 ? "及格" : "待提高",
    exam_date: row.exam_date,
    notes: row.notes || "",
    created_at: row.created_at,
    updated_at: row.updated_at,
  };
}

function noteSummary(row) {
  const content = row.content_markdown || "";
  return {
    id: row.id,
    title: row.title,
    subject: row.subject,
    snippet: content.replace(/[#*`]/g, "").trim().slice(0, 140),
    content_length: content.length,
    source_image: row.source_image || null,
    has_audit: Boolean(row.audit_report),
    has_graph: Boolean(row.knowledge_graph),
    created_at: row.created_at,
    updated_at: row.updated_at,
  };
}

function noteSerialize(row) {
  return { ...noteSummary(row), content_markdown: row.content_markdown || "", audit_report: null, knowledge_graph: null };
}

function sessionSerialize(row, taskTitle) {
  return {
    id: row.id,
    task_id: row.task_id || null,
    task_title: taskTitle || null,
    subject: row.subject,
    duration_minutes: row.duration_minutes,
    session_type: row.session_type || "pomodoro",
    started_at: row.started_at,
    ended_at: row.ended_at || null,
    note: row.note || "",
    created_at: row.created_at,
  };
}

function errorSerialize(row) {
  return {
    id: row.id,
    subject: row.subject,
    question: row.question,
    student_answer: row.student_answer || "",
    correct_answer: row.correct_answer || "",
    analysis: row.analysis || "",
    knowledge_points: row.knowledge_points || [],
    mastery: row.mastery || "new",
    source: row.source || "manual",
    created_at: row.created_at,
    updated_at: row.updated_at,
  };
}

function cardSerialize(row) {
  const today = todayIso();
  return {
    id: row.id,
    note_id: row.note_id || null,
    front: row.front,
    back: row.back,
    subject: row.subject,
    mastery_level: row.mastery_level || 0,
    review_count: row.review_count || 0,
    next_review_date: row.next_review_date || null,
    last_reviewed_at: row.last_reviewed_at || null,
    is_due: !row.next_review_date || row.next_review_date <= today,
    created_at: row.created_at,
    updated_at: row.updated_at,
  };
}

async function tasks() {
  return (await rawAll("tasks")).sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at)));
}

async function taskCounts() {
  const rows = await tasks();
  const today = todayIso();
  return {
    total: rows.length,
    pending: rows.filter((r) => r.status === "pending").length,
    in_progress: rows.filter((r) => r.status === "in_progress").length,
    completed: rows.filter((r) => r.status === "completed").length,
    overdue: rows.filter((r) => r.status !== "completed" && r.due_date && r.due_date < today).length,
    due_today: rows.filter((r) => r.status !== "completed" && r.due_date === today).length,
    open_estimated_minutes: rows.filter((r) => r.status !== "completed").reduce((sum, r) => sum + (r.estimated_minutes || 0), 0),
  };
}

async function listTasks(query = {}) {
  const status = query.status || "all";
  const subject = query.subject || "all";
  const search = String(query.q || "").toLowerCase();
  let rows = await tasks();
  if (status === "open") rows = rows.filter((r) => r.status !== "completed");
  else if (status !== "all" && status !== "history") rows = rows.filter((r) => r.status === status);
  else if (status === "history") rows = rows.filter((r) => r.status === "completed");
  if (subject !== "all") rows = rows.filter((r) => r.subject === subject);
  if (search) rows = rows.filter((r) => `${r.title} ${r.description}`.toLowerCase().includes(search));
  return envelope({
    tasks: rows.slice(0, Math.min(Number(query.limit) || 100, 300)).map(taskSerialize),
    counts: await taskCounts(),
    filters: { status, subject, q: query.q || "" },
  });
}

async function createTask(body) {
  const now = nowIso();
  const row = {
    title: requireTitle(body.title, "任务标题"),
    subject: String(body.subject || "综合").trim() || "综合",
    description: String(body.description || "").trim(),
    due_date: body.due_date || null,
    estimated_minutes: num(body.estimated_minutes, 30),
    difficulty: num(body.difficulty, 3),
    priority: num(body.priority, 2),
    status: "pending",
    actual_minutes: 0,
    planned_date: body.planned_date || null,
    planned_start: body.planned_start || null,
    planned_minutes: body.planned_minutes || null,
    source: "manual",
    ai_meta: body.ai_meta || null,
    completed_at: null,
    created_at: now,
    updated_at: now,
    local_uid: uid(),
  };
  row.id = await rawPut("tasks", row);
  return envelope(taskSerialize(row), "任务已添加");
}

async function findTask(id) {
  const row = await rawGet("tasks", Number(id));
  if (!row) throw new GuestError("任务不存在或已被删除", "NOT_FOUND", 404);
  return row;
}

async function updateTask(id, body) {
  const row = await findTask(id);
  const allowed = ["title", "subject", "description", "due_date", "estimated_minutes", "difficulty", "priority", "planned_date", "planned_start", "planned_minutes"];
  for (const key of allowed) if (Object.prototype.hasOwnProperty.call(body, key)) row[key] = body[key];
  row.title = requireTitle(row.title, "任务标题");
  row.updated_at = nowIso();
  await rawPut("tasks", row);
  return envelope(taskSerialize(row), "任务已更新");
}

async function mutateTask(id, status, actual = null) {
  const row = await findTask(id);
  row.status = status;
  if (status === "completed") {
    row.actual_minutes = actual === null ? row.actual_minutes || 0 : Math.max(0, Number(actual) || 0);
    row.completed_at = nowIso();
  } else if (status === "pending") {
    row.completed_at = null;
  }
  row.updated_at = nowIso();
  await rawPut("tasks", row);
  return envelope(taskSerialize(row));
}

async function listGrades() {
  return (await rawAll("grades")).sort((a, b) => String(a.exam_date).localeCompare(String(b.exam_date)));
}

function analyticsFor(rows, subject = "all", range = "90") {
  const all = rows.map(gradeSerialize);
  const filtered = all.filter((r) => (subject === "all" || r.subject === subject));
  const bySubject = new Map();
  for (const item of filtered) {
    if (!bySubject.has(item.subject)) bySubject.set(item.subject, []);
    bySubject.get(item.subject).push(item);
  }
  const colors = ["#2563eb", "#0d9488", "#d97706", "#7c3aed", "#db2777", "#0891b2"];
  const subjectSeries = [];
  const subjectComparison = [];
  [...bySubject.entries()].sort().forEach(([name, items], index) => {
    const average = Math.round(items.reduce((s, i) => s + i.percentage, 0) / items.length * 10) / 10;
    subjectSeries.push({ subject: name, color: colors[index % colors.length], points: items.map((i) => ({ date: i.exam_date, percentage: i.percentage, score: i.score, max_score: i.max_score, exam_name: i.exam_name, grade_id: i.id })), average, latest: items[items.length - 1].percentage, delta: items.length > 1 ? Math.round((items[items.length - 1].percentage - items[items.length - 2].percentage) * 10) / 10 : 0, count: items.length });
    subjectComparison.push({ subject: name, average, latest: items[items.length - 1].percentage, delta: 0, count: items.length, color: colors[index % colors.length] });
  });
  subjectComparison.sort((a, b) => b.average - a.average).forEach((item, index) => { item.rank = index + 1; });
  const byDate = new Map();
  for (const item of filtered) {
    if (!byDate.has(item.exam_date)) byDate.set(item.exam_date, []);
    byDate.get(item.exam_date).push(item);
  }
  const overall = [...byDate.entries()].sort().map(([date, items]) => ({ date, percentage: Math.round(items.reduce((s, i) => s + i.score, 0) / Math.max(1, items.reduce((s, i) => s + i.max_score, 0)) * 1000) / 10, exam_count: items.length, subjects: items.map((i) => i.subject) }));
  const average = filtered.length ? Math.round(filtered.reduce((s, i) => s + i.percentage, 0) / filtered.length * 10) / 10 : null;
  const latest = overall.length ? overall[overall.length - 1].percentage : null;
  return {
    range: range || "90", start_date: null, end_date: todayIso(), subject_filter: subject,
    records: [...filtered].reverse(), chart_records: filtered, subject_series: subjectSeries,
    subject_comparison: subjectComparison, overall_series: overall,
    kpis: { average_percentage: average, latest_percentage: latest, change_from_previous: overall.length > 1 ? Math.round((overall[overall.length - 1].percentage - overall[overall.length - 2].percentage) * 10) / 10 : null, exam_count: filtered.length, subject_count: bySubject.size, best_subject: subjectComparison[0] || null, weakest_subject: subjectComparison[subjectComparison.length - 1] || null },
    available_subjects: [...new Set(all.map((i) => i.subject))].sort(),
    data_range: { first: all.length ? all[0].exam_date : null, last: all.length ? all[all.length - 1].exam_date : null },
    notice: "访客成绩分析基于当前设备中的本地数据。",
  };
}

async function sessionSummary() {
  const rows = await rawAll("sessions");
  const today = todayIso();
  const todayRows = rows.filter((r) => String(r.started_at).slice(0, 10) === today);
  const weekStart = new Date(); weekStart.setDate(weekStart.getDate() - 6); const week = weekStart.toISOString().slice(0, 10);
  const weekRows = rows.filter((r) => String(r.started_at).slice(0, 10) >= week);
  const days = [...new Set(rows.map((r) => String(r.started_at).slice(0, 10)))];
  const bySubject = new Map();
  for (const row of rows) bySubject.set(row.subject, (bySubject.get(row.subject) || 0) + row.duration_minutes);
  const activity = [];
  for (let i = 6; i >= 0; i -= 1) {
    const d = new Date(); d.setDate(d.getDate() - i); const key = d.toISOString().slice(0, 10);
    activity.push({ date: key, minutes: rows.filter((r) => String(r.started_at).slice(0, 10) === key).reduce((s, r) => s + r.duration_minutes, 0) });
  }
  return { today_minutes: todayRows.reduce((s, r) => s + r.duration_minutes, 0), today_sessions: todayRows.length, week_minutes: weekRows.reduce((s, r) => s + r.duration_minutes, 0), week_sessions: weekRows.length, study_days: days.length, total_minutes: rows.reduce((s, r) => s + r.duration_minutes, 0), by_subject: [...bySubject.entries()].map(([subject, minutes]) => ({ subject, minutes, sessions: rows.filter((r) => r.subject === subject).length })), week_activity: activity };
}

async function achievementState() {
  const [taskRows, sessionRows, noteRows, gradeRows, cardRows] = await Promise.all([tasks(), rawAll("sessions"), rawAll("notes"), rawAll("grades"), rawAll("flashcards")]);
  const stats = { tasks_completed: taskRows.filter((r) => r.status === "completed").length, study_minutes: sessionRows.reduce((s, r) => s + r.duration_minutes, 0), study_days: new Set(sessionRows.map((r) => String(r.started_at).slice(0, 10))).size, notes_count: noteRows.length, grades_count: gradeRows.length, flashcards_count: cardRows.length };
  let stored = await metaGet("achievements");
  stored = stored || {};
  return { stats, stored };
}

function achievementData(stats, stored) {
  const unlock = (code, condition) => {
    if (condition && !stored[code]) stored[code] = nowIso();
  };
  unlock("first_task", stats.tasks_completed >= 1);
  unlock("focus_25", stats.study_minutes >= 25);
  unlock("focus_300", stats.study_minutes >= 300);
  unlock("notes_3", stats.notes_count >= 3);
  unlock("grades_3", stats.grades_count >= 3);
  unlock("cards_5", stats.flashcards_count >= 5);
  const items = ACHIEVEMENTS.map(([code, title, description, icon]) => ({ code, title, description, icon, criterion: description, unlocked: Boolean(stored[code]), unlocked_at: stored[code] || null }));
  return { items, unlocked_count: items.filter((i) => i.unlocked).length, total: items.length, stats, summary: stats };
}

async function saveAchievements(stats, stored) {
  await metaSet("achievements", stored);
  return achievementData(stats, stored);
}

async function listNotes(query = {}) {
  let rows = await rawAll("notes");
  if (query.subject && query.subject !== "all") rows = rows.filter((r) => r.subject === query.subject);
  if (query.q) { const q = String(query.q).toLowerCase(); rows = rows.filter((r) => `${r.title} ${r.content_markdown}`.toLowerCase().includes(q)); }
  rows.sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at)));
  return envelope({ notes: rows.map(noteSummary), subjects: [...new Set((await rawAll("notes")).map((r) => r.subject))].sort(), filters: { subject: query.subject || "all", q: query.q || "" } });
}

async function listErrors() {
  const rows = (await rawAll("errors")).sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at)));
  const counts = { total: rows.length, new: rows.filter((r) => r.mastery === "new").length, reviewing: rows.filter((r) => r.mastery === "reviewing").length, mastered: rows.filter((r) => r.mastery === "mastered").length };
  return envelope({ errors: rows.map(errorSerialize), counts, subjects: [...new Set(rows.map((r) => r.subject))].sort(), filters: {} });
}

async function listCards() {
  const rows = (await rawAll("flashcards")).sort((a, b) => String(a.next_review_date || "").localeCompare(String(b.next_review_date || "")));
  return envelope({ flashcards: rows.map(cardSerialize), subjects: [...new Set(rows.map((r) => r.subject))].sort() });
}

async function listSessions(query = {}) {
  let rows = (await rawAll("sessions")).sort((a, b) => String(b.started_at).localeCompare(String(a.started_at)));
  if (query.date) rows = rows.filter((r) => String(r.started_at).slice(0, 10) === query.date);
  if (query.subject && query.subject !== "all") rows = rows.filter((r) => r.subject === query.subject);
  const taskRows = await tasks();
  return envelope({ sessions: rows.slice(0, Number(query.limit) || 100).map((row) => sessionSerialize(row, taskRows.find((t) => t.id === row.task_id)?.title)), summary: await sessionSummary(), filters: { date: query.date || null, subject: query.subject || "all" } });
}

async function dashboard() {
  const [profileValue, taskRows, gradeRows, sessionRows, summary, ach] = await Promise.all([loadProfile(), tasks(), listGrades(), listSessions(), sessionSummary(), achievementState()]);
  const today = todayIso();
  const todayTasks = taskRows.filter((r) => r.planned_date === today || r.due_date === today || (r.status !== "completed" && r.due_date && r.due_date < today));
  const showTasks = todayTasks.length ? todayTasks : taskRows.filter((r) => r.status !== "completed").slice(0, 5);
  const completed = showTasks.filter((r) => r.status === "completed");
  const recentGrades = [];
  const seen = new Set();
  for (const row of [...gradeRows].reverse()) {
    const item = gradeSerialize(row);
    if (seen.has(item.subject)) continue;
    seen.add(item.subject);
    const prior = gradeRows.filter((g) => g.subject === item.subject && g.exam_date < item.exam_date).pop();
    item.delta = prior ? Math.round((item.percentage - gradeSerialize(prior).percentage) * 10) / 10 : null;
    recentGrades.push(item);
    if (recentGrades.length >= 4) break;
  }
  const achievementView = achievementData(ach.stats, ach.stored);
  const stats = {
    today_tasks_total: showTasks.length, today_tasks_completed: completed.length,
    today_completion_rate: showTasks.length ? Math.round(completed.length / showTasks.length * 100) : 0,
    today_focus_minutes: summary.today_minutes, today_sessions: summary.today_sessions,
    daily_goal_minutes: profileValue.daily_goal_minutes, goal_progress: profileValue.daily_goal_minutes ? Math.min(100, Math.round(summary.today_minutes / profileValue.daily_goal_minutes * 100)) : 0,
    week_focus_minutes: summary.week_minutes, week_sessions: summary.week_sessions,
    total_study_minutes: summary.total_minutes, open_tasks: taskRows.filter((r) => r.status !== "completed").length,
    overdue_tasks: taskRows.filter((r) => r.status !== "completed" && r.due_date && r.due_date < today).length,
    due_today: taskRows.filter((r) => r.status !== "completed" && r.due_date === today).length,
    streak_days: summary.study_days, achievements_unlocked: achievementView.unlocked_count,
    achievements_total: achievementView.total, study_days: summary.study_days,
    recent_average: recentGrades.length ? Math.round(recentGrades.reduce((s, i) => s + i.percentage, 0) / recentGrades.length * 10) / 10 : null,
  };
  const now = new Date();
  const weekdays = ["日", "一", "二", "三", "四", "五", "六"];
  return envelope({
    server_time: nowIso(), date: today, date_label: `${now.getMonth() + 1}月${now.getDate()}日`,
    weekday_label: `星期${weekdays[now.getDay()]}`,
    greeting: now.getHours() < 12 ? "早上好" : now.getHours() < 18 ? "下午好" : "晚上好",
    user: profileValue, stats,
    today_tasks: showTasks.map(taskSerialize), recent_grades: recentGrades,
    recent_sessions: (await listSessions({ limit: 5 })).data.sessions,
    achievements: achievementView.items.filter((i) => i.unlocked).slice(0, 4).map(({ code, title, icon, unlocked_at }) => ({ code, title, icon, unlocked_at })),
    week_activity: summary.week_activity, task_counts: await taskCounts(), has_fallback_tasks: !todayTasks.length, today,
  });
}

async function dailyReport(day) {
  const date = day || todayIso();
  const [profileValue, taskRows, sessionRows, gradeRows, noteRows, errorRows, cards, ach] = await Promise.all([loadProfile(), tasks(), rawAll("sessions"), listGrades(), rawAll("notes"), rawAll("errors"), rawAll("flashcards"), achievementState()]);
  const dayTasks = taskRows.filter((r) => r.planned_date === date || r.due_date === date || String(r.completed_at || "").slice(0, 10) === date);
  const daySessions = sessionRows.filter((r) => String(r.started_at).slice(0, 10) === date);
  const completed = dayTasks.filter((r) => r.status === "completed");
  const pending = dayTasks.filter((r) => r.status !== "completed");
  const minutes = daySessions.reduce((s, r) => s + r.duration_minutes, 0);
  const bySubject = new Map();
  for (const row of daySessions) bySubject.set(row.subject, (bySubject.get(row.subject) || 0) + row.duration_minutes);
  const dateValue = new Date(`${date}T12:00:00`);
  const labels = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
  return envelope({
    date, date_label: dayLabel(date), weekday: labels[dateValue.getDay()], is_today: date === todayIso(), generated_at: nowIso(),
    user: { display_name: profileValue.display_name },
    goal: { target_minutes: profileValue.daily_goal_minutes, actual_minutes: minutes, progress: profileValue.daily_goal_minutes ? Math.min(100, Math.round(minutes / profileValue.daily_goal_minutes * 100)) : 0 },
    tasks: { total: dayTasks.length, completed: completed.length, pending: pending.length, completion_rate: dayTasks.length ? Math.round(completed.length / dayTasks.length * 100) : 0, items: dayTasks.map((r) => ({ id: r.id, title: r.title, subject: r.subject, status: r.status, actual_minutes: r.actual_minutes || 0 })), pending_items: pending.map((r) => ({ id: r.id, title: r.title, subject: r.subject, status: r.status })) },
    study: { total_minutes: minutes, sessions: daySessions.map((r) => sessionSerialize(r, taskRows.find((t) => t.id === r.task_id)?.title)), subject_breakdown: [...bySubject.entries()].map(([subject, value]) => ({ subject, minutes: value })) },
    grades: gradeRows.filter((r) => r.exam_date === date).map(gradeSerialize),
    notes: noteRows.filter((r) => String(r.created_at).slice(0, 10) === date).map(noteSummary),
    errors: errorRows.filter((r) => String(r.created_at).slice(0, 10) === date).map(errorSerialize),
    flashcards: { reviewed: cards.filter((r) => String(r.last_reviewed_at || "").slice(0, 10) === date).length },
    achievements: achievementData(ach.stats, ach.stored).items.filter((i) => i.unlocked && String(i.unlocked_at).slice(0, 10) === date),
    narrative: [],
    suggestions: [
      minutes ? "保持今天的学习节奏，睡前用几分钟回顾重点。" : "先完成一个 15 到 25 分钟的小任务，让今天有一个明确的开始。",
      pending.length ? "把未完成任务重新安排到一个具体时间段。" : "明天可以提前安排一个清晰的小目标。",
    ],
  });
}

function guestMeta() {
  return envelope({
    app: { name: "StudyFlow", version: "guest", tagline: "访客本地学习空间" },
    server_time: nowIso(), user: profileCache || { display_name: "访客同学" }, account: null,
    subjects: SUBJECTS,
    ai: { text: { effective_mode: "unavailable", configured: false }, vision: { effective_mode: "unavailable", configured: false } },
    demo: { loaded: false, counts: {}, total_records: 0, seeded_at: null },
    limits: { max_image_mb: 8, supported_image_types: ["JPG", "PNG", "WebP"], notes_max_chars: 200000 },
  });
}

async function guestUpload(body) {
  const form = body;
  const file = form && (form.get("image") || form.get("file"));
  if (!file) throw new GuestError("请选择要上传的图片", "VALIDATION_ERROR", 400);
  if (!/^image\/(jpeg|png|webp)$/.test(file.type)) throw new GuestError("仅支持 JPG、PNG、WebP 图片", "UNSUPPORTED_FILE_TYPE", 415);
  const dataUrl = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new GuestError("图片读取失败", "INVALID_IMAGE", 400));
    reader.readAsDataURL(file);
  });
  const row = { local_uid: uid(), data_url: dataUrl, mime_type: file.type, size_bytes: file.size, original_name: file.name, created_at: nowIso() };
  row.id = await rawPut("uploads", row);
  return envelope({ filename: `guest-upload-${row.id}`, url: dataUrl, mime_type: file.type, size_bytes: file.size, width: 0, height: 0, original_name: file.name }, "图片已保存到当前设备");
}

function parseId(path, pattern) {
  const match = path.match(pattern);
  return match ? Number(match[1]) : null;
}

export async function guestRequest(path, { method = "GET", body = undefined, query = undefined, formData = false } = {}) {
  await loadProfile();
  const cleanPath = path.split("?")[0];
  const q = query || {};
  const verb = method.toUpperCase();

  if (formData || body instanceof FormData) return guestUpload(body);

  if (cleanPath.startsWith("/ai/")) {
    throw new GuestError("访客模式不开放智能工具。请登录正式账户后使用智能功能。", "GUEST_AI_DISABLED", 403);
  }
  if (cleanPath === "/meta") return guestMeta();
  if (cleanPath === "/health") return envelope({ status: "ok" });
  if (cleanPath === "/settings" && verb === "GET") return envelope({ user: profileCache, ai: guestMeta().data.ai, demo: guestMeta().data.demo, subjects: SUBJECTS });
  if (cleanPath === "/settings" && (verb === "PUT" || verb === "PATCH")) {
    const allowed = ["display_name", "email", "avatar_color", "daily_goal_minutes", "pomodoro_minutes", "short_break_minutes", "long_break_minutes"];
    for (const key of allowed) if (body && Object.prototype.hasOwnProperty.call(body, key)) profileCache[key] = body[key];
    profileCache.updated_at = nowIso();
    await metaSet(GUEST_PROFILE_KEY, profileCache);
    return envelope({ user: profileCache }, "设置已保存");
  }
  if (cleanPath === "/dashboard") return dashboard();
  if (cleanPath === "/export") {
    const [taskRows, gradeRows, noteRows, sessionRows, errorRows, cardRows] = await Promise.all([rawAll("tasks"), rawAll("grades"), rawAll("notes"), rawAll("sessions"), rawAll("errors"), rawAll("flashcards")]);
    return { exported_at: nowIso(), user: profileCache, tasks: taskRows.map(taskSerialize), grades: gradeRows.map(gradeSerialize), notes: noteRows.map(noteSerialize), study_sessions: sessionRows, error_records: errorRows.map(errorSerialize), flashcards: cardRows.map(cardSerialize) };
  }
  if (cleanPath === "/demo" || cleanPath === "/demo/load" || cleanPath === "/demo/clear") {
    if (verb === "GET") return envelope({ loaded: false, counts: {}, total_records: 0, seeded_at: null });
    throw new GuestError("访客模式不使用演示数据。", "GUEST_DEMO_DISABLED", 403);
  }

  if (cleanPath === "/tasks") {
    if (verb === "GET") return listTasks(q);
    if (verb === "POST") return createTask(body || {});
  }
  if (cleanPath === "/tasks/history" && verb === "GET") {
    const result = await listTasks({ ...q, status: "history" });
    return envelope({ tasks: result.data.tasks });
  }
  if (cleanPath === "/tasks/plan/preview" && verb === "POST") {
    return planPreview(body || {});
  }
  if (cleanPath === "/tasks/plan/apply" && verb === "POST") {
    return planApply(body || {});
  }
  if (cleanPath.startsWith("/tasks/")) {
    const id = parseId(cleanPath, /^\/tasks\/(\d+)(?:\/(start|complete|reopen))?$/);
    if (id) {
      if (cleanPath.endsWith("/start")) return mutateTask(id, "in_progress");
      if (cleanPath.endsWith("/complete")) return mutateTask(id, "completed", (body || {}).actual_minutes);
      if (cleanPath.endsWith("/reopen")) return mutateTask(id, "pending");
      if (verb === "GET") return envelope(taskSerialize(await findTask(id)));
      if (verb === "PUT" || verb === "PATCH") return updateTask(id, body || {});
      if (verb === "DELETE") { await findTask(id); await rawDelete("tasks", id); return envelope({ deleted_id: id }, "任务已删除"); }
    }
  }

  if (cleanPath === "/grades/analytics" && verb === "GET") return envelope(analyticsFor(await listGrades(), q.subject || "all", q.range || "90"));
  if (cleanPath === "/grades" && verb === "GET") return envelope({ records: (await listGrades()).map(gradeSerialize) });
  if (cleanPath === "/grades" && verb === "POST") {
    const now = nowIso();
    const row = { subject: requireTitle(body?.subject, "学科"), exam_name: requireTitle(body?.exam_name, "考试名称"), score: num(body?.score), max_score: num(body?.max_score, 100), exam_date: body?.exam_date || todayIso(), notes: String(body?.notes || ""), created_at: now, updated_at: now, local_uid: uid() };
    row.id = await rawPut("grades", row);
    return envelope(gradeSerialize(row), "成绩已保存");
  }
  if (cleanPath.startsWith("/grades/")) {
    const id = parseId(cleanPath, /^\/grades\/(\d+)$/);
    if (id) {
      const row = await rawGet("grades", id);
      if (!row) throw new GuestError("成绩记录不存在", "NOT_FOUND", 404);
      if (verb === "PUT" || verb === "PATCH") { Object.assign(row, { ...body, updated_at: nowIso() }); await rawPut("grades", row); return envelope(gradeSerialize(row), "成绩已更新"); }
      if (verb === "DELETE") { await rawDelete("grades", id); return envelope({ deleted_id: id }, "成绩已删除"); }
    }
  }

  if (cleanPath === "/notes" && verb === "GET") return listNotes(q);
  if (cleanPath === "/notes" && verb === "POST") {
    const now = nowIso();
    const row = { title: requireTitle(body?.title, "笔记标题"), subject: String(body?.subject || "综合"), content_markdown: String(body?.content_markdown || ""), source_image: body?.source_image || null, audit_report: null, knowledge_graph: null, created_at: now, updated_at: now, local_uid: uid() };
    row.id = await rawPut("notes", row);
    return envelope(noteSerialize(row), "笔记已保存");
  }
  if (cleanPath.startsWith("/notes/")) {
    const id = parseId(cleanPath, /^\/notes\/(\d+)(?:\/(audit|graph))?$/);
    if (id) {
      const row = await rawGet("notes", id);
      if (!row) throw new GuestError("笔记不存在或已被删除", "NOT_FOUND", 404);
      if (cleanPath.endsWith("/audit") || cleanPath.endsWith("/graph")) throw new GuestError("访客模式不开放智能工具。请登录正式账户后使用智能功能。", "GUEST_AI_DISABLED", 403);
      if (verb === "GET") return envelope(noteSerialize(row));
      if (verb === "PUT" || verb === "PATCH") { Object.assign(row, body || {}); row.updated_at = nowIso(); await rawPut("notes", row); return envelope(noteSerialize(row), "笔记已更新"); }
      if (verb === "DELETE") { await rawDelete("notes", id); return envelope({ deleted_id: id }, "笔记已删除"); }
    }
  }

  if (cleanPath === "/study/sessions" && verb === "GET") return listSessions(q);
  if (cleanPath === "/study/sessions" && verb === "POST") {
    const id = body?.task_id ? Number(body.task_id) : null;
    if (id && !(await rawGet("tasks", id))) throw new GuestError("关联的任务不存在", "TASK_NOT_FOUND", 404);
    const started = body?.started_at || nowIso();
    const row = { task_id: id, subject: String(body?.subject || "综合"), duration_minutes: num(body?.duration_minutes, 25), session_type: String(body?.session_type || "pomodoro"), started_at: started, ended_at: body?.ended_at || started, note: String(body?.note || ""), created_at: nowIso(), local_uid: uid() };
    row.id = await rawPut("sessions", row);
    return envelope({ session: sessionSerialize(row, (await rawGet("tasks", id))?.title), unlocked_achievements: [] }, "学习记录已保存");
  }
  if (cleanPath.startsWith("/study/sessions/") && verb === "DELETE") {
    const id = parseId(cleanPath, /^\/study\/sessions\/(\d+)$/);
    if (id) { if (!(await rawGet("sessions", id))) throw new GuestError("学习记录不存在", "NOT_FOUND", 404); await rawDelete("sessions", id); return envelope({ deleted_id: id }, "学习记录已删除"); }
  }
  if (cleanPath === "/study/stats") return envelope(await sessionSummary());
  if (cleanPath === "/achievements") { const state = await achievementState(); return envelope(await saveAchievements(state.stats, state.stored)); }

  if (cleanPath === "/flashcards" && verb === "GET") return listCards();
  if (cleanPath === "/flashcards" && verb === "POST") {
    const now = nowIso();
    const row = { note_id: body?.note_id ? Number(body.note_id) : null, front: requireTitle(body?.front, "卡片正面"), back: requireTitle(body?.back, "卡片背面"), subject: String(body?.subject || "综合"), mastery_level: num(body?.mastery_level), review_count: 0, next_review_date: null, last_reviewed_at: null, created_at: now, updated_at: now, local_uid: uid() };
    row.id = await rawPut("flashcards", row);
    return envelope(cardSerialize(row), "闪卡已创建");
  }
  if (cleanPath.startsWith("/flashcards/")) {
    const match = cleanPath.match(/^\/flashcards\/(\d+)(?:\/(review))?$/);
    if (match) {
      const id = Number(match[1]); const row = await rawGet("flashcards", id);
      if (!row) throw new GuestError("闪卡不存在", "NOT_FOUND", 404);
      if (cleanPath.endsWith("/review") && verb === "POST") {
        const rating = Math.max(1, Math.min(5, num(body?.rating, 3)));
        row.mastery_level = rating >= 4 ? Math.min(5, row.mastery_level + 1) : rating <= 2 ? Math.max(0, row.mastery_level - 1) : row.mastery_level;
        row.review_count += 1; row.last_reviewed_at = nowIso();
        const days = rating >= 4 ? 3 : rating === 3 ? 1 : 0;
        const next = new Date(); next.setDate(next.getDate() + days); row.next_review_date = next.toISOString().slice(0, 10); row.updated_at = nowIso();
        await rawPut("flashcards", row); return envelope({ flashcard: cardSerialize(row) });
      }
      if (verb === "PUT" || verb === "PATCH") { Object.assign(row, body || {}, { updated_at: nowIso() }); await rawPut("flashcards", row); return envelope(cardSerialize(row), "闪卡已更新"); }
      if (verb === "DELETE") { await rawDelete("flashcards", id); return envelope({ deleted_id: id }, "闪卡已删除"); }
    }
  }

  if (cleanPath === "/errors" && verb === "GET") return listErrors();
  if (cleanPath === "/errors" && verb === "POST") {
    const now = nowIso();
    const row = { subject: requireTitle(body?.subject, "学科"), question: requireTitle(body?.question, "题目"), student_answer: String(body?.student_answer || ""), correct_answer: String(body?.correct_answer || ""), analysis: String(body?.analysis || ""), knowledge_points: Array.isArray(body?.knowledge_points) ? body.knowledge_points : [], mastery: String(body?.mastery || "new"), source: "manual", created_at: now, updated_at: now, local_uid: uid() };
    row.id = await rawPut("errors", row);
    return envelope(errorSerialize(row), "错题已保存");
  }
  if (cleanPath.startsWith("/errors/")) {
    const match = cleanPath.match(/^\/errors\/(\d+)$/);
    if (match) {
      const id = Number(match[1]); const row = await rawGet("errors", id);
      if (!row) throw new GuestError("错题不存在", "NOT_FOUND", 404);
      if (verb === "PUT" || verb === "PATCH") { Object.assign(row, body || {}, { updated_at: nowIso() }); await rawPut("errors", row); return envelope(errorSerialize(row), "错题已更新"); }
      if (verb === "DELETE") { await rawDelete("errors", id); return envelope({ deleted_id: id }, "错题已删除"); }
    }
  }

  if (cleanPath === "/reports/daily") return dailyReport(q.date);
  throw new GuestError("访客模式暂不支持该操作", "GUEST_ENDPOINT_UNAVAILABLE", 404);
}

async function planPreview(body) {
  const rows = (await tasks()).filter((r) => r.status !== "completed");
  const available = Math.max(15, num(body.available_minutes, 120));
  const start = String(body.start_time || "18:00");
  const [hour, minute] = start.split(":").map(Number);
  let cursor = hour * 60 + minute;
  const endLimit = 24 * 60;
  const schedule = [];
  let used = 0;
  const unscheduled = [];
  for (const row of rows) {
    const minutes = Math.max(5, row.estimated_minutes || 30);
    if (used + minutes > available || cursor + minutes > endLimit) { unscheduled.push({ id: row.id, title: row.title, reason: "本次可用时间不足" }); continue; }
    const end = cursor + minutes;
    const fmt = (value) => `${String(Math.floor(value / 60)).padStart(2, "0")}:${String(value % 60).padStart(2, "0")}`;
    schedule.push({ task_id: row.id, title: row.title, subject: row.subject, start_time: fmt(cursor), end_time: fmt(end), planned_minutes: minutes, partial: false, reason: "按预计时长顺序排入" });
    cursor = end; used += minutes;
  }
  return envelope({ plan_date: body.plan_date || todayIso(), start_time: start, available_minutes: available, scheduled_minutes: used, schedule, unscheduled_tasks: unscheduled, beyond_midnight: false, notice: "访客排期只保存在当前设备。", summary: schedule.length ? `已排入 ${schedule.length} 个任务。` : "没有可排期的任务。" });
}

async function planApply(body) {
  const schedule = Array.isArray(body.schedule) ? body.schedule : [];
  const planDate = body.plan_date || todayIso();
  let count = 0;
  for (const item of schedule) {
    const row = await rawGet("tasks", Number(item.task_id)); if (!row) continue;
    row.planned_date = planDate; row.planned_start = item.start_time; row.planned_minutes = num(item.planned_minutes, 30); row.updated_at = nowIso(); await rawPut("tasks", row); count += 1;
  }
  return envelope({ applied: count }, "计划已应用");
}

export async function guestImportSummary() {
  const counts = {};
  for (const name of ["tasks", "grades", "notes", "sessions", "flashcards", "errors"]) counts[name] = (await rawAll(name)).length;
  return { counts, total: Object.values(counts).reduce((s, n) => s + n, 0), device_id: deviceId() };
}

export async function guestImportPayload(clientBatchId) {
  const [taskRows, gradeRows, noteRows, sessionRows, errorRows, cardRows] = await Promise.all([rawAll("tasks"), rawAll("grades"), rawAll("notes"), rawAll("sessions"), rawAll("errors"), rawAll("flashcards")]);
  const taskByUid = new Map(taskRows.map((r) => [r.id, r.local_uid || uid()]));
  const noteByUid = new Map(noteRows.map((r) => [r.id, r.local_uid || uid()]));
  const clean = (row, extra = {}) => ({ ...row, ...extra, local_uid: row.local_uid || uid() });
  return {
    client_batch_id: clientBatchId,
    device_id: deviceId(),
    data: {
      tasks: taskRows.map((r) => clean(r)),
      grades: gradeRows.map((r) => clean(r)),
      notes: noteRows.map((r) => clean(r, { source_image: null })),
      study_sessions: sessionRows.map((r) => clean(r, { local_task_uid: r.task_id ? taskByUid.get(r.task_id) || null : null })),
      flashcards: cardRows.map((r) => clean(r, { local_note_uid: r.note_id ? noteByUid.get(r.note_id) || null : null })),
      errors: errorRows.map((r) => clean(r)),
    },
  };
}

export async function clearGuestData() {
  for (const name of ["tasks", "grades", "notes", "sessions", "flashcards", "errors", "uploads"]) {
    for (const row of await rawAll(name)) await rawDelete(name, row.id);
  }
  await metaSet("achievements", {});
  await metaSet("last_import", null);
}
