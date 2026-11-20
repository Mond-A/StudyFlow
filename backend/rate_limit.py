"""Shared SQLite rate limiting helpers.

The login limiter and the account-email actions all use the existing
``login_rate_limits`` table. That keeps the patch migration-free and avoids
introducing Redis or another service.
"""

from __future__ import annotations

import hashlib
import math
import sqlite3
import time

from .db import get_db

# Keep all counters long enough for every configured window. Expired rows are
# removed opportunistically; this is intentionally longer than any normal
# login/email window so cleanup by one feature cannot reset another feature.
RATE_LIMIT_RETENTION_SECONDS = 24 * 60 * 60


class RateLimitUnavailable(RuntimeError):
    """The rate-limit store is temporarily unavailable (for example, locked)."""


def _key_hash(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def consume_limits(limits: list[tuple[str, int, int]]) -> int:
    """Atomically consume one attempt for every key, or consume none.

    ``limits`` contains ``(key, max_attempts, window_seconds)``. A request is
    allowed only when all dimensions are below their limits. The whole
    read-modify-write runs under ``BEGIN IMMEDIATE`` so concurrent processes
    cannot pass a check-then-increment race.
    """
    if not limits:
        return 0

    now = time.time()
    db = None
    prepared: list[tuple[str, int, float]] = []
    retry_after = 0
    max_window = max(int(window) for _, _, window in limits)
    try:
        db = get_db()
        db.execute("BEGIN IMMEDIATE")
        for raw_key, max_attempts, window in limits:
            key_hash = _key_hash(raw_key)
            row = db.execute(
                "SELECT attempts, window_started FROM login_rate_limits "
                "WHERE key_hash = ?",
                (key_hash,),
            ).fetchone()
            elapsed = now - float(row["window_started"]) if row else None
            if row is None or elapsed >= int(window):
                attempts = 1
                started = now
            else:
                attempts = int(row["attempts"]) + 1
                started = float(row["window_started"])
                if int(row["attempts"]) >= int(max_attempts):
                    retry_after = max(
                        retry_after,
                        max(1, math.ceil(int(window) - elapsed)),
                    )
                    continue
            prepared.append((key_hash, attempts, started))

        if retry_after:
            # Do not consume the other dimensions when one dimension is full.
            db.rollback()
            return retry_after

        for key_hash, attempts, started in prepared:
            db.execute(
                """
                INSERT INTO login_rate_limits (key_hash, attempts, window_started)
                VALUES (?, ?, ?)
                ON CONFLICT(key_hash) DO UPDATE SET
                    attempts = excluded.attempts,
                    window_started = excluded.window_started
                """,
                (key_hash, attempts, started),
            )
        db.execute(
            "DELETE FROM login_rate_limits WHERE window_started < ?",
            (now - max(max_window, RATE_LIMIT_RETENTION_SECONDS),),
        )
        db.commit()
    except sqlite3.OperationalError as exc:
        if db is not None:
            db.rollback()
        # A locked/busy database is a service-capacity problem, not a rate
        # limit decision. The caller maps this to 503, never 429.
        raise RateLimitUnavailable("rate-limit store is temporarily unavailable") from exc
    except Exception:
        if db is not None:
            db.rollback()
        raise
    return 0
