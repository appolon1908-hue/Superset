# Codestra service API contract: Apache Superset

This repository owns the **certified-read-only-business-analytics-authority** for the Codestra observability, analytics, telemetry, and secrets suite.

## Communication rule

Apache Superset keeps its native API and protocol. The shared Codestra control plane in `appolon1908-hue/Codestra-Telemetry` performs only sanitized health, readiness, contract, topology, and immutable-release read-back. It never proxies dashboard, chart, dataset, SQL, credential, secret, or mutation APIs.

Canonical hostname: `supe.codestra.media`  
Native exposure: `loopback_edge_only`  
Deployment class: `central`  
Contract: `codestra/api/service-contract.v1.json`

## Native operations

| Method | Path | Category | Access | Control-plane rule |
|---|---|---|---|---|
| `GET` | `/health` | health | read_only | never proxied by the Codestra control API |
| `GET` | `/health` | readiness | read_only | never proxied by the Codestra control API |
| `GET` | `/api/v1/dashboard/` | query | read_only | never proxied by the Codestra control API |
| `GET` | `/api/v1/chart/` | query | read_only | never proxied by the Codestra control API |
| `GET` | `/api/v1/dataset/` | query | read_only | never proxied by the Codestra control API |

## Suite integrations

| Peer | Direction | Signal | Protocol | Purpose |
|---|---|---|---|---|
| `openbao` | outbound | `identity-secrets` | `secret-file` | obtain short-lived read-only dataset credentials |
| `certified-readonly-datasets` | outbound | `analytics` | `sql-read-only` | query certified row-level-secured datasets |

Datasets must be certified, read only, row-level secured, and business scoped. Superset is not permitted to connect with application-owner, migration, superuser, replication, write, or schema-administration credentials.

## Identity and correlation

Every private request should propagate `X-Correlation-ID` and W3C `traceparent` when the native protocol supports them. `request_id`, `trace_id`, and `tenant_id` remain structured, protected, non-indexed fields. Metrics use only the bounded dimensions `codestra_business`, `application`, `service`, `environment`, `server`, `region`, and `deployment`.

Business identity is deployment-controlled. Caller-supplied business identity, cross-business defaults, anonymous management access, insecure TLS verification, inline database credentials, and embedded OpenBao tokens are prohibited.

## Release and runtime boundary

The control plane reads source revision and image digest only from deployment environment variables. A valid release requires a 40-character Git SHA and `sha256:<64 lowercase hex>` image digest. This source change does not deploy Superset, create a database connection, issue a credential, import a dashboard, enable SQL Lab writes, expose the native service, or activate any business mutation.


## Contract authority handoff

- Canonical schema repository: `appolon1908-hue/Codestra-Telemetry`
- Canonical merged Telemetry SHA: `c35d880a730ca5206d445e8a9a688cb465ae2ad4`
- Contract version: `1.0.0`
- Downstream exact head: this PR branch commit; the authoritative literal SHA is the GitHub PR `headRefOid` recorded after this handoff commit.
- Deployment authorization: unauthorized until staging certification and protected production promotion are complete.
