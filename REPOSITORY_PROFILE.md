# Repository Profile — `Superset`

## Identity

- **Repository:** `appolon1908-hue/Superset`
- **Category:** Analytics UI — Apache Superset
- **Visibility:** `public`
- **Default branch:** `main`
- **Canonical hostname:** `supe.codestra.media`
- **Exposure:** Browser-facing only through authenticated Caddy routing
- **Authority:** Primary curated dataset, chart, dashboard, role, and row-level-security analytics authority

## Purpose

Provides read-only business and operational analytics from curated read models without connecting analysts directly to provider-administration or write-capable production databases.

## Owns

- Superset configuration, curated datasets, charts, dashboards, semantic metrics, and row-level security
- Analytics role mapping, query limits, caching, and read-only connection policy
- Superset validation, backup/restore, upgrade, and rollback source

## Does not own

- Operational systems of record or business writes
- Direct provider-administration databases
- Write-capable analytics credentials or unrestricted cross-tenant access

## Key integrations

- Curated analytics databases/read models
- Keycloak OIDC client `superset-analytics`
- Caddy authenticated edge route
- Communications, CRM, product, and platform reporting sources through approved models

## Current priorities

1. Provision version-controlled datasets, charts, and dashboards
2. Enforce tenant-safe row-level security and least-privilege roles
3. Add query timeouts, resource controls, audit, and data-freshness indicators
4. Prove OIDC, read-only credentials, backup/restore, upgrade, and rollback

## Governance and safety

- Promotion model: `feature/docs/fix/security/upgrade -> development -> test -> staging -> production -> main`.
- Native port `8088` must remain private; public access is only through `supe.codestra.media` and approved authentication.
- Never commit database passwords, OIDC secrets, customer data extracts, private keys, or secret-bearing query results.
- Every dataset must identify its authoritative source, tenant boundary, freshness, and approved purpose.
- Merge does not deploy Superset, install credentials, create Keycloak clients, reload Caddy, or enable database writes.

## Account-wide catalog

See `appolon1908-hue/documentaions/REPOSITORY_CATALOG.md`.
