"""StudyFlow development entry point.

Usage:
    python run.py
"""

from __future__ import annotations

import os

from backend.app import create_app

app = create_app()


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    try:
        port = int(os.getenv("PORT", "5000"))
    except ValueError:
        port = 5000
    debug = os.getenv("FLASK_ENV", "development").lower() == "development"
    print(f"\n  StudyFlow MVP running at http://{host}:{port}\n")
    app.run(host=host, port=port, debug=debug)
