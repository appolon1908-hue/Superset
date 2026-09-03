#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

runtime_root="${1:?runtime root is required}"
secret_root="${2:?secret root is required}"
source_sha="${3:?protected source SHA is required}"
image="${4:?immutable image identity is required}"
image_digest="${5:?image digest is required}"
loopback_port="${6:?loopback port is required}"
expected_host="${7:?expected host is required}"
candidate_source="${8:?candidate Compose path is required}"
infrastructure_source="${9:?infrastructure Compose path is required}"

IFS= read -r wire_one || wire_one=
IFS= read -r wire_two || wire_two=

fail() {
  printf 'SUPERSET_PRODUCTION_DEPLOYMENT=FAIL reason=%s\n' "$1" >&2
  exit 1
}

[[ "$runtime_root" =~ ^/[A-Za-z0-9._/-]+$ ]] || fail invalid_runtime_root
[[ "$secret_root" =~ ^/[A-Za-z0-9._/-]+$ ]] || fail invalid_secret_root
[[ "$runtime_root" != / && "$runtime_root" != *'..'* && "$runtime_root" != *'//'* ]] || fail unsafe_runtime_root
[[ "$secret_root" != / && "$secret_root" != *'..'* && "$secret_root" != *'//'* ]] || fail unsafe_secret_root
[[ "$source_sha" =~ ^[0-9a-f]{40}$ ]] || fail invalid_source_sha
[[ "$image_digest" =~ ^sha256:[0-9a-f]{64}$ ]] || fail invalid_image_digest
[[ "$image" == "ghcr.io/appolon1908-hue/superset-superset@${image_digest}" ]] || fail image_identity_mismatch
[[ "$loopback_port" =~ ^[0-9]{2,5}$ ]] || fail invalid_loopback_port
(( loopback_port >= 1024 && loopback_port <= 65535 )) || fail loopback_port_out_of_range
[[ "$expected_host" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]] || fail invalid_expected_host
[[ -f "$candidate_source" && ! -L "$candidate_source" ]] || fail missing_candidate_compose
[[ -f "$infrastructure_source" && ! -L "$infrastructure_source" ]] || fail missing_infrastructure_compose
[[ -n "$wire_one" ]] || fail missing_ghcr_token

for command in awk base64 curl docker flock getent grep openssl python3 readlink sed sha256sum; do
  command -v "$command" >/dev/null 2>&1 || fail "missing_command_${command}"
done

run_uid="$(id -u)"
run_gid="$(id -g)"
root_prefix=()
if [[ "$run_uid" -eq 0 ]]; then
  :
elif command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
  root_prefix=(sudo -n)
else
  fail passwordless_sudo_required
fi

# A non-root deploy identity always executes Docker through passwordless sudo so
# Compose can read root-only secret paths without weakening their permissions.
docker_prefix=()
if [[ "$run_uid" -eq 0 ]]; then
  docker info >/dev/null 2>&1 || fail docker_access_unavailable
elif "${root_prefix[@]}" docker info >/dev/null 2>&1; then
  docker_prefix=("${root_prefix[@]}")
else
  fail docker_access_unavailable
fi

as_root() {
  "${root_prefix[@]}" "$@"
}

docker_cmd() {
  "${docker_prefix[@]}" docker "$@"
}

[[ ! -L "$runtime_root" && ! -L "$secret_root" ]] || fail symbolic_runtime_or_secret_root
as_root install -d -o "$run_uid" -g "$run_gid" -m 0750 \
  "$runtime_root" "$runtime_root/releases" "$runtime_root/backups"
as_root install -d -m 0700 "$secret_root"

lock_file="$runtime_root/.production-deploy.lock"
as_root touch "$lock_file"
as_root chown "$run_uid:$run_gid" "$lock_file"
chmod 0600 "$lock_file"
exec 9>"$lock_file"
flock -n 9 || fail deployment_lock_held

release_dir="$runtime_root/releases/$source_sha"
as_root install -d -o "$run_uid" -g "$run_gid" -m 0750 "$release_dir"
as_root install -m 0644 "$candidate_source" "$release_dir/compose.candidate.yaml"
as_root install -m 0644 "$infrastructure_source" "$release_dir/compose.infrastructure.yaml"

secret_file() {
  printf '%s/%s' "$secret_root" "$1"
}

write_secret_if_missing() {
  local path="$1"
  local value="$2"
  if as_root test -s "$path"; then
    return 0
  fi
  local temporary
  temporary="$(mktemp)"
  printf '%s\n' "$value" >"$temporary"
  chmod 0400 "$temporary"
  as_root install -m 0444 "$temporary" "$path"
  rm -f -- "$temporary"
}

superset_secret_key="$(openssl rand -hex 64)"
postgres_password="$(openssl rand -hex 32)"
redis_password="$(openssl rand -hex 32)"
write_secret_if_missing "$(secret_file secret-key)" "$superset_secret_key"
write_secret_if_missing "$(secret_file postgres-password)" "$postgres_password"

if ! as_root test -s "$(secret_file redis-acl)"; then
  redis_acl="user default on >${redis_password} ~* &* +@all"
  write_secret_if_missing "$(secret_file redis-acl)" "$redis_acl"
fi

if ! as_root test -s "$(secret_file oidc-client-secret)"; then
  if [[ -n "$wire_two" ]]; then
    decoded_two="$(printf '%s' "$wire_two" | base64 --decode)"
    [[ -n "$decoded_two" ]] || fail empty_oidc_client_secret
    write_secret_if_missing "$(secret_file oidc-client-secret)" "$decoded_two"
    unset decoded_two
  elif as_root test -s /run/secrets/superset_oidc_client_secret; then
    as_root install -m 0444 /run/secrets/superset_oidc_client_secret \
      "$(secret_file oidc-client-secret)"
  else
    fail missing_oidc_client_secret
  fi
fi

postgres_password="$(as_root cat "$(secret_file postgres-password)")"
redis_password="$(as_root sed -n 's/^user default on >\([^ ]*\).*/\1/p' "$(secret_file redis-acl)")"
[[ "$postgres_password" =~ ^[0-9a-f]{64}$ ]] || fail invalid_postgres_password_file
[[ "$redis_password" =~ ^[0-9a-f]{64}$ ]] || fail invalid_redis_acl_file
write_secret_if_missing \
  "$(secret_file metadata-database-uri)" \
  "postgresql+psycopg2://superset:${postgres_password}@superset-postgres:5432/superset"
write_secret_if_missing \
  "$(secret_file redis-url)" \
  "redis://:${redis_password}@superset-redis:6379/0"
unset postgres_password redis_password superset_secret_key wire_two

for required_secret in \
  secret-key metadata-database-uri redis-url oidc-client-secret \
  postgres-password redis-acl; do
  as_root test -s "$(secret_file "$required_secret")" || fail "missing_secret_${required_secret}"
done

for network in codestra-analytics codestra-observability; do
  if ! docker_cmd network inspect "$network" >/dev/null 2>&1; then
    docker_cmd network create --internal "$network" >/dev/null
  fi
done

runtime_env="$release_dir/runtime.env"
temporary_env="$(mktemp)"
cat >"$temporary_env" <<EOF
CODESTRA_SUPERSET_IMAGE=$image
CODESTRA_SOURCE_SHA=$source_sha
CODESTRA_IMAGE_DIGEST=$image_digest
CODESTRA_ENVIRONMENT=production
CODESTRA_REGION=hetzner-eu
CODESTRA_SERVER=$expected_host
CODESTRA_SUPERSET_DEPLOYMENT_ID=$source_sha
SUPERSET_LOOPBACK_PORT=$loopback_port
CODESTRA_ANALYTICS_NETWORK=codestra-analytics
CODESTRA_OBSERVABILITY_NETWORK=codestra-observability
SUPERSET_SECRET_KEY_FILE_SOURCE=$(secret_file secret-key)
SUPERSET_METADATA_DATABASE_URI_FILE_SOURCE=$(secret_file metadata-database-uri)
SUPERSET_REDIS_URL_FILE_SOURCE=$(secret_file redis-url)
SUPERSET_OIDC_CLIENT_SECRET_FILE_SOURCE=$(secret_file oidc-client-secret)
SUPERSET_POSTGRES_PASSWORD_FILE_SOURCE=$(secret_file postgres-password)
SUPERSET_REDIS_ACL_FILE_SOURCE=$(secret_file redis-acl)
EOF
chmod 0400 "$temporary_env"
as_root install -o "$run_uid" -g "$run_gid" -m 0440 "$temporary_env" "$runtime_env"
rm -f -- "$temporary_env"

infra_compose=(
  compose --project-name codestra-superset-infrastructure
  --env-file "$runtime_env"
  -f "$release_dir/compose.infrastructure.yaml"
)
app_compose=(
  compose --project-name codestra-superset-corporate
  --env-file "$runtime_env"
  -f "$release_dir/compose.candidate.yaml"
)

docker_cmd "${infra_compose[@]}" config --quiet
docker_cmd "${app_compose[@]}" --profile candidate-after-approval config --quiet
docker_cmd "${app_compose[@]}" --profile bootstrap-after-approval config --quiet

docker_config="$(mktemp -d)"
chmod 0700 "$docker_config"
docker_auth_cmd() {
  "${docker_prefix[@]}" env DOCKER_CONFIG="$docker_config" docker "$@"
}
cleanup_sensitive() {
  if [[ -d "${docker_config:-}" ]]; then
    docker_auth_cmd logout ghcr.io >/dev/null 2>&1 || true
    as_root rm -rf -- "$docker_config"
  fi
  unset wire_one wire_two decoded_one decoded_two
}
trap cleanup_sensitive EXIT

decoded_one="$(printf '%s' "$wire_one" | base64 --decode)"
[[ -n "$decoded_one" ]] || fail empty_ghcr_token
printf '%s' "$decoded_one" | docker_auth_cmd login ghcr.io \
  --username appolon1908-hue --password-stdin >/dev/null
unset decoded_one wire_one
docker_auth_cmd pull "$image" >/dev/null

test "$(docker_cmd image inspect "$image" --format '{{index .Config.Labels "org.opencontainers.image.source"}}')" = \
  'https://github.com/appolon1908-hue/Superset' || fail image_source_label_mismatch
test "$(docker_cmd image inspect "$image" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}')" = \
  "$source_sha" || fail image_revision_label_mismatch
test "$(docker_cmd image inspect "$image" --format '{{.Config.User}}')" = \
  '10001:10001' || fail image_runtime_user_mismatch
docker_cmd image inspect "$image" --format '{{json .RepoDigests}}' |
  python3 -c 'import json,sys; expected=sys.argv[1]; values=json.load(sys.stdin); raise SystemExit(0 if expected in values else 1)' \
  "$image" || fail local_image_digest_mismatch

previous_release=""
if as_root test -L "$runtime_root/current"; then
  previous_release="$(as_root readlink -f "$runtime_root/current")"
  [[ "$previous_release" == "$runtime_root/releases/"* ]] || fail unsafe_previous_release_link
fi

changed_runtime=false
backup_file="$runtime_root/backups/metadata-before-${source_sha}.dump"

rollback_runtime() {
  docker_cmd "${app_compose[@]}" --profile candidate-after-approval down --remove-orphans >/dev/null 2>&1 || true
  postgres_id="$(docker_cmd "${infra_compose[@]}" ps -q superset-postgres 2>/dev/null || true)"
  if [[ -n "$postgres_id" ]] && as_root test -s "$backup_file"; then
    docker_cmd cp "$backup_file" "$postgres_id:/tmp/rollback.dump" >/dev/null 2>&1 || true
    docker_cmd exec "$postgres_id" psql -U superset -d postgres -v ON_ERROR_STOP=1 -c \
      "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='superset' AND pid <> pg_backend_pid();" \
      >/dev/null 2>&1 || true
    docker_cmd exec "$postgres_id" dropdb -U superset --if-exists superset >/dev/null 2>&1 || true
    docker_cmd exec "$postgres_id" createdb -U superset -O superset superset >/dev/null 2>&1 || true
    docker_cmd exec "$postgres_id" pg_restore -U superset -d superset --no-owner --no-privileges \
      /tmp/rollback.dump >/dev/null 2>&1 || true
  fi
  if [[ -n "$previous_release" ]] && as_root test -f "$previous_release/runtime.env"; then
    previous_app=(
      compose --project-name codestra-superset-corporate
      --env-file "$previous_release/runtime.env"
      -f "$previous_release/compose.candidate.yaml"
    )
    docker_cmd "${previous_app[@]}" --profile candidate-after-approval up -d \
      superset-web superset-worker superset-beat >/dev/null 2>&1 || true
    as_root ln -sfn "$previous_release" "$runtime_root/current" || true
  fi
}

on_exit() {
  local status=$?
  trap - EXIT ERR
  if [[ "$status" -ne 0 && "$changed_runtime" == true ]]; then
    rollback_runtime || true
    printf 'SUPERSET_PRODUCTION_ROLLBACK=ATTEMPTED\n' >&2
  elif [[ "$status" -ne 0 ]]; then
    printf 'SUPERSET_PRODUCTION_ROLLBACK=NOT_REQUIRED\n' >&2
  fi
  cleanup_sensitive
  exit "$status"
}
trap on_exit EXIT

docker_cmd "${infra_compose[@]}" up -d superset-postgres superset-redis >/dev/null
for service in superset-postgres superset-redis; do
  container_id="$(docker_cmd "${infra_compose[@]}" ps -q "$service")"
  [[ -n "$container_id" ]] || fail "missing_infrastructure_container_${service}"
  for attempt in $(seq 1 90); do
    state="$(docker_cmd inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id")"
    [[ "$state" == healthy ]] && break
    if [[ "$attempt" -eq 90 ]]; then
      docker_cmd logs --tail 100 "$container_id" >&2 || true
      fail "infrastructure_unhealthy_${service}"
    fi
    sleep 2
  done
done

postgres_id="$(docker_cmd "${infra_compose[@]}" ps -q superset-postgres)"
docker_cmd exec "$postgres_id" pg_dump -U superset -d superset -Fc -f /tmp/pre-deploy.dump
docker_cmd exec "$postgres_id" pg_restore --list /tmp/pre-deploy.dump >/dev/null
temporary_backup="$(mktemp)"
docker_cmd cp "$postgres_id:/tmp/pre-deploy.dump" "$temporary_backup"
as_root install -m 0600 "$temporary_backup" "$backup_file"
rm -f -- "$temporary_backup"

changed_runtime=true
docker_cmd "${app_compose[@]}" --profile bootstrap-after-approval run --rm \
  superset-bootstrap
docker_cmd "${app_compose[@]}" --profile candidate-after-approval up -d \
  --remove-orphans superset-web superset-worker superset-beat >/dev/null

web_id="$(docker_cmd "${app_compose[@]}" ps -q superset-web)"
[[ -n "$web_id" ]] || fail missing_superset_web_container
for attempt in $(seq 1 100); do
  state="$(docker_cmd inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$web_id")"
  [[ "$state" == healthy ]] && break
  if [[ "$attempt" -eq 100 ]]; then
    docker_cmd logs --tail 200 "$web_id" >&2 || true
    fail superset_web_unhealthy
  fi
  sleep 3
done

docker_cmd "${app_compose[@]}" exec -T superset-web \
  python /app/pythonpath/check_metadata_readiness.py >/dev/null
curl --fail --silent --show-error --connect-timeout 5 --max-time 15 \
  "http://127.0.0.1:${loopback_port}/health" >/dev/null
curl --fail --silent --show-error --connect-timeout 10 --max-time 30 \
  https://supe.codestra.media/health >/dev/null

login_headers="$(mktemp)"
login_status="$(curl --silent --show-error --connect-timeout 10 --max-time 30 \
  --dump-header "$login_headers" --output /dev/null --write-out '%{http_code}' \
  https://supe.codestra.media/login/keycloak)"
[[ "$login_status" =~ ^(302|303)$ ]] || fail "oidc_login_redirect_status_${login_status}"
grep -Eqi '^location: https://auth\.codestra\.co/realms/codestra/' "$login_headers" || \
  fail oidc_login_redirect_target_mismatch
rm -f -- "$login_headers"

csrf_status="$(curl --silent --show-error --connect-timeout 10 --max-time 30 \
  --output /dev/null --write-out '%{http_code}' \
  https://supe.codestra.media/api/v1/security/csrf_token/)"
[[ "$csrf_status" =~ ^(200|302|401|403)$ ]] || fail "csrf_route_status_${csrf_status}"

as_root ln -sfn "$release_dir" "$runtime_root/current"
evidence_file="$release_dir/deployment-evidence.txt"
temporary_evidence="$(mktemp)"
cat >"$temporary_evidence" <<EOF
SUPERSET_PRODUCTION_DEPLOYMENT=PASS
PROTECTED_SOURCE_SHA=$source_sha
IMMUTABLE_IMAGE=$image
IMAGE_DIGEST=$image_digest
TARGET_HOST=$expected_host
LOOPBACK_PORT=$loopback_port
METADATA_BACKUP=$backup_file
WEB_LIVENESS=PASS
METADATA_DATABASE_READINESS=PASS
OIDC_LOGIN_REDIRECT=PASS
CSRF_ROUTE=PASS
ROLLBACK_PREPARED=PASS
PRODUCTION_EXTERNAL_EFFECTS=READ_ONLY_ANALYTICS_ONLY
EOF
as_root install -o "$run_uid" -g "$run_gid" -m 0640 \
  "$temporary_evidence" "$evidence_file"
rm -f -- "$temporary_evidence"
sha256sum "$candidate_source" "$infrastructure_source" | as_root tee \
  "$release_dir/source-checksums.sha256" >/dev/null

changed_runtime=false
printf 'SUPERSET_PRODUCTION_DEPLOYMENT=PASS\n'
printf 'SUPERSET_PROTECTED_SOURCE_SHA=%s\n' "$source_sha"
printf 'SUPERSET_IMMUTABLE_IMAGE=%s\n' "$image"
printf 'SUPERSET_METADATA_BACKUP=PASS\n'
printf 'SUPERSET_WEB_LIVENESS=PASS\n'
printf 'SUPERSET_METADATA_DATABASE_READINESS=PASS\n'
printf 'SUPERSET_OIDC_LOGIN_REDIRECT=PASS\n'
printf 'SUPERSET_CSRF_ROUTE=PASS\n'
printf 'SUPERSET_ROLLBACK_PREPARED=PASS\n'
