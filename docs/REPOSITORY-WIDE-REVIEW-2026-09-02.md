# Superset Repository-Wide Review — 2026-09-02

## Scope

This review covers every open pull request, the Codestra-owned overlay for
`supe.codestra.media`, promotion branches, exact-head workflows, runtime contracts, identity and role
logic, evidence gates, repository documentation, and the imported upstream
lock. It does not certify a running server or any datasource.

## Pull-request findings

- PR 21 contained the corrected service/API contract and real metadata
  readiness probe. Its exact-head workflows passed and it was promoted from
  `test` to `staging`.
- PR 16 attempted `staging` to `production` while four review findings remained:
  issuer-bound userinfo resolution, stale custom-role permissions, an
  unsubstantiated evidence checksum, and a 50,000-row default.
- PR 9 and PR 19 were old feature branches based directly on `main`, had no
  exact-head CI, and bypassed the documented promotion chain.
- Orbit adoption remains blocked on the exact authority in
  `appolon1908-hue/SDK-repository` pull request 75.

## Repository-wide corrections

1. One issuer-bound Keycloak security implementation is used by both runtime
   manifests; the compatibility copy must remain identical.
2. OAuth userinfo uses the absolute configured realm endpoint and rejects
   malformed issuers, unverified email, missing subject, malformed role claims,
   and identities without approved roles.
3. Custom business roles are reconciled to current Alpha/Gamma permissions on
   every bootstrap. Only separately granted database/schema/datasource access
   is retained; independent RLS relationships are not overwritten.
4. Both runtime configurations enforce a 10,000-row default and 100,000-row
   hard limit.
5. Both Compose contracts use the same configuration, security manager,
   mounted secret files, non-root identity, read-only root filesystem,
   capability drop, loopback web publication, and metadata readiness probe.
6. Database migrations and role bootstrap remain an explicit one-shot
   `bootstrap` profile; they do not run during normal web/worker startup.
7. Staging evidence can no longer pass from a random checksum. The workflow
   binds an exact successful collector run to one unexpired artifact, verifies
   its GitHub attestation, validates archive and manifest hashes, checks the
   exact Superset and Middleware subjects, requires every denial/soak/rollback
   result to pass, and rejects any enabled external effect.
8. Root README, repository profile, Orbit declaration, and a repository-wide
   validator now establish one durable source authority.

## State after source remediation

The repository remains **source prepared, not deployed** (`SOURCE_PREPARED_NOT_DEPLOYED`). No runtime, database,
dataset, dashboard, DNS, Keycloak client, Caddy route, secret, communication
provider, financial capability, or business-write path is activated by these
changes.

## Remaining non-source gates

- Branch protections/rulesets must be enabled for promotion branches in GitHub
  settings.
- SDK-repository pull request 75 must be protected-merged and released before
  Orbit consumer certification.
- Codestra-Prometheus must publish the standardized attested evidence artifact
  before the staging evidence workflow can pass.
- Server-side staging tests, backup/restore, upgrade, rollback, RLS denial,
  datasource read-only enforcement, and production change approval remain
  required.
