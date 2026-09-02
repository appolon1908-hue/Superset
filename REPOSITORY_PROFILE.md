# Repository Profile — `Superset`

## Identity

- **Repository:** `appolon1908-hue/Superset`
- **Category:** Authenticated analytics operator UI — Apache Superset
- **Visibility:** Public source repository; private runtime and data plane
- **Default branch:** `main`
- **Canonical hostname:** `supe.codestra.media`
- **Native bind:** `127.0.0.1:8088`
- **Target production host:** `37.27.128.39`
- **Runtime state:** Source prepared, not deployed
- **Authority:** Curated datasets, charts, dashboards, semantic metrics,
  analytics roles, and Superset row-level-security configuration

## Purpose

Provide read-only business and operational analytics from certified read
models without giving analysts direct access to provider-administration,
write-capable production databases, or cross-business data.

## Owns

- Superset runtime configuration and supported branding
- Signed configuration image derived from the exact official Apache Superset
  6.1.0 digest with hash-locked runtime extras
- Keycloak OIDC/PKCE mapping for approved global and business roles
- Curated datasets, charts, dashboards, semantic metrics, and Superset RLS
- Query limits, cache policy, metadata readiness, audit, backup/restore,
  upgrade, rollback, and source-side certification controls

## Does not own

- Operational systems of record or business mutations
- Provider-administration databases
- Write-capable analytics credentials
- Public or anonymous analytics APIs
- Email, SMS, voice, financial, trading, Odoo, or n8n activation

## Required integrations

- Keycloak client `superset-analytics`
- Authenticated Caddy edge route for `supe.codestra.media`
- Dedicated PostgreSQL metadata database
- Dedicated Redis cache and worker broker
- OpenBao or approved mounted secret files
- Certified read-only reporting schemas, replicas, or warehouse models
- Prometheus/Grafana observability and attested staging evidence

## Governance

- Promotion:
  `feature/docs/fix/security/upgrade → development → test → staging → production → main`.
- Native port `8088` remains private and loopback-bound.
- Every dataset identifies source authority, owner, business/tenant boundary,
  freshness, sensitivity, and approved purpose.
- Every custom role mirrors its supported Superset base role while preserving
  only separately granted data-access permissions and independent RLS
  relationships.
- Merge does not deploy Superset, install credentials, create Keycloak clients,
  reload Caddy, connect a datasource, or enable production traffic.
- Database passwords, OIDC secrets, customer extracts, private keys, and
  secret-bearing query results must never be committed.
