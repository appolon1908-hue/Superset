# Backup, restore, and rollback

Before deployment, capture the exact image digest, configuration checksum, Compose manifest, Superset metadata database backup, Redis/celery state disposition, and the persistent-home volume location. Prove metadata backup restoration outside production.

Rollback uses the previous approved digest without rebuilding, preserves persistent data, renders Compose first, and performs a controlled up operation. Never delete the volume.
