#!/usr/bin/env python3
"""Fail-closed Superset liveness and metadata-database readiness probe.

The native `/health` route is a process liveness signal only. This probe combines
that signal with a real read-only `SELECT 1` against the configured metadata
store. It never prints the metadata URI or database exception text.
"""

from __future__ import annotations

import os
import sys
import urllib.request
from pathlib import Path

from sqlalchemy import create_engine, text


def fail(reason: str) -> None:
    print(f"SUPERSET_METADATA_READINESS=FAIL reason={reason}", file=sys.stderr)
    raise SystemExit(1)


def required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        fail(f"missing_{name.lower()}")
    return value


def check_liveness() -> None:
    url = os.environ.get(
        "SUPERSET_LIVENESS_URL", "http://127.0.0.1:8088/health"
    ).strip()
    try:
        with urllib.request.urlopen(url, timeout=4) as response:  # noqa: S310
            if response.status != 200:
                fail("liveness_status")
            body = response.read(256)
            if len(body) > 256:
                fail("liveness_response_too_large")
    except SystemExit:
        raise
    except Exception:
        fail("liveness_unavailable")


def read_metadata_uri() -> str:
    path = Path(required_environment("SUPERSET_METADATA_DATABASE_URI_FILE"))
    try:
        uri = path.read_text(encoding="utf-8").strip()
    except OSError:
        fail("metadata_uri_unreadable")
    if not uri:
        fail("metadata_uri_empty")
    return uri


def check_metadata_database(uri: str) -> None:
    engine = None
    try:
        engine = create_engine(
            uri,
            pool_pre_ping=True,
            pool_recycle=60,
            pool_timeout=4,
        )
        with engine.connect() as connection:
            value = connection.execute(text("SELECT 1")).scalar_one()
        if int(value) != 1:
            fail("metadata_query_unexpected_result")
    except SystemExit:
        raise
    except Exception:
        fail("metadata_database_unavailable")
    finally:
        if engine is not None:
            engine.dispose()


def main() -> None:
    check_liveness()
    check_metadata_database(read_metadata_uri())
    print("SUPERSET_LIVENESS_AND_METADATA_READINESS=PASS")


if __name__ == "__main__":
    main()
