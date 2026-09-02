from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlsplit

from superset.security import SupersetSecurityManager


DEFAULT_KEYCLOAK_ISSUER = "https://auth.codestra.co/realms/codestra"
BUSINESS_SLUGS = {
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
GLOBAL_ROLE_KEYS = {
    "superset-admin",
    "superset-analyst",
    "superset-viewer",
    "superset-security-auditor",
}
BUSINESS_ROLE_KEYS = {
    f"business-{business}-{access}"
    for business in BUSINESS_SLUGS
    for access in ("viewer", "analyst")
}
APPROVED_ROLE_KEYS = GLOBAL_ROLE_KEYS | BUSINESS_ROLE_KEYS


def keycloak_issuer() -> str:
    """Return a validated, absolute HTTPS Keycloak issuer."""

    issuer = os.environ.get("KEYCLOAK_ISSUER", DEFAULT_KEYCLOAK_ISSUER).strip()
    issuer = issuer.rstrip("/")
    parsed = urlsplit(issuer)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or "/realms/" not in parsed.path
    ):
        raise RuntimeError("KEYCLOAK_ISSUER must be an absolute HTTPS realm issuer")
    return issuer


def _claim_roles(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {role for role in value if isinstance(role, str) and role}


class CodestraSecurityManager(SupersetSecurityManager):
    """Fail-closed Keycloak identity mapping for Codestra analytics."""

    def oauth_user_info(
        self, provider: str, response: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        del response
        if provider != "keycloak":
            raise PermissionError("Only the Codestra Keycloak provider is approved")

        issuer = keycloak_issuer()
        remote = self.oauth_remotes[provider]
        profile_response = remote.get(
            f"{issuer}/protocol/openid-connect/userinfo"
        )
        profile_response.raise_for_status()
        profile = profile_response.json()
        if not isinstance(profile, dict):
            raise PermissionError("Keycloak userinfo response must be an object")

        subject = profile.get("sub")
        if not isinstance(subject, str) or not subject:
            raise PermissionError("Keycloak userinfo response has no subject")
        if profile.get("email_verified") is not True:
            raise PermissionError("A verified email is required")

        client_id = os.environ.get(
            "SUPERSET_OAUTH_CLIENT_ID", "superset-analytics"
        ).strip()
        if not client_id:
            raise RuntimeError("SUPERSET_OAUTH_CLIENT_ID is required")

        realm_access = profile.get("realm_access")
        if not isinstance(realm_access, dict):
            realm_access = {}
        resource_access = profile.get("resource_access")
        if not isinstance(resource_access, dict):
            resource_access = {}
        client_access = resource_access.get(client_id)
        if not isinstance(client_access, dict):
            client_access = {}

        realm_roles = _claim_roles(realm_access.get("roles"))
        client_roles = _claim_roles(client_access.get("roles"))
        role_keys = sorted((realm_roles | client_roles) & APPROVED_ROLE_KEYS)
        if not role_keys:
            raise PermissionError("No approved Codestra Superset role was supplied")

        username = profile.get("preferred_username") or profile.get("email")
        if not isinstance(username, str) or not username:
            raise PermissionError("Keycloak userinfo response has no username")

        def text_claim(name: str) -> str:
            value = profile.get(name, "")
            return value if isinstance(value, str) else ""

        return {
            "username": username,
            "first_name": text_claim("given_name"),
            "last_name": text_claim("family_name"),
            "email": text_claim("email"),
            "role_keys": role_keys,
        }
