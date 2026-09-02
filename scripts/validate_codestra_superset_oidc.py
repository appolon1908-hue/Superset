#!/usr/bin/env python3
"""Validate the exact Codestra Superset Keycloak and private-edge contract."""

from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNTIME_PATH = ROOT / "codestra" / "runtime-v1" / "runtime.v1.json"
COMPOSE_PATH = ROOT / "codestra" / "runtime-v1" / "compose.production.yaml"
CONFIG_PATH = ROOT / "codestra" / "runtime-v1" / "superset_config.py"

ISSUER = "https://auth.codestra.co/realms/codestra"
CLIENT_ID = "superset-analytics"
CALLBACK = "https://supe.codestra.media/oauth-authorized/keycloak"
SECRET_FILE = "/run/secrets/superset_oidc_client_secret"


def fail(message: str) -> None:
    print(f"SUPERSET_OIDC_VALIDATION_ERROR={message}", file=sys.stderr)
    raise SystemExit(1)


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot parse {path.relative_to(ROOT)}: {exc}")
    if not isinstance(value, dict):
        fail(f"{path.relative_to(ROOT)} must contain an object")
    return value


def load_yaml(path: pathlib.Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        fail(f"cannot parse {path.relative_to(ROOT)}: {exc}")
    if not isinstance(value, dict):
        fail(f"{path.relative_to(ROOT)} must contain an object")
    return value


def main() -> None:
    runtime = load_json(RUNTIME_PATH)
    if runtime.get("canonicalHostname") != "supe.codestra.media":
        fail("canonical hostname mismatch")
    if runtime.get("hostBind") != "127.0.0.1:8088":
        fail("native Superset listener must remain loopback-only")
    if runtime.get("status") != "PRODUCTION_CONFIG_READY_NOT_DEPLOYED":
        fail("Superset must remain production-config-ready/not-deployed")

    identity = runtime.get("identity", {})
    expected_identity = {
        "provider": "keycloak",
        "issuer": ISSUER,
        "clientId": CLIENT_ID,
        "callback": CALLBACK,
        "authorizationCode": True,
        "pkce": "S256",
        "ssoRequired": True,
        "anonymousAccess": False,
        "selfRegistrationWithoutApprovedRole": False,
        "roleSyncAtLogin": True,
    }
    for key, expected in expected_identity.items():
        if identity.get(key) != expected:
            fail(f"identity contract mismatch for {key}")

    activation = runtime.get("activation")
    if not isinstance(activation, dict) or not activation:
        fail("runtime activation map is missing")
    enabled = sorted(
        key
        for key, value in activation.items()
        if key != "immutableImageRecorded" and value is not False
    )
    if enabled:
        fail(f"runtime activation must remain false: {enabled}")
    if activation.get("immutableImageRecorded") is not True:
        fail("runtime must record the immutable image")

    compose = load_yaml(COMPOSE_PATH)
    common = compose.get("x-superset-common", {})
    environment = common.get("environment", {})
    if environment.get("SUPERSET_OAUTH_CLIENT_ID") != CLIENT_ID:
        fail("Compose OIDC client ID mismatch")
    if environment.get("SUPERSET_OIDC_CLIENT_SECRET_FILE") != SECRET_FILE:
        fail("Compose OIDC client-secret file mismatch")
    if "SUPERSET_OIDC_CLIENT_SECRET" in environment:
        fail("raw OIDC client secret environment variable is prohibited")

    services = compose.get("services", {})
    web = services.get("superset-web", {})
    ports = web.get("ports", [])
    if len(ports) != 1 or not str(ports[0]).startswith("127.0.0.1:"):
        fail("Superset web publication must remain loopback-only")
    for name in ("superset-worker", "superset-beat"):
        if services.get(name, {}).get("ports"):
            fail(f"{name} must not publish a port")

    try:
        config = CONFIG_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        fail(f"cannot read {CONFIG_PATH.relative_to(ROOT)}: {exc}")
    for required in (
        '"name": "keycloak"',
        '"superset-analytics"',
        'read_secret("SUPERSET_OIDC_CLIENT_SECRET_FILE")',
        'os.environ["KEYCLOAK_ISSUER"]',
        '"code_challenge_method": "S256"',
        'AUTH_ROLES_SYNC_AT_LOGIN = True',
    ):
        if required not in config:
            fail(f"Superset configuration omits OIDC control: {required}")
    for forbidden in (
        "client_secret\": \"",
        "SUPERSET_OIDC_CLIENT_SECRET =",
        "AUTH_ANONYMOUS",
        "InsecureSkipVerify",
    ):
        if forbidden in config:
            fail(f"Superset configuration contains forbidden OIDC pattern: {forbidden}")

    print("CODESTRA_SUPERSET_OIDC_VALIDATION_PASS=1")


if __name__ == "__main__":
    main()
