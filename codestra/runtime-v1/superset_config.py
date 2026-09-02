"""Canonical Codestra Superset configuration.

Production secrets are read only from externally mounted files. The native
webserver must remain loopback-bound behind the approved Codestra edge and
Keycloak boundary.
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from celery.schedules import crontab
from flask_appbuilder.security.manager import AUTH_OAUTH

from codestra_security_manager import (
    BUSINESS_SLUGS,
    CodestraSecurityManager,
    DEFAULT_KEYCLOAK_ISSUER,
)


BUSINESSES = (
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
if set(BUSINESSES) != BUSINESS_SLUGS:
    raise RuntimeError("Superset business catalogue diverges from the security manager")

CANONICAL_KEYCLOAK_ISSUER = "https://auth.codestra.co/realms/codestra"
if CANONICAL_KEYCLOAK_ISSUER != DEFAULT_KEYCLOAK_ISSUER:
    raise RuntimeError("Superset Keycloak issuer authority diverges")


def read_secret(variable: str) -> str:
    raw_path = os.environ.get(variable, "").strip()
    if not raw_path:
        raise RuntimeError(f"missing required Superset secret-file variable: {variable}")
    path = Path(raw_path)
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise RuntimeError(f"empty required Superset secret file: {variable}")
    return value


APP_NAME = "Codestra Business Intelligence"
LOGO_TOOLTIP = "Codestra corporate analytics"
WEBSERVER_BASEURL = os.environ.get(
    "SUPERSET_PUBLIC_URL", "https://supe.codestra.media"
).rstrip("/")
PREFERRED_URL_SCHEME = "https"
ENABLE_PROXY_FIX = True
PROXY_FIX_CONFIG = {
    "x_for": 1,
    "x_proto": 1,
    "x_host": 1,
    "x_port": 1,
    "x_prefix": 1,
}

SECRET_KEY = read_secret("SUPERSET_SECRET_KEY_FILE")
SQLALCHEMY_DATABASE_URI = read_secret("SUPERSET_METADATA_DATABASE_URI_FILE")
REDIS_URL = read_secret("SUPERSET_REDIS_URL_FILE")
SQLALCHEMY_TRACK_MODIFICATIONS = False
SQLALCHEMY_ENGINE_OPTIONS = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

AUTH_TYPE = AUTH_OAUTH
AUTH_USER_REGISTRATION = True
AUTH_USER_REGISTRATION_ROLE = "Gamma"
AUTH_ROLES_SYNC_AT_LOGIN = True
CUSTOM_SECURITY_MANAGER = CodestraSecurityManager

KEYCLOAK_ISSUER = os.environ.get(
    "KEYCLOAK_ISSUER", CANONICAL_KEYCLOAK_ISSUER
).rstrip("/")
OAUTH_PROVIDERS = [
    {
        "name": "keycloak",
        "icon": "fa-key",
        "token_key": "access_token",
        "remote_app": {
            "client_id": os.environ.get(
                "SUPERSET_OAUTH_CLIENT_ID", "superset-analytics"
            ),
            "client_secret": read_secret("SUPERSET_OIDC_CLIENT_SECRET_FILE"),
            "server_metadata_url": (
                f"{KEYCLOAK_ISSUER}/.well-known/openid-configuration"
            ),
            "client_kwargs": {"scope": "openid profile email roles"},
            "code_challenge_method": "S256",
        },
    }
]

AUTH_ROLES_MAPPING = {
    "superset-admin": ["Admin"],
    "superset-analyst": ["Alpha"],
    "superset-viewer": ["Gamma"],
    "superset-security-auditor": ["Codestra Security Auditor"],
}
for business in BUSINESSES:
    AUTH_ROLES_MAPPING[f"business-{business}-viewer"] = [
        f"Codestra Business {business} Viewer"
    ]
    AUTH_ROLES_MAPPING[f"business-{business}-analyst"] = [
        f"Codestra Business {business} Analyst"
    ]

WTF_CSRF_ENABLED = True
WTF_CSRF_TIME_LIMIT = timedelta(hours=1)
SESSION_COOKIE_NAME = "codestra_superset_session"
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
REMEMBER_COOKIE_SECURE = True
REMEMBER_COOKIE_HTTPONLY = True
REMEMBER_COOKIE_SAMESITE = "Lax"
TALISMAN_ENABLED = True
TALISMAN_CONFIG = {
    # TLS and redirects are enforced by the trusted Codestra edge. Application
    # force_https must remain disabled so the loopback HTTP health probe is not
    # redirected to TLS on Gunicorn's plain-HTTP container port.
    "force_https": False,
    "strict_transport_security": True,
    "strict_transport_security_max_age": 31536000,
    "content_security_policy": {
        "base-uri": ["'self'"],
        "default-src": ["'self'"],
        "script-src": ["'self'", "'strict-dynamic'"],
        "style-src": ["'self'", "'unsafe-inline'"],
        "img-src": ["'self'", "data:"],
        "font-src": ["'self'", "data:"],
        "connect-src": ["'self'"],
        "worker-src": ["'self'", "blob:"],
        "frame-ancestors": ["'none'"],
        "object-src": ["'none'"],
    },
    "content_security_policy_nonce_in": ["script-src"],
}
CONTENT_SECURITY_POLICY_WARNING = False
X_FRAME_OPTIONS = "DENY"
ENABLE_CORS = False
FAB_ADD_SECURITY_API = False
FAB_API_SWAGGER_UI = False
PUBLIC_ROLE_LIKE = None

CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 300,
    "CACHE_KEY_PREFIX": "codestra:superset:metadata:",
    "CACHE_REDIS_URL": REDIS_URL,
}
DATA_CACHE_CONFIG = {
    **CACHE_CONFIG,
    "CACHE_KEY_PREFIX": "codestra:superset:data:",
    "CACHE_DEFAULT_TIMEOUT": 900,
}
FILTER_STATE_CACHE_CONFIG = {
    **CACHE_CONFIG,
    "CACHE_KEY_PREFIX": "codestra:superset:filters:",
    "CACHE_DEFAULT_TIMEOUT": 86400,
}
EXPLORE_FORM_DATA_CACHE_CONFIG = {
    **CACHE_CONFIG,
    "CACHE_KEY_PREFIX": "codestra:superset:explore:",
    "CACHE_DEFAULT_TIMEOUT": 86400,
}
RATELIMIT_STORAGE_URI = REDIS_URL

CELERY_BEAT_SCHEDULER_EXPIRES = timedelta(weeks=1)


class CeleryConfig:
    broker_url = REDIS_URL
    result_backend = REDIS_URL
    imports = (
        "superset.sql_lab",
        "superset.tasks.deletion_retention",
        "superset.tasks.scheduler",
        "superset.tasks.thumbnails",
        "superset.tasks.cache",
        "superset.tasks.slack",
        "superset.tasks.export_dashboard_excel",
        "superset.tasks.version_history_retention",
    )
    task_acks_late = True
    worker_prefetch_multiplier = 1
    task_reject_on_worker_lost = True
    broker_connection_retry_on_startup = True
    task_serializer = "json"
    result_serializer = "json"
    accept_content = ["json"]
    timezone = "UTC"
    task_annotations = {
        "sql_lab.get_sql_results": {"rate_limit": "100/s"},
    }
    beat_schedule = {
        "reports.scheduler": {
            "task": "reports.scheduler",
            "schedule": crontab(minute="*", hour="*"),
            "options": {
                "expires": int(CELERY_BEAT_SCHEDULER_EXPIRES.total_seconds())
            },
        },
        "reports.prune_log": {
            "task": "reports.prune_log",
            "schedule": crontab(minute=0, hour=0),
        },
        "version_history.prune_old_versions": {
            "task": "version_history.prune_old_versions",
            "schedule": crontab(minute=0, hour=3),
        },
        "deletion_retention.purge_soft_deleted": {
            "task": "deletion_retention.purge_soft_deleted",
            "schedule": crontab(minute=0, hour=0),
        },
    }


CELERY_CONFIG = CeleryConfig

FEATURE_FLAGS = {
    "ROW_LEVEL_SECURITY": True,
    "DASHBOARD_RBAC": True,
    "TAGGING_SYSTEM": True,
    "ALERT_REPORTS": False,
    "ENABLE_TEMPLATE_PROCESSING": False,
    "EMBEDDED_SUPERSET": False,
    "GLOBAL_ASYNC_QUERIES": False,
}

ROW_LIMIT = 10000
SQL_MAX_ROW = 100000
DISPLAY_MAX_ROW = 10000
SQLLAB_TIMEOUT = 60
SQLLAB_ASYNC_TIME_LIMIT_SEC = 600
SQLLAB_CTAS_NO_LIMIT = False
SQLLAB_ALLOW_ADHOC_SUBQUERY = False
SUPERSET_WEBSERVER_TIMEOUT = 60
PREVENT_UNSAFE_DB_CONNECTIONS = True

LANGUAGES = {
    "en": {"flag": "us", "name": "English"},
    "es": {"flag": "es", "name": "Spanish"},
    "fr": {"flag": "fr", "name": "French"},
}
BABEL_DEFAULT_LOCALE = "en"

# Direct SMTP, SMS, voice, embedded access, and alert/report delivery remain
# disabled. Distribution must use the governed Codestra Middleware path after
# separate recipient, business-scope, and release approval.
EMAIL_NOTIFICATIONS = False
