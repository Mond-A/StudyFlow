"""Daily report endpoints."""

from __future__ import annotations

from flask import Blueprint, request

from ..db import get_current_user_id
from ..services.reports import build_daily_report
from ..utils.exceptions import APIError
from ..utils.responses import success
from ..utils.timeutils import parse_date, today_iso

bp = Blueprint("reports", __name__)


@bp.get("/reports/daily")
def daily_report():
    user_id = get_current_user_id()
    raw_date = (request.args.get("date") or "").strip()
    day = parse_date(raw_date, "date").isoformat() if raw_date else today_iso()
    if day > today_iso():
        raise APIError(
            "不能查看未来日期的学习报告", code="INVALID_DATE", status_code=400
        )
    return success(build_daily_report(user_id, day))
