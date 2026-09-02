# Repository profile

This repository owns the immutable Codestra Superset configuration image and read-only business-analytics policy. The signed image is derived from the exact official Apache Superset 6.1.0 digest and embeds the file-secret configuration, Keycloak role mapping, and bounded readiness probe.

Production activation remains disabled. Dataset certification, row-level security, write denial, OIDC, backup, and rollback require protected-environment evidence.
