# Security policy

Report vulnerabilities privately through GitHub Security Advisories for this
repository. Do not include production secrets, tokens, customer data or exploit
payloads in public issues.

Production controls are fail closed: Keycloak OIDC with PKCE, approved role
mapping, verified email, loopback-only publication, read-only root filesystems,
dropped capabilities, external secret files, read-only curated data sources and
explicit migrations. Direct mail and provider traffic remain disabled.

No repository workflow may deploy production or push directly to a protected
promotion branch.
