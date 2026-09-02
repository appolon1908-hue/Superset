"""Canonical Codestra production Superset configuration.

Every secret is read from an externally mounted file. The native webserver must
bind to loopback and remain behind the Codestra Caddy/Keycloak boundary.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

from flask_appbuilder.security.manager import AUTH_OAUTH

from codestra_security_manager import CodestraSecurityManager


BUSINESSES: Final[tuple[str, ...]] = (
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
)


def read_secret(variable: str) -> str:
    path = Path(os.environ[variable])
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise RuntimeError(f"empty required Superset secret file: {variable}")
    return value


SECRET_KEY = read_secret("SUPERSET_SECRET_KEY_FILE")
SQLALCHEMY_DATABASE_URI = read_secret("SUPERSET_METADATA_DATABASE_URI_FILE")
REDIS_URL = read_secret("SUPERSET_REDIS_URL_FILE")

ENABLE_PROXY_FIX = True
PREFERRED_URL_SCHEME = "https"
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_NAME = "codestra_superset_session"
PERMANENT_SESSION_LIFETIME = 3600
WTF_CSRF_ENABLED = True
WTF_CSRF_TIME_LIMIT = 3600
TALISMAN_ENABLED = True
TALISMAN_CONFIG = {
    "force_https": True,
    "strict_transport_security": True,
    "strict_transport_security_max_age": 31536000,
    "content_security_policy": {
        "default-src": ["'self'"],
        "script-src": ["'self'"],
        "style-src": ["'self'", "'unsafe-inline'"],
        "img-src": ["'self'", "data:"],
        "font-src": ["'self'", "data:"],
        "connect-src": ["'self'"],
        "frame-ancestors": ["'none'"],
        "object-src": ["'none'"],
    },
}

AUTH_TYPE = AUTH_OAUTH
AUTH_USER_REGISTRATION = True
AUTH_USER_REGISTRATION_ROLE = "Gamma"
AUTH_ROLES_SYNC_AT_LOGIN = True
AUTH_ROLES_MAPPING = {
    "superset-admin": ["Admin"],
    "superset-analyst": ["Alpha"],
    "superset-viewer": ["Gamma"],
    "superset-security-auditor": ["Codestra Security Auditor"],
    **{
        f"business-{business}-viewer": [
            f"Codestra Business {business} Viewer"
        ]
        for business in BUSINESSES
    },
    **{
        f"business-{business}-analyst": [
            f"Codestra Business {business} Analyst"
        ]
        for business in BUSINESSES
    },
}
CUSTOM_SECURITY_MANAGER = CodestraSecurityManager
KEYCLOAK_ISSUER = os.environ["KEYCLOAK_ISSUER"].rstrip("/")
OAUTH_PROVIDERS = [
    {
        "name": "keycloak",
        "token_key": "access_token",
        "icon": "fa-key",
        "remote_app": {
            "client_id": os.environ.get(
                "SUPERSET_OAUTH_CLIENT_ID", "superset-analytics"
            ),
            "client_secret": read_secret("SUPERSET_OIDC_CLIENT_SECRET_FILE"),
            "client_kwargs": {"scope": "openid profile email roles"},
            "server_metadata_url": f"{KEYCLOAK_ISSUER}/.well-known/openid-configuration",
            "code_challenge_method": "S256",
        },
    }
]

CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 300,
    "CACHE_KEY_PREFIX": "codestra_superset_metadata_",
    "CACHE_REDIS_URL": REDIS_URL,
}
DATA_CACHE_CONFIG = {
    **CACHE_CONFIG,
    "CACHE_DEFAULT_TIMEOUT": 900,
    "CACHE_KEY_PREFIX": "codestra_superset_data_",
}
FILTER_STATE_CACHE_CONFIG = {
    **CACHE_CONFIG,
    "CACHE_KEY_PREFIX": "codestra_superset_filter_",
}
EXPLORE_FORM_DATA_CACHE_CONFIG = {
    **CACHE_CONFIG,
    "CACHE_KEY_PREFIX": "codestra_superset_explore_",
}


class CeleryConfig:
    broker_url = REDIS_URL
    result_backend = REDIS_URL
    task_acks_late = True
    worker_prefetch_multiplier = 1
    task_reject_on_worker_lost = True
    broker_connection_retry_on_startup = True
    task_serializer = "json"
    result_serializer = "json"
    accept_content = ["json"]
    timezone = "UTC"


CELERY_CONFIG = CeleryConfig

FEATURE_FLAGS = {
    "ROW_LEVEL_SECURITY": True,
    "DASHBOARD_RBAC": True,
    "TAGGING_SYSTEM": True,
    "ALERT_REPORTS": False,
    "ENABLE_TEMPLATE_PROCESSING": False,
    "EMBEDDED_SUPERSET": False,
}

SQL_MAX_ROW = 100000
DISPLAY_MAX_ROW = 10000
SUPERSET_WEBSERVER_TIMEOUT = 60
SQLLAB_TIMEOUT = 60
SQLLAB_ASYNC_TIME_LIMIT_SEC = 600
SQLLAB_CTAS_NO_LIMIT = False
SQLLAB_ALLOW_ADHOC_SUBQUERY = False
ENABLE_CORS = False
FAB_API_SWAGGER_UI = False
FAB_ADD_SECURITY_API = False
PUBLIC_ROLE_LIKE = None
PREVENT_UNSAFE_DB_CONNECTIONS = True

# Direct SMTP, SMS and voice delivery are intentionally absent. Scheduled report
# distribution remains disabled until it is routed through the governed Codestra
# Middleware notification path with recipient and business-scope approval.
EMAIL_NOTIFICATIONS = False

# Datasources are provisioned separately from the repository with read-only
# OpenBao-managed credentials and the controls in analytics-control-plane.v1.json.
