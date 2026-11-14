"""Gunicorn configuration for the single-admin StudyFlow deployment.

Gunicorn is deliberately bound to loopback only. ChmlFrp / a reverse proxy
may later forward public traffic to this local port; Flask must not be exposed
directly to the LAN or internet.
"""

from __future__ import annotations

import os
from pathlib import Path

_project_dir = Path(os.getenv("STUDYFLOW_APP_DIR", "/opt/studyflow")).resolve()
_log_dir = Path(os.getenv("STUDYFLOW_LOG_DIR", str(_project_dir / "logs"))).resolve()
_log_dir.mkdir(parents=True, exist_ok=True)

bind = "127.0.0.1:5000"
workers = max(1, int(os.getenv("GUNICORN_WORKERS", "2")))
threads = max(1, int(os.getenv("GUNICORN_THREADS", "2")))
worker_class = "gthread"

timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
graceful_timeout = 30
keepalive = 5
max_requests = 1000
max_requests_jitter = 100

# Set to false: SQLite connections are per-request and must not be inherited
# by forked workers.
preload_app = False

accesslog = str(_log_dir / "access.log")
errorlog = str(_log_dir / "error.log")
capture_output = True
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)sus'

# The reverse proxy runs on the same host. Do not trust arbitrary LAN clients.
forwarded_allow_ips = "127.0.0.1"
proxy_protocol = False
