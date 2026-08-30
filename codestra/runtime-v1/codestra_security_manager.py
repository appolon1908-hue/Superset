from __future__ import annotations

import os
from typing import Any

from superset.security import SupersetSecurityManager


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


class CodestraSecurityManager(SupersetSecurityManager):
    """Fail-closed Keycloak identity mapping for Codestra Business Intelligence."""

    def oauth_user_info(
        self, provider: str, response: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if provider != "keycloak":
            raise PermissionError("Only the Codestra Keycloak provider is approved")

        remote = self.oauth_remotes[provider]
        profile_response = remote.get("userinfo")
        profile_response.raise_for_status()
        profile = profile_response.json()

        if not profile.get("sub"):
            raise PermissionError("Keycloak userinfo response has no subject")
        if profile.get("email_verified") is not True:
            raise PermissionError("A verified email is required")

        client_id = os.environ["SUPERSET_OAUTH_CLIENT_ID"]
        realm_roles = set(profile.get("realm_access", {}).get("roles", []))
        client_roles = set(
            profile.get("resource_access", {})
            .get(client_id, {})
            .get("roles", [])
        )
        role_keys = sorted((realm_roles | client_roles) & APPROVED_ROLE_KEYS)
        if not role_keys:
            raise PermissionError("No approved Codestra Superset role was supplied")

        username = profile.get("preferred_username") or profile.get("email")
        if not username:
            raise PermissionError("Keycloak userinfo response has no username")

        return {
            "username": username,
            "first_name": profile.get("given_name", ""),
            "last_name": profile.get("family_name", ""),
            "email": profile.get("email", ""),
            "role_keys": role_keys,
        }
