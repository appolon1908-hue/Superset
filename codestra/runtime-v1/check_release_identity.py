#!/usr/bin/env python3
"""Fail closed unless runtime source and image identities are immutable."""

from __future__ import annotations

import os
import re

EXPECTED_IMAGE_DIGEST = (
    "sha256:59cd4af66006fe4cc98906eda42a771dbefdacb432f9ab083e02cdc6ff01f29d"
)


def main() -> None:
    source = os.environ.get("CODESTRA_SUPERSET_SOURCE_REVISION", "")
    digest = os.environ.get("CODESTRA_SUPERSET_IMAGE_DIGEST", "")
    if not re.fullmatch(r"[0-9a-f]{40}", source):
        raise SystemExit("invalid protected Superset source revision")
    if digest != EXPECTED_IMAGE_DIGEST:
        raise SystemExit("Superset image digest does not match the reviewed lock")
    print("SUPERSET_RELEASE_IDENTITY=PASS")


if __name__ == "__main__":
    main()
