# Backup, restore and rollback contract

This repository defines procedures and does not operate live resources.

Before activation, the operator must record an off-host, encrypted PostgreSQL
metadata backup and the immutable configuration bundle digest. Redis is a cache
and task broker; durable scheduled-task state must be quiesced or reconciled
before rollback. Dashboard exports, dataset definitions, role mappings and row
level security definitions must be captured with the database backup.

Restore must be tested in isolated temporary PostgreSQL and Redis resources.
The test must run the exact locked image, restore the backup, execute metadata
readiness, verify OIDC denial without an approved role, verify cross-business
denial and record an evidence checksum. It must never overwrite production.

Rollback uses the previously recorded OCI index digest and signed configuration
bundle digest. Run the explicit `migrate` profile only when the target release's
reviewed migration instructions require it. Restore the prior metadata backup
only when schema compatibility cannot be maintained, then validate `/health`,
metadata `SELECT 1`, authentication, RBAC and business isolation before routing
traffic. A failed validation leaves traffic on the prior healthy release.
