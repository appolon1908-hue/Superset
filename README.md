# Codestra Superset

This repository is Codestra's source authority for a hardened Apache Superset
analytics service. The Apache upstream snapshot is retained under `upstream/`;
Codestra-owned runtime, identity, governance, integration, and validation
material lives outside that directory.

## Current state

- Canonical protected hostname: `supe.codestra.media`
- Identity authority: Keycloak at `https://auth.codestra.co/realms/codestra`
- Native listener: loopback only (`127.0.0.1:8088`)
- Data access: certified read-only datasets and reporting schemas or replicas
- Default query row limit: 10,000; hard limit: 100,000
- Runtime status: **source prepared, not deployed**
- Production activation: **not authorized by this repository change**

No committed file contains database passwords, OIDC secrets, private keys,
customer extracts, or live tokens. Runtime secrets must be supplied as mounted
files by the approved secret-management path.

## Repository layout

| Path | Authority |
| --- | --- |
| `upstream/` | Pinned Apache Superset source snapshot |
| `CODESTRA_UPSTREAM_LOCK.json` | Exact upstream commit lock |
| `codestra/runtime-v1/` | Canonical Superset configuration, security manager, role reconciliation, Compose manifests, and readiness probe |
| `codestra/api/` | Codestra service/API contract |
| `codestra/docs/` | Corporate analytics operating model |
| `integration/` | Non-activating integration and evidence contracts |
| `orbit/` | Fail-closed Codestra Orbit adoption declaration |
| `scripts/` | Repository, runtime, identity, readiness, and governance validators |
| `.github/workflows/` | Exact-head validation and evidence-verification gates |

`codestra/runtime-v1/superset_config.py` is the canonical runtime
configuration. The `.example` copy is retained only for compatibility and CI
requires it to remain byte-for-byte identical. The canonical security manager
is `codestra_security_manager.py`; the `_v2` copy is likewise compatibility
material and may not diverge.

## Validation

Run the source-side gates before promotion:

```bash
python -m py_compile codestra/runtime-v1/*.py scripts/*.py
python scripts/validate_codestra_repository.py
python scripts/validate_codestra_superset.py
python scripts/validate_codestra_review_hardening.py
python scripts/validate_codestra_superset_oidc.py
python scripts/validate_codestra_superset_readiness.py
```

Render both Compose contracts with an immutable image reference and required
non-secret deployment metadata before deployment review. Repository validation
does not connect to a database, create an identity client, provision a
datasource, import a dashboard, or change a server.

After the release signature and provenance are verified, bind the deployment
inputs to the locally pulled signed image before Compose is rendered:

```bash
scripts/verify_release_identity.sh \
  ghcr.io/appolon1908-hue/superset-superset@sha256:<verified-digest> \
  <protected-production-source-sha>
```

The gate requires the exact canonical repository digest, the OCI source and
revision labels emitted by the protected release workflow, and the non-root
runtime user. Placeholder values are deliberately rejected.

## Promotion model

Changes move through:

`feature/docs/fix/security/upgrade → development → test → staging → production → main`

Direct feature-to-`main` merges are not the repository authority. Every
promotion must use the exact tested head, pass all required workflows, have no
unresolved review findings, and preserve false activation flags until separate
runtime evidence exists.

## Production gates

Production remains blocked until all of the following are evidenced against an
immutable release:

1. Keycloak Authorization Code + PKCE login, role synchronization, logout, and
   anonymous-access denial.
2. Read-only metadata and datasource credentials supplied outside Git.
3. Database-native and Superset row-level security, including cross-business
   denial tests.
4. Real web liveness plus metadata-database `SELECT 1` readiness.
5. Certified datasets, query budgets, backup/restore, upgrade, and rollback.
6. Attested staging evidence with denial, no-secret, no-PII, no-external-effect,
   soak, and rollback results.
7. A separate reviewed production activation change.

The evidence verification workflow downloads an exact successful
Codestra-Prometheus artifact, verifies its GitHub attestation, checks both
archive and manifest digests, and validates every required result. A supplied
checksum without the artifact and attestation cannot pass.
