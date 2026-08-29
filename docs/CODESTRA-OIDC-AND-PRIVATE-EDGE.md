# Codestra Superset OIDC and Private Edge

## Authority

This repository owns the Superset-specific application configuration for:

```text
https://supe.codestra.media
```

Caddy owns public TLS and reverse proxying. Keycloak owns identity. `Infustruction-repo` owns the shared private-network/firewall topology.

## Network boundary

The Superset webserver must bind to `127.0.0.1:8088` or an equivalent private Docker listener. Port 8088 must never be published on the public interface. Caddy is the only public HTTP(S) listener.

Caddy forwards the canonical host and `X-Forwarded-*` metadata. Superset enables `ENABLE_PROXY_FIX` and secure session cookies.

## OIDC

Keycloak client:

```text
superset-analytics
```

Callback:

```text
https://supe.codestra.media/oauth-authorized/keycloak
```

Required behavior:

- Authorization Code Flow;
- PKCE S256;
- exact redirect/origin allowlists;
- client secret supplied as `SUPERSET_OIDC_CLIENT_SECRET` outside Git;
- no implicit or password/direct grant;
- login rejected when the user has no approved observability role.

Role mapping:

```text
observability-viewer   -> Gamma
observability-operator -> Alpha
observability-admin    -> Admin
```

The example custom security manager extracts `realm_access.roles` from Keycloak userinfo and returns only approved roles. It must be copied beside the active `superset_config.py` at deployment time.

## Data policy

Superset is a business/operations analytics layer, not an authoritative runtime database or write surface.

Allowed:

- curated communications analytics read models;
- tenant-scoped or row-level-secured datasets;
- read-only database roles;
- aggregated usage, delivery, quality, cost, SLA, and campaign views.

Prohibited:

- live Postal, Jasmin, VICIdial, OpenBao, Keycloak, or provider administration databases;
- write-capable database credentials;
- raw secrets, message bodies, recordings, payment data, or unrestricted PII;
- direct mutation of provider or business systems.

## Deployment inputs

Required secret values are supplied outside Git:

```text
SUPERSET_SECRET_KEY
SUPERSET_METADATA_DATABASE_URI
SUPERSET_OIDC_CLIENT_SECRET
```

Curated datasource credentials are independently provisioned and should be read-only.

## Validation

```bash
python3 scripts/validate-codestra-integration.py
```

Before production access:

1. accept the Keycloak client through its protected apply flow;
2. install secrets through the approved secret path;
3. deploy Superset on a private listener;
4. configure only approved curated read models;
5. validate the exact Caddy source and reload through its release process;
6. prove unauthenticated login redirection;
7. prove users without approved roles are denied;
8. prove viewer/operator/admin role separation;
9. prove row-level/tenant isolation;
10. perform backup, restore, rollback, and external port tests.

A merge does not authorize deployment or public access.
