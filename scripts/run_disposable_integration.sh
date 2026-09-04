#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

source_sha="${1:?exact checked-out source SHA is required}"
supplied_image="${2:-}"
evidence_path="${3:-}"
[[ "$source_sha" =~ ^[0-9a-f]{40}$ ]]
test "$(git rev-parse HEAD)" = "$source_sha"

runtime="$(jq -er '.upstreamImage' codestra/release/runtime-base.lock.json)"
if [[ -n "$supplied_image" ]]; then
  [[ "$supplied_image" =~ ^ghcr\.io/appolon1908-hue/superset-superset@sha256:[0-9a-f]{64}$ ]]
  image="$supplied_image"
  release_mode=signed-immutable
  docker pull "$image" >/dev/null
  test "$(docker image inspect "$image" --format '{{index .Config.Labels "org.opencontainers.image.source"}}')" = \
    'https://github.com/appolon1908-hue/Superset'
  test "$(docker image inspect "$image" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}')" = \
    "$source_sha"
  test "$(docker image inspect "$image" --format '{{.Config.User}}')" = '10001:10001'
  docker image inspect "$image" --format '{{json .RepoDigests}}' |
    python3 -c 'import json,sys; expected=sys.argv[1]; values=json.load(sys.stdin); raise SystemExit(0 if expected in values else 1)' \
    "$image"
else
  image="local/codestra-superset-integration:${source_sha}"
  release_mode=source-build
  docker build \
    --file codestra/runtime-v1/Dockerfile \
    --build-arg "SUPERSET_BASE_IMAGE=$runtime" \
    --label "org.opencontainers.image.source=https://github.com/appolon1908-hue/Superset" \
    --label "org.opencontainers.image.revision=$source_sha" \
    --tag "$image" \
    .
fi

suffix="${source_sha:0:12}-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}"
network="superset-ci-${suffix}"
postgres="superset-postgres-${suffix}"
redis="superset-redis-${suffix}"
web="superset-web-${suffix}"
secret_root="${RUNNER_TEMP:-/tmp}/superset-secrets-${suffix}"
backup_file="$secret_root/superset.dump"

cleanup() {
  docker rm -f "$web" "$redis" "$postgres" >/dev/null 2>&1 || true
  docker network rm "$network" >/dev/null 2>&1 || true
  rm -rf -- "$secret_root"
}
trap cleanup EXIT

password="$(openssl rand -hex 24)"
install -d -m 0711 "$secret_root"
openssl rand -hex 42 >"$secret_root/secret_key"
printf '%s\n' \
  "postgresql+psycopg2://superset:${password}@${postgres}:5432/superset" \
  >"$secret_root/database_uri"
printf '%s\n' "redis://${redis}:6379/0" >"$secret_root/redis_url"
openssl rand -hex 32 >"$secret_root/oidc_secret"
chmod 0444 "$secret_root"/secret_key "$secret_root"/database_uri \
  "$secret_root"/redis_url "$secret_root"/oidc_secret

docker network create --internal "$network" >/dev/null

docker run -d --name "$postgres" --network "$network" \
  -e POSTGRES_USER=superset \
  -e POSTGRES_PASSWORD="$password" \
  -e POSTGRES_DB=superset \
  --health-cmd='pg_isready -U superset -d superset' \
  --health-interval=2s \
  --health-timeout=3s \
  --health-retries=45 \
  postgres:17.6-alpine@sha256:ef257d85f76e48da1c64832459b59fcaba1a4dac97bf5d7450c77753542eee94 \
  >/dev/null

docker run -d --name "$redis" --network "$network" \
  --health-cmd='redis-cli ping' \
  --health-interval=2s \
  --health-timeout=3s \
  --health-retries=45 \
  redis:8.2.1-alpine@sha256:987c376c727652f99625c7d205a1cba3cb2c53b92b0b62aade2bd48ee1593232 \
  >/dev/null

wait_for_healthy() {
  local container="$1"
  local attempts="$2"
  local state
  for attempt in $(seq 1 "$attempts"); do
    state="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container")"
    if [[ "$state" == healthy ]]; then
      return 0
    fi
    if [[ "$state" == exited || "$attempt" -eq "$attempts" ]]; then
      docker logs "$container" >&2 || true
      return 1
    fi
    sleep 2
  done
}

wait_for_healthy "$postgres" 60
wait_for_healthy "$redis" 60

common=(
  --network "$network"
  --read-only
  --tmpfs /tmp:rw,noexec,nosuid,nodev,size=128m,mode=1777
  --tmpfs /app/superset_home:rw,noexec,nosuid,nodev,size=256m,mode=1777
  -e PYTHONDONTWRITEBYTECODE=1
  -e SUPERSET_CONFIG_PATH=/app/pythonpath/superset_config.py
  -e PYTHONPATH=/app/pythonpath
  -e KEYCLOAK_ISSUER=https://auth.codestra.co/realms/codestra
  -e SUPERSET_OAUTH_CLIENT_ID=superset-analytics
  -e SUPERSET_SECRET_KEY_FILE=/run/secrets/secret_key
  -e SUPERSET_METADATA_DATABASE_URI_FILE=/run/secrets/database_uri
  -e SUPERSET_REDIS_URL_FILE=/run/secrets/redis_url
  -e SUPERSET_OIDC_CLIENT_SECRET_FILE=/run/secrets/oidc_secret
  -e CODESTRA_SOURCE_SHA="$source_sha"
  -e CODESTRA_IMAGE_DIGEST="${image##*@}"
  -v "$secret_root:/run/secrets:ro"
  --mount "type=bind,source=$PWD/tests/validate_bootstrap_runtime.py,target=/app/pythonpath/validate_bootstrap_runtime.py,readonly"
  --mount "type=bind,source=$PWD/tests/validate_celery_runtime.py,target=/app/pythonpath/validate_celery_runtime.py,readonly"
)

docker run --rm "${common[@]}" --entrypoint /bin/sh "$image" -ec \
  'superset db upgrade &&
   superset init &&
   python /app/pythonpath/bootstrap_roles.py &&
   python /app/pythonpath/bootstrap_roles.py &&
   python /app/pythonpath/validate_bootstrap_runtime.py &&
   python /app/pythonpath/validate_celery_runtime.py'

start_web() {
  docker run -d --name "$web" "${common[@]}" \
    --health-cmd='python /app/pythonpath/check_metadata_readiness.py' \
    --health-interval=3s \
    --health-timeout=8s \
    --health-start-period=30s \
    --health-retries=60 \
    --entrypoint /bin/sh "$image" -ec \
    'exec gunicorn --bind=0.0.0.0:8088 --workers=1 --worker-class=gevent --timeout=120 "superset.app:create_app()"' \
    >/dev/null
  wait_for_healthy "$web" 75
  docker exec "$web" python /app/pythonpath/check_metadata_readiness.py |
    grep -qx 'SUPERSET_LIVENESS_AND_METADATA_READINESS=PASS'
}

start_web

docker exec "$postgres" pg_dump -U superset -d superset -Fc -f /tmp/superset.dump
docker exec "$postgres" pg_restore --list /tmp/superset.dump >/dev/null
docker cp "$postgres:/tmp/superset.dump" "$backup_file" >/dev/null
chmod 0400 "$backup_file"
backup_sha256="$(sha256sum "$backup_file" | awk '{print $1}')"
[[ "$backup_sha256" =~ ^[0-9a-f]{64}$ ]]

docker exec "$postgres" createdb -U superset superset_restore
docker exec "$postgres" pg_restore \
  -U superset \
  -d superset_restore \
  --no-owner \
  --no-privileges \
  /tmp/superset.dump

table_count="$(docker exec "$postgres" psql \
  -U superset \
  -d superset_restore \
  -v ON_ERROR_STOP=1 \
  -Atc "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';")"
[[ "$table_count" =~ ^[0-9]+$ ]] && (( table_count > 0 ))

docker exec -i "$postgres" psql \
  -U superset \
  -d superset_restore \
  -v ON_ERROR_STOP=1 <<'SQL'
CREATE ROLE analytics_readonly NOLOGIN;
CREATE TABLE certified_dataset (
  codestra_business text NOT NULL,
  metric_value integer NOT NULL
);
INSERT INTO certified_dataset VALUES ('klyrow', 1), ('telnexa', 2);
ALTER TABLE certified_dataset ENABLE ROW LEVEL SECURITY;
ALTER TABLE certified_dataset FORCE ROW LEVEL SECURITY;
CREATE POLICY business_isolation ON certified_dataset
  USING (codestra_business = current_setting('app.codestra_business', true));
GRANT SELECT ON certified_dataset TO analytics_readonly;
SQL

query_count() {
  local business="$1"
  docker exec "$postgres" psql \
    -U superset \
    -d superset_restore \
    -v ON_ERROR_STOP=1 \
    -qAtc "SET ROLE analytics_readonly; SET app.codestra_business='${business}'; SELECT count(*) FROM certified_dataset;"
}

test "$(query_count klyrow)" = 1
test "$(query_count telnexa)" = 1
test "$(query_count unauthorized-business)" = 0

if docker exec "$postgres" psql \
  -U superset \
  -d superset_restore \
  -v ON_ERROR_STOP=1 \
  -c "SET ROLE analytics_readonly; INSERT INTO certified_dataset VALUES ('klyrow', 3);"; then
  echo "read-only analytics role unexpectedly performed a write" >&2
  exit 1
fi

# Rehearse fail-closed runtime rollback by removing the candidate web process and
# starting the same exact immutable digest against the verified metadata state.
docker rm -f "$web" >/dev/null
web="${web}-rollback"
start_web

if [[ -n "$evidence_path" ]]; then
  EVIDENCE_PATH="$evidence_path" \
  SOURCE_SHA="$source_sha" \
  IMAGE_IDENTITY="$image" \
  IMAGE_DIGEST="${image##*@}" \
  RELEASE_MODE="$release_mode" \
  BACKUP_SHA256="$backup_sha256" \
  RESTORED_TABLE_COUNT="$table_count" \
  python3 - <<'PY'
import json
import os
from pathlib import Path

payload = {
    "schema": "codestra.superset-bounded-staging-evidence.v1",
    "source_sha": os.environ["SOURCE_SHA"],
    "image": os.environ["IMAGE_IDENTITY"],
    "image_digest": os.environ["IMAGE_DIGEST"],
    "release_mode": os.environ["RELEASE_MODE"],
    "metadata_backup_sha256": os.environ["BACKUP_SHA256"],
    "restored_table_count": int(os.environ["RESTORED_TABLE_COUNT"]),
    "migration": "PASS",
    "bootstrap_idempotency": "PASS",
    "metadata_readiness": "PASS",
    "backup_integrity": "PASS",
    "restore": "PASS",
    "runtime_rollback_restart": "PASS",
    "database_native_rls": "PASS",
    "cross_business_denial": "PASS",
    "write_attempt_denied": "PASS",
    "public_traffic_changed": False,
    "production_runtime_changed": False,
    "live_effects_enabled": False,
}
Path(os.environ["EVIDENCE_PATH"]).write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY
fi

echo SUPERSET_DISPOSABLE_MIGRATION_READINESS_BACKUP_RESTORE_RLS_WRITE_DENIAL=PASS
echo SUPERSET_BOUNDED_STAGING_ROLLBACK=PASS
