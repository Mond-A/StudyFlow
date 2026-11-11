"""Grade analytics shared by the Analytics page and AI advice."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from ..db import query_all
from ..utils.serializers import serialize_grade
from ..utils.timeutils import today_iso


def parse_range(range_value: str | None) -> tuple[str | None, str]:
    value = (range_value or "90").lower()
    if value == "all":
        return None, "all"
    try:
        days = int(value)
    except ValueError:
        days = 90
    days = max(7, min(days, 730))
    start = (date.fromisoformat(today_iso()) - timedelta(days=days - 1)).isoformat()
    return start, str(days)


def grade_analytics(user_id: int, *, subject: str | None = None, range_value: str = "90") -> dict:
    start, normalized_range = parse_range(range_value)
    sql = "SELECT * FROM grades WHERE user_id = ?"
    params: list = [user_id]
    if subject and subject != "all":
        sql += " AND subject = ?"
        params.append(subject)
    if start:
        sql += " AND exam_date >= ?"
        params.append(start)
    sql += " ORDER BY exam_date ASC, id ASC"
    rows = query_all(sql, params)
    records = [serialize_grade(row) for row in rows]

    by_subject: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        by_subject[record["subject"]].append(record)

    colors = [
        "#2563eb",
        "#0d9488",
        "#d97706",
        "#7c3aed",
        "#db2777",
        "#0891b2",
        "#65a30d",
        "#ea580c",
        "#4f46e5",
        "#475569",
    ]
    subject_series = []
    subject_comparison = []
    for index, (name, items) in enumerate(sorted(by_subject.items())):
        points = [
            {
                "date": item["exam_date"],
                "percentage": item["percentage"],
                "score": item["score"],
                "max_score": item["max_score"],
                "exam_name": item["exam_name"],
                "grade_id": item["id"],
            }
            for item in items
        ]
        average = round(sum(item["percentage"] for item in items) / len(items), 1)
        latest = items[-1]
        previous = items[-2] if len(items) > 1 else None
        delta = (
            round(latest["percentage"] - previous["percentage"], 1) if previous else 0.0
        )
        subject_series.append(
            {
                "subject": name,
                "color": colors[index % len(colors)],
                "points": points,
                "average": average,
                "latest": latest["percentage"],
                "delta": delta,
                "count": len(items),
            }
        )
        subject_comparison.append(
            {
                "subject": name,
                "average": average,
                "latest": latest["percentage"],
                "delta": delta,
                "count": len(items),
                "color": colors[index % len(colors)],
            }
        )

    subject_comparison.sort(key=lambda item: item["average"], reverse=True)
    for rank, item in enumerate(subject_comparison, start=1):
        item["rank"] = rank

    # Aggregate exams sharing a date into one "overall" point.
    by_date: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        by_date[record["exam_date"]].append(record)
    overall_series = []
    for exam_date, items in sorted(by_date.items()):
        total_score = sum(item["score"] for item in items)
        total_max = sum(item["max_score"] for item in items)
        overall_series.append(
            {
                "date": exam_date,
                "percentage": round(total_score / total_max * 100, 1) if total_max else 0,
                "exam_count": len(items),
                "subjects": [item["subject"] for item in items],
            }
        )

    average = (
        round(sum(item["percentage"] for item in records) / len(records), 1)
        if records
        else None
    )
    latest_percentage = overall_series[-1]["percentage"] if overall_series else None
    previous_percentage = (
        overall_series[-2]["percentage"] if len(overall_series) > 1 else None
    )
    change = (
        round(latest_percentage - previous_percentage, 1)
        if latest_percentage is not None and previous_percentage is not None
        else None
    )

    available_dates = query_all(
        "SELECT MIN(exam_date) AS first, MAX(exam_date) AS last FROM grades WHERE user_id = ?",
        (user_id,),
    )
    all_subjects = [
        row["subject"]
        for row in query_all(
            "SELECT DISTINCT subject FROM grades WHERE user_id = ? ORDER BY subject",
            (user_id,),
        )
    ]

    return {
        "range": normalized_range,
        "start_date": start,
        "end_date": today_iso(),
        "subject_filter": subject or "all",
        "records": list(reversed(records)),
        "chart_records": records,
        "subject_series": subject_series,
        "subject_comparison": subject_comparison,
        "overall_series": overall_series,
        "kpis": {
            "average_percentage": average,
            "latest_percentage": latest_percentage,
            "change_from_previous": change,
            "exam_count": len(records),
            "subject_count": len(by_subject),
            "best_subject": subject_comparison[0] if subject_comparison else None,
            "weakest_subject": subject_comparison[-1] if subject_comparison else None,
        },
        "available_subjects": all_subjects,
        "data_range": {
            "first": available_dates[0]["first"] if available_dates else None,
            "last": available_dates[0]["last"] if available_dates else None,
        },
        "notice": "成绩分析基于你录入的数据，AI 建议仅供参考。",
    }
