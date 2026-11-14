"""StudyFlow Flask application factory.

The backend serves both the REST API (`/api/*`) and the static vanilla-JS SPA
from `frontend/`. Keeping them in separate directories preserves a clean
front-end/back-end split without requiring a Node build step.
"""

from __future__ import annotations

import logging
from pathlib import Path

from flask import Flask, abort, current_app, send_from_directory
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

from .auth import init_auth
from .config import Config
from .db import close_db, init_schema, query_one
from .routes.ai import bp as ai_bp
from .routes.dashboard import bp as dashboard_bp
from .routes.errors import bp as errors_bp
from .routes.flashcards import bp as flashcards_bp
from .routes.grades import bp as grades_bp
from .routes.meta import bp as meta_bp
from .routes.notes import bp as notes_bp
from .routes.reports import bp as reports_bp
from .routes.study import bp as study_bp
from .routes.tasks import bp as tasks_bp
from .routes.uploads import bp as uploads_bp
from .services.demo_data import seed_demo_data
from .utils.responses import register_error_handlers


def _register_blueprints(app: Flask) -> None:
    for blueprint in (
        meta_bp,
        dashboard_bp,
        tasks_bp,
        grades_bp,
        notes_bp,
        ai_bp,
        uploads_bp,
        study_bp,
        flashcards_bp,
        errors_bp,
        reports_bp,
    ):
        app.register_blueprint(blueprint, url_prefix="/api")


def _configure_logging(app: Flask) -> None:
    if not app.logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    app.json.ensure_ascii = False
    app.json.sort_keys = False
    app.config["FRONTEND_DIR"] = Path(app.config["FRONTEND_DIR"]).resolve()
    app.config["UPLOAD_DIR"] = Path(app.config["UPLOAD_DIR"]).resolve()
    app.config["UPLOAD_DIR"].mkdir(parents=True, exist_ok=True)
    app.config["MAX_CONTENT_LENGTH"] = int(app.config["MAX_CONTENT_LENGTH"])

    _configure_logging(app)
    if app.config.get("TRUST_PROXY"):
        # Only trust one reverse-proxy hop. Keep TRUST_PROXY=false when Flask
        # is reached directly from the LAN.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    init_auth(app)

    db_path = Path(app.config["DATABASE_PATH"])
    if str(db_path) != ":memory:":
        db_path.parent.mkdir(parents=True, exist_ok=True)

    # Initialize schema and optional demo data inside an application context so
    # helpers such as ensure_default_user can read configuration.
    with app.app_context():
        init_schema(app)
        if app.config.get("SEED_DEMO", True):
            try:
                seed_demo_data(force=False)
            except Exception:
                app.logger.exception("Demo seed failed; application continues without it.")
                app.logger.info("You can initialize manually with scripts/init_db.py")

    app.teardown_appcontext(close_db)
    register_error_handlers(app)
    _register_blueprints(app)

    origins = app.config.get("CORS_ORIGINS") or []
    if origins:
        CORS(app, resources={r"/api/*": {"origins": origins}})

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if request_is_api():
            response.headers["Cache-Control"] = "no-store"
        return response

    def request_is_api() -> bool:
        from flask import request

        return request.path.startswith("/api/")

    @app.get("/")
    def index():
        frontend = Path(app.config["FRONTEND_DIR"])
        if not (frontend / "index.html").exists():
            abort(404)
        response = send_from_directory(frontend, "index.html")
        response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/uploads/<path:filename>")
    def uploaded_file(filename: str):
        upload_dir = Path(current_app.config["UPLOAD_DIR"])
        target = (upload_dir / filename).resolve()
        if upload_dir not in target.parents or not target.is_file():
            abort(404)
        response = send_from_directory(upload_dir, filename)
        response.headers["Cache-Control"] = "private, max-age=3600"
        return response

    @app.get("/<path:path>")
    def frontend_file(path: str):
        if path.startswith("api/") or path.startswith("uploads/"):
            abort(404)
        frontend = Path(app.config["FRONTEND_DIR"])
        candidate = (frontend / path).resolve()
        if frontend in candidate.parents and candidate.is_file():
            response = send_from_directory(frontend, path)
            if path.startswith("vendor/") or path.startswith("assets/"):
                response.headers["Cache-Control"] = "public, max-age=86400"
            return response
        if "." in Path(path).name:
            abort(404)
        response = send_from_directory(frontend, "index.html")
        response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/api/health/db")
    def db_health():
        from .utils.responses import success

        row = query_one("SELECT sqlite_version() AS version")
        return success({"sqlite": row["version"] if row else "unknown", "status": "ok"})

    return app
