#!/usr/bin/env python3
"""Fail closed unless Superset runtime identity inputs are exact and aligned."""
from __future__ import annotations
import os
import re

IMAGE = re.compile(r"^ghcr\.io/appolon1908-hue/superset-superset@sha256:([0-9a-f]{64})$")
SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^sha256:([0-9a-f]{64})$")

def fail(message: str) -> None:
    raise SystemExit(f"SUPERSET_RUNTIME_IDENTITY=FAIL reason={message}")

def main() -> None:
    image_match = IMAGE.fullmatch(os.environ.get("CODESTRA_SUPERSET_IMAGE", ""))
    digest_match = DIGEST.fullmatch(os.environ.get("CODESTRA_IMAGE_DIGEST", ""))
    if not image_match:
        fail("image must be the immutable release repository plus lowercase sha256 digest")
    if not SHA.fullmatch(os.environ.get("CODESTRA_SOURCE_SHA", "")):
        fail("source SHA must be 40 lowercase hexadecimal characters")
    if not digest_match or digest_match.group(1) != image_match.group(1):
        fail("image digest readback must equal the image reference digest")
    print("SUPERSET_RUNTIME_IDENTITY=PASS")

if __name__ == "__main__":
    main()
