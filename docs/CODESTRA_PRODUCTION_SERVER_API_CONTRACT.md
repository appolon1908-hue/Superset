# Codestra Superset Production Server and Native API Contract

## Authority

- Repository: `appolon1908-hue/Superset`
- Role: certified read-only business analytics authority
- Canonical hostname: `supe.codestra.media`
- Central production host: `37.27.128.39`
- Status: `SOURCE_CONTRACT_PREPARED_NOT_DEPLOYED`

Superset owns approved read-only datasets, dashboards, charts, query controls, row-level security, OIDC integration, metadata backup/recovery, release evidence, and rollback. It does not replace Grafana, write business records, execute provider actions, or receive financial/trading authority.

## Native API and readiness surface

| Method or command | Path or command | Purpose | Boundary |
|---|---|---|---|
| `GET` | `/health` | web-process liveness only; it does not prove metadata-database health | authenticated edge/read-only |
| internal command | `python /app/pythonpath/check_metadata_readiness.py` | combines `/health` liveness with a read-only metadata-database `SELECT 1` | container healthcheck only; no public route |
| `GET` | `/api/v1/security/csrf_token/` | CSRF token for authenticated API use | authenticated session |
| approved methods | dashboard APIs | read/provision managed dashboards | role-scoped |
| approved methods | chart APIs | read/provision managed charts | role-scoped |
| approved methods | dataset APIs | certified dataset access | role and RLS scoped |
| approved methods | query APIs | bounded read-only analytics | certified datasets only |

`FAB_API_SWAGGER_UI = False` is the intentional production setting. `/swagger/v1` is therefore not a required production route and an expected `404` for that disabled route is not counted as an unexpected required-route failure. API-version evidence comes from the exact pinned Superset source, repository contract tests, and the enabled authenticated API routes—not from enabling an unnecessary Swagger UI.

Expected unauthenticated behavior for enabled protected routes may be OIDC redirect, `401`, or `403`. Unexpected `404` on an enabled required route, unhandled `5xx`, liveness without metadata readiness, unrestricted SQL, or write-capable production credentials block certification.

## Metadata readiness contract

- `/health` is liveness only.
- The candidate container healthcheck executes `/app/pythonpath/check_metadata_readiness.py`.
- The probe first checks loopback `/health`, then reads the metadata URI from `SUPERSET_METADATA_DATABASE_URI_FILE`, opens the configured metadata database, and executes read-only `SELECT 1`.
- The probe never prints the URI, password, exception text, or database response content.
- Missing or unreadable secret files, liveness failure, connection failure, timeout, or a non-`1` result fail closed.
- The candidate is not ready merely because Gunicorn accepts connections.

## Identity, RLS, and query controls

- Use the approved Keycloak OIDC client with Authorization Code and PKCE S256.
- Anonymous access, default/demo credentials, public database access, and unapproved self-registration are disabled.
- Map every approved business claim to a unique business-specific role.
- Business access remains disabled until database-native RLS, Superset RLS, certified dataset grants, and negative cross-business tests all pass.
- Template processing and unrestricted SQL Lab access are disabled for production business users.
- Queries have row, runtime, concurrency, and result-size limits.
- Metadata and dataset credentials come from OpenBao or approved secret files.
- All business connections are read-only and cannot perform lender, provider, payment, communications, or trading mutations.

## Production gates

```text
PROTECTED_PRODUCTION_SHA=PASS
WEB_LIVENESS=PASS
METADATA_DATABASE_READINESS=PASS
READINESS_SECRET_VALUE_EXPOSURE=0
FAB_API_SWAGGER_UI=DISABLED
OIDC_CONFIGURATION=PASS
PKCE_S256=PASS
BUSINESS_ROLE_MAPPING=PASS
CSRF=PASS
DATABASE_NATIVE_RLS=PASS
SUPERSET_RLS=PASS
CERTIFIED_DATASET_GRANTS=PASS
NEGATIVE_CROSS_BUSINESS_TESTS=PASS
UNRESTRICTED_SQL=NO
WRITE_CAPABLE_CREDENTIALS=NO
QUERY_LIMITS=PASS
IMMUTABLE_IMAGE_DIGEST=PASS
IMAGE_SIGNATURE=PASS
SBOM=PASS
PROVENANCE=PASS
SECRET_SCAN=PASS
METADATA_BACKUP=PASS
METADATA_RESTORE=PASS
ROLLBACK_MANIFEST=PASS
```

## Runtime certification

```text
GET_/health_LIVENESS=PASS
METADATA_DATABASE_READINESS_COMMAND=PASS
METADATA_DATABASE_SELECT_1=PASS
METADATA_URI_OR_PASSWORD_LOGGED=NO
GET_/api/v1/security/csrf_token/_ROUTE_EXISTS=PASS
GET_/swagger/v1_EXPECTED_DISABLED_404=PASS
DASHBOARD_API=PASS
CHART_API=PASS
DATASET_API=PASS
READ_ONLY_QUERY_API=PASS
OIDC_LOGIN_LOGOUT=PASS
WRONG_ROLE_DENIED=PASS
WRONG_BUSINESS_DENIED=PASS
DATABASE_RLS=PASS
SUPERSET_RLS=PASS
WRITE_ATTEMPT_DENIED=PASS
UNEXPECTED_REQUIRED_ROUTE_404=0
UNEXPECTED_5XX=0
SOURCE_RUNTIME_DRIFT=0
```

Use synthetic read-only RLS fixtures and certified staging datasets. Do not query customer or financial production data merely to prove routing. The expected disabled Swagger response must be tested separately from the enabled-route `404` counter.

## Repository-first remediation

Preserve the previous healthy Superset workload on failure. Fix configuration, readiness, role mapping, RLS, query, or metadata defects here with regression tests; commit/push; exact-head CI/review; protected merge; signed immutable rebuild; BOM update; then retry. Never patch a role, datasource, or container healthcheck only in the live UI or server filesystem.

## Safety

This document does not deploy Superset or enable business access. SSH changes, business writes, communications delivery, provider effects, lending, payments, and trading remain disabled.