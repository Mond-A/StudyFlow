"""Initialize the SQLite database and optionally seed demo data.

Usage:
    python scripts/init_db.py            # apply schema, seed only on first run
    python scripts/init_db.py --no-seed  # apply schema without demo seeding
    python scripts/init_db.py --reload-demo  # reload demo data if none exists
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app import create_app  # noqa: E402
from backend.db import query_one  # noqa: E402
from backend.services.demo_data import demo_summary, seed_demo_data  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize StudyFlow database")
    parser.add_argument("--no-seed", action="store_true", help="skip demo data")
    parser.add_argument(
        "--reload-demo", action="store_true", help="load demo data if not present"
    )
    args = parser.parse_args()

    config = {"SEED_DEMO": False}
    app = create_app(test_config=config)
    with app.app_context():
        if args.reload_demo:
            result = seed_demo_data(force=True)
            print("Demo:", result)
        counts = {}
        for table in (
            "users",
            "tasks",
            "grades",
            "notes",
            "study_sessions",
            "achievements",
            "error_records",
            "flashcards",
        ):
            row = query_one(f"SELECT COUNT(*) AS count FROM {table}")
            counts[table] = row["count"] if row else 0
        print(f"Database: {app.config['DATABASE_PATH']}")
        print("Tables:", counts)
        print("Demo:", demo_summary())
        if args.no_seed:
            print("Demo seeding skipped (existing data was not changed).")
    print("Schema initialized successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
