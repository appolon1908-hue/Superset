# Superset Repository-Wide Review — 2026-09-02

## Scope

This review covers every open and draft pull request, the Codestra-owned overlay
for `supe.codestra.media`, imported Apache source identity, image and release
inputs, promotion branches, exact-head workflows, runtime configuration,
identity and role logic, readiness, evidence gates, and repository
documentation. It does not certify or modify a running server or datasource.

## Pull-request disposition

- PR 23 established the selected release architecture: a signed Codestra image
  derived from the exact official Apache Superset 6.1.0 digest with hash-locked
  runtime extras. It is merged into `development`.
- PR 22 proposed a competing signed-configuration-bundle architecture from an
  older base. It conflicts with the selected signed-image model and is not safe
  to merge wholesale. Its useful upstream-tree, CSP, Celery, health-probe, and
  runtime-test controls are consolidated into the selected architecture.
- PR 21 supplied the corrected service/API contract and metadata-readiness
  probe and was promoted through staging.
- PR 16 promoted the previously consolidated source authority to production
  after its four review findings were fixed and resolved.
- Old drafts PR 9 and PR 19 were closed as superseded because they targeted
  `main` directly and bypassed the promotion chain.
- Orbit adoption remains fail closed pending the protected SDK-repository
  authority and a released compatible package.

## Findings discovered during the complete review

1. The merged role bootstrap imported `superset.app` as though it were the Flask
   application. On Superset 6.1.0 it is a module, so `app.app_context()` failed
   before any Codestra business role could be created.
2. The signed image copied the bootstrap file but its CI inspection never ran
   metadata migration, `superset init`, role bootstrap, or post-bootstrap role
   assertions. The production-breaking import defect therefore passed source
   checks.
3. Application-level `force_https` redirected the loopback HTTP health request
   toward TLS on Gunicorn's plain-HTTP container port.
4. The custom CSP omitted Superset's script nonce injection and
   `strict-dynamic`, which could block OAuth and SPA inline scripts.
5. The custom Celery configuration omitted Superset's SQL Lab and maintenance
   task imports and beat schedules, allowing unregistered asynchronous tasks and
   missing retention work.
6. The imported `upstream/` source tree recorded a commit but did not bind the
   actual Git tree or prevent text normalization.
7. The root README still described superseded duplicate Compose and
   compatibility authorities rather than the merged signed-image model.
8. PR 22's old validation workflow also had two correctness defects: an
   unpropagated target-only Python dependency installation and use of the
   synthetic merge SHA where the checked-out PR head identity was required.
   That workflow is not carried into the selected architecture.

## Repository-wide corrections

1. `bootstrap_roles.py` now creates the Superset Flask application through
   `superset.app.create_app()`, enters its application context, reconciles every
   business viewer/analyst role, commits once, and is safe to run repeatedly.
2. Exact-image CI now uses a disposable metadata database under a read-only,
   network-disabled container, runs `superset db upgrade`, `superset init`, and
   the role bootstrap twice, then verifies every business role mirrors the
   current Gamma or Alpha permission set.
3. TLS and redirects remain the trusted edge's responsibility; application
   `force_https` is disabled so the internal liveness probe remains valid.
4. CSP nonce injection and `strict-dynamic` are restored while framing,
   cross-origin, and object restrictions remain fail closed.
5. Celery restores SQL Lab and supported maintenance task registration,
   scheduler expiry, report-log pruning, version-history pruning, and
   soft-delete retention schedules. External report delivery remains disabled.
6. `.gitattributes` preserves imported bytes and
   `CODESTRA_UPSTREAM_LOCK.json` binds `upstream/` to tree
   `e8eb116376da9ec2a53b374b67f4b1cf9480262b`.
7. Repository validators and unit tests now reject bootstrap-factory regressions,
   upstream-tree drift, mutable release inputs, duplicate runtime authorities,
   missing exact-image tests, unpinned actions, direct protected-branch pushes,
   and enabled activation flags.
8. The README now documents the actual signed derived-image authority, file
   boundaries, validation commands, promotion chain, and remaining activation
   gates.

## Selected runtime authority

- Executable base: exact official Apache Superset 6.1.0 image digest.
- Codestra artifact: signed derived image with hash-locked `gevent` and
  PostgreSQL support.
- Configuration embedded into image: `superset_config.py.example`.
- Identical source-side config: `superset_config.py`.
- Runtime topology: `compose.candidate.yaml` only.
- Migration and role initialization: inactive
  `bootstrap-after-approval` profile only.
- Native web publication: loopback only.
- Secrets: mounted files only.
- Production activation: false.

## State after source remediation

The repository remains **source prepared, not deployed**. No database,
datasource, dashboard, DNS record, Keycloak client, Caddy route, secret,
communications provider, lending, payment, financial, trading, Odoo, n8n, or
business-write capability is activated by these changes.

## Remaining runtime and account-side gates

- Promotion branches need enforced GitHub rulesets and required-check contexts;
  repository files cannot substitute for account-side protection.
- The signed image must be released from the exact protected production SHA and
  its digest recorded in the deployment bill of materials.
- Staging must prove mounted secrets, PostgreSQL and Redis readiness, OIDC and
  logout behavior, worker/beat execution, database-native and Superset RLS,
  cross-business denial, certified read-only datasource credentials, and query
  limits.
- Backup, restore, upgrade, rollback, source/runtime drift, image signature,
  SBOM, provenance, vulnerability, no-secret, no-PII, no-external-effect, and
  soak evidence remain required before a separate activation approval.
