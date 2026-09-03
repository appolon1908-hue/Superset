# Superset Repository-Wide Review — 2026-09-02

## Scope

This review covers every open and draft pull request, the Codestra-owned overlay
for `supe.codestra.media`, imported Apache source identity, image and release
inputs, promotion branches, exact-head workflows, runtime configuration,
identity and role logic, readiness, evidence gates, operational documentation,
and repository authority. It does not certify or modify a running production
server or datasource.

## Pull-request disposition

- PR 23 established the selected release architecture: a signed Codestra image
  derived from the exact official Apache Superset 6.1.0 digest with hash-locked
  runtime extras. It is merged into `development`.
- PR 22 proposed a competing signed-configuration-bundle architecture from an
  older base. It conflicts with the selected signed-image model and is not safe
  to merge wholesale. Its useful upstream-tree, CSP, Celery, health-probe,
  backup/restore, and runtime-test controls are consolidated into the selected
  architecture.
- PR 27 independently carried several of the same runtime corrections and added
  useful signed-OCI readback plus PostgreSQL/Redis integration. Its integration
  created a root-owned secret directory with mode `0700`, so UID 10001 could not
  traverse the bind mount and the test could not reach migration or readiness.
  Those unique controls are consolidated with mode `0711`, read-only files,
  repeated bootstrap, role/Celery verification, and no competing authority.
- PR 28 is the single consolidation PR for all remaining useful draft content.
- PR 21 supplied the corrected service/API contract and metadata-readiness probe
  and was promoted through staging.
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
5. The custom Celery configuration omitted Superset's SQL Lab and supported
   reporting task imports and beat schedules, allowing unregistered
   asynchronous tasks and missing report-log pruning.
6. The imported `upstream/` source tree recorded a commit but did not bind the
   actual Git tree or prevent text normalization.
7. The root README still described superseded duplicate Compose and
   compatibility authorities rather than the merged signed-image model.
8. PR 22's old validation workflow had two correctness defects: an unpropagated
   target-only Python dependency installation and use of the synthetic merge SHA
   where the checked-out PR head identity was required. That workflow is not
   carried into the selected architecture.
9. PR 27's disposable integration used directory mode `0700` for files mounted
   into a container running as `10001:10001`; read-only file modes did not make
   the parent directory traversable.
10. The selected architecture did not yet have a post-signature gate binding a
    locally pulled GHCR digest to its canonical source label, protected revision
    label, repository digest, and non-root user.
11. Source-level Celery string assertions existed, but the exact built image did
    not load default task modules and verify registered task and beat identities.
12. Backup/restore and upgrade documents were too short to define source/image
    identities, restore evidence, rollback abort conditions, and deployment
    readback.
13. The official base image did not contain Authlib. As soon as the exact-image
    test constructed the configured OAuth security manager, Superset failed with
    `ModuleNotFoundError: No module named 'authlib'`, so Keycloak login and every
    CLI operation that initializes Flask-AppBuilder were blocked.

## Repository-wide corrections

1. `bootstrap_roles.py` now creates the Superset Flask application through
   `superset.app.create_app()`, enters its application context, reconciles every
   business viewer/analyst role, commits once, and is safe to run repeatedly.
2. Exact-image CI now uses a disposable metadata database under a read-only,
   network-disabled container, runs `superset db upgrade`, `superset init`, and
   the role bootstrap twice, then verifies every business role mirrors the
   current Gamma or Alpha permission set.
3. The exact image loads Celery default modules and proves the executable
   Superset 6.1 SQL Lab, report scheduler, and report-log pruning task set and
   beat schedules are registered. It does not claim newer source-only retention
   tasks that the locked 6.1 image cannot execute.
4. TLS and redirects remain the trusted edge's responsibility; application
   `force_https` is disabled so the internal liveness probe remains valid.
5. CSP nonce injection and `strict-dynamic` are restored while framing,
   cross-origin, and object restrictions remain fail closed.
6. Celery restores SQL Lab and supported reporting task registration, scheduler
   expiry, and report-log pruning. Newer version-history and soft-delete task
   modules remain intentionally absent until an upgraded exact image proves
   them executable. External report delivery remains disabled.
7. `.gitattributes` preserves imported bytes and
   `CODESTRA_UPSTREAM_LOCK.json` binds `upstream/` to tree
   `e8eb116376da9ec2a53b374b67f4b1cf9480262b`.
8. A separate internal-only integration builds the exact branch image, starts
   pinned PostgreSQL and Redis, supplies generated secrets through a `0711`
   directory with `0444` files, repeats bootstrap, verifies roles and Celery,
   proves metadata readiness, dumps/restores the metadata database, and tests
   business RLS, unauthorized-business denial, and write denial.
9. `verify_release_identity.sh` binds deployment inputs to the canonical GHCR
   digest, OCI source label, protected revision label, and user `10001:10001`
   after signature/provenance/SBOM verification.
10. Authlib 1.6.12 is now a separate exact, hash-locked OAuth supplement. It is
    installed with dependency resolution disabled; the immutable official base
    continues to supply cryptography, and the Docker build plus exact-image
    runtime test assert the reviewed Authlib and cryptography versions before
    Superset startup.
11. Repository validators and unit tests now reject bootstrap-factory
    regressions, missing OAuth dependencies, OAuth hash or package-source drift,
    secret-directory traversal regressions, upstream-tree drift, mutable release
    inputs, duplicate runtime authorities, missing exact-image or PostgreSQL/Redis
    tests, unpinned actions, direct protected-branch pushes, and enabled
    activation flags.
12. The README, repository profile, backup/restore/rollback policy, and upgrade
    policy now document the actual signed-image authority and operational gates.
13. The corporate Compose validator's previously unreachable profile, immutable
    image, resource-limit, and PID consistency checks were corrected.

## Selected runtime authority

- Executable base: exact official Apache Superset 6.1.0 image digest.
- Codestra artifact: signed derived image with hash-locked `gevent`, PostgreSQL,
  and Authlib OAuth support, plus runtime-verified base cryptography.
- Configuration embedded into image: `superset_config.py.example`.
- Identical source-side config: `superset_config.py`.
- Identity authority: `codestra_security_manager.py`; compatibility copy must
  remain byte-for-byte identical.
- Runtime topology: `compose.candidate.yaml` only.
- Migration and role initialization: inactive
  `bootstrap-after-approval` profile only.
- Native web publication: loopback only.
- Secrets: mounted files only.
- Required CI: source, synthetic merge, exact image, OAuth startup, role/Celery
  runtime, and internal PostgreSQL/Redis integration.
- Production activation: false.

## State after source remediation

The repository remains **source prepared, not deployed**. No production
database, datasource, dashboard, DNS record, Keycloak client, Caddy route,
secret, communications provider, lending, payment, financial, trading, Odoo,
n8n, or business-write capability is activated by these changes.

## Remaining runtime and account-side gates

- Promotion branches need enforced GitHub rulesets and required-check contexts;
  repository files cannot substitute for account-side protection.
- The signed image must be released from the exact protected production SHA and
  its digest recorded in the deployment bill of materials.
- Signature, signer identity, provenance, SBOM, vulnerability, and exact OAuth
  dependency evidence must pass before `verify_release_identity.sh` is used on
  the pulled digest.
- Staging must prove real mounted secrets, PostgreSQL and Redis readiness, OIDC
  login/logout and role synchronization, worker/beat execution, database-native
  and Superset RLS, cross-business denial, certified read-only datasource
  credentials, query limits, and audit retention.
- A fresh installation-specific backup/restore and rollback rehearsal remains
  required; disposable CI evidence is necessary but not sufficient.
- Source/runtime drift, no-secret, no-PII, no-external-effect, soak, rollback,
  and separate activation approval remain required before live service.
