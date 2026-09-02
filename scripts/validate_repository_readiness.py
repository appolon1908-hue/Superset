#!/usr/bin/env python3
"""Validate repository-only Superset release readiness."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
IMAGE = re.compile(r"^[a-z0-9./_-]+@sha256:[0-9a-f]{64}$")
AUTHORITY = (
    "appolon1908-hue/Codestra-Telemetry/.github/workflows/"
    "reusable-release-config-bundle.yml@777292781faeca9348d0e2ecdce6ac3f50c91d93"
)
REQUIRED = (
    "README.md",
    "REPOSITORY_PROFILE.md",
    "SECURITY.md",
    ".github/CODEOWNERS",
    "docs/BACKUP_RESTORE_ROLLBACK.md",
    "docs/UPGRADE.md",
    ".gitleaks.toml",
    "CODESTRA_UPSTREAM_LOCK.json",
    "codestra/release/runtime-image.lock.json",
    "codestra/release/config-bundle.manifest.json",
    "scripts/build_config_bundle.py",
    ".github/workflows/release-config-bundle.yml",
    "requirements-validation.txt",
)
CANONICAL_RUNTIME_FILES = (
    "codestra/runtime-v1/compose.production.yaml",
    "codestra/runtime-v1/superset_config.py",
    "codestra/runtime-v1/codestra_security_manager.py",
    "codestra/runtime-v1/check_release_identity.py",
)


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def load(relative: str) -> dict:
    value = json.loads((ROOT / relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        fail(f"{relative} must contain an object")
    return value


def main() -> None:
    missing = [path for path in REQUIRED if not (ROOT / path).is_file()]
    if missing:
        fail(f"missing readiness files: {missing}")
    ambiguous = [
        path
        for path in (
            "codestra/runtime-v1/compose.yaml",
            "codestra/runtime-v1/compose.candidate.yaml",
            "codestra/runtime-v1/superset_config.py.example",
            "codestra/runtime-v1/codestra_security_manager_v2.py",
        )
        if (ROOT / path).exists()
    ]
    if ambiguous:
        fail(f"ambiguous runtime authorities remain: {ambiguous}")
    for path in CANONICAL_RUNTIME_FILES:
        if not (ROOT / path).is_file():
            fail(f"canonical runtime file missing: {path}")

    upstream = load("CODESTRA_UPSTREAM_LOCK.json")
    tree = subprocess.check_output(
        ["git", "rev-parse", "HEAD:upstream"], cwd=ROOT, text=True
    ).strip()
    if upstream.get("schema_version") != "1.1" or tree != upstream.get(
        "imported_tree_sha"
    ):
        fail("vendored upstream tree does not match its lock")
    if upstream.get("source_tree_verification") is not True:
        fail("upstream source-tree verification must be enabled")
    if upstream.get("deployment_enabled") is not False:
        fail("upstream source import may not deploy")

    lock = load("codestra/release/runtime-image.lock.json")
    if lock.get("releaseModel") != "verified-upstream-image-plus-signed-config":
        fail("Superset must use release Model B")
    if not IMAGE.fullmatch(str(lock.get("image", ""))):
        fail("runtime image is mutable")
    for field in ("upstreamTagCommit",):
        if not GIT_SHA.fullmatch(str(lock.get(field, ""))):
            fail(f"invalid Git identity: {field}")
    for field in ("imageIndexDigest", "linuxAmd64ManifestDigest"):
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", str(lock.get(field, ""))):
            fail(f"invalid OCI identity: {field}")
    if lock.get("image") != f"docker.io/apache/superset@{lock['imageIndexDigest']}":
        fail("image reference and index digest disagree")
    if lock.get("upstreamSignatureState") != "UNAVAILABLE_FROM_UPSTREAM_RELEASE":
        fail("upstream signature disposition is inaccurate")
    if lock.get("productionActivation") is not False:
        fail("repository source may not activate production")

    manifest = load("codestra/release/config-bundle.manifest.json")
    if manifest.get("component") != "superset" or manifest.get(
        "repository"
    ) != "appolon1908-hue/Superset":
        fail("configuration manifest identity mismatch")
    if manifest.get("productionActivation") is not False:
        fail("configuration bundle may not activate production")
    files = manifest.get("files")
    if not isinstance(files, dict) or len(files) < 8:
        fail("configuration manifest is incomplete")
    for relative, expected in files.items():
        path = ROOT / relative
        if not path.is_file() or not SHA256.fullmatch(str(expected)):
            fail(f"invalid configuration manifest entry: {relative}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            fail(f"configuration checksum mismatch: {relative}")
    if manifest.get("generatedFiles") != {
        "codestra/runtime-v1/release-identity.json": (
            "protected_source_and_runtime_image_identity"
        )
    }:
        fail("signed release identity generation policy is missing")

    compose_text = (ROOT / CANONICAL_RUNTIME_FILES[0]).read_text(encoding="utf-8")
    compose = yaml.safe_load(compose_text)
    services = compose.get("services", {})
    required_services = {
        "superset-migrate",
        "superset-web",
        "superset-worker",
        "superset-beat",
    }
    if set(services) != required_services:
        fail("canonical Superset topology mismatch")
    for name, service in services.items():
        if service.get("image") != lock["image"]:
            fail(f"runtime image identity mismatch: {name}")
        if service.get("user") != lock["imageDeclaredUser"]:
            fail(f"runtime user identity mismatch: {name}")
        if service.get("privileged") is True or service.get("network_mode") == "host":
            fail(f"unsafe container boundary: {name}")
        if service.get("read_only") is not True or "ALL" not in service.get(
            "cap_drop", []
        ):
            fail(f"container hardening incomplete: {name}")
        environment = service.get("environment", {})
        if environment.get("CODESTRA_SUPERSET_IMAGE_DIGEST") != lock[
            "imageIndexDigest"
        ]:
            fail(f"runtime image read-back mismatch: {name}")
        if "CODESTRA_SUPERSET_SOURCE_REVISION" not in str(
            environment.get("CODESTRA_SUPERSET_SOURCE_REVISION", "")
        ):
            fail(f"runtime source read-back missing: {name}")
        if "check_release_identity.py" not in " ".join(service.get("command", [])):
            fail(f"runtime release identity is not verified before startup: {name}")
        mounted = " ".join(str(value) for value in service.get("volumes", []))
        if "release-identity.json:/app/pythonpath/release-identity.json:ro" not in mounted:
            fail(f"signed release identity is not mounted read-only: {name}")
    if services["superset-migrate"].get("profiles") != ["migrate"]:
        fail("schema migration requires the explicit migrate profile")
    for name in ("superset-web", "superset-worker", "superset-beat"):
        if "superset db upgrade" in " ".join(services[name].get("command", [])):
            fail(f"routine service automatically migrates schema: {name}")

    release = yaml.safe_load(
        (ROOT / ".github/workflows/release-config-bundle.yml").read_text()
    )
    job = release.get("jobs", {}).get("release", {})
    if job.get("uses") != AUTHORITY or job.get("with", {}).get(
        "component_id"
    ) != "superset":
        fail("release caller authority mismatch")
    for workflow in (ROOT / ".github/workflows").glob("*.yml"):
        text = workflow.read_text(encoding="utf-8")
        for reference in re.findall(r"(?m)^\s*(?:-\s*)?uses:\s*([^\s#]+)", text):
            if not reference.startswith("./") and not re.fullmatch(
                r"[^@\s]+@[0-9a-f]{40}", reference
            ):
                fail(f"mutable action: {workflow.name}: {reference}")
        if re.search(
            r"git push\s+origin\s+HEAD:(?:main|development|test|staging|production)",
            text,
        ):
            fail(f"direct protected-branch push: {workflow.name}")
    print("SUPERSET_REPOSITORY_READINESS_SOURCE=PASS")
    print("ARTIFACT_MODEL=SIGNED_CONFIGURATION_BUNDLE")
    print("PRODUCTION_ACTIVATION=NO")


if __name__ == "__main__":
    main()
