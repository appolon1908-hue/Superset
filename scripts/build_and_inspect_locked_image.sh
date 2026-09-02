#!/usr/bin/env bash
set -Eeuo pipefail

source_sha="${1:?exact source SHA is required}"
[[ "$source_sha" =~ ^[0-9a-f]{40}$ ]]
test "$(git rev-parse HEAD)" = "$source_sha"
runtime="$(jq -r '.upstreamImage' codestra/release/runtime-base.lock.json)"
tag="local/codestra-superset:${source_sha}"
startup_dir=""
container_id=""
cleanup() {
  if [[ -n "$container_id" ]]; then
    docker container rm "$container_id" >/dev/null
  fi
  if [[ -n "$startup_dir" && -f "$startup_dir/secret" ]]; then
    unlink "$startup_dir/secret"
    rmdir "$startup_dir"
  fi
}
trap cleanup EXIT

docker build \
  --file codestra/runtime-v1/Dockerfile \
  --build-arg "SUPERSET_BASE_IMAGE=$runtime" \
  --tag "$tag" \
  .
docker run --rm --network none --entrypoint python "$tag" -c 'import importlib.metadata, gevent, psycopg2; from gunicorn.workers.ggevent import GeventWorker; assert importlib.metadata.version("apache-superset") == "6.1.0"'
startup_dir="${RUNNER_TEMP:-/tmp}/superset-startup-${source_sha}"
mkdir -p "$startup_dir"
openssl rand -out "$startup_dir/secret" -hex 32
docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,nodev \
  --mount "type=bind,source=$PWD/tests/superset_startup_config.py,target=/tmp/codestra-startup/superset_config.py,readonly" \
  --mount "type=bind,source=$startup_dir/secret,target=/run/codestra-test-secret,readonly" \
  --env SUPERSET_CONFIG_PATH=/tmp/codestra-startup/superset_config.py \
  --env CODESTRA_TEST_SECRET_FILE=/run/codestra-test-secret \
  --entrypoint python "$tag" \
  -c 'from superset.app import create_app; application = create_app(); assert application is not None'
test "$(docker image inspect "$tag" --format '{{.Config.User}}')" = '10001:10001'

container_id="$(docker create "$tag")"
evidence_dir="${RUNNER_TEMP:-/tmp}/superset-image-${source_sha}"
mkdir -p "$evidence_dir"
for file in image-build.v1.json runtime-base.lock.json runtime.v1.json; do
  docker cp "$container_id:/usr/share/codestra/$file" "$evidence_dir/$file"
done
docker cp "$container_id:/app/pythonpath/superset_config.py" "$evidence_dir/superset_config.py"
docker cp "$container_id:/app/pythonpath/codestra_security_manager.py" "$evidence_dir/codestra_security_manager.py"
docker cp "$container_id:/app/pythonpath/check_metadata_readiness.py" "$evidence_dir/check_metadata_readiness.py"
cmp codestra/release/image-build.v1.json "$evidence_dir/image-build.v1.json"
cmp codestra/release/runtime-base.lock.json "$evidence_dir/runtime-base.lock.json"
cmp codestra/runtime-v1/runtime.v1.json "$evidence_dir/runtime.v1.json"
cmp codestra/runtime-v1/superset_config.py.example "$evidence_dir/superset_config.py"
cmp codestra/runtime-v1/codestra_security_manager.py "$evidence_dir/codestra_security_manager.py"
cmp codestra/runtime-v1/check_metadata_readiness.py "$evidence_dir/check_metadata_readiness.py"
echo "SUPERSET_LOCKED_IMAGE_INSPECTION=PASS"
