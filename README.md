# Codestra Superset

Repository authority for the Codestra Superset analytics control plane. The
canonical production desired state is
`codestra/runtime-v1/compose.production.yaml`; merging this repository does not
deploy or activate it.

The runtime uses the verified Apache Superset 6.1.0 `dev` target by immutable
index digest because the upstream lean target omits the PostgreSQL driver
required by the production metadata topology. The larger upstream target is
accepted only after the exact-digest vulnerability gate. A separately signed
Codestra configuration bundle embeds the protected source SHA and runtime
digest in `release-identity.json`; every service verifies that identity before
startup. Secrets
must be supplied as external files. Keycloak OIDC is mandatory, the native web
listener is loopback-only, and direct SMTP, SMS, voice and provider traffic are
disabled.

Validate with:

```sh
python3 -m pip install -r requirements-validation.txt
python3 scripts/validate_repository_readiness.py
python3 -m unittest discover -s tests -p 'test_*.py'
python3 scripts/build_config_bundle.py \
  --source-revision "$(git rev-parse HEAD)" \
  --output /tmp/superset-config.tar.gz
```

Activation requires a separate reviewed server mission with real protected
merge, release, configuration and rollback identities.
