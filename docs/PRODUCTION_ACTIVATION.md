# Superset Production Activation

## Authority

This runbook activates the signed Codestra Superset image on the canonical host
`37.27.128.39` and loopback endpoint `127.0.0.1:18088`. Caddy remains the public
TLS authority for `https://supe.codestra.media`; Keycloak remains the identity
authority at `https://auth.codestra.co/realms/codestra`.

The release workflow is fail-closed. It first verifies the exact `production`
branch SHA, pinned SSH host key, server capacity, DNS, TLS, Caddy route, Keycloak
discovery and the `superset-analytics` authorization endpoint. It does not alter
SSH configuration, firewall policy, DNS, Caddy, Keycloak, or unrelated Docker
workloads.

## Required protected GitHub environment

Create a protected `production` environment in this repository. It must supply:

| Name | Type | Required | Purpose |
| --- | --- | --- | --- |
| `PRODUCTION_SSH_PRIVATE_KEY` | secret | yes | Existing deploy identity; no key is generated or installed on the server |
| `PRODUCTION_SSH_KNOWN_HOSTS` | secret | yes | Pinned host-key line for strict host verification |
| `SUPERSET_OIDC_CLIENT_SECRET` | secret | conditional | Required when the approved secret is not already available at `/run/secrets/superset_oidc_client_secret` on the target |
| `PRODUCTION_HOST` | secret or variable | no | Defaults to `37.27.128.39` |
| `PRODUCTION_USER` | secret or variable | no | Defaults to `root`; a non-root identity needs passwordless sudo and Docker access |
| `PRODUCTION_SSH_PORT` | variable | no | Defaults to `22` |
| `PRODUCTION_RUNTIME_ROOT` | variable | no | Defaults to `/srv/codestra/superset` |
| `PRODUCTION_SECRET_ROOT` | variable | no | Defaults to `/etc/codestra/secrets/superset` |
| `SUPERSET_LOOPBACK_PORT` | variable | no | Defaults to `18088` |

Environment reviewers should be retained where the GitHub plan supports them.
Repository and environment secrets are never written to GitHub artifacts or
command arguments. The OIDC secret and run-scoped GHCR token are base64 encoded
only for transport through the already authenticated SSH channel and are read
from standard input by the remote deployment script.

## Activation sequence

1. The workflow proves that it is operating on the exact current production
   commit and generates a publish-once release tag.
2. A read-only remote preflight verifies strict SSH access, Docker Compose,
   capacity, DNS, TLS, the Caddy route, Keycloak discovery, and the Superset
   OIDC client redirect contract.
3. The reusable Codestra release workflow builds the manifest-defined image,
   scans source and image, publishes by digest, emits provenance and SBOM
   attestations, and signs the exact digest.
4. The deploy job authenticates to GHCR with the run-scoped GitHub token,
   resolves the immutable digest, verifies image labels and GitHub attestation,
   and transfers a checksum-bound deployment package.
5. The target creates only the dedicated `codestra-superset-*` networks,
   volumes, infrastructure services, and application services. It does not
   remove or reconfigure unrelated containers.
6. A dedicated PostgreSQL 17.6 metadata database and Redis 8.2.1 broker are
   started from exact digests. Generated credentials remain in the root-only
   secret directory and are mounted into containers as files.
7. A logical metadata backup is taken and validated before migration. The
   one-shot bootstrap runs `superset db upgrade`, `superset init`, and Codestra
   role reconciliation. Normal web, worker, and beat startup never runs a
   migration.
8. The web service must become healthy only after `/health` and metadata
   `SELECT 1` pass. Public HTTPS, OIDC redirect, CSRF route, and intentionally
   disabled Swagger behavior are then tested from an independent GitHub runner.
9. Evidence is retained for one year. On failure after runtime mutation, the
   workflow stops the candidate, restores the pre-deploy metadata dump, and
   attempts to restore the previous immutable release without deleting volumes.

## Stop conditions

The workflow stops before release or deployment when any of these are true:

- the selected SHA is not the exact current `production` head;
- the SSH key or pinned known-host record is absent;
- less than 8 GiB of Docker disk or 3 GiB of available memory remains;
- `supe.codestra.media` does not resolve to the approved host;
- TLS, Caddy route, Keycloak discovery, or the OIDC client redirect is invalid;
- Docker access or passwordless sudo is unavailable;
- the release tag already exists;
- image digest, source label, runtime user, provenance, or attestation differs;
- the OIDC client secret is unavailable;
- metadata backup, migration, bootstrap, readiness, public liveness, OIDC
  redirect, CSRF route, or rollback preparation fails.

## Remaining business-data certification

A successful activation establishes the authenticated Superset platform and its
dedicated metadata services. It does not invent business datasets or grant
write access. Each datasource still requires a separately approved read-only
credential, dataset ownership, freshness policy, PII classification,
database-native RLS, Superset RLS, and negative cross-business evidence before
that datasource is exposed to a business role.
