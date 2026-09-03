#!/usr/bin/env python3
"""Validate Superset liveness, metadata readiness, and API-description policy."""

from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
READINESS = ROOT / "codestra" / "runtime-v1" / "check_metadata_readiness.py"
COMPOSE = ROOT / "codestra" / "runtime-v1" / "compose.candidate.yaml"
CONFIG = ROOT / "codestra" / "runtime-v1" / "superset_config.py.example"
CONTRACT = ROOT / "docs" / "CODESTRA_PRODUCTION_SERVER_API_CONTRACT.md"


def fail(message: str) -> None:
    print(f"SUPERSET_READINESS_CONTRACT_ERROR={message}", file=sys.stderr)
    raise SystemExit(1)


def read(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        fail(f"cannot read {path.relative_to(ROOT)}: {exc.__class__.__name__}")


def main() -> None:
    readiness = read(READINESS)
    try:
        ast.parse(readiness, filename=str(READINESS))
    except SyntaxError as exc:
        fail(f"invalid readiness Python: line {exc.lineno}")

    required_readiness = (
        "SUPERSET_LIVENESS_URL",
        "SUPERSET_METADATA_DATABASE_URI_FILE",
        "urllib.request.urlopen",
        "create_engine(",
        'text("SELECT 1")',
        ".scalar_one()",
        "pool_pre_ping=True",
        "pool_timeout=4",
        "SUPERSET_LIVENESS_AND_METADATA_READINESS=PASS",
        "metadata_database_unavailable",
    )
    for fragment in required_readiness:
        if fragment not in readiness:
            fail(f"readiness probe omits {fragment}")
    for forbidden in (
        "print(uri",
        "print(metadata_uri",
        "print(exc",
        "print(error",
        "str(exc)",
        "str(error)",
        "repr(exc)",
        "repr(error)",
    ):
        if forbidden in readiness:
            fail(f"readiness probe may disclose metadata connection details: {forbidden}")

    compose = read(COMPOSE)
    for fragment in (
        "SUPERSET_LIVENESS_URL: http://127.0.0.1:8088/health",
        "- /app/pythonpath/check_metadata_readiness.py",
        "timeout: 8s",
    ):
        if fragment not in compose:
            fail(f"Compose readiness wiring omits {fragment}")
    if "urllib.request.urlopen('http://127.0.0.1:8088/health'" in compose:
        fail("Compose still certifies only the liveness route")
    if "./check_metadata_readiness.py:" in compose:
        fail("readiness code must be embedded in the immutable image")

    config = read(CONFIG)
    if "FAB_API_SWAGGER_UI = False" not in config:
        fail("production Superset configuration must keep Swagger UI disabled")
    if "FAB_API_SWAGGER_UI = True" in config:
        fail("production Superset configuration enables Swagger UI")

    contract = read(CONTRACT)
    for fragment in (
        "web-process liveness only",
        "METADATA_DATABASE_READINESS=PASS",
        "METADATA_DATABASE_SELECT_1=PASS",
        "GET_/swagger/v1_EXPECTED_DISABLED_404=PASS",
        "UNEXPECTED_REQUIRED_ROUTE_404=0",
        "FAB_API_SWAGGER_UI = False",
    ):
        if fragment not in contract:
            fail(f"production contract omits {fragment}")
    if "GET_/swagger/v1_ROUTE_EXISTS=PASS" in contract:
        fail("production contract still requires the intentionally disabled Swagger UI")

    print("CODESTRA_SUPERSET_METADATA_READINESS_CONTRACT=PASS")


if __name__ == "__main__":
    main()
