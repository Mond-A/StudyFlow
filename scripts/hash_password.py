"""Generate a Werkzeug password hash for STUDYFLOW_PASSWORD_HASH.

Usage:
    python scripts/hash_password.py

The plaintext password is read without echo, confirmed, and never written to
disk or printed. Only the resulting hash is printed for insertion into .env.
"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from werkzeug.security import generate_password_hash  # noqa: E402


def main() -> int:
    print("StudyFlow legacy password hash generator")
    print("The password must be at least 12 characters.")
    password = getpass.getpass("Password: ")
    if len(password) < 12:
        print("Error: password must be at least 12 characters.", file=sys.stderr)
        return 1
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Error: passwords do not match.", file=sys.stderr)
        return 1
    if password.strip() != password:
        print("Error: leading/trailing whitespace is not allowed.", file=sys.stderr)
        return 1

    digest = generate_password_hash(password, method="scrypt")
    print()
    print("Add this single line to .env and keep .env mode 600:")
    print(f"STUDYFLOW_PASSWORD_HASH={digest}")
    print()
    print("Do not commit the hash or the password to Git.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
