"""Shared product constants."""

from __future__ import annotations

SUBJECTS = [
    "语文",
    "数学",
    "英语",
    "物理",
    "化学",
    "生物",
    "政治",
    "历史",
    "地理",
    "综合",
]

TASK_STATUSES = {"pending", "in_progress", "completed"}
SESSION_TYPES = {"pomodoro", "free", "manual", "task"}

ACHIEVEMENT_DEFS = [
    {
        "code": "first_task",
        "title": "旗开得胜",
        "description": "完成第 1 个学习任务",
        "icon": "flag",
        "criterion": "tasks_completed >= 1",
    },
    {
        "code": "task_5",
        "title": "渐入佳境",
        "description": "累计完成 5 个任务",
        "icon": "check-check",
        "criterion": "tasks_completed >= 5",
    },
    {
        "code": "task_20",
        "title": "任务达人",
        "description": "累计完成 20 个任务",
        "icon": "trophy",
        "criterion": "tasks_completed >= 20",
    },
    {
        "code": "focus_first",
        "title": "专注起步",
        "description": "完成第 1 次学习计时",
        "icon": "timer",
        "criterion": "sessions_count >= 1",
    },
    {
        "code": "focus_300",
        "title": "五小时俱乐部",
        "description": "累计专注学习 300 分钟",
        "icon": "clock-3",
        "criterion": "study_minutes >= 300",
    },
    {
        "code": "focus_1000",
        "title": "长期主义者",
        "description": "累计专注学习 1000 分钟",
        "icon": "calendar-check",
        "criterion": "study_minutes >= 1000",
    },
    {
        "code": "note_first",
        "title": "知识收藏家",
        "description": "保存第 1 篇笔记",
        "icon": "notebook-pen",
        "criterion": "notes_count >= 1",
    },
    {
        "code": "note_5",
        "title": "笔记成册",
        "description": "保存 5 篇笔记",
        "icon": "library",
        "criterion": "notes_count >= 5",
    },
    {
        "code": "grade_first",
        "title": "记录成长",
        "description": "录入第 1 条成绩记录",
        "icon": "chart-line",
        "criterion": "grades_count >= 1",
    },
    {
        "code": "grade_5",
        "title": "数据分析师",
        "description": "累计录入 5 条成绩记录",
        "icon": "chart-no-axes-combined",
        "criterion": "grades_count >= 5",
    },
    {
        "code": "streak_3",
        "title": "三日坚持",
        "description": "在 3 个不同日期留下学习记录",
        "icon": "flame",
        "criterion": "study_days >= 3",
    },
    {
        "code": "flashcard_first",
        "title": "记忆工程师",
        "description": "创建第 1 张闪卡",
        "icon": "layers",
        "criterion": "flashcards_count >= 1",
    },
]
