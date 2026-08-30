# Codestra Superset Corporate Features

## Mission

Superset is the corporate business-intelligence and management-reporting layer for Codestra and every managed business. It complements Grafana: Grafana answers operational health/incident questions; Superset answers business performance, usage, quality and trend questions.

## Corporate identity and RBAC

Use Keycloak SSO. Default access is read-only. Separate platform administrators, BI editors/analysts, business viewers and any business-scoped roles. Row-level security and dataset permissions prevent one business or tenant from seeing another business/tenant's protected analytics.

## Corporate portfolio dashboards

- Codestra executive portfolio summary;
- MoneyBee funnel, servicing and operational analytics;
- Beyvra safe trading-platform operational/business analytics;
- Breero marketplace/provider analytics;
- LARIM-A booking/provider/operations analytics;
- Transportation/Freight shipment, margin and carrier analytics;
- Booked4Seasons booking/occupancy/service analytics;
- Codestra Social publishing/campaign analytics;
- Klyrow email deliverability/usage analytics;
- Telnexa SMS delivery/usage/provider analytics;
- Kyqra crawl/job/quality analytics;
- Restaurant operational/customer analytics;
- Provisioning volume/SLA analytics.

## Enterprise features

- curated/certified datasets;
- semantic metrics definitions;
- business and tenant row-level security;
- executive scorecards and trend dashboards;
- provider quality comparisons;
- SLA attainment and customer-success views;
- cost/usage/margin reporting where authorized;
- query/time/resource limits;
- PII masking/minimization;
- auditability of dashboard/dataset changes;
- scheduled report generation with distribution handled through an approved governed path.

## Data-source policy

Superset uses read-only connections to curated analytics stores, read replicas or purpose-built reporting schemas. It must not write to production business databases or connect directly to provider-administration databases as an operational shortcut.

Credentials are injected from OpenBao or approved secret files, never Git.

## Financial boundaries

MoneyBee analytics must not submit lenders, fund loans or alter loan state. Beyvra analytics must not place/cancel/replace trades, alter balances or positions, or receive broker/exchange signing secrets.

## Release rule

`supe.codestra.media` is an authenticated browser application protected by SSO and TLS. Corporate configuration stays outside imported upstream source, and merge does not authorize deployment.
