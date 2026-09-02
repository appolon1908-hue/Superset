# Upgrade procedure

1. Select an official Apache Superset release and record its tag commit, OCI
   index, linux/amd64 child manifest, declared user and source labels.
2. Update the runtime image lock and canonical Compose file in one focused PR.
3. Review upstream release notes and migrations. Test backup and restore with
   disposable PostgreSQL and Redis resources.
4. Run exact-head configuration, OIDC, tenant-isolation, migration, secret,
   vulnerability, SBOM and provenance gates.
5. Promote through `development`, `test`, `staging`, `production`, then `main`
   using protected PRs. Publish the signed configuration release from the exact
   protected production SHA.
6. A later approved server mission may run the explicit `migrate` profile once,
   then start web, worker and beat. Routine services never create or migrate the
   schema automatically.

Rollback follows `BACKUP_RESTORE_ROLLBACK.md` and uses recorded prior digests;
never substitute a mutable tag.
