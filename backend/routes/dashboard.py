"""Dashboard REST endpoint."""

from __future__ import annotations

from flask import Blueprint

from ..db import get_current_user_id
from ..services.dashboard import build_dashboard
from ..utils.responses import success

bp = Blueprint("dashboard", __name__)


@bp.get("/dashboard")
def dashboard():
    return success(build_dashboard(get_current_user_id()))
