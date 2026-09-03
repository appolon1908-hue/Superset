"""Isolated build-inspection configuration; no production credential or endpoint."""
from __future__ import annotations

import os
from pathlib import Path

SECRET_KEY = Path(os.environ["CODESTRA_TEST_SECRET_FILE"]).read_text(
    encoding="utf-8"
).strip()
SQLALCHEMY_DATABASE_URI = "sqlite:////tmp/codestra-superset-startup.db"
WTF_CSRF_ENABLED = True
