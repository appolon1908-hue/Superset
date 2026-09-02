# Repository profile

- Repository: `appolon1908-hue/Superset`
- Component: Codestra Superset
- Release model: verified upstream image plus signed configuration artifact
- Upstream source: `apache/superset`
- Runtime image: locked in `codestra/release/runtime-image.lock.json`
- Deployment authority: `codestra/runtime-v1/compose.production.yaml`
- Configuration authority: `codestra/runtime-v1/superset_config.py`
- Promotion order: `development` -> `test` -> `staging` -> `production` -> `main`
- Runtime activation from repository workflows: prohibited

The vendored `upstream/` tree is byte-preserved and bound to
`CODESTRA_UPSTREAM_LOCK.json`. Codestra-owned files remain subject to exact-head
validation, secret scanning and protected review.
