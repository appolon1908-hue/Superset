#!/usr/bin/env python3
"""Build the deterministic Codestra Superset configuration archive."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import tarfile
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "codestra/release/config-bundle.manifest.json"
RUNTIME_LOCK = ROOT / "codestra/release/runtime-image.lock.json"
SOURCE_SHA = re.compile(r"^[0-9a-f]{40}$")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=ROOT / "dist/superset-config.tar.gz"
    )
    parser.add_argument(
        "--source-revision",
        default=os.environ.get("GITHUB_SHA", ""),
        help="exact protected source SHA embedded in the signed bundle",
    )
    args = parser.parse_args()
    if not SOURCE_SHA.fullmatch(args.source_revision):
        raise SystemExit("--source-revision must be an exact 40-character SHA")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    runtime_lock = json.loads(RUNTIME_LOCK.read_text(encoding="utf-8"))
    generated_path = "codestra/runtime-v1/release-identity.json"
    if manifest.get("generatedFiles") != {
        generated_path: "protected_source_and_runtime_image_identity"
    }:
        raise SystemExit("configuration manifest generated-file policy mismatch")
    release_identity = (
        json.dumps(
            {
                "component": "superset",
                "protectedSourceSha": args.source_revision,
                "runtimeImageDigest": runtime_lock["imageIndexDigest"],
                "schemaVersion": "1.0",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    paths: list[Path] = []
    for relative, expected in sorted(manifest["files"].items()):
        path = ROOT / relative
        actual = digest(path)
        if actual != expected:
            raise SystemExit(
                f"checksum mismatch for {relative}: {actual} != {expected}"
            )
        paths.append(path)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(
                fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT
            ) as archive:
                for path in paths + [MANIFEST]:
                    relative = path.relative_to(ROOT)
                    info = archive.gettarinfo(str(path), arcname=str(relative))
                    info.uid = info.gid = info.mtime = 0
                    info.uname = info.gname = ""
                    with path.open("rb") as source:
                        archive.addfile(info, source)
                identity_info = tarfile.TarInfo(generated_path)
                identity_info.mode = 0o444
                identity_info.uid = identity_info.gid = identity_info.mtime = 0
                identity_info.uname = identity_info.gname = ""
                identity_info.size = len(release_identity)
                archive.addfile(identity_info, BytesIO(release_identity))
    print(f"CONFIG_BUNDLE={args.output}")
    print(f"CONFIG_BUNDLE_SHA256={digest(args.output)}")


if __name__ == "__main__":
    main()
