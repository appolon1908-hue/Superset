#!/usr/bin/env python3
"""Fail closed unless runtime source and image identities are immutable."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

EXPECTED_IMAGE_DIGEST = (
    "sha256:07d08f5dae5ffd50e4b3a1efda6abd5da1823cd8cc65172cdbb1c6d5f45b24d8"
)
IDENTITY_FILE = Path("/app/pythonpath/release-identity.json")


def main() -> None:
    source = os.environ.get("CODESTRA_SUPERSET_SOURCE_REVISION", "")
    digest = os.environ.get("CODESTRA_SUPERSET_IMAGE_DIGEST", "")
    if not re.fullmatch(r"[0-9a-f]{40}", source):
        raise SystemExit("invalid protected Superset source revision")
    try:
        identity = json.loads(IDENTITY_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        raise SystemExit("signed Superset release identity is unavailable") from None
    if set(identity) != {
        "schemaVersion",
        "component",
        "protectedSourceSha",
        "runtimeImageDigest",
    }:
        raise SystemExit("signed Superset release identity has an invalid schema")
    if (
        identity.get("schemaVersion") != "1.0"
        or identity.get("component") != "superset"
    ):
        raise SystemExit("signed Superset release identity has the wrong component")
    if source != identity.get("protectedSourceSha"):
        raise SystemExit("Superset source revision does not match the signed release")
    if digest != EXPECTED_IMAGE_DIGEST or digest != identity.get("runtimeImageDigest"):
        raise SystemExit("Superset image digest does not match the reviewed lock")
    print("SUPERSET_RELEASE_IDENTITY=PASS")


if __name__ == "__main__":
    main()
