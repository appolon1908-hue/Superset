from __future__ import annotations

from typing import Any

from superset import app

from codestra_security_manager import BUSINESS_SLUGS


def _permission_identity(permission_view: Any) -> tuple[Any, str, str]:
    permission = getattr(permission_view, "permission", None)
    view_menu = getattr(permission_view, "view_menu", None)
    return (
        getattr(permission_view, "id", None),
        getattr(permission, "name", ""),
        getattr(view_menu, "name", ""),
    )


def reconcile_base_permissions(
    security_manager: Any, source_name: str, target_name: str
) -> None:
    """Mirror a built-in role while retaining separately granted data access.

    Superset row-level-security relationships are stored separately from the
    role's PermissionView collection, so replacing that collection does not
    remove RLS assignments. Only database/schema/datasource access permissions
    that were granted separately are retained.
    """

    source = security_manager.find_role(source_name)
    if source is None:
        raise RuntimeError(f"Required Superset base role is missing: {source_name}")

    target = security_manager.find_role(target_name)
    if target is None:
        target = security_manager.add_role(target_name)

    source_permissions = list(source.permissions)
    source_identities = {
        _permission_identity(permission_view)
        for permission_view in source_permissions
    }
    data_access_permissions = set(security_manager.data_access_permissions)
    preserved_data_access = [
        permission_view
        for permission_view in list(target.permissions)
        if _permission_identity(permission_view) not in source_identities
        and getattr(
            getattr(permission_view, "permission", None), "name", None
        )
        in data_access_permissions
    ]

    target.permissions = source_permissions + preserved_data_access


with app.app_context():
    sm = app.appbuilder.sm
    for business in sorted(BUSINESS_SLUGS):
        reconcile_base_permissions(
            sm, "Gamma", f"Codestra Business {business} Viewer"
        )
        reconcile_base_permissions(
            sm, "Alpha", f"Codestra Business {business} Analyst"
        )
    reconcile_base_permissions(sm, "Gamma", "Codestra Security Auditor")
    sm.get_session.commit()
