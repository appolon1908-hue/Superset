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
RUNTIME_ROOT = CODESTRA / "runtime-v1"
RUNTIME = RUNTIME_ROOT / "runtime.v1.json"
CONTROL = RUNTIME_ROOT / "analytics-control-plane.v1.json"
ACTIVE_CONFIG = RUNTIME_ROOT / "superset_config.py"
IMAGE_CONFIG = RUNTIME_ROOT / "superset_config.py.example"
SECURITY_MANAGER = RUNTIME_ROOT / "codestra_security_manager.py"
COMPATIBILITY_MANAGER = RUNTIME_ROOT / "codestra_security_manager_v2.py"
BOOTSTRAP = RUNTIME_ROOT / "bootstrap_roles.py"
COMPOSE = RUNTIME_ROOT / "compose.candidate.yaml"
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
    "superset-web",
    "superset-worker",
    "superset-beat",
    "superset-bootstrap",
}
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
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"invalid JSON {path.relative_to(ROOT)}: {exc}")


def load_yaml(path: pathlib.Path) -> Any:
    try:
        return yaml.safe_load(require_file(path))
    except (OSError, yaml.YAMLError) as exc:
        fail(f"invalid YAML {path.relative_to(ROOT)}: {exc}")


def validate_runtime() -> None:
    runtime = load_json(RUNTIME)
    if runtime.get("schemaVersion") != "1.0" or runtime.get("component") != "superset":
        fail("Superset runtime identity mismatch")
    if runtime.get("canonicalHostname") != "supe.codestra.media":
        fail("canonical Superset hostname mismatch")
    if runtime.get("hostBind") != "127.0.0.1:8088":
        fail("Superset native listener must remain loopback-only")
    if runtime.get("status") != "CONFIG_PREPARED_NOT_DEPLOYED":
        fail("Superset runtime must remain source prepared and not deployed")
    if set(runtime.get("businessScope", [])) != BUSINESSES:
        fail("Superset business catalogue mismatch")

    identity = runtime.get("identity", {})
    expected_identity = {
        "provider": "keycloak",
        "issuer": "https://auth.codestra.co/realms/codestra",
        "clientId": "superset-analytics",
        "pkce": "S256",
        "ssoRequired": True,
        "anonymousAccess": False,
        "selfRegistrationWithoutApprovedRole": False,
        "roleSyncAtLogin": True,
    }
    for key, expected in expected_identity.items():
        if identity.get(key) != expected:
            fail(f"Superset identity contract mismatch: {key}")

    analytics = runtime.get("analyticsControlPlane", {})
    for field in (
        "curatedDatasetsOnly",
        "datasetCertificationRequired",
        "semanticMetricsRequired",
        "rowLevelSecurityRequired",
        "preferReportingSchemasReadReplicasOrWarehouse",
        "piiMaskingRequired",
        "queryRowAndTimeLimitsRequired",
        "dashboardAndDatasetChangeAuditRequired",
    ):
        if analytics.get(field) is not True:
            fail(f"Superset analytics control must remain true: {field}")
    for field in (
        "productionWriteConnections",
        "directProviderAdminDatabaseAccess",
        "rawOperationalDatabaseAccess",
    ):
        if analytics.get(field) is not False:
            fail(f"Superset data boundary must remain false: {field}")

    scheduled = runtime.get("scheduledReporting", {})
    if scheduled.get("directUnapprovedEmailOrSmsDelivery") is not False:
        fail("Superset may not directly deliver unapproved reports")
    if scheduled.get("enabledBeforeApproval") is not False:
        fail("scheduled reporting must remain disabled before approval")

    activation = runtime.get("activation", {})
    if not activation or any(value is not False for value in activation.values()):
        fail("all Superset activation gates must remain false")


def validate_control_plane() -> None:
    control = load_json(CONTROL)
    if control.get("status") != "CONTROL_PLANE_PREPARED_NOT_APPLIED":
        fail("Superset analytics control plane must remain unapplied")
    if set(control.get("businesses", [])) != BUSINESSES:
        fail("Superset control-plane business catalogue mismatch")
    if control.get("businessColumn") != "codestra_business":
        fail("Superset business RLS column mismatch")

    role_model = control.get("roleModel", {})
    required_roles = {
        "superset-admin",
        "superset-analyst",
        "superset-viewer",
        "superset-security-auditor",
        "business-<business>-viewer",
        "business-<business>-analyst",
    }
    if not required_roles.issubset(role_model):
        fail("Superset role model is incomplete")
    for role in ("business-<business>-viewer", "business-<business>-analyst"):
        if role_model[role].get("rlsClause") != "codestra_business = '<business>'":
            fail(f"Superset business role has unsafe RLS clause: {role}")

    datasets = control.get("datasetRequirements", {})
    for field in (
        "certified",
        "ownerRequired",
        "descriptionRequired",
        "freshnessSlaRequired",
        "businessColumnRequired",
        "sensitivityClassificationRequired",
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
    if guardrails.get("hardRowLimit") != 100000:
        fail("Superset hard row limit mismatch")
    if not 1 <= int(guardrails.get("interactiveTimeoutSeconds", 0)) <= 60:
        fail("Superset interactive timeout must be bounded")
    if guardrails.get("crossDatabaseQueries") is not False:
        fail("Superset cross-database queries must remain disabled")
    if guardrails.get("templateProcessing") is not False:
        fail("Superset template processing must remain disabled")

    release_gates = control.get("releaseGates", {})
    if not release_gates or any(value is not False for value in release_gates.values()):
        fail("Superset release gates must remain false before runtime evidence exists")


def validate_python_configuration() -> None:
    active_text = require_file(ACTIVE_CONFIG)
    image_text = require_file(IMAGE_CONFIG)
    manager_text = require_file(SECURITY_MANAGER)
    compatibility_manager_text = require_file(COMPATIBILITY_MANAGER)
    bootstrap_text = require_file(BOOTSTRAP)

    if active_text != image_text:
        fail("active and image-build Superset configurations diverge")
    if manager_text != compatibility_manager_text:
        fail("canonical and compatibility security managers diverge")

    for path, text in (
        (ACTIVE_CONFIG, active_text),
        (IMAGE_CONFIG, image_text),
        (SECURITY_MANAGER, manager_text),
        (COMPATIBILITY_MANAGER, compatibility_manager_text),
        (BOOTSTRAP, bootstrap_text),
    ):
        try:
            ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            fail(f"invalid Python {path.relative_to(ROOT)}: {exc}")

    for variable in REQUIRED_SECRET_FILES:
        if variable not in image_text:
            fail(f"Superset config omits secret-file variable {variable}")

    required_config = (
        "AUTH_TYPE = AUTH_OAUTH",
        "AUTH_ROLES_SYNC_AT_LOGIN = True",
        '"code_challenge_method": "S256"',
        '"ROW_LEVEL_SECURITY": True',
        '"DASHBOARD_RBAC": True',
        '"ALERT_REPORTS": False',
        '"ENABLE_TEMPLATE_PROCESSING": False',
        "ROW_LIMIT = 10000",
        "SQL_MAX_ROW = 100000",
        "ENABLE_CORS = False",
        "PUBLIC_ROLE_LIKE = None",
        "EMAIL_NOTIFICATIONS = False",
        '"force_https": False',
        '"script-src": ["\'self\'", "\'strict-dynamic\'"]',
        '"content_security_policy_nonce_in": ["script-src"]',
        "from celery.schedules import crontab",
        '"superset.sql_lab"',
        '"superset.tasks.scheduler"',
        '"superset.tasks.thumbnails"',
        '"superset.tasks.cache"',
        '"superset.tasks.slack"',
        '"sql_lab.get_sql_results"',
        '"reports.scheduler"',
        '"reports.prune_log"',
    )
    for fragment in required_config:
        if fragment not in image_text:
            fail(f"Superset config omits runtime control: {fragment}")

    forbidden_config = (
        '"force_https": True',
        "SUPERSET_SECRET_KEY =",
        'client_secret": "',
        "postgresql://superset:",
        "redis://:",
        "smtp_password",
        "InsecureSkipVerify",
        '"superset.tasks.deletion_retention"',
        '"superset.tasks.version_history_retention"',
        '"superset.tasks.export_dashboard_excel"',
        '"deletion_retention.purge_soft_deleted"',
        '"version_history.prune_old_versions"',
    )
    lowered = (image_text + manager_text).lower()
    for fragment in forbidden_config:
        if fragment.lower() in lowered:
            fail(f"Superset configuration contains forbidden pattern: {fragment}")

    for business in BUSINESSES:
        if f'"{business}"' not in manager_text:
            fail(f"Superset security manager omits business: {business}")
    for fragment in (
        'provider != "keycloak"',
        'email_verified") is not True',
        "resource_access",
        "APPROVED_ROLE_KEYS",
        "role_keys",
        "protocol/openid-connect/userinfo",
    ):
        if fragment not in manager_text:
            fail(f"Superset security manager omits fail-closed behavior: {fragment}")

    if "from superset import app" in bootstrap_text:
        fail("role bootstrap treats the superset.app module as a Flask app")
    for fragment in (
        "from superset.app import create_app",
        "application = create_app()",
        "with application.app_context():",
        "CODESTRA_SUPERSET_ROLE_BOOTSTRAP=PASS",
    ):
        if fragment not in bootstrap_text:
            fail(f"role bootstrap omits application-factory control: {fragment}")


def validate_compose() -> None:
    compose = load_yaml(COMPOSE)
    services = compose.get("services", {})
    if set(services) != REQUIRED_SERVICES:
        fail("Superset candidate topology mismatch")

    for name, service in services.items():
        if service.get("read_only") is not True:
            fail(f"Superset service must use a read-only root filesystem: {name}")
        if service.get("user") != "10001:10001":
            fail(f"Superset service must run as 10001:10001: {name}")
        if "ALL" not in service.get("cap_drop", []):
            fail(f"Superset service must drop all capabilities: {name}")
        if "no-new-privileges:true" not in service.get("security_opt", []):
            fail(f"Superset service must set no-new-privileges: {name}")
        if service.get("privileged") is True or service.get("network_mode") == "host":
            fail(f"Superset service has forbidden host authority: {name}")

        image = str(service.get("image", ""))
        if "CODESTRA_SUPERSET_IMAGE" not in image or "@sha256:" not in image:
            fail(f"Superset service lacks immutable Codestra image contract: {name}")

        limits = service.get("deploy", {}).get("resources", {}).get("limits", {})
        for field in ("cpus", "memory", "pids"):
            if field not in limits:
                fail(f"Superset service {name} lacks {field} limit")
        if int(service.get("pids_limit", 0)) != int(limits["pids"]):
            fail(f"Superset service pids_limit differs from deploy limit: {name}")

        expected_profile = (
            ["bootstrap-after-approval"]
            if name == "superset-bootstrap"
            else ["candidate-after-approval"]
        )
        if service.get("profiles") != expected_profile:
            fail(f"Superset service has incorrect inactive profile: {name}")

    normal_services = ("superset-web", "superset-worker", "superset-beat")
    for name in normal_services:
        command = " ".join(str(part) for part in services[name].get("command", []))
        for forbidden in ("superset db upgrade", "superset init", "bootstrap_roles.py"):
            if forbidden in command:
                fail(f"routine service performs one-shot initialization: {name}")

    bootstrap_command = " ".join(
        str(part) for part in services["superset-bootstrap"].get("command", [])
    )
    for required in ("superset db upgrade", "superset init", "bootstrap_roles.py"):
        if required not in bootstrap_command:
            fail(f"one-shot bootstrap omits required step: {required}")

    web_ports = services["superset-web"].get("ports", [])
    if len(web_ports) != 1 or not str(web_ports[0]).startswith("127.0.0.1:"):
        fail("Superset web port must bind only to loopback")
    if services["superset-worker"].get("ports") or services["superset-beat"].get("ports"):
        fail("Superset background services may not publish ports")

    healthcheck = services["superset-web"].get("healthcheck", {})
    if "check_metadata_readiness.py" not in " ".join(
        str(part) for part in healthcheck.get("test", [])
    ):
        fail("Superset web healthcheck must execute metadata readiness")

    common = compose.get("x-superset-common", {})
    if "build" in common or "env_file" in common:
        fail("Superset Compose must remain deploy-only and file-secret-bound")
    mounted = " ".join(str(value) for value in common.get("volumes", []))
    if "/app/pythonpath/" in mounted:
        fail("Superset runtime code/configuration must be embedded in the image")

    secret_definitions = compose.get("secrets", {})
    if set(secret_definitions) != {
        "superset_secret_key",
        "superset_metadata_database_uri",
        "superset_redis_url",
        "superset_oidc_client_secret",
    }:
        fail("Superset top-level secret-file set is incomplete")
    for name, value in secret_definitions.items():
        if set(value) != {"file"} or not str(value["file"]).startswith("${SUPERSET_"):
            fail(f"Superset secret is not supplied as an external file: {name}")

    serialized = require_file(COMPOSE)
    for fragment in (
        ":latest",
        "privileged: true",
        "network_mode: host",
        "pid: host",
        "0.0.0.0:8088:8088",
        "SUPERSET_SECRET_KEY=",
        "SUPERSET_OIDC_CLIENT_SECRET=",
        "env_file:",
    ):
        if fragment in serialized:
            fail(f"Superset candidate contains forbidden content: {fragment}")


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
    print("CODESTRA_SUPERSET_CORPORATE_CONFIGURATION=PASS")


if __name__ == "__main__":
    main()
