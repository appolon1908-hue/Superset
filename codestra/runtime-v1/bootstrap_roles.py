from __future__ import annotations

from superset import app

from codestra_security_manager import BUSINESS_SLUGS


def add_base_permissions(security_manager, source_name: str, target_name: str) -> None:
    source = security_manager.find_role(source_name)
    if source is None:
        raise RuntimeError(f"Required Superset base role is missing: {source_name}")
    target = security_manager.find_role(target_name)
    if target is None:
        target = security_manager.add_role(target_name)
    for permission_view in source.permissions:
        security_manager.add_permission_role(target, permission_view)


with app.app_context():
    sm = app.appbuilder.sm
    for business in sorted(BUSINESS_SLUGS):
        add_base_permissions(sm, "Gamma", f"Codestra Business {business} Viewer")
        add_base_permissions(sm, "Alpha", f"Codestra Business {business} Analyst")
    add_base_permissions(sm, "Gamma", "Codestra Security Auditor")
    sm.get_session.commit()
