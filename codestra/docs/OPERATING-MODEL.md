# Codestra Superset operating model

## Product boundary

Superset is the management and business-intelligence portal for Codestra and the businesses it manages. Grafana remains the operational incident and infrastructure portal. Superset does not become an operational control plane, provider-administration console, communications sender, identity authority, secret store, lender gateway or trading terminal.

## Corporate user experience

The authenticated landing page must present a Codestra portfolio summary and then business-scoped workspaces. Every dashboard identifies its business, owner, data-freshness SLA, certification status and last reviewed date. Executive scorecards lead with decisions and exceptions rather than raw charts. Operations views include volume, SLA, backlog, quality, customer-success and data-quality context.

## Identity and access

All browser access uses Keycloak Authorization Code flow with PKCE. Anonymous access is denied. A user must carry an approved global or business role. Business roles are `business-<business>-viewer` or `business-<business>-analyst`; they are paired with row-level security on `codestra_business`. Cross-business access requires an explicit portfolio role and must never be inferred from a customer-controlled claim.

`superset-admin`, `superset-analyst`, `superset-viewer` and `superset-security-auditor` are platform-controlled roles. Admin, dataset-editor and viewer duties remain separate. Role synchronization occurs at login and access is removed when Keycloak removes the role.

## Datasource rules

Only curated reporting schemas, read replicas or analytics warehouses are approved. Connections are read-only and use credentials delivered by OpenBao or approved secret files. Direct production write credentials, provider-administration databases, broker/exchange signing credentials and unrestricted raw operational schemas are prohibited.

Every dataset has an owner, description, sensitivity classification, business column, freshness SLA and certification status. PII is masked, pseudonymized or excluded. Small cohorts are suppressed when identification risk exists.

## Row-level security

Access is deny-by-default. Every business dataset carries `codestra_business`. Business roles receive a fixed server-managed clause, never a clause derived from URL parameters, form input or client headers. Tenant-level restrictions use a protected `tenant_scope_id` only after an explicit dataset and identity review. Release evidence must include positive same-business tests and negative cross-business tests.

## Query and performance governance

Interactive queries default to 10,000 rows, have a hard limit of 100,000 rows and time out after 60 seconds. Reusable dashboards use cached results. Cross-database queries, production DDL/DML, unrestricted template processing and uncontrolled SQL Lab access are prohibited. Expensive datasets receive dedicated concurrency and freshness budgets.

## Scheduled reports

Superset may generate approved PDF, PNG or CSV artifacts. Direct SMTP, SMS or voice credentials are not stored in Superset. Distribution is disabled until an approved Middleware notification path validates recipients, business scope, sensitivity and audit metadata.

## Financial boundaries

MoneyBee reporting cannot submit applications to lenders, initiate funding or change loan state. Beyvra reporting cannot place, cancel or replace trades, alter balances or positions, or receive broker/exchange signing credentials. Financial figures must identify whether they are authoritative, delayed, estimated or reconciled.

## Promotion

Promotion is `feature/* -> development -> test -> staging -> production -> main`. A green source PR proves configuration quality only. Production additionally requires immutable image evidence, Keycloak role tests, datasource approval, RLS denial tests, PII review, performance evidence, dashboard ownership and Caddy route approval.
