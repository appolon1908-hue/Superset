# Backup, restore, and rollback

## Required pre-change evidence

Before any installation or upgrade, record all of the following against the
same approved change:

- protected Superset source SHA;
- verified signed image identity and immutable digest;
- image signature, provenance, SBOM, and vulnerability disposition;
- rendered Compose manifest and non-secret environment metadata;
- metadata-database backup identity, checksum, encryption state, retention, and
  off-host location;
- Redis/Celery state disposition;
- persistent `superset_home` volume identity and protection plan;
- current migration head, Keycloak client/role mapping, datasource inventory,
  dashboard/dataset export disposition, and previous known-good release;
- approved RPO, RTO, rollback owner, and abort criteria.

Do not reveal connection URIs, passwords, tokens, or customer data in evidence.
Never delete or recreate the persistent volume as part of routine rollback.

## Repository integration proof

The exact-head repository workflow performs a non-production proof using only
pinned images and an internal Docker network. It:

1. builds the reviewed derived image;
2. starts disposable PostgreSQL and Redis services;
3. supplies generated secrets through a searchable-but-nonlistable mounted
   directory with read-only files;
4. runs `superset db upgrade`, `superset init`, and role reconciliation twice;
5. verifies the business-role catalogue and Celery task/schedule registration;
6. starts Gunicorn and proves web plus metadata-database readiness;
7. creates a PostgreSQL dump and restores it into a separate database;
8. proves database-native business RLS, unauthorized-business denial, and write
   denial.

This is required source evidence, but it does not replace a fresh backup and
restore rehearsal for the actual installation before a server-side change.

## Rollback sequence

1. Stop promotion and preserve diagnostics without logging secrets.
2. Keep the current metadata database and persistent volume intact.
3. Verify the previous image's signature, provenance, SBOM, and vulnerability
   evidence.
4. Pull the previous immutable digest; never rebuild or retag it.
5. Run:

   ```bash
   scripts/verify_release_identity.sh \
     ghcr.io/appolon1908-hue/superset-superset@sha256:<previous-digest> \
     <previous-protected-source-sha>
   ```

6. Render the previous Compose/BOM inputs and compare source, digest, mounted
   secret-file names, network names, and loopback publication before applying.
7. If the failed change advanced metadata incompatibly, follow the reviewed
   database restore or forward-fix procedure; never guess a downgrade path.
8. Start the previous workload in a controlled manner and verify liveness,
   metadata readiness, OIDC, role mapping, RLS denial, bounded query behavior,
   worker/beat registration, dashboards, and audit logging.
9. Record rollback start/end time, result, data-loss assessment, restored
   identities, and follow-up issue.

The long-running web, worker, and beat services must retain
`restart: unless-stopped` in both the promoted and rollback manifests. The
bootstrap service must retain `restart: "no"`; replaying migrations or role
initialization through an automatic restart is prohibited.

A source/revision/digest mismatch, failed restore proof, failed readiness check,
missing previous artifact, or uncertain schema compatibility blocks rollback
execution until a safe recovery path is reviewed.
