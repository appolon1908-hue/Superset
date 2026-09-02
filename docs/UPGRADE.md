# Upgrade policy

## Source and base-image selection

Upgrade only to an official Apache Superset release. Resolve the release tag to
its exact Git commit and multi-platform OCI index, then verify the unique
`linux/amd64` child manifest, package version, embedded source labels, declared
runtime user, and upstream signature disposition before changing repository
locks.

Update together, in one reviewed pull request:

- `CODESTRA_UPSTREAM.json` and `CODESTRA_UPSTREAM_LOCK.json`;
- the byte-preserved `upstream/` source snapshot and imported tree SHA;
- `codestra/release/runtime-base.lock.json`;
- `codestra/release/image-build.v1.json`;
- hash-locked runtime dependencies and the Dockerfile when the new release
  requires them;
- configuration, security manager, bootstrap, readiness, Compose, tests,
  documentation, and rollback evidence.

The vendored source is audit and upgrade-review material, not executable
production authority. The executable artifact remains the Codestra signed image
derived from the exact locked official base.

## Required validation

Before promotion, the same source SHA must pass:

1. complete JSON/YAML/Python and repository-policy validation;
2. secret scanning and immutable-action checks;
3. exact derived-image build and package/runtime import inspection;
4. read-only, network-disabled Superset application startup;
5. metadata migration, `superset init`, repeated role bootstrap, role catalogue,
   CSP, internal health, and Celery registration checks;
6. internal-only PostgreSQL/Redis migration, readiness, backup/restore, RLS,
   unauthorized-business, and write-denial proof;
7. source and synthetic-merge image builds;
8. protected-branch validation through development, test, staging, production,
   and main.

No migration runs automatically in the normal web, worker, or beat services.
The one-shot `bootstrap-after-approval` profile is the only repository-defined
migration and role-initialization path.

## Release and deployment identity

The protected production SHA is released through the pinned reusable image
workflow. Before any later installation:

- verify the keyless signature and signer identity;
- verify provenance and SBOM subjects against the same digest;
- confirm vulnerability and secret-scan policy results;
- pull only the immutable digest;
- run:

  ```bash
  scripts/verify_release_identity.sh \
    ghcr.io/appolon1908-hue/superset-superset@sha256:<verified-digest> \
    <protected-production-source-sha>
  ```

The readback must prove the OCI source label, protected revision label,
canonical repository digest, and non-root runtime user all agree. A mutable tag,
syntactically valid but differently labeled digest, or source/digest mismatch is
not an eligible upgrade.

## Staging and production

Use a fresh metadata backup and restore proof before applying the migration to a
real environment. Validate OIDC login/logout, role synchronization, database and
Superset RLS, read-only datasource credentials, query limits, web/worker/beat
health, dashboards, alerts-disabled behavior, audit logging, and rollback.

Promotion does not itself authorize deployment. Production activation requires a
separate reviewed change with exact source/image identities, runtime evidence,
rollback authority, and all activation flags explicitly approved.
