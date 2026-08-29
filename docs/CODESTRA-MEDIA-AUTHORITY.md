# Codestra Superset Authority

Principal repository: `appolon1908-hue/Superset`
Canonical service host: `supe.codestra.media`
Canonical DNS target: `37.27.128.39`

Use no alternate authoritative hostname.

## Ownership
Own Superset application configuration, datasets, curated analytics connections, dashboards, RBAC templates, migrations and upgrade runbooks. Do not own source application databases, provider runtime configuration, Grafana, Caddy or secrets.

## Exposure
Browser access is allowed only through authenticated HTTPS ingress. Direct Superset service ports stay private.

## Integration
Upstream: curated analytics/read models only, with least-privilege read credentials. Downstream: authorized business/operations users.

## Branch policy
Persistent: `main`, `development`, `test`, `staging`, `production`. Temporary: `feature/*`, `fix/*`, `upgrade/*`, `security/*`, `docs/*`, `hotfix/*`, optional `release/*`, `rollback/*`. Promotion: work -> development -> test -> staging -> production -> main.
