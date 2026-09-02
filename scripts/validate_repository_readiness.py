#!/usr/bin/env python3
"""Validate repository-only Superset signed-image readiness."""
from __future__ import annotations
import json
import re
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
IMAGE = re.compile(r"^[a-z0-9./_-]+@sha256:[0-9a-f]{64}$")
AUTHORITY = "appolon1908-hue/Codestra-Telemetry/.github/workflows/reusable-release-image.yml@9a6aebb849bbc068105c10d9d1dfd39ebf6f78bd"
REQUIRED = (
    "REPOSITORY_PROFILE.md", "SECURITY.md", ".github/CODEOWNERS",
    "docs/BACKUP_RESTORE_ROLLBACK.md", "docs/UPGRADE.md", ".dockerignore",
    ".gitleaks.toml", "codestra/release/image-build.v1.json",
    "codestra/release/runtime-base.lock.json", ".github/workflows/release-image.yml",
    "scripts/build_and_inspect_locked_image.sh", "scripts/validate_runtime_identity.py",
    "requirements-validation.txt",
)

def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")

def load(path: str) -> dict:
    value = json.loads((ROOT / path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        fail(f"{path} must contain an object")
    return value

def main() -> None:
    missing = [path for path in REQUIRED if not (ROOT / path).is_file()]
    if missing:
        fail(f"missing readiness files: {missing}")
    if (ROOT / "codestra/runtime-v1/compose.yaml").exists():
        fail("conflicting legacy Compose authority must remain absent")
    manifest = load("codestra/release/image-build.v1.json")
    lock = load("codestra/release/runtime-base.lock.json")
    if manifest.get("imageId") != "superset" or manifest.get("context") != "." or manifest.get("productionActivation") is not False:
        fail("image manifest identity/context/activation mismatch")
    if lock.get("artifactModel") != "repository-configured-signed-image" or lock.get("productionActivation") is not False:
        fail("runtime lock model/activation mismatch")
    for field in ("buildFrontendImage", "upstreamImage"):
        if not IMAGE.fullmatch(str(lock.get(field, ""))):
            fail(f"mutable build input: {field}")
    if manifest.get("buildArgs") != {"SUPERSET_BASE_IMAGE": lock["upstreamImage"]}:
        fail("manifest build arguments mismatch")
    if lock.get("upstreamRelease") != "6.1.0" or lock.get("upstreamReleaseCommit") != "c83fb2bb1dcfac41ac51bcebd82471f4a7180d18":
        fail("official Superset release authority mismatch")
    if lock.get("vendoredSourceExecutableUsed") is not False:
        fail("unreleased vendored source may not be executable authority")
    dockerfile = (ROOT / manifest["dockerfile"]).read_text(encoding="utf-8")
    if dockerfile.splitlines()[0] != f"# syntax={lock['buildFrontendImage']}":
        fail("Dockerfile frontend mismatch")
    for token in ("FROM ${SUPERSET_BASE_IMAGE}", "superset_config.py.example", "runtime-base.lock.json", "USER 10001:10001"):
        if token not in dockerfile:
            fail(f"Dockerfile release boundary missing: {token}")
    compose = yaml.safe_load((ROOT / "codestra/runtime-v1/compose.candidate.yaml").read_text(encoding="utf-8"))
    common = compose.get("x-superset-common", {})
    if "build" in common or "env_file" in common or common.get("privileged") is True:
        fail("Superset Compose is not a deploy-only file-secret boundary")
    if any(set(value) != {"file"} for value in compose.get("secrets", {}).values()):
        fail("Superset secret definitions must be file-only")
    runtime = load("codestra/runtime-v1/runtime.v1.json")
    if runtime.get("status") != "CONFIG_PREPARED_NOT_DEPLOYED" or any(runtime.get("activation", {}).values()):
        fail("Superset runtime activation must remain false")
    release = yaml.safe_load((ROOT / ".github/workflows/release-image.yml").read_text(encoding="utf-8"))
    job = release.get("jobs", {}).get("release", {})
    if job.get("uses") != AUTHORITY or job.get("with", {}).get("image_id") != "superset":
        fail("release authority mismatch")
    build_call = 'bash scripts/build_and_inspect_locked_image.sh "$GITHUB_SHA"'
    for relative in (".github/workflows/validate-repository-readiness.yml", ".github/workflows/validate-repository-readiness-protected.yml"):
        if build_call not in (ROOT / relative).read_text(encoding="utf-8"):
            fail(f"merge/protected image build missing: {relative}")
    for workflow in (ROOT / ".github/workflows").glob("*.yml"):
        text = workflow.read_text(encoding="utf-8")
        for reference in re.findall(r"(?m)^\s*(?:-\s*)?uses:\s*([^\s#]+)", text):
            if not reference.startswith("./") and not re.fullmatch(r"[^@\s]+@[0-9a-f]{40}", reference):
                fail(f"mutable action: {workflow.name}: {reference}")
        if re.search(r"git push\s+origin\s+HEAD:(?:main|development|test|staging|production)", text):
            fail(f"direct protected-branch push: {workflow.name}")
    print("SUPERSET_REPOSITORY_READINESS_SOURCE=PASS")
    print("ARTIFACT_MODEL=SIGNED_DERIVED_IMAGE")
    print("PRODUCTION_ACTIVATION=NO")

if __name__ == "__main__":
    main()
