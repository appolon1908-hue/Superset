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

- installs hash-locked `gevent`, PostgreSQL, and Authlib OAuth runtime
  requirements; Authlib is installed without dependency resolution while the
  immutable base image supplies and runtime-verifies the reviewed cryptography
  version;
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
| `requirements-runtime.in` / `.txt` | Exact hash-locked gevent and PostgreSQL runtime supplement |
| `requirements-oauth.in` / `.txt` | Exact hash-locked Authlib OAuth supplement |
| `codestra/runtime-v1/Dockerfile` | Codestra signed-image build authority |
| `codestra/runtime-v1/compose.candidate.yaml` | Inactive, deploy-only, file-secret runtime topology |
| `codestra/runtime-v1/superset_config.py.example` | Configuration embedded in the derived image |
| `codestra/runtime-v1/superset_config.py` | Identical source-side configuration copy used by validators |
| `codestra/runtime-v1/codestra_security_manager.py` | Fail-closed Keycloak identity and role-claim mapping |
| `codestra/runtime-v1/bootstrap_roles.py` | Idempotent business-role reconciliation after explicit initialization |
| `codestra/runtime-v1/check_metadata_readiness.py` | Web liveness plus metadata-database `SELECT 1` readiness |
| `scripts/build_and_inspect_locked_image.sh` | Exact image, startup, OAuth, migration, role, Celery, and embedded-file proof |
| `scripts/run_disposable_integration.sh` | Internal PostgreSQL/Redis readiness, backup/restore, RLS, and write-denial proof |
| `scripts/verify_release_identity.sh` | Post-signature OCI source, revision, user, and digest readback |
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
- The exact derived image must contain Authlib 1.6.12 and the reviewed
  base-image cryptography version before Superset may construct its OAuth
  security manager.
- Missing subject, unverified email, malformed role claims, unknown issuer, and
  identities without an approved role fail closed.
- Each Codestra business receives unique viewer and analyst roles. The bootstrap
  reconciles them to the current Gamma and Alpha permission sets while retaining
  only separately granted database/schema/datasource permissions; RLS
  relationships remain independent.
- Application-level HTTPS redirection is disabled because TLS and redirects are
  enforced at the trusted edge; this preserves the loopback HTTP health probe.
- CSP retains Superset's nonce support and `strict-dynamic` behavior.
- Celery registers the SQL Lab and Superset 6.1 reporting tasks that the exact
  image proves executable. Beat is limited to bounded report scheduling and
  report-log pruning; newer version-history and soft-delete tasks are not
  claimed by this release. Alert/report delivery remains disabled.
- Secrets are read only from externally mounted files. The disposable CI secret
  directory is searchable by UID 10001 but not listable, while individual files
  are read-only. No default password, client secret, private key, customer
  extract, or live token belongs in Git.

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
bash scripts/run_disposable_integration.sh "$(git rev-parse HEAD)"
```

The exact-image gate builds the locked image; verifies Superset, Authlib,
cryptography, gevent, PostgreSQL, and Gunicorn runtime imports; starts Superset
without network access on a read-only filesystem; migrates a disposable metadata
database; runs `superset init`; executes the Codestra role bootstrap twice;
verifies every business role and permission mirror; validates Celery task and
beat registration; and compares the image's embedded files to the reviewed
source.

The separate disposable integration uses only an internal Docker network and
pinned PostgreSQL and Redis images. It proves real metadata readiness, backup and
restore into a separate database, database-native RLS for two businesses,
unauthorized-business denial, and write denial. Neither test contacts a
production server, production datasource, Keycloak runtime, or provider.

## Signed release identity

After the exact production source SHA is released, first verify the image's
GitHub/Sigstore signature, provenance, SBOM, and vulnerability evidence. Pull
only the verified digest, then bind the deployment inputs to the local OCI
object:

```bash
scripts/verify_release_identity.sh \
  ghcr.io/appolon1908-hue/superset-superset@sha256:<verified-digest> \
  <protected-production-source-sha>
```

The readback requires the canonical repository digest, the exact OCI source and
revision labels emitted by the protected release workflow, and runtime user
`10001:10001`. A mutable tag, differently labeled digest, wrong source SHA, or
unpulled image fails closed.

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
