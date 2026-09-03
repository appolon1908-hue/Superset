# Security policy

Report security issues privately to the repository owner. Never commit database DSNs, Redis credentials, OIDC secrets, session keys, cookies, or authentication headers.

Superset credentials are mounted from approved files. Analytics sources must be read-only, curated, and row-level-security constrained. Direct report delivery and production writes remain disabled.
