"""Optional, clearly removable demo dataset for first-run exploration."""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta

from ..db import get_current_user, get_current_user_id, get_db, get_meta, set_meta
from ..utils.timeutils import get_timezone, now_iso, now_local, today_iso
from .constants import ACHIEVEMENT_DEFS

DEMO_SEED_KEY = "demo_seeded_at"
DEMO_CLEARED_KEY = "demo_cleared_at"

DEMO_NOTES = [
    {
        "title": "二次函数：一般式与顶点",
        "subject": "数学",
        "days_ago": 2,
        "content": r"""# 二次函数：一般式与顶点

## 一般式

二次函数的一般式为：

$$y = ax^2 + bx + c \quad (a \ne 0)$$

其中 $a$ 决定抛物线的开口方向和开口大小。

## 顶点坐标

将一般式配方后可得顶点式：

$$y = a\left(x + \frac{b}{2a}\right)^2 + \frac{4ac - b^2}{4a}$$

因此顶点坐标为：

$$\left(-\frac{b}{2a}, \frac{4ac - b^2}{4a}\right)$$

## 对称轴

对称轴是直线 $x = -\frac{b}{2a}$。

- 若 $a > 0$，抛物线开口向上，顶点处取得最小值；
- 若 $a < 0$，抛物线开口向下，顶点处取得最大值。

## 与 x 轴的位置关系

判别式 $\Delta = b^2 - 4ac$：

| 判别式 | 交点情况 |
| --- | --- |
| $\Delta > 0$ | 两个不同交点 |
| $\Delta = 0$ | 一个交点（相切） |
| $\Delta < 0$ | 无实数交点 |

> 复习：留意“$a \ne 0$”这个前提，做题时先确认是否真的是二次函数。
""",
    },
    {
        "title": "英语：定语从句关系代词",
        "subject": "英语",
        "days_ago": 5,
        "content": """# 定语从句关系代词

## 基本结构

定语从句放在名词或代词之后，用来修饰这个名词。被修饰的词叫先行词。

The book **that I bought yesterday** is very interesting.

## 常见关系代词

- **who**：指人，在从句中作主语或宾语。
- **whom**：指人，在从句中作宾语，较正式。
- **which**：指物，在从句中作主语或宾语。
- **that**：指人或物，在限制性定语从句中常用。
- **whose**：表示所属关系，指人或物。

## 选择思路

1. 先找先行词，判断指人还是指物；
2. 再看关系词在从句中充当什么成分；
3. 注意介词提前时通常不用 that，也不能省略。

> 易错点：关系代词在从句中作宾语时可以省略，但作主语时不能省略。
""",
    },
    {
        "title": "物理：浮力与阿基米德原理",
        "subject": "物理",
        "days_ago": 9,
        "content": r"""# 浮力与阿基米德原理

## 浮力的方向

浸在液体（或气体）中的物体受到向上的托力，这个力叫浮力。浮力的方向总是竖直向上。

## 阿基米德原理

浸在液体中的物体所受浮力的大小等于它排开的液体所受的重力：

$$F_{浮} = G_{排} = \rho_{液} g V_{排}$$

- $\rho_{液}$：液体密度；
- $g$：重力加速度，通常取 $9.8\ \mathrm{N/kg}$；
- $V_{排}$：物体排开液体的体积。

## 物体的浮沉

- 当 $F_{浮} > G_{物}$ 时，物体上浮（最终漂浮）；
- 当 $F_{浮} = G_{物}$ 时，物体悬浮或漂浮；
- 当 $F_{浮} < G_{物}$ 时，物体下沉。

## 实验注意

测量浮力时可以用称重法：$F_{浮} = G - F_{示}$。读数时视线要与弹簧测力计刻度盘垂直。

> 待补充：整理典型浮沉条件例题（TODO）。
""",
    },
]


def _dt(day: date, hour: int, minute: int = 0) -> str:
    value = datetime.combine(day, time(hour, minute), tzinfo=get_timezone())
    return value.isoformat()


def _track(conn, user_id: int, table: str, record_id: int, timestamp: str) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO demo_records (user_id, table_name, record_id, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, table, record_id, timestamp),
    )


def demo_summary() -> dict:
    conn = get_db()
    rows = conn.execute(
        "SELECT table_name, COUNT(*) AS count FROM demo_records GROUP BY table_name"
    ).fetchall()
    counts = {row["table_name"]: row["count"] for row in rows}
    return {
        "loaded": bool(counts),
        "counts": counts,
        "total_records": sum(counts.values()),
        "seeded_at": get_meta(DEMO_SEED_KEY),
    }


def seed_demo_data(*, force: bool = False) -> dict:
    """Insert demo data once, unless force=True is used from Settings."""
    existing = demo_summary()
    if existing["loaded"]:
        return {**existing, "already_loaded": True, "created": 0}
    if get_meta(DEMO_SEED_KEY) and not force:
        return {
            "loaded": False,
            "already_cleared": True,
            "created": 0,
            "counts": {},
            "message": "演示数据曾被清除，不会在重启时自动重建。",
        }

    user = get_current_user()
    user_id = int(user["id"])
    conn = get_db()
    now = now_local()
    today = now.date()
    timestamp = now_iso()
    created_counts: dict[str, int] = {}

    def count(table: str) -> None:
        created_counts[table] = created_counts.get(table, 0) + 1

    try:
        # Tasks: a mix of completed and pending items across the coming days.
        task_specs = [
            {
                "title": "订正数学单元测错题",
                "subject": "数学",
                "description": "整理错题原因，重点看二次函数顶点与判别式。",
                "due": today,
                "estimated": 40,
                "actual": 35,
                "difficulty": 4,
                "status": "completed",
                "priority": 1,
                "planned_date": today,
                "planned_start": "17:30",
                "planned_minutes": 40,
                "completed_at": _dt(today, 18, 10),
                "created_at": _dt(today - timedelta(days=1), 20, 0),
            },
            {
                "title": "完成英语阅读练习",
                "subject": "英语",
                "description": "完成 Unit 5 阅读练习，标记不熟悉的短语。",
                "due": today,
                "estimated": 30,
                "actual": 0,
                "difficulty": 2,
                "status": "pending",
                "priority": 1,
                "planned_date": today,
                "planned_start": "19:30",
                "planned_minutes": 30,
                "completed_at": None,
                "created_at": _dt(today - timedelta(days=1), 21, 10),
            },
            {
                "title": "物理：整理浮力实验笔记",
                "subject": "物理",
                "description": "补充称重法测浮力的步骤和实验注意事项。",
                "due": today + timedelta(days=1),
                "estimated": 45,
                "actual": 0,
                "difficulty": 3,
                "status": "pending",
                "priority": 2,
                "planned_date": today,
                "planned_start": "20:10",
                "planned_minutes": 45,
                "completed_at": None,
                "created_at": _dt(today - timedelta(days=2), 19, 0),
            },
            {
                "title": "语文：阅读《背影》并写批注",
                "subject": "语文",
                "description": "关注文中四次背影描写，写下两处批注。",
                "due": today + timedelta(days=2),
                "estimated": 50,
                "actual": 0,
                "difficulty": 3,
                "status": "pending",
                "priority": 2,
                "planned_date": today + timedelta(days=1),
                "planned_start": "19:00",
                "planned_minutes": 50,
                "completed_at": None,
                "created_at": _dt(today - timedelta(days=1), 18, 30),
            },
            {
                "title": "背记英语 Unit 5 单词",
                "subject": "英语",
                "description": "用间隔复习法复习 20 个单词。",
                "due": today - timedelta(days=1),
                "estimated": 25,
                "actual": 30,
                "difficulty": 2,
                "status": "completed",
                "priority": 2,
                "planned_date": today - timedelta(days=1),
                "planned_start": "20:00",
                "planned_minutes": 25,
                "completed_at": _dt(today - timedelta(days=1), 20, 35),
                "created_at": _dt(today - timedelta(days=3), 19, 30),
            },
        ]
        task_ids = []
        for spec in task_specs:
            cursor = conn.execute(
                """
                INSERT INTO tasks
                    (user_id, title, subject, description, due_date, estimated_minutes,
                     actual_minutes, difficulty, status, priority, planned_date,
                     planned_start, planned_minutes, source, completed_at,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'manual', ?, ?, ?)
                """,
                (
                    user_id,
                    spec["title"],
                    spec["subject"],
                    spec["description"],
                    spec["due"].isoformat(),
                    spec["estimated"],
                    spec["actual"],
                    spec["difficulty"],
                    spec["status"],
                    spec["priority"],
                    spec["planned_date"].isoformat(),
                    spec["planned_start"],
                    spec["planned_minutes"],
                    spec["completed_at"],
                    spec["created_at"],
                    spec["completed_at"] or spec["created_at"],
                ),
            )
            task_id = int(cursor.lastrowid)
            task_ids.append(task_id)
            _track(conn, user_id, "tasks", task_id, timestamp)
            count("tasks")

        # Grades across maths, English and physics to make charts meaningful.
        grade_specs = [
            ("数学", "第一次月考", 78, 100, 44, "函数题失分较多。"),
            ("英语", "第一次月考", 84, 100, 43, "阅读稳定，作文可再提升。"),
            ("数学", "期中考试", 86, 100, 28, "计算准确率提升。"),
            ("物理", "期中考试", 72, 100, 27, "浮力综合题需要加强。"),
            ("英语", "单元测验", 80, 100, 21, "完形填空错 3 题。"),
            ("数学", "二次函数单元测", 91, 100, 12, "顶点式和判别式掌握较好。"),
            ("物理", "浮力单元测", 79, 100, 8, "实验步骤描述不够完整。"),
            ("英语", "阅读专项", 88, 100, 4, "阅读速度与定位均有进步。"),
        ]
        for subject, exam_name, score, max_score, days, notes in grade_specs:
            exam_day = (today - timedelta(days=days)).isoformat()
            created = _dt(today - timedelta(days=days), 21, 0)
            cursor = conn.execute(
                """
                INSERT INTO grades
                    (user_id, subject, exam_name, score, max_score, exam_date, notes,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    subject,
                    exam_name,
                    score,
                    max_score,
                    exam_day,
                    notes,
                    created,
                    created,
                ),
            )
            _track(conn, user_id, "grades", int(cursor.lastrowid), timestamp)
            count("grades")

        # Notes with real Markdown + KaTeX so every rendering path is exercised.
        note_ids = []
        for spec in DEMO_NOTES:
            created_day = today - timedelta(days=spec["days_ago"])
            created = _dt(created_day, 16, 20)
            cursor = conn.execute(
                """
                INSERT INTO notes
                    (user_id, title, subject, content_markdown, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, spec["title"], spec["subject"], spec["content"], created, created),
            )
            note_id = int(cursor.lastrowid)
            note_ids.append(note_id)
            _track(conn, user_id, "notes", note_id, timestamp)
            count("notes")

        # Sessions populate today's dashboard, weekly activity and reports.
        session_specs = [
            (today, 9, 0, 25, "数学", "pomodoro", "完成一套错题订正", task_ids[0]),
            (today, 10, 0, 40, "英语", "pomodoro", "阅读理解精练", None),
            (today - timedelta(days=1), 20, 0, 30, "英语", "pomodoro", "单词复习", task_ids[4]),
            (today - timedelta(days=2), 19, 20, 45, "数学", "pomodoro", "二次函数练习", None),
            (today - timedelta(days=4), 18, 40, 25, "物理", "pomodoro", "浮力错题复盘", None),
        ]
        for day, hour, minute, duration, subject, session_type, note, task_id in session_specs:
            started = datetime.combine(day, time(hour, minute), tzinfo=get_timezone())
            ended = started + timedelta(minutes=duration)
            cursor = conn.execute(
                """
                INSERT INTO study_sessions
                    (user_id, task_id, subject, duration_minutes, session_type,
                     started_at, ended_at, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    task_id,
                    subject,
                    duration,
                    session_type,
                    started.isoformat(),
                    ended.isoformat(),
                    note,
                    ended.isoformat(),
                ),
            )
            _track(conn, user_id, "study_sessions", int(cursor.lastrowid), timestamp)
            count("study_sessions")

        # Two wrong-question records with knowledge tags.
        error_specs = [
            (
                "数学",
                "已知二次函数 y = ax² + bx + c 的图象经过点 (1, 0) 和 (3, 0)，且开口向上，求 a 的取值范围。",
                "只写出 a > 0，没有利用两个交点建立方程。",
                "设 y = a(x-1)(x-3)，由开口向上得 a > 0；再根据题目补充条件确定具体范围。",
                "二次函数的交点式",
                ["二次函数", "交点式", "抛物线开口方向"],
                "reviewing",
                4,
            ),
            (
                "英语",
                "The book ___ I borrowed from the library is very interesting. (that/which/who)",
                "选了 who",
                "先行词 book 指物，应使用 that 或 which；不能用 who。",
                "定语从句关系代词的选择",
                ["定语从句", "关系代词", "先行词"],
                "new",
                7,
            ),
        ]
        for (
            subject,
            question,
            student_answer,
            correct_answer,
            analysis,
            knowledge_points,
            mastery,
            days,
        ) in error_specs:
            created = _dt(today - timedelta(days=days), 21, 30)
            cursor = conn.execute(
                """
                INSERT INTO error_records
                    (user_id, subject, question, student_answer, correct_answer,
                     analysis, knowledge_points, mastery, source, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'manual', ?, ?)
                """,
                (
                    user_id,
                    subject,
                    question,
                    student_answer,
                    correct_answer,
                    analysis,
                    json.dumps(knowledge_points, ensure_ascii=False),
                    mastery,
                    created,
                    created,
                ),
            )
            _track(conn, user_id, "error_records", int(cursor.lastrowid), timestamp)
            count("error_records")

        # Flashcards, mostly due now to make the review flow demonstrable.
        flashcard_specs = [
            (
                note_ids[0],
                "二次函数一般式中，决定开口方向的是哪个系数？",
                "a。a > 0 开口向上，a < 0 开口向下；且 a ≠ 0。",
                "数学",
                2,
                3,
                0,
            ),
            (
                note_ids[0],
                "二次函数对称轴公式是什么？",
                r"$x = -\frac{b}{2a}$",
                "数学",
                1,
                1,
                -1,
            ),
            (
                note_ids[1],
                "先行词指物时，定语从句常用哪些关系代词？",
                "which 或 that；在限制性定语从句中 that 也常用于指物。",
                "英语",
                2,
                0,
                0,
            ),
            (
                note_ids[2],
                "阿基米德原理的表达式是什么？",
                r"$F_{浮} = G_{排} = \rho_{液} g V_{排}$",
                "物理",
                1,
                5,
                5,
            ),
        ]
        for note_id, front, back, subject, mastery, reviews, offset in flashcard_specs:
            created = _dt(today - timedelta(days=3), 18, 0)
            next_review = (today + timedelta(days=offset)).isoformat()
            cursor = conn.execute(
                """
                INSERT INTO flashcards
                    (user_id, note_id, front, back, subject, mastery_level,
                     review_count, next_review_date, last_reviewed_at,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    note_id,
                    front,
                    back,
                    subject,
                    mastery,
                    reviews,
                    next_review,
                    None,
                    created,
                    created,
                ),
            )
            _track(conn, user_id, "flashcards", int(cursor.lastrowid), timestamp)
            count("flashcards")

        # Track a few achievements so the dashboard demonstrates states.
        earned_codes = {"first_task", "focus_first", "note_first", "grade_first"}
        definitions = {item["code"]: item for item in ACHIEVEMENT_DEFS}
        for code in earned_codes:
            definition = definitions[code]
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO achievements
                    (user_id, code, title, description, icon, unlocked_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    code,
                    definition["title"],
                    definition["description"],
                    definition["icon"],
                    _dt(today, 12, 0),
                ),
            )
            if cursor.rowcount:
                _track(conn, user_id, "achievements", int(cursor.lastrowid), timestamp)
                count("achievements")

        conn.execute(
            """
            INSERT INTO app_meta (key, value, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (DEMO_SEED_KEY, timestamp, timestamp),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return {
        "loaded": True,
        "created": sum(created_counts.values()),
        "counts": created_counts,
        "message": "演示数据已写入。可在设置页一键清除，不会影响你自己创建的数据。",
    }


DEMO_TABLES_DELETE_ORDER = [
    "study_sessions",
    "flashcards",
    "achievements",
    "error_records",
    "grades",
    "notes",
    "tasks",
]


def clear_demo_data() -> dict:
    conn = get_db()
    rows = conn.execute(
        "SELECT table_name, record_id FROM demo_records ORDER BY id DESC"
    ).fetchall()
    if not rows:
        return {"cleared": 0, "counts": {}, "message": "当前没有可清除的演示数据。"}
    by_table: dict[str, list[int]] = {}
    for row in rows:
        by_table.setdefault(row["table_name"], []).append(int(row["record_id"]))
    counts: dict[str, int] = {}
    user_id = get_current_user_id()
    try:
        for table in DEMO_TABLES_DELETE_ORDER:
            ids = by_table.get(table, [])
            if not ids:
                continue
            placeholders = ",".join("?" for _ in ids)
            cursor = conn.execute(
                f"DELETE FROM {table} WHERE id IN ({placeholders})",  # table is whitelisted
                ids,
            )
            counts[table] = cursor.rowcount
        conn.execute("DELETE FROM demo_records")
        # Some achievements may have auto-unlocked while exploring demo data and
        # therefore aren't individually tracked. Recompute from the remaining
        # (real) data after clearing, so demo-only unlocks don't linger.
        conn.execute("DELETE FROM achievements WHERE user_id = ?", (user_id,))
        now = now_iso()
        conn.execute(
            """
            INSERT INTO app_meta (key, value, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (DEMO_CLEARED_KEY, now, now),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    # Reunlock achievements that are genuinely supported by the user's own data.
    from .achievements import evaluate_achievements

    evaluate_achievements(user_id)
    return {
        "cleared": sum(counts.values()),
        "counts": counts,
        "message": "演示数据已清除，你创建的数据仍然保留。",
    }
