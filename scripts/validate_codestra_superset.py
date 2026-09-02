#!/usr/bin/env python3
"""Fail-closed validation for the Codestra Superset corporate overlay."""

from __future__ import annotations

import ast
import json
import pathlib
import re
import sys
from typing import Any

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CODESTRA = ROOT / "codestra"
RUNTIME = CODESTRA / "runtime-v1" / "runtime.v1.json"
CONTROL = CODESTRA / "runtime-v1" / "analytics-control-plane.v1.json"
CONFIG = CODESTRA / "runtime-v1" / "superset_config.py"
SECURITY_MANAGER = CODESTRA / "runtime-v1" / "codestra_security_manager.py"
COMPOSE = CODESTRA / "runtime-v1" / "compose.production.yaml"
OPERATING_MODEL = CODESTRA / "docs" / "OPERATING-MODEL.md"
CORPORATE_FEATURES = CODESTRA / "docs" / "CORPORATE-FEATURES.md"

BUSINESSES = {
    "codestra",
    "moneybee",
    "beyvra",
    "breero",
    "larim-a",
    "transportation",
    "booked4seasons",
    "social",
    "klyrow",
    "telnexa",
    "kyqra",
    "restaurant",
    "provisioning",
}
REQUIRED_SERVICES = {
    "superset-migrate",
    "superset-web",
    "superset-worker",
    "superset-beat",
}
IMMUTABLE_IMAGE = (
    "docker.io/apache/superset@"
    "sha256:07d08f5dae5ffd50e4b3a1efda6abd5da1823cd8cc65172cdbb1c6d5f45b24d8"
)
REQUIRED_SECRET_FILES = {
    "SUPERSET_SECRET_KEY_FILE",
    "SUPERSET_METADATA_DATABASE_URI_FILE",
    "SUPERSET_REDIS_URL_FILE",
    "SUPERSET_OIDC_CLIENT_SECRET_FILE",
}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def require_file(path: pathlib.Path) -> str:
    if not path.is_file():
        fail(f"missing required file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def load_json(path: pathlib.Path) -> Any:
    try:
        return json.loads(require_file(path))
    except Exception as exc:
        fail(f"invalid JSON {path.relative_to(ROOT)}: {exc}")


def load_yaml(path: pathlib.Path) -> Any:
    try:
        return yaml.safe_load(require_file(path))
    except Exception as exc:
        fail(f"invalid YAML {path.relative_to(ROOT)}: {exc}")


def validate_runtime() -> None:
    runtime = load_json(RUNTIME)
    if runtime.get("schemaVersion") != "1.0" or runtime.get("component") != "superset":
        fail("Superset runtime identity mismatch")
    if runtime.get("canonicalHostname") != "supe.codestra.media":
        fail("canonical Superset hostname mismatch")
    if runtime.get("hostBind") != "127.0.0.1:8088":
        fail("Superset native listener must remain loopback-only")
    if runtime.get("status") != "PRODUCTION_CONFIG_READY_NOT_DEPLOYED":
        fail("Superset runtime must remain production-config-ready/not-deployed")
    if set(runtime.get("businessScope", [])) != BUSINESSES:
        fail("Superset business catalogue mismatch")

    identity = runtime.get("identity", {})
    if identity.get("provider") != "keycloak":
        fail("Superset identity provider must be Keycloak")
    if identity.get("issuer") != "https://auth.codestra.co/realms/codestra":
        fail("Superset Keycloak issuer mismatch")
    if identity.get("pkce") != "S256" or identity.get("ssoRequired") is not True:
        fail("Superset must require SSO and PKCE S256")
    if identity.get("anonymousAccess") is not False:
        fail("anonymous Superset access must remain disabled")

    control = runtime.get("analyticsControlPlane", {})
    required_true = (
        "curatedDatasetsOnly",
        "datasetCertificationRequired",
        "semanticMetricsRequired",
        "rowLevelSecurityRequired",
        "piiMaskingRequired",
        "queryRowAndTimeLimitsRequired",
        "dashboardAndDatasetChangeAuditRequired",
    )
    for field in required_true:
        if control.get(field) is not True:
            fail(f"Superset control must remain enabled: {field}")
    for field in (
        "productionWriteConnections",
        "directProviderAdminDatabaseAccess",
        "rawOperationalDatabaseAccess",
    ):
        if control.get(field) is not False:
            fail(f"Superset data boundary must remain false: {field}")

    scheduled = runtime.get("scheduledReporting", {})
    if scheduled.get("directUnapprovedEmailOrSmsDelivery") is not False:
        fail("Superset may not directly deliver unapproved reports")
    if scheduled.get("enabledBeforeApproval") is not False:
        fail("scheduled reporting must remain disabled before approval")

    activation = runtime.get("activation", {})
    if activation.get("immutableImageRecorded") is not True:
        fail("Superset immutable image must be recorded")
    if any(
        value is not False
        for field, value in activation.items()
        if field != "immutableImageRecorded"
    ):
        fail("all live Superset activation gates must remain false")


def validate_control_plane() -> None:
    control = load_json(CONTROL)
    if control.get("status") != "PRODUCTION_CONTROL_PLANE_DESIRED_STATE_READY_NOT_APPLIED":
        fail("Superset analytics control plane must remain unapplied")
    if set(control.get("businesses", [])) != BUSINESSES:
        fail("Superset control-plane business catalogue mismatch")
    if control.get("businessColumn") != "codestra_business":
        fail("Superset business RLS column mismatch")

    role_model = control.get("roleModel", {})
    for role in (
        "superset-admin",
        "superset-analyst",
        "superset-viewer",
        "superset-security-auditor",
        "business-<business>-viewer",
        "business-<business>-analyst",
    ):
        if role not in role_model:
            fail(f"Superset role model omits {role}")
    for role in ("business-<business>-viewer", "business-<business>-analyst"):
        if role_model[role].get("rlsClause") != "codestra_business = '<business>'":
            fail(f"Superset business role has unsafe RLS clause: {role}")

    datasets = control.get("datasetRequirements", {})
    for field in (
        "certified",
        "ownerRequired",
        "freshnessSlaRequired",
        "businessColumnRequired",
        "readOnlyConnectionRequired",
        "reportingSchemaOrReplicaRequired",
        "rawPiiColumnsDefaultHidden",
    ):
        if datasets.get(field) is not True:
            fail(f"Superset dataset requirement missing: {field}")
    for field in (
        "freeFormSqlOnProductionSources",
        "writeDmlOrDdl",
        "providerAdministrationSources",
    ):
        if datasets.get(field) is not False:
            fail(f"Superset forbidden datasource capability enabled: {field}")

    guardrails = control.get("queryGuardrails", {})
    if guardrails.get("defaultRowLimit") != 10000:
        fail("Superset default row limit mismatch")
    if not 10000 <= int(guardrails.get("hardRowLimit", 0)) <= 100000:
        fail("Superset hard row limit must be bounded")
    if not 1 <= int(guardrails.get("interactiveTimeoutSeconds", 0)) <= 60:
        fail("Superset interactive timeout must be bounded")
    if guardrails.get("crossDatabaseQueries") is not False:
        fail("Superset cross-database queries must remain disabled")
    if guardrails.get("templateProcessing") is not False:
        fail("Superset template processing must remain disabled")

    release_gates = control.get("releaseGates", {})
    if not release_gates or any(value is not False for value in release_gates.values()):
        fail("Superset release gates must remain false before evidence exists")

    catalogue = control.get("dashboardCatalogue", [])
    if not catalogue or any(not item.get("owner") for item in catalogue):
        fail("every Superset dashboard definition requires an owner")

    governance = load_json(CODESTRA / "runtime-v1" / "analytics-governance.json")
    for dataset in governance.get("certifiedDatasets", []):
        for field in (
            "owner",
            "sourceLineage",
            "freshnessSlaMinutes",
            "sensitivity",
            "readOnly",
        ):
            if field not in dataset:
                fail(f"certified dataset {dataset.get('name')} omits {field}")
        if dataset["readOnly"] is not True or dataset["freshnessSlaMinutes"] <= 0:
            fail(f"certified dataset {dataset.get('name')} has unsafe governance")


def validate_python_configuration() -> None:
    config_text = require_file(CONFIG)
    manager_text = require_file(SECURITY_MANAGER)
    for path, text in ((CONFIG, config_text), (SECURITY_MANAGER, manager_text)):
        try:
            ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            fail(f"invalid Python {path.relative_to(ROOT)}: {exc}")

    for variable in REQUIRED_SECRET_FILES:
        if variable not in config_text:
            fail(f"Superset config omits secret-file variable {variable}")
    for fragment in (
        'AUTH_TYPE = AUTH_OAUTH',
        'AUTH_ROLES_SYNC_AT_LOGIN = True',
        '"code_challenge_method": "S256"',
        '"ROW_LEVEL_SECURITY": True',
        '"DASHBOARD_RBAC": True',
        '"ALERT_REPORTS": False',
        '"ENABLE_TEMPLATE_PROCESSING": False',
        'ENABLE_CORS = False',
        'PUBLIC_ROLE_LIKE = None',
        'EMAIL_NOTIFICATIONS = False',
        'FAB_ADD_SECURITY_API = False',
        'PREVENT_UNSAFE_DB_CONNECTIONS = True',
        'RATELIMIT_STORAGE_URI = REDIS_URL',
        'MCP_AUTH_ENABLED = False',
        'MCP_API_KEY_ENABLED = False',
        '"content_security_policy_nonce_in": ["script-src"]',
        '"superset.sql_lab"',
        '"version_history.prune_old_versions"',
        '"deletion_retention.purge_soft_deleted"',
    ):
        if fragment not in config_text:
            fail(f"Superset config omits corporate control: {fragment}")

    for business in BUSINESSES:
        if f'"{business}"' not in manager_text:
            fail(f"Superset security manager omits business: {business}")
    for fragment in (
        'provider != "keycloak"',
        'email_verified") is not True',
        'resource_access',
        'APPROVED_ROLE_KEYS',
        'role_keys',
        'protocol/openid-connect/userinfo',
    ):
        if fragment not in manager_text:
            fail(f"Superset security manager omits fail-closed behavior: {fragment}")

    forbidden = (
        "SUPERSET_SECRET_KEY =",
        "client_secret\": \"",
        "postgresql://superset:",
        "redis://:",
        "smtp_password",
        "InsecureSkipVerify",
    )
    lowered = (config_text + manager_text).lower()
    for fragment in forbidden:
        if fragment.lower() in lowered:
            fail(f"Superset configuration contains forbidden secret/bypass pattern: {fragment}")


def validate_compose() -> None:
    compose = load_yaml(COMPOSE)
    services = compose.get("services", {})
    if set(services) != REQUIRED_SERVICES:
        fail("Superset candidate must define web, worker and beat services")

    for name, service in services.items():
        if service.get("read_only") is not True:
            fail(f"Superset service must use a read-only root filesystem: {name}")
        if service.get("user") != "superset":
            fail(f"Superset service must run non-root: {name}")
        if "ALL" not in service.get("cap_drop", []):
            fail(f"Superset service must drop all capabilities: {name}")
        if "no-new-privileges:true" not in service.get("security_opt", []):
            fail(f"Superset service must set no-new-privileges: {name}")
        if service.get("privileged") is True or service.get("network_mode") == "host":
            fail(f"Superset service has forbidden host authority: {name}")
        image = str(service.get("image", ""))
        if image != IMMUTABLE_IMAGE:
            fail(f"Superset image contract is not immutable: {name}")
        limits = service.get("deploy", {}).get("resources", {}).get("limits", {})
        for field in ("cpus", "memory", "pids"):
            if field not in limits:
                fail(f"Superset service {name} lacks {field} limit")

    if services["superset-migrate"].get("profiles") != ["migrate"]:
        fail("Superset migration must require the explicit migrate profile")
    if services["superset-migrate"].get("restart") != "no":
        fail("Superset migration must be a one-shot operation")
    migration_command = " ".join(services["superset-migrate"].get("command", []))
    if "superset db upgrade" not in migration_command:
        fail("Superset migration service must apply reviewed migrations")
    for name in ("superset-web", "superset-worker", "superset-beat"):
        if "superset db upgrade" in " ".join(services[name].get("command", [])):
            fail(f"routine service may not automatically migrate: {name}")
    for name, service in services.items():
        if "check_release_identity.py" not in " ".join(service.get("command", [])):
            fail(f"runtime release identity is not verified before startup: {name}")

    web_ports = services["superset-web"].get("ports", [])
    if len(web_ports) != 1 or not str(web_ports[0]).startswith("127.0.0.1:"):
        fail("Superset web port must bind only to loopback")
    if any(services[name].get("ports") for name in ("superset-migrate", "superset-worker", "superset-beat")):
        fail("Superset background services may not publish ports")
    if not services["superset-web"].get("healthcheck"):
        fail("Superset web service requires a healthcheck")

    serialized = require_file(COMPOSE)
    for fragment in (
        ":latest",
        "privileged: true",
        "network_mode: host",
        "pid: host",
        "0.0.0.0:8088:8088",
        "SUPERSET_SECRET_KEY=",
        "SUPERSET_OIDC_CLIENT_SECRET=",
    ):
        if fragment in serialized:
            fail(f"Superset production configuration contains forbidden content: {fragment}")


def validate_docs_and_secret_safety() -> None:
    for path in (OPERATING_MODEL, CORPORATE_FEATURES):
        text = require_file(path).lower()
        for token in ("keycloak", "row-level", "read-only", "openbao", "beyvra"):
            if token not in text:
                fail(f"Superset documentation {path.name} omits {token}")

    signatures = (
        "-----BEGIN PRIVATE KEY-----",
        "-----BEGIN OPENSSH PRIVATE KEY-----",
        "AKIA",
    )
    for path in CODESTRA.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for signature in signatures:
            if signature in text:
                fail(f"secret-shaped material found in {path.relative_to(ROOT)}")


def main() -> None:
    validate_runtime()
    validate_control_plane()
    validate_python_configuration()
    validate_compose()
    validate_docs_and_secret_safety()
    print("Codestra Superset corporate configuration validation PASS")


if __name__ == "__main__":
    main()
