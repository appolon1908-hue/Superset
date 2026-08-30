from __future__ import annotations

import os
from datetime import timedelta

from flask_appbuilder.security.manager import AUTH_OAUTH

from codestra_security_manager_v2 import BUSINESS_SLUGS, CodestraSecurityManager


APP_NAME = "Codestra Business Intelligence"
LOGO_TOOLTIP = "Codestra corporate analytics"
WEBSERVER_BASEURL = "https://supe.codestra.media"
PREFERRED_URL_SCHEME = "https"
ENABLE_PROXY_FIX = True
PROXY_FIX_CONFIG = {
    "x_for": 1,
    "x_proto": 1,
    "x_host": 1,
    "x_port": 1,
    "x_prefix": 1,
}

SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]
SQLALCHEMY_DATABASE_URI = os.environ["SUPERSET_METADATA_DATABASE_URI"]
SQLALCHEMY_TRACK_MODIFICATIONS = False

AUTH_TYPE = AUTH_OAUTH
AUTH_USER_REGISTRATION = True
AUTH_USER_REGISTRATION_ROLE = "Gamma"
AUTH_ROLES_SYNC_AT_LOGIN = True
CUSTOM_SECURITY_MANAGER = CodestraSecurityManager

KEYCLOAK_ISSUER = os.environ["KEYCLOAK_ISSUER"].rstrip("/")
OAUTH_PROVIDERS = [
    {
        "name": "keycloak",
        "icon": "fa-key",
        "token_key": "access_token",
        "remote_app": {
            "client_id": os.environ["SUPERSET_OAUTH_CLIENT_ID"],
            "client_secret": os.environ["SUPERSET_OAUTH_CLIENT_SECRET"],
            "server_metadata_url": (
                f"{KEYCLOAK_ISSUER}/.well-known/openid-configuration"
            ),
            "client_kwargs": {
                "scope": "openid profile email roles",
            },
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
for business in BUSINESS_SLUGS:
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
CONTENT_SECURITY_POLICY_WARNING = True
X_FRAME_OPTIONS = "DENY"
ENABLE_CORS = False
FAB_ADD_SECURITY_API = False

CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 300,
    "CACHE_KEY_PREFIX": "codestra:superset:metadata:",
    "CACHE_REDIS_URL": os.environ["SUPERSET_CACHE_REDIS_URL"],
}
DATA_CACHE_CONFIG = {
    **CACHE_CONFIG,
    "CACHE_KEY_PREFIX": "codestra:superset:data:",
    "CACHE_DEFAULT_TIMEOUT": 600,
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
RATELIMIT_STORAGE_URI = os.environ["SUPERSET_RATELIMIT_REDIS_URI"]

FEATURE_FLAGS = {
    "DASHBOARD_RBAC": True,
    "ENABLE_TEMPLATE_PROCESSING": False,
    "TAGGING_SYSTEM": True,
    "ALERT_REPORTS": False,
    "EMBEDDED_SUPERSET": False,
    "GLOBAL_ASYNC_QUERIES": False,
}

ROW_LIMIT = 50000
SQL_MAX_ROW = 100000
DISPLAY_MAX_ROW = 10000
SQLLAB_TIMEOUT = 60
SUPERSET_WEBSERVER_TIMEOUT = 60
PREVENT_UNSAFE_DB_CONNECTIONS = True

LANGUAGES = {
    "en": {"flag": "us", "name": "English"},
    "es": {"flag": "es", "name": "Spanish"},
    "fr": {"flag": "fr", "name": "French"},
}
BABEL_DEFAULT_LOCALE = "en"

# Codestra sends notifications through governed platform paths. Superset direct
# email/report delivery remains disabled until a reviewed Klyrow/Middleware
# adapter exists and its audit evidence is attached to a release.
