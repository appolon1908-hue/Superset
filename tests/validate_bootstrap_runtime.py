from __future__ import annotations

from typing import Any

from superset.app import create_app

from codestra_security_manager import BUSINESS_SLUGS


def permission_identities(role: Any) -> set[tuple[str, str]]:
    return {
        (
            getattr(getattr(permission_view, "permission", None), "name", ""),
            getattr(getattr(permission_view, "view_menu", None), "name", ""),
        )
        for permission_view in role.permissions
    }


def require_role(security_manager: Any, role_name: str) -> Any:
    role = security_manager.find_role(role_name)
    if role is None:
        raise SystemExit(f"missing bootstrapped Superset role: {role_name}")
    return role


def main() -> None:
    application = create_app()
    with application.app_context():
        security_manager = application.appbuilder.sm
        gamma_permissions = permission_identities(
            require_role(security_manager, "Gamma")
        )
        alpha_permissions = permission_identities(
            require_role(security_manager, "Alpha")
        )

        expected_names: list[str] = []
        for business in sorted(BUSINESS_SLUGS):
            viewer_name = f"Codestra Business {business} Viewer"
            analyst_name = f"Codestra Business {business} Analyst"
            expected_names.extend((viewer_name, analyst_name))

            viewer = require_role(security_manager, viewer_name)
            analyst = require_role(security_manager, analyst_name)
            if permission_identities(viewer) != gamma_permissions:
                raise SystemExit(
                    f"viewer permissions do not mirror Gamma: {viewer_name}"
                )
            if permission_identities(analyst) != alpha_permissions:
                raise SystemExit(
                    f"analyst permissions do not mirror Alpha: {analyst_name}"
                )

        auditor_name = "Codestra Security Auditor"
        expected_names.append(auditor_name)
        auditor = require_role(security_manager, auditor_name)
        if permission_identities(auditor) != gamma_permissions:
            raise SystemExit("security auditor permissions do not mirror Gamma")

        if len(expected_names) != len(BUSINESS_SLUGS) * 2 + 1:
            raise SystemExit("unexpected Codestra role catalogue size")

    print("CODESTRA_SUPERSET_BOOTSTRAP_RUNTIME_VALIDATION=PASS")


if __name__ == "__main__":
    main()
