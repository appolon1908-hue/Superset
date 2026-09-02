# Backup, restore, and rollback

Before deployment, capture the exact image digest, configuration checksum, Compose manifest, Superset metadata database backup, Redis/celery state disposition, and the persistent-home volume location. Prove metadata backup restoration outside production.

The exact-head repository gate performs the non-production proof with isolated
PostgreSQL and Redis containers on an internal-only disposable network. It
applies the supported migration and role bootstrap, checks application and
metadata readiness, restores the dump into a separate database, and validates
tenant RLS plus write denial. This evidence is required but does not replace a
reviewed backup of the real installation before a later server-side change.
The disposable secret directory is traversable but not writable by the
non-root application identity; its individual files remain read-only and are
removed by the test cleanup trap.

Rollback uses the previous approved digest without rebuilding, preserves persistent data, renders Compose first, and performs a controlled up operation. Never delete the volume.

The rollback bundle must record the previous protected source SHA alongside the
previous immutable image digest. After signature and provenance verification,
run `scripts/verify_release_identity.sh PREVIOUS_IMAGE@sha256:DIGEST
PREVIOUS_SOURCE_SHA`; a mismatch blocks rollback. The candidate must also pass
the internal HTTP liveness check, CSP nonce assertions, Celery task-registration
checks, metadata migration/restore test, and role-bootstrap smoke test before it
can replace the current workload.
