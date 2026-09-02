# Backup, restore, and rollback

Before deployment, capture the exact image digest, configuration checksum, Compose manifest, Superset metadata database backup, Redis/celery state disposition, and the persistent-home volume location. Prove metadata backup restoration outside production.

Rollback uses the previous approved digest without rebuilding, preserves persistent data, renders Compose first, and performs a controlled up operation. Never delete the volume.

The rollback bundle must record the previous protected source SHA alongside the
previous immutable image digest. After signature and provenance verification,
run `scripts/verify_release_identity.sh PREVIOUS_IMAGE@sha256:DIGEST
PREVIOUS_SOURCE_SHA`; a mismatch blocks rollback. The candidate must also pass
the internal HTTP liveness check, CSP nonce assertions, Celery task-registration
checks, metadata migration/restore test, and role-bootstrap smoke test before it
can replace the current workload.
