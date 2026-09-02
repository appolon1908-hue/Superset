#!/usr/bin/env bash
set -Eeuo pipefail

source_sha="${1:?exact checked-out source SHA is required}"
[[ "$source_sha" =~ ^[0-9a-f]{40}$ ]]
test "$(git rev-parse HEAD)" = "$source_sha"

runtime="$(jq -er '.upstreamImage' codestra/release/runtime-base.lock.json)"
image="local/codestra-superset-integration:${source_sha}"
suffix="${source_sha:0:12}-${GITHUB_RUN_ATTEMPT:-1}"
network="superset-ci-${suffix}"
postgres="superset-postgres-${suffix}"
redis="superset-redis-${suffix}"
web="superset-web-${suffix}"
secret_root="${RUNNER_TEMP:-/tmp}/superset-secrets-${suffix}"

cleanup() {
  docker rm -f "$web" "$redis" "$postgres" >/dev/null 2>&1 || true
  docker network rm "$network" >/dev/null 2>&1 || true
  if [[ -d "$secret_root" ]]; then
    find "$secret_root" -type f -exec unlink {} \;
    rmdir "$secret_root"
  fi
}
trap cleanup EXIT

docker build \
  --file codestra/runtime-v1/Dockerfile \
  --build-arg "SUPERSET_BASE_IMAGE=$runtime" \
  --label "org.opencontainers.image.source=https://github.com/appolon1908-hue/Superset" \
  --label "org.opencontainers.image.revision=$source_sha" \
  --tag "$image" \
  .

password="$(openssl rand -hex 24)"
mkdir -m 0700 "$secret_root"
openssl rand -hex 42 >"$secret_root/secret_key"
printf '%s\n' "postgresql+psycopg2://superset:${password}@${postgres}:5432/superset" >"$secret_root/database_uri"
printf '%s\n' "redis://${redis}:6379/0" >"$secret_root/redis_url"
openssl rand -hex 32 >"$secret_root/oidc_secret"
chmod 0444 "$secret_root"/*
chmod 0555 "$secret_root"

docker network create --internal "$network"
docker run -d --name "$postgres" --network "$network" \
  -e POSTGRES_USER=superset -e POSTGRES_PASSWORD="$password" -e POSTGRES_DB=superset \
  --health-cmd='pg_isready -U superset -d superset' \
  --health-interval=2s --health-timeout=3s --health-retries=45 \
  postgres:17.6-alpine@sha256:ef257d85f76e48da1c64832459b59fcaba1a4dac97bf5d7450c77753542eee94
docker run -d --name "$redis" --network "$network" \
  --health-cmd='redis-cli ping' --health-interval=2s --health-timeout=3s --health-retries=45 \
  redis:8.2.1-alpine@sha256:987c376c727652f99625c7d205a1cba3cb2c53b92b0b62aade2bd48ee1593232

for container in "$postgres" "$redis"; do
  for attempt in $(seq 1 60); do
    state="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container")"
    [[ "$state" == healthy ]] && break
    [[ "$attempt" -lt 60 ]]
    sleep 2
  done
done

common=(
  --network "$network"
  --read-only
  --tmpfs /tmp:rw,noexec,nosuid,nodev,size=128m
  --tmpfs /app/superset_home:rw,nosuid,nodev,size=256m
  -e PYTHONDONTWRITEBYTECODE=1
  -e SUPERSET_CONFIG_PATH=/app/pythonpath/superset_config.py
  -e PYTHONPATH=/app/pythonpath
  -e KEYCLOAK_ISSUER=https://auth.codestra.co/realms/codestra
  -e SUPERSET_OAUTH_CLIENT_ID=superset-analytics
  -e SUPERSET_SECRET_KEY_FILE=/run/secrets/secret_key
  -e SUPERSET_METADATA_DATABASE_URI_FILE=/run/secrets/database_uri
  -e SUPERSET_REDIS_URL_FILE=/run/secrets/redis_url
  -e SUPERSET_OIDC_CLIENT_SECRET_FILE=/run/secrets/oidc_secret
  -v "$secret_root:/run/secrets:ro"
)

docker run --rm "${common[@]}" --entrypoint /bin/sh "$image" -ec \
  'superset db upgrade && superset init && python /app/pythonpath/bootstrap_roles.py'
docker run -d --name "$web" "${common[@]}" \
  --health-cmd='python /app/pythonpath/check_metadata_readiness.py' \
  --health-interval=3s --health-timeout=8s --health-retries=60 \
  --entrypoint /bin/sh "$image" -ec \
  'exec gunicorn --bind=0.0.0.0:8088 --workers=1 --worker-class=gevent --timeout=120 "superset.app:create_app()"'

for attempt in $(seq 1 75); do
  state="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$web")"
  [[ "$state" == healthy ]] && break
  if [[ "$attempt" -eq 75 ]]; then
    docker logs "$web"
    exit 1
  fi
  sleep 3
done

docker exec "$postgres" pg_dump -U superset -d superset -Fc -f /tmp/superset.dump
docker exec "$postgres" createdb -U superset superset_restore
docker exec "$postgres" pg_restore -U superset -d superset_restore --no-owner /tmp/superset.dump
docker exec "$postgres" psql -U superset -d superset_restore -v ON_ERROR_STOP=1 -Atc \
  "SELECT count(*) > 0 FROM information_schema.tables WHERE table_schema = 'public';" | grep -qx t
docker exec -i "$postgres" psql -U superset -d superset_restore -v ON_ERROR_STOP=1 <<'SQL'
CREATE ROLE analytics_readonly NOLOGIN;
CREATE TABLE certified_dataset (codestra_business text NOT NULL, metric_value integer NOT NULL);
INSERT INTO certified_dataset VALUES ('klyrow', 1), ('telnexa', 2);
ALTER TABLE certified_dataset ENABLE ROW LEVEL SECURITY;
ALTER TABLE certified_dataset FORCE ROW LEVEL SECURITY;
CREATE POLICY business_isolation ON certified_dataset USING (codestra_business = current_setting('app.codestra_business', true));
GRANT SELECT ON certified_dataset TO analytics_readonly;
SQL
test "$(docker exec "$postgres" psql -U superset -d superset_restore -v ON_ERROR_STOP=1 -qAtc "SET ROLE analytics_readonly; SET app.codestra_business='klyrow'; SELECT count(*) FROM certified_dataset;")" = 1
if docker exec "$postgres" psql -U superset -d superset_restore -v ON_ERROR_STOP=1 \
  -c "SET ROLE analytics_readonly; INSERT INTO certified_dataset VALUES ('klyrow', 3);"; then
  echo "read-only analytics role unexpectedly performed a write" >&2
  exit 1
fi

echo "SUPERSET_DISPOSABLE_MIGRATION_HEALTH_BACKUP_RESTORE_RLS=PASS"
