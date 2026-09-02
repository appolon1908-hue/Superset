# Repository Profile — `Superset`

## Identity

- **Repository:** `appolon1908-hue/Superset`
- **Category:** Authenticated analytics operator UI — Apache Superset
- **Visibility:** Public source repository; private runtime and data plane
- **Default branch:** `main`
- **Canonical hostname:** `supe.codestra.media`
- **Native bind:** `127.0.0.1:8088`
- **Target production host:** `37.27.128.39`
- **Runtime state:** Source prepared, not deployed
- **Authority:** Curated datasets, charts, dashboards, semantic metrics,
  analytics roles, Superset row-level security, and signed runtime artifacts

## Purpose

Provide read-only business and operational analytics from certified read models
without giving analysts direct access to provider administration, write-capable
production databases, or cross-business data.

## Owns

- byte-preserved Apache Superset source import for audit and upgrade comparison;
- exact upstream source tree, release commit, OCI index, and `linux/amd64`
  manifest locks;
- Codestra signed image derived from Apache Superset 6.1.0 with hash-locked
  `gevent`, PostgreSQL, and Authlib OAuth runtime support;
- runtime verification that the immutable base supplies the reviewed
  cryptography version required by Authlib;
- Keycloak OIDC/PKCE mapping for approved global and business roles;
- idempotent business-role reconciliation and runtime role verification;
- curated datasets, charts, dashboards, semantic metrics, and Superset RLS;
- query limits, cache policy, CSP, Celery task registration, metadata readiness,
  audit, backup/restore, upgrade, rollback, and source-side certification;
- post-signature OCI source/revision/digest readback before deployment inputs are
  accepted.

## Does not own

- operational systems of record or business mutations;
- provider-administration databases;
- write-capable analytics credentials;
- public or anonymous analytics APIs;
- direct email, SMS, voice, financial, trading, Odoo, or n8n activation;
- production deployment authorization merely because source was merged.

## Required integrations

- Keycloak client `superset-analytics`;
- authenticated Caddy edge route for `supe.codestra.media`;
- dedicated PostgreSQL metadata database;
- dedicated Redis cache and worker broker;
- OpenBao or approved mounted secret files;
- certified read-only reporting schemas, replicas, or warehouse models;
- Prometheus/Grafana observability and attested staging evidence;
- GHCR signed image identity tied to the exact protected source SHA.

## Canonical runtime and release files

- `requirements-runtime.in` and `requirements-runtime.txt` — reviewed,
  hash-locked gevent and PostgreSQL supplement;
- `requirements-oauth.in` and `requirements-oauth.txt` — reviewed, hash-locked
  Authlib OAuth supplement;
- `codestra/runtime-v1/Dockerfile` — derived-image build authority;
- `codestra/runtime-v1/compose.candidate.yaml` — only runtime topology;
- `codestra/runtime-v1/superset_config.py.example` — embedded configuration;
- `codestra/runtime-v1/superset_config.py` — identical source-side copy;
- `codestra/runtime-v1/codestra_security_manager.py` — identity authority;
- `codestra/runtime-v1/bootstrap_roles.py` — one-shot role reconciliation;
- `codestra/runtime-v1/check_metadata_readiness.py` — liveness plus metadata
  readiness;
- `scripts/build_and_inspect_locked_image.sh` — exact-image OAuth, startup,
  migration, role, Celery, and embedded-file execution proof;
- `scripts/run_disposable_integration.sh` — PostgreSQL/Redis, restore, RLS, and
  write-denial proof;
- `scripts/verify_release_identity.sh` — signed release readback.

`codestra/runtime-v1/compose.yaml` must remain absent. Normal web, worker, and
beat processes may not migrate metadata or run initialization. The
`bootstrap-after-approval` profile is the only repository-defined migration,
initialization, and role-bootstrap path.

## Governance

- Promotion:
  `feature/docs/fix/security/upgrade → development → test → staging → production → main`.
- Native port `8088` remains private and loopback-bound.
- Every dataset identifies source authority, owner, business/tenant boundary,
  freshness, sensitivity, and approved purpose.
- Every custom role mirrors its supported Superset base role while preserving
  only separately granted data-access permissions and independent RLS
  relationships.
- Pull-request CI must validate the exact head, synthetic merge, exact built
  image, Authlib and cryptography versions, repeated role bootstrap, Celery
  registration, and internal-only PostgreSQL/Redis integration.
- Merge does not deploy Superset, install credentials, create Keycloak clients,
  reload Caddy, connect a datasource, or enable production traffic.
- Database passwords, OIDC secrets, customer extracts, private keys, and
  secret-bearing query results must never be committed or printed.
