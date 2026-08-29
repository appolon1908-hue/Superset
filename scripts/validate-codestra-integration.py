#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "config" / "codestra" / "runtime.v1.json"
SUPERSET_CONFIG = ROOT / "config" / "codestra" / "superset_config.py.example"
SECURITY_MANAGER = (
    ROOT / "config" / "codestra" / "custom_keycloak_security_manager.py.example"
)


def fail(message: str) -> None:
    print(f"SUPERSET_CODESTRA_VALIDATION_ERROR={message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    data = json.loads(RUNTIME.read_text(encoding="utf-8"))
    if data.get("hostname") != "supe.codestra.media":
        fail("canonical hostname mismatch")
    if data.get("hostBind") != "127.0.0.1:8088":
        fail("Superset host port must bind to loopback")
    if data.get("publicNativePortAllowed") is not False:
        fail("native Superset port must not be public")

    oidc = data.get("oidc", {})
    if oidc.get("issuer") != "https://auth.codestra.co/realms/codestra":
        fail("issuer mismatch")
    if oidc.get("clientId") != "superset-analytics":
        fail("client ID mismatch")
    if oidc.get("callback") != "https://supe.codestra.media/oauth-authorized/keycloak":
        fail("callback mismatch")
    if oidc.get("pkce") != "S256":
        fail("PKCE S256 is required")

    policy = data.get("dataPolicy", {})
    if policy.get("curatedReadModelsOnly") is not True:
        fail("Superset must use curated read models")
    if policy.get("liveProviderAdminDatabasesAllowed") is not False:
        fail("live provider administration databases are prohibited")
    if policy.get("writeCredentialsAllowed") is not False:
        fail("write credentials are prohibited")
    if policy.get("rowLevelSecurityRequired") is not True:
        fail("row-level security is required")
    if any(value is True for value in data.get("activation", {}).values()):
        fail("source branch must not activate deployment")

    config_text = SUPERSET_CONFIG.read_text(encoding="utf-8")
    manager_text = SECURITY_MANAGER.read_text(encoding="utf-8")
    for path, text in ((SUPERSET_CONFIG, config_text), (SECURITY_MANAGER, manager_text)):
        try:
            ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            fail(f"invalid Python example {path}: {exc}")

    required_fragments = (
        'AUTH_TYPE = AUTH_OAUTH',
        '"superset-analytics"',
        'SUPERSET_OIDC_CLIENT_SECRET',
        'code_challenge_method',
        '"S256"',
        'AUTH_ROLES_SYNC_AT_LOGIN = True',
        'ENABLE_PROXY_FIX = True',
        'SESSION_COOKIE_SECURE = True',
        'CUSTOM_SECURITY_MANAGER = CustomKeycloakSecurityManager',
    )
    for fragment in required_fragments:
        if fragment not in config_text:
            fail(f"Superset configuration is missing {fragment}")

    for role in (
        "observability-viewer",
        "observability-operator",
        "observability-admin",
    ):
        if role not in config_text or role not in manager_text:
            fail(f"role mapping is incomplete for {role}")

    prohibited = ("client_secret = '...", "client_secret = \"...", "postgresql://")
    if any(fragment in config_text for fragment in prohibited):
        fail("example contains an embedded secret or database URL")

    print("SUPERSET_CODESTRA_INTEGRATION_VALID=1")


if __name__ == "__main__":
    main()
