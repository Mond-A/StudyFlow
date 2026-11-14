"""Production WSGI entry point for Gunicorn.

Gunicorn must never use run.py / Flask's development server in production.
"""

from backend.app import create_app

app = create_app()
