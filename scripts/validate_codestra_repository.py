#!/usr/bin/env python3
"""Fail-closed validation for the complete Codestra Superset overlay."""

from __future__ import annotations

import ast
import json
import pathlib
import re
import sys
from typing import Any

import yaml


ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNTIME_ROOT = ROOT / "codestra" / "runtime-v1"
CANONICAL_CONFIG = RUNTIME_ROOT / "superset_config.py"
COMPAT_CONFIG = RUNTIME_ROOT / "superset_config.py.example"
CANONICAL_MANAGER = RUNTIME_ROOT / "codestra_security_manager.py"
COMPAT_MANAGER = RUNTIME_ROOT / "codestra_security_manager_v2.py"
BOOTSTRAP = RUNTIME_ROOT / "bootstrap_roles.py"
CANDIDATE_COMPOSE = RUNTIME_ROOT / "compose.candidate.yaml"
RUNTIME_COMPOSE = RUNTIME_ROOT / "compose.yaml"
EVIDENCE_CONTRACT = ROOT / "integration" / "staging-activation-contract-v1.json"
EVIDENCE_WORKFLOW = (
    ROOT / ".github" / "workflows" / "controlled-intake-staging-activation-gate.yml"
)
EXPECTED_HOST = "supe.codestra.media"
EXPECTED_ISSUER = "https://auth.codestra.co/realms/codestra"
EXPECTED_ORBIT_SHA = "47695963643edbbf63d2d480744bd2935228f4f2"


def fail(message: str) -> None:
    print(f"CODESTRA_SUPERSET_REPOSITORY_ERROR={message}", file=sys.stderr)
    raise SystemExit(1)


def read(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        fail(f"cannot read {path.relative_to(ROOT)}: {exc.__class__.__name__}")


def load_json(path: pathlib.Path) -> Any:
    try:
        return json.loads(read(path))
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON {path.relative_to(ROOT)}: line {exc.lineno}")


def load_yaml(path: pathlib.Path) -> Any:
    try:
        return yaml.safe_load(read(path))
    except yaml.YAMLError as exc:
        fail(f"invalid YAML {path.relative_to(ROOT)}: {exc.__class__.__name__}")


def parse_python(path: pathlib.Path) -> str:
    text = read(path)
    try:
        ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        fail(f"invalid Python {path.relative_to(ROOT)}: line {exc.lineno}")
    return text


def validate_required_files() -> None:
    required = (
        ROOT / "README.md",
        ROOT / "REPOSITORY_PROFILE.md",
        ROOT / "CODESTRA_UPSTREAM.json",
        ROOT / "CODESTRA_UPSTREAM_LOCK.json",
        ROOT / "orbit" / "adoption-manifest.json",
        ROOT / "docs" / "REPOSITORY-WIDE-REVIEW-2026-09-02.md",
        CANONICAL_CONFIG,
        COMPAT_CONFIG,
        CANONICAL_MANAGER,
        COMPAT_MANAGER,
        BOOTSTRAP,
        CANDIDATE_COMPOSE,
        RUNTIME_COMPOSE,
        EVIDENCE_CONTRACT,
        EVIDENCE_WORKFLOW,
    )
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        fail("missing required files: " + ", ".join(missing))


def validate_json_catalogue() -> None:
    roots = (
        ROOT / "codestra",
        ROOT / "integration",
        ROOT / "orbit",
    )
    json_paths = [
        ROOT / "CODESTRA_UPSTREAM.json",
        ROOT / "CODESTRA_UPSTREAM_LOCK.json",
    ]
    for directory in roots:
        json_paths.extend(path for path in directory.rglob("*.json") if path.is_file())
    for path in sorted(set(json_paths)):
        load_json(path)


def validate_upstream_lock() -> None:
    authority = load_json(ROOT / "CODESTRA_UPSTREAM.json")
    lock = load_json(ROOT / "CODESTRA_UPSTREAM_LOCK.json")
    if authority.get("codestra_repository") != "appolon1908-hue/Superset":
        fail("upstream authority repository mismatch")
    if authority.get("upstream_repository") != "apache/superset":
        fail("upstream repository mismatch")
    if authority.get("import_path") != "upstream":
        fail("upstream import path mismatch")
    if authority.get("lock_file") != "CODESTRA_UPSTREAM_LOCK.json":
        fail("upstream lock file is not authoritative")
    if authority.get("deployment_enabled") is not False:
        fail("upstream source authority may not activate deployment")
    if authority.get("branches") != [
        "development",
        "test",
        "staging",
        "production",
        "main",
    ]:
        fail("upstream authority omits the promotion chain")
    commit = lock.get("upstream_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        fail("upstream snapshot is not locked to an exact commit")
    if lock.get("deployment_enabled") is not False:
        fail("upstream lock may not activate deployment")


def validate_identity_and_configuration() -> None:
    canonical_manager = parse_python(CANONICAL_MANAGER)
    compatibility_manager = parse_python(COMPAT_MANAGER)
    if canonical_manager != compatibility_manager:
        fail("security-manager compatibility copy diverges from the canonical file")
    if 'remote.get("userinfo")' in canonical_manager:
        fail("relative Keycloak userinfo resolution is prohibited")
    for fragment in (
        'DEFAULT_KEYCLOAK_ISSUER = "https://auth.codestra.co/realms/codestra"',
        'f"{issuer}/protocol/openid-connect/userinfo"',
        'parsed.scheme != "https"',
        'email_verified") is not True',
        "APPROVED_ROLE_KEYS",
        "No approved Codestra Superset role was supplied",
    ):
        if fragment not in canonical_manager:
            fail(f"canonical security manager omits {fragment}")

    canonical_config = parse_python(CANONICAL_CONFIG)
    compatibility_config = parse_python(COMPAT_CONFIG)
    if canonical_config != compatibility_config:
        fail("configuration compatibility copy diverges from the canonical file")
    for fragment in (
        "from codestra_security_manager import (",
        'read_secret("SUPERSET_SECRET_KEY_FILE")',
        'read_secret("SUPERSET_METADATA_DATABASE_URI_FILE")',
        'read_secret("SUPERSET_REDIS_URL_FILE")',
        'read_secret("SUPERSET_OIDC_CLIENT_SECRET_FILE")',
        'AUTH_TYPE = AUTH_OAUTH',
        'AUTH_ROLES_SYNC_AT_LOGIN = True',
        '"code_challenge_method": "S256"',
        '"ROW_LEVEL_SECURITY": True',
        '"ALERT_REPORTS": False',
        '"ENABLE_TEMPLATE_PROCESSING": False',
        "ROW_LIMIT = 10000",
        "SQL_MAX_ROW = 100000",
        "FAB_API_SWAGGER_UI = False",
        "PUBLIC_ROLE_LIKE = None",
        "EMAIL_NOTIFICATIONS = False",
    ):
        if fragment not in canonical_config:
            fail(f"canonical Superset configuration omits {fragment}")
    for fragment in (
        'os.environ["SUPERSET_SECRET_KEY"]',
        'os.environ["SUPERSET_METADATA_DATABASE_URI"]',
        'os.environ["SUPERSET_OAUTH_CLIENT_SECRET"]',
        "ROW_LIMIT = 50000",
    ):
        if fragment in canonical_config:
            fail(f"canonical Superset configuration contains {fragment}")


def validate_role_reconciliation() -> None:
    bootstrap = parse_python(BOOTSTRAP)
    for fragment in (
        "reconcile_base_permissions",
        "security_manager.data_access_permissions",
        "target.permissions = source_permissions + preserved_data_access",
        "from codestra_security_manager import BUSINESS_SLUGS",
    ):
        if fragment not in bootstrap:
            fail(f"role bootstrap omits {fragment}")
    if "def add_base_permissions" in bootstrap:
        fail("additive-only role synchronization is prohibited")


def validate_compose(path: pathlib.Path, expected_services: set[str]) -> None:
    document = load_yaml(path)
    if not isinstance(document, dict):
        fail(f"{path.name} must contain a Compose object")
    services = document.get("services")
    if not isinstance(services, dict) or set(services) != expected_services:
        fail(f"{path.name} service catalogue mismatch")

    source = read(path)
    for forbidden in (
        ":latest",
        "privileged: true",
        "network_mode: host",
        "pid: host",
        "codestra_security_manager_v2.py:",
        "superset_config.py.example:",
        "env_file:",
    ):
        if forbidden in source:
            fail(f"{path.name} contains forbidden runtime drift: {forbidden}")
    for required in (
        "./superset_config.py:/app/pythonpath/superset_config.py:ro",
        "./codestra_security_manager.py:/app/pythonpath/codestra_security_manager.py:ro",
        "./check_metadata_readiness.py:/app/pythonpath/check_metadata_readiness.py:ro",
        "SUPERSET_SECRET_KEY_FILE: /run/secrets/superset_secret_key",
        "SUPERSET_METADATA_DATABASE_URI_FILE: /run/secrets/superset_metadata_database_uri",
        "KEYCLOAK_ISSUER: https://auth.codestra.co/realms/codestra",
    ):
        if required not in source:
            fail(f"{path.name} omits {required}")

    for name, service in services.items():
        if service.get("user") != "10001:10001":
            fail(f"{path.name}:{name} must run as 10001:10001")
        if service.get("read_only") is not True:
            fail(f"{path.name}:{name} must use a read-only root filesystem")
        if "ALL" not in service.get("cap_drop", []):
            fail(f"{path.name}:{name} must drop all capabilities")
        if "no-new-privileges:true" not in service.get("security_opt", []):
            fail(f"{path.name}:{name} must set no-new-privileges")
        image = str(service.get("image", ""))
        if "@sha256:" not in image:
            fail(f"{path.name}:{name} image contract is not digest-bound")
        limits = service.get("deploy", {}).get("resources", {}).get("limits", {})
        for field in ("cpus", "memory", "pids"):
            if field not in limits:
                fail(f"{path.name}:{name} lacks {field} limit")

    web = services["superset-web"]
    ports = web.get("ports", [])
    if len(ports) != 1 or not str(ports[0]).startswith("127.0.0.1:"):
        fail(f"{path.name} web service must publish only on loopback")
    healthcheck = web.get("healthcheck", {})
    if "/app/pythonpath/check_metadata_readiness.py" not in healthcheck.get(
        "test", []
    ):
        fail(f"{path.name} web service lacks metadata readiness")
    for name in ("superset-worker", "superset-beat"):
        if services[name].get("ports"):
            fail(f"{path.name}:{name} may not publish a port")


def validate_compose_contracts() -> None:
    validate_compose(
        CANDIDATE_COMPOSE,
        {"superset-web", "superset-worker", "superset-beat"},
    )
    validate_compose(
        RUNTIME_COMPOSE,
        {"superset-web", "superset-worker", "superset-beat", "superset-bootstrap"},
    )
    runtime = load_yaml(RUNTIME_COMPOSE)
    bootstrap = runtime["services"]["superset-bootstrap"]
    if bootstrap.get("profiles") != ["bootstrap"]:
        fail("runtime bootstrap must remain an explicit one-shot profile")
    command = " ".join(str(part) for part in bootstrap.get("command", []))
    for fragment in ("superset db upgrade", "superset init", "bootstrap_roles.py"):
        if fragment not in command:
            fail(f"runtime bootstrap omits {fragment}")
    web_command = " ".join(
        str(part) for part in runtime["services"]["superset-web"].get("command", [])
    )
    if "db upgrade" in web_command or "superset init" in web_command:
        fail("normal web startup may not run migrations or initialization")


def validate_runtime_contracts() -> None:
    runtime = load_json(RUNTIME_ROOT / "runtime.v1.json")
    control = load_json(RUNTIME_ROOT / "analytics-control-plane.v1.json")
    if runtime.get("canonicalHostname") != EXPECTED_HOST:
        fail("runtime canonical hostname mismatch")
    identity = runtime.get("identity", {})
    if identity.get("issuer") != EXPECTED_ISSUER:
        fail("runtime issuer mismatch")
    if identity.get("pkce") != "S256" or identity.get("anonymousAccess") is not False:
        fail("runtime identity boundary mismatch")
    activation = runtime.get("activation")
    if not isinstance(activation, dict) or not activation:
        fail("runtime activation map is missing")
    if any(value is not False for value in activation.values()):
        fail("runtime activation flags must remain false")
    guardrails = control.get("queryGuardrails", {})
    if guardrails.get("defaultRowLimit") != 10000:
        fail("control-plane default row limit mismatch")
    if guardrails.get("hardRowLimit") != 100000:
        fail("control-plane hard row limit mismatch")
    release_gates = control.get("releaseGates")
    if not isinstance(release_gates, dict) or not release_gates:
        fail("release-gate map is missing")
    if any(value is not False for value in release_gates.values()):
        fail("release gates must remain false before runtime evidence")


def validate_evidence_gate() -> None:
    contract = load_json(EVIDENCE_CONTRACT)
    workflow = read(EVIDENCE_WORKFLOW)
    if contract.get("schema_version") != "1.2":
        fail("staging evidence contract must use schema 1.2")
    evidence = contract.get("staging_evidence", {})
    if evidence.get("state") != "PENDING_ATTESTED_RUNTIME_EXECUTION":
        fail("staging evidence must remain pending an attested execution")
    for field in (
        "manifest_attestation_required",
        "archive_checksum_required",
        "manifest_checksum_required",
    ):
        if evidence.get(field) is not True:
            fail(f"staging evidence omits {field}")
    for fragment in (
        "CODESTRA_EVIDENCE_READER_TOKEN",
        "/actions/runs/${EVIDENCE_RUN_ID}",
        "/artifacts?per_page=100",
        "gh attestation verify",
        "evidence archive checksum mismatch",
        "evidence manifest checksum mismatch",
        'results.get(name) != "PASS"',
        "external effects are not disabled",
        "collector workflow run is not successful",
        "exactly one unexpired evidence artifact is required",
    ):
        if fragment not in workflow:
            fail(f"evidence workflow omits {fragment}")
    for forbidden in (
        "STAGING_EVIDENCE_CHECKSUM",
        "runtime evidence must differ from every release or image checksum",
    ):
        if forbidden in workflow:
            fail(f"evidence workflow retains checksum-only bypass: {forbidden}")
    effects = contract.get("runtime_effects")
    if not isinstance(effects, dict) or not effects:
        fail("runtime-effects map is missing")
    if any(value is not False for value in effects.values()):
        fail("evidence contract authorizes a runtime effect")


def validate_repository_identity() -> None:
    readme = read(ROOT / "README.md")
    profile = read(ROOT / "REPOSITORY_PROFILE.md")
    review = read(ROOT / "docs" / "REPOSITORY-WIDE-REVIEW-2026-09-02.md")
    for path, text in (
        (ROOT / "README.md", readme),
        (ROOT / "REPOSITORY_PROFILE.md", profile),
        (ROOT / "docs" / "REPOSITORY-WIDE-REVIEW-2026-09-02.md", review),
    ):
        for fragment in (
            "supe.codestra.media",
            "source prepared",
            "not deployed",
        ):
            if fragment.lower() not in text.lower():
                fail(f"{path.name} omits repository state: {fragment}")

    adoption = load_json(ROOT / "orbit" / "adoption-manifest.json")
    if adoption.get("repository") != "appolon1908-hue/Superset":
        fail("Orbit repository identity mismatch")
    if adoption.get("domain") != EXPECTED_HOST:
        fail("Orbit domain mismatch")
    if adoption.get("targetBranch") != "development":
        fail("Orbit adoption must enter through development")
    if adoption.get("status") != "blocked-pending-orbit-authority-merge":
        fail("Orbit adoption must remain fail-closed")
    authority = adoption.get("orbitAuthority", {})
    if authority.get("repository") != "appolon1908-hue/SDK-repository":
        fail("Orbit SDK authority mismatch")
    if authority.get("pullRequest") != 75:
        fail("Orbit authority pull request mismatch")
    if authority.get("requiredExactHeadSha") != EXPECTED_ORBIT_SHA:
        fail("Orbit authority exact-head mismatch")
    activation = adoption.get("activation")
    if not isinstance(activation, dict) or not activation:
        fail("Orbit activation map is missing")
    if any(value is not False for value in activation.values()):
        fail("Orbit activation must remain false")


def validate_secret_safety() -> None:
    roots = (
        ROOT / "codestra",
        ROOT / "integration",
        ROOT / "orbit",
        ROOT / "docs",
    )
    signatures = (
        "-----BEGIN PRIVATE KEY-----",
        "-----BEGIN OPENSSH PRIVATE KEY-----",
        "AKIA",
    )
    for root in roots:
        for path in root.rglob("*"):
            if (
                not path.is_file()
                or "__pycache__" in path.parts
                or path.resolve() == pathlib.Path(__file__).resolve()
            ):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for signature in signatures:
                if signature in text:
                    fail(f"secret-shaped material found in {path.relative_to(ROOT)}")


def main() -> None:
    validate_required_files()
    validate_json_catalogue()
    validate_upstream_lock()
    validate_identity_and_configuration()
    validate_role_reconciliation()
    validate_compose_contracts()
    validate_runtime_contracts()
    validate_evidence_gate()
    validate_repository_identity()
    validate_secret_safety()
    print("CODESTRA_SUPERSET_REPOSITORY_WIDE_VALIDATION=PASS")


if __name__ == "__main__":
    main()
