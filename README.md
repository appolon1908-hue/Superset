# Codestra Superset

This repository is Codestra's source authority for a hardened Apache Superset
business-analytics service at `supe.codestra.media`. It combines a byte-preserved
Apache source snapshot for audit and upgrade comparison with a Codestra-owned,
signed derived-image release model.

## Current state

- Canonical hostname: `supe.codestra.media`
- Identity authority: `https://auth.codestra.co/realms/codestra`
- Native listener: loopback only (`127.0.0.1:8088`)
- Data boundary: certified read-only datasets, reporting schemas, replicas, or
  approved warehouse models
- Default query row limit: 10,000; hard limit: 100,000
- Repository state: **source prepared, not deployed**
- Production activation: **false**

No repository merge deploys Superset, installs a credential, creates a Keycloak
client, connects a datasource, reloads an edge route, or enables a business,
communications, financial, provider, or trading mutation.

## Release architecture

The executable authority is a Codestra image derived from the exact official
Apache Superset 6.1.0 image digest recorded in
`codestra/release/runtime-base.lock.json`. The derived image:

- installs only the hash-locked `gevent` and PostgreSQL runtime requirements;
- embeds the reviewed Superset configuration, Keycloak security manager,
  metadata-readiness probe, role bootstrap, runtime contract, and release lock;
- runs as UID/GID `10001:10001` with a read-only root filesystem, dropped
  capabilities, and no host networking;
- is published only by the pinned reusable release workflow in
  `.github/workflows/release-image.yml` with provenance, SBOM, vulnerability
  scanning, and GitHub/Sigstore attestations.

The imported `upstream/` tree is not executed directly. It is retained for
license preservation, audit, and upgrade review. `.gitattributes` prevents text
normalization, and `CODESTRA_UPSTREAM_LOCK.json` binds the import to its exact Git
tree SHA.

## Authoritative repository layout

| Path | Authority |
| --- | --- |
| `upstream/` | Byte-preserved Apache Superset source snapshot for audit and upgrades |
| `CODESTRA_UPSTREAM_LOCK.json` | Exact imported source commit and tree identity |
| `codestra/release/` | Immutable upstream-image lock and deterministic derived-image manifest |
| `codestra/runtime-v1/Dockerfile` | Codestra signed-image build authority |
| `codestra/runtime-v1/compose.candidate.yaml` | Inactive, deploy-only, file-secret runtime topology |
| `codestra/runtime-v1/superset_config.py.example` | Configuration embedded in the derived image |
| `codestra/runtime-v1/superset_config.py` | Identical source-side configuration copy used by validators |
| `codestra/runtime-v1/codestra_security_manager.py` | Fail-closed Keycloak identity and role-claim mapping |
| `codestra/runtime-v1/bootstrap_roles.py` | Idempotent business-role reconciliation after explicit initialization |
| `codestra/runtime-v1/check_metadata_readiness.py` | Web liveness plus metadata-database `SELECT 1` readiness |
| `codestra/api/` | Codestra read-only service/API contract |
| `codestra/docs/` | Analytics governance and operating model |
| `integration/` | Non-activating monitoring and evidence contracts |
| `orbit/` | Fail-closed Codestra Orbit adoption declaration |
| `scripts/` and `tests/` | Source, image, identity, bootstrap, readiness, and release gates |

There is no second active Compose authority. `compose.yaml` must remain absent.
The normal web, worker, and beat services never migrate metadata. Database
migration, `superset init`, and Codestra role reconciliation are isolated in the
`bootstrap-after-approval` profile.

## Identity and runtime controls

- Keycloak Authorization Code with PKCE S256 is required.
- Userinfo is fetched from the absolute configured issuer endpoint.
- Missing subject, unverified email, malformed role claims, unknown issuer, and
  identities without an approved role fail closed.
- Each Codestra business receives unique viewer and analyst roles. The bootstrap
  reconciles them to the current Gamma and Alpha permission sets while retaining
  only separately granted database/schema/datasource permissions; RLS
  relationships remain independent.
- Application-level HTTPS redirection is disabled because TLS and redirects are
  enforced at the trusted edge; this preserves the loopback HTTP health probe.
- CSP retains Superset's nonce support and `strict-dynamic` behavior.
- Celery registers SQL Lab and supported maintenance tasks and retains bounded
  scheduler, report-log pruning, version-history, and soft-delete retention
  schedules. Alert/report delivery remains disabled.
- Secrets are read only from externally mounted files. No default password,
  client secret, private key, customer extract, or live token belongs in Git.

## Validation

Install the pinned source-validation dependency and run:

```bash
python3 -m pip install --disable-pip-version-check --no-cache-dir \
  -r requirements-validation.txt
python3 -m py_compile codestra/runtime-v1/*.py scripts/*.py tests/*.py
python3 scripts/validate_codestra_repository.py
python3 scripts/validate_codestra_superset.py
python3 scripts/validate_codestra_review_hardening.py
python3 scripts/validate_codestra_superset_oidc.py
python3 scripts/validate_codestra_superset_readiness.py
python3 scripts/validate_repository_readiness.py
python3 scripts/validate_runtime_identity.py
python3 -m unittest discover -s tests -p 'test_*.py'
bash scripts/build_and_inspect_locked_image.sh "$(git rev-parse HEAD)"
```

The exact-image gate builds the locked image, starts Superset without network
access on a read-only filesystem, migrates a disposable metadata database, runs
`superset init`, executes the Codestra role bootstrap twice, verifies every
business role and permission mirror, and compares the image's embedded files to
the reviewed source. It does not contact a production server or datasource.

## Promotion model

Changes move only through:

`feature/docs/fix/security/upgrade → development → test → staging → production → main`

Every promotion must use the exact tested head, pass source and synthetic-merge
workflows, have no unresolved review findings, retain immutable release inputs,
and preserve all activation flags as false until separately approved runtime
evidence exists.

## Production gates

Production activation remains blocked until an immutable signed image and the
intended server environment prove all of the following:

1. OIDC login, role synchronization, logout, session behavior, and anonymous
   denial.
2. Mounted secrets, dedicated PostgreSQL metadata, and dedicated Redis.
3. Database-native and Superset RLS, certified dataset grants, and negative
   cross-business tests.
4. Web liveness, metadata readiness, bounded queries, worker/beat execution, and
   no unexpected required-route `404` or `5xx` responses.
5. Backup, restore, upgrade, rollback, image-signature, SBOM, provenance,
   vulnerability, and source/runtime-drift evidence.
6. An attested Codestra-Prometheus staging artifact containing required denial,
   no-secret, no-PII, no-external-effect, soak, and rollback results.
7. A separate reviewed production activation change.
