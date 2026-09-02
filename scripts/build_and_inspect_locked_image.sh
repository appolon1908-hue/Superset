#!/usr/bin/env bash
set -Eeuo pipefail

source_sha="${1:?exact source SHA is required}"
[[ "$source_sha" =~ ^[0-9a-f]{40}$ ]]
test "$(git rev-parse HEAD)" = "$source_sha"

runtime="$(jq -r '.upstreamImage' codestra/release/runtime-base.lock.json)"
tag="local/codestra-superset:${source_sha}"
work_root="${RUNNER_TEMP:-/tmp}"
startup_dir="${work_root}/superset-startup-${source_sha}"
evidence_dir="${work_root}/superset-image-${source_sha}"
container_id=""

cleanup() {
  if [[ -n "$container_id" ]]; then
    docker container rm -f "$container_id" >/dev/null 2>&1 || true
  fi
  rm -rf -- "$startup_dir" "$evidence_dir"
}
trap cleanup EXIT
rm -rf -- "$startup_dir" "$evidence_dir"
mkdir -p "$startup_dir" "$evidence_dir"

docker build \
  --file codestra/runtime-v1/Dockerfile \
  --build-arg "SUPERSET_BASE_IMAGE=$runtime" \
  --tag "$tag" \
  .

docker run --rm --network none --entrypoint python "$tag" -c \
  'import importlib.metadata, gevent, psycopg2; from gunicorn.workers.ggevent import GeventWorker; assert importlib.metadata.version("apache-superset") == "6.1.0"'

# Prove that the exact image can construct a Superset application under a
# read-only filesystem without network access or a committed secret.
openssl rand -out "$startup_dir/startup_secret" -hex 32
chmod 0444 "$startup_dir/startup_secret"
docker run --rm --network none --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,nodev,mode=1777 \
  --mount "type=bind,source=$PWD/tests/superset_startup_config.py,target=/tmp/codestra-startup/superset_config.py,readonly" \
  --mount "type=bind,source=$startup_dir/startup_secret,target=/run/codestra-test-secret,readonly" \
  --env SUPERSET_CONFIG_PATH=/tmp/codestra-startup/superset_config.py \
  --env CODESTRA_TEST_SECRET_FILE=/run/codestra-test-secret \
  --env PYTHONDONTWRITEBYTECODE=1 \
  --entrypoint python "$tag" \
  -c 'from superset.app import create_app; application = create_app(); assert application is not None'

# Execute the real embedded configuration and one-shot bootstrap against a
# fresh disposable metadata store. Running bootstrap twice proves idempotency;
# runtime validators confirm all business roles and Celery registrations.
openssl rand -out "$startup_dir/superset_secret_key" -hex 32
printf '%s\n' 'sqlite:////tmp/superset-bootstrap.db' > "$startup_dir/superset_metadata_database_uri"
printf '%s\n' 'redis://127.0.0.1:6379/0' > "$startup_dir/superset_redis_url"
printf '%s\n' 'ci-only-oidc-client-secret' > "$startup_dir/superset_oidc_client_secret"
chmod 0444 \
  "$startup_dir/superset_secret_key" \
  "$startup_dir/superset_metadata_database_uri" \
  "$startup_dir/superset_redis_url" \
  "$startup_dir/superset_oidc_client_secret"

docker run --rm --network none --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,nodev,mode=1777 \
  --tmpfs /app/superset_home:rw,noexec,nosuid,nodev,mode=1777 \
  --mount "type=bind,source=$startup_dir,target=/run/codestra-bootstrap-secrets,readonly" \
  --mount "type=bind,source=$PWD/tests/validate_bootstrap_runtime.py,target=/app/pythonpath/validate_bootstrap_runtime.py,readonly" \
  --mount "type=bind,source=$PWD/tests/validate_celery_runtime.py,target=/app/pythonpath/validate_celery_runtime.py,readonly" \
  --env KEYCLOAK_ISSUER=https://auth.codestra.co/realms/codestra \
  --env SUPERSET_OAUTH_CLIENT_ID=superset-analytics \
  --env SUPERSET_SECRET_KEY_FILE=/run/codestra-bootstrap-secrets/superset_secret_key \
  --env SUPERSET_METADATA_DATABASE_URI_FILE=/run/codestra-bootstrap-secrets/superset_metadata_database_uri \
  --env SUPERSET_REDIS_URL_FILE=/run/codestra-bootstrap-secrets/superset_redis_url \
  --env SUPERSET_OIDC_CLIENT_SECRET_FILE=/run/codestra-bootstrap-secrets/superset_oidc_client_secret \
  --env PYTHONDONTWRITEBYTECODE=1 \
  --entrypoint /bin/sh "$tag" -ec \
  'superset db upgrade &&
   superset init &&
   python /app/pythonpath/bootstrap_roles.py &&
   python /app/pythonpath/bootstrap_roles.py &&
   python /app/pythonpath/validate_bootstrap_runtime.py &&
   python /app/pythonpath/validate_celery_runtime.py'

echo "SUPERSET_BOOTSTRAP_AND_CELERY_RUNTIME=PASS"
test "$(docker image inspect "$tag" --format '{{.Config.User}}')" = '10001:10001'

container_id="$(docker create "$tag")"
for file in image-build.v1.json runtime-base.lock.json runtime.v1.json; do
  docker cp "$container_id:/usr/share/codestra/$file" "$evidence_dir/$file"
done
docker cp "$container_id:/app/pythonpath/superset_config.py" "$evidence_dir/superset_config.py"
docker cp "$container_id:/app/pythonpath/codestra_security_manager.py" "$evidence_dir/codestra_security_manager.py"
docker cp "$container_id:/app/pythonpath/bootstrap_roles.py" "$evidence_dir/bootstrap_roles.py"
docker cp "$container_id:/app/pythonpath/check_metadata_readiness.py" "$evidence_dir/check_metadata_readiness.py"

cmp codestra/release/image-build.v1.json "$evidence_dir/image-build.v1.json"
cmp codestra/release/runtime-base.lock.json "$evidence_dir/runtime-base.lock.json"
cmp codestra/runtime-v1/runtime.v1.json "$evidence_dir/runtime.v1.json"
cmp codestra/runtime-v1/superset_config.py.example "$evidence_dir/superset_config.py"
cmp codestra/runtime-v1/codestra_security_manager.py "$evidence_dir/codestra_security_manager.py"
cmp codestra/runtime-v1/bootstrap_roles.py "$evidence_dir/bootstrap_roles.py"
cmp codestra/runtime-v1/check_metadata_readiness.py "$evidence_dir/check_metadata_readiness.py"

echo "SUPERSET_LOCKED_IMAGE_INSPECTION=PASS"
