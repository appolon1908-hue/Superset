#!/usr/bin/env python3
"""Validate repository-only Superset signed-image readiness."""

from __future__ import annotations

import ast
import json
import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
IMAGE = re.compile(r"^[a-z0-9./_-]+@sha256:[0-9a-f]{64}$")
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
AUTHORITY = (
    "appolon1908-hue/Codestra-Telemetry/.github/workflows/"
    "reusable-release-image.yml@9a6aebb849bbc068105c10d9d1dfd39ebf6f78bd"
)
REQUIRED = (
    ".dockerignore",
    ".gitattributes",
    ".github/CODEOWNERS",
    ".gitleaks.toml",
    "CODESTRA_UPSTREAM_LOCK.json",
    "README.md",
    "REPOSITORY_PROFILE.md",
    "SECURITY.md",
    ".github/workflows/release-image.yml",
    ".github/workflows/validate-repository-readiness.yml",
    ".github/workflows/validate-repository-readiness-protected.yml",
    "codestra/release/image-build.v1.json",
    "codestra/release/runtime-base.lock.json",
    "codestra/runtime-v1/Dockerfile",
    "codestra/runtime-v1/bootstrap_roles.py",
    "codestra/runtime-v1/compose.candidate.yaml",
    "docs/BACKUP_RESTORE_ROLLBACK.md",
    "docs/UPGRADE.md",
    "requirements-runtime.in",
    "requirements-runtime.txt",
    "requirements-validation.txt",
    "scripts/build_and_inspect_locked_image.sh",
    "scripts/run_disposable_integration.sh",
    "scripts/validate_runtime_identity.py",
    "scripts/verify_release_identity.sh",
    "tests/superset_startup_config.py",
    "tests/validate_bootstrap_runtime.py",
    "tests/validate_celery_runtime.py",
)


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def load(path: str) -> dict:
    value = json.loads((ROOT / path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        fail(f"{path} must contain an object")
    return value


def require_tokens(path: str, tokens: tuple[str, ...]) -> str:
    text = (ROOT / path).read_text(encoding="utf-8")
    for token in tokens:
        if token not in text:
            fail(f"{path} omits required control: {token}")
    return text


def validate_python(path: str) -> str:
    text = (ROOT / path).read_text(encoding="utf-8")
    try:
        ast.parse(text, filename=path)
    except SyntaxError as exc:
        fail(f"invalid Python {path}: line {exc.lineno}")
    return text


def validate_upstream_tree() -> None:
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    if "upstream/** -text" not in attributes.splitlines():
        fail("vendored upstream bytes are not protected from text normalization")

    lock = load("CODESTRA_UPSTREAM_LOCK.json")
    if lock.get("schema_version") != "1.1":
        fail("upstream lock schema must be 1.1")
    if lock.get("import_path") != "upstream":
        fail("upstream import path mismatch")
    if lock.get("source_tree_verification") is not True:
        fail("upstream source-tree verification must remain enabled")
    if lock.get("deployment_enabled") is not False:
        fail("upstream import may not activate a deployment")

    expected_tree = str(lock.get("imported_tree_sha", ""))
    if not GIT_SHA.fullmatch(expected_tree):
        fail("upstream imported tree identity is invalid")
    actual_tree = subprocess.check_output(
        ["git", "rev-parse", "HEAD:upstream"],
        cwd=ROOT,
        text=True,
    ).strip()
    if actual_tree != expected_tree:
        fail("vendored upstream tree differs from CODESTRA_UPSTREAM_LOCK.json")


def validate_bootstrap_and_celery() -> None:
    source = validate_python("codestra/runtime-v1/bootstrap_roles.py")
    if "from superset import app" in source:
        fail("bootstrap imports the superset.app module as a Flask application")
    for token in (
        "from superset.app import create_app",
        "application = create_app()",
        "with application.app_context():",
        "application.appbuilder.sm",
        "security_manager.get_session.commit()",
        "CODESTRA_SUPERSET_ROLE_BOOTSTRAP=PASS",
    ):
        if token not in source:
            fail(f"role bootstrap omits required factory/reconciliation control: {token}")

    role_validator = validate_python("tests/validate_bootstrap_runtime.py")
    for token in (
        "from superset.app import create_app",
        "Codestra Security Auditor",
        "Viewer",
        "Analyst",
        "permission_identities(viewer) != gamma_permissions",
        "permission_identities(analyst) != alpha_permissions",
        "CODESTRA_SUPERSET_BOOTSTRAP_RUNTIME_VALIDATION=PASS",
    ):
        if token not in role_validator:
            fail(f"role runtime validator omits: {token}")

    celery_validator = validate_python("tests/validate_celery_runtime.py")
    for token in (
        "celery_app.loader.import_default_modules()",
        "sql_lab.get_sql_results",
        "reports.scheduler",
        "reports.prune_log",
        "version_history.prune_old_versions",
        "deletion_retention.purge_soft_deleted",
        "CODESTRA_SUPERSET_CELERY_RUNTIME_VALIDATION=PASS",
    ):
        if token not in celery_validator:
            fail(f"Celery runtime validator omits: {token}")


def validate_signed_image() -> None:
    manifest = load("codestra/release/image-build.v1.json")
    lock = load("codestra/release/runtime-base.lock.json")
    if (
        manifest.get("imageId") != "superset"
        or manifest.get("context") != "."
        or manifest.get("productionActivation") is not False
    ):
        fail("image manifest identity/context/activation mismatch")
    if (
        lock.get("artifactModel") != "repository-configured-signed-image"
        or lock.get("productionActivation") is not False
    ):
        fail("runtime lock model/activation mismatch")
    for field in ("buildFrontendImage", "upstreamImage"):
        if not IMAGE.fullmatch(str(lock.get(field, ""))):
            fail(f"mutable build input: {field}")
    if manifest.get("buildArgs") != {"SUPERSET_BASE_IMAGE": lock["upstreamImage"]}:
        fail("manifest build arguments mismatch")
    if (
        lock.get("upstreamRelease") != "6.1.0"
        or lock.get("upstreamReleaseCommit")
        != "c83fb2bb1dcfac41ac51bcebd82471f4a7180d18"
    ):
        fail("official Superset release authority mismatch")
    if lock.get("vendoredSourceExecutableUsed") is not False:
        fail("unreleased vendored source may not be executable authority")

    dockerfile = (ROOT / manifest["dockerfile"]).read_text(encoding="utf-8")
    if dockerfile.splitlines()[0] != f"# syntax={lock['buildFrontendImage']}":
        fail("Dockerfile frontend mismatch")
    for token in (
        "FROM ${SUPERSET_BASE_IMAGE}",
        "requirements-runtime.txt",
        "uv pip install",
        "--require-hashes",
        "import gevent, psycopg2",
        "superset_config.py.example",
        "bootstrap_roles.py",
        "runtime-base.lock.json",
        "USER 10001:10001",
    ):
        if token not in dockerfile:
            fail(f"Dockerfile release boundary missing: {token}")

    runtime_input = (
        ROOT / "requirements-runtime.in"
    ).read_text(encoding="utf-8").splitlines()
    if runtime_input != [
        "gevent==24.2.1",
        "greenlet==3.1.1",
        "psycopg2-binary==2.9.9",
        "setuptools==80.9.0",
        "zope-event==5.0",
        "zope-interface==5.4.0",
    ]:
        fail("Superset 6.1.0 runtime extras differ from release constraints")
    runtime_lock = (ROOT / "requirements-runtime.txt").read_text(encoding="utf-8")
    for dependency in runtime_input:
        if dependency not in runtime_lock:
            fail(f"runtime dependency lock omits {dependency}")
    if "--hash=sha256:" not in runtime_lock:
        fail("runtime dependency lock must contain exact distribution hashes")

    inspection = require_tokens(
        "scripts/build_and_inspect_locked_image.sh",
        (
            "importlib.metadata, gevent, psycopg2",
            "from superset.app import create_app",
            "--network none",
            "--read-only",
            "superset db upgrade",
            "superset init",
            "tests/validate_bootstrap_runtime.py",
            "tests/validate_celery_runtime.py",
            "SUPERSET_BOOTSTRAP_AND_CELERY_RUNTIME=PASS",
            "SUPERSET_LOCKED_IMAGE_INSPECTION=PASS",
        ),
    )
    if inspection.count("python /app/pythonpath/bootstrap_roles.py") < 2:
        fail("exact-image validation must execute role bootstrap twice")


def validate_release_identity() -> None:
    source = require_tokens(
        "scripts/verify_release_identity.sh",
        (
            "ghcr\\.io/appolon1908-hue/superset-superset@sha256:",
            "org.opencontainers.image.source",
            "org.opencontainers.image.revision",
            "https://github.com/appolon1908-hue/Superset",
            "10001:10001",
            ".RepoDigests",
            "SUPERSET_RELEASE_IDENTITY=PASS",
        ),
    )
    for forbidden in (":latest", "docker pull", "--privileged", "network_mode"):
        if forbidden in source:
            fail(f"release identity readback contains forbidden behavior: {forbidden}")


def validate_disposable_integration() -> None:
    source = require_tokens(
        "scripts/run_disposable_integration.sh",
        (
            'test "$(git rev-parse HEAD)" = "$source_sha"',
            "docker network create --internal",
            "install -d -m 0711",
            "chmod 0444",
            "postgres:17.6-alpine@sha256:ef257d85f76e48da1c64832459b59fcaba1a4dac97bf5d7450c77753542eee94",
            "redis:8.2.1-alpine@sha256:987c376c727652f99625c7d205a1cba3cb2c53b92b0b62aade2bd48ee1593232",
            "--read-only",
            "superset db upgrade",
            "superset init",
            "tests/validate_bootstrap_runtime.py",
            "tests/validate_celery_runtime.py",
            "check_metadata_readiness.py",
            "SUPERSET_LIVENESS_AND_METADATA_READINESS=PASS",
            "pg_dump",
            "pg_restore",
            "ENABLE ROW LEVEL SECURITY",
            "FORCE ROW LEVEL SECURITY",
            "SET ROLE analytics_readonly",
            "unauthorized-business",
            "read-only analytics role unexpectedly performed a write",
            "SUPERSET_DISPOSABLE_MIGRATION_READINESS_BACKUP_RESTORE_RLS_WRITE_DENIAL=PASS",
        ),
    )
    if "mkdir -m 0700" in source or "install -d -m 0700" in source:
        fail("disposable secret directory is not traversable by UID 10001")
    if source.count("python /app/pythonpath/bootstrap_roles.py") < 2:
        fail("disposable integration must prove bootstrap idempotency")
    if "--network host" in source or "-p " in source or "--publish" in source:
        fail("disposable integration may not expose its internal network")


def validate_compose_and_release() -> None:
    if (ROOT / "codestra/runtime-v1/compose.yaml").exists():
        fail("conflicting legacy Compose authority must remain absent")

    compose = yaml.safe_load(
        (ROOT / "codestra/runtime-v1/compose.candidate.yaml").read_text(
            encoding="utf-8"
        )
    )
    common = compose.get("x-superset-common", {})
    if "build" in common or "env_file" in common or common.get("privileged") is True:
        fail("Superset Compose is not a deploy-only file-secret boundary")
    if any(set(value) != {"file"} for value in compose.get("secrets", {}).values()):
        fail("Superset secret definitions must be file-only")
    if set(compose.get("services", {})) != {
        "superset-web",
        "superset-worker",
        "superset-beat",
        "superset-bootstrap",
    }:
        fail("Superset candidate topology mismatch")
    if compose["services"]["superset-bootstrap"].get("profiles") != [
        "bootstrap-after-approval"
    ]:
        fail("Superset bootstrap must remain inactive without explicit approval")

    runtime = load("codestra/runtime-v1/runtime.v1.json")
    if runtime.get("status") != "CONFIG_PREPARED_NOT_DEPLOYED" or any(
        runtime.get("activation", {}).values()
    ):
        fail("Superset runtime activation must remain false")

    release = yaml.safe_load(
        (ROOT / ".github/workflows/release-image.yml").read_text(encoding="utf-8")
    )
    job = release.get("jobs", {}).get("release", {})
    if job.get("uses") != AUTHORITY or job.get("with", {}).get("image_id") != "superset":
        fail("release authority mismatch")

    pull_request_workflow = (
        ROOT / ".github/workflows/validate-repository-readiness.yml"
    ).read_text(encoding="utf-8")
    for token in (
        'test "$(git rev-parse HEAD)" = "$HEAD_SHA"',
        'bash scripts/build_and_inspect_locked_image.sh "$HEAD_SHA"',
        'bash scripts/run_disposable_integration.sh "$HEAD_SHA"',
        "validate-disposable-integration:",
        'bash scripts/build_and_inspect_locked_image.sh "$GITHUB_SHA"',
    ):
        if token not in pull_request_workflow:
            fail(f"exact-head/synthetic-merge validation omits: {token}")

    protected_workflow = (
        ROOT / ".github/workflows/validate-repository-readiness-protected.yml"
    ).read_text(encoding="utf-8")
    if 'bash scripts/build_and_inspect_locked_image.sh "$GITHUB_SHA"' not in protected_workflow:
        fail("protected-branch exact-image validation is missing")

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


def main() -> None:
    missing = [path for path in REQUIRED if not (ROOT / path).is_file()]
    if missing:
        fail(f"missing readiness files: {missing}")

    validate_upstream_tree()
    validate_bootstrap_and_celery()
    validate_signed_image()
    validate_release_identity()
    validate_disposable_integration()
    validate_compose_and_release()

    print("SUPERSET_REPOSITORY_READINESS_SOURCE=PASS")
    print("UPSTREAM_TREE_IDENTITY=PASS")
    print("BOOTSTRAP_AND_CELERY_RUNTIME_GATE=REQUIRED")
    print("DISPOSABLE_POSTGRES_REDIS_INTEGRATION=REQUIRED")
    print("SIGNED_RELEASE_IDENTITY_READBACK=REQUIRED")
    print("ARTIFACT_MODEL=SIGNED_DERIVED_IMAGE")
    print("PRODUCTION_ACTIVATION=NO")


if __name__ == "__main__":
    main()
