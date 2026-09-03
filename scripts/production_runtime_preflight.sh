#!/usr/bin/env bash
set -Eeuo pipefail

runtime_root="${1:?runtime root is required}"
secret_root="${2:?secret root is required}"
expected_host="${3:?expected production host is required}"
loopback_port="${4:?loopback port is required}"

fail() {
  printf 'SUPERSET_PRODUCTION_PREFLIGHT=FAIL reason=%s\n' "$1" >&2
  exit 1
}

[[ "$runtime_root" =~ ^/[A-Za-z0-9._/-]+$ ]] || fail invalid_runtime_root
[[ "$secret_root" =~ ^/[A-Za-z0-9._/-]+$ ]] || fail invalid_secret_root
[[ "$runtime_root" != / && "$runtime_root" != *'..'* && "$runtime_root" != *'//'* ]] || fail unsafe_runtime_root
[[ "$secret_root" != / && "$secret_root" != *'..'* && "$secret_root" != *'//'* ]] || fail unsafe_secret_root
[[ "$expected_host" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]] || fail invalid_expected_host
[[ "$loopback_port" =~ ^[0-9]{2,5}$ ]] || fail invalid_loopback_port
(( loopback_port >= 1024 && loopback_port <= 65535 )) || fail loopback_port_out_of_range

for command in awk curl df dirname docker getent grep openssl python3 sed sha256sum sort ss; do
  command -v "$command" >/dev/null 2>&1 || fail "missing_command_${command}"
done

docker_prefix=()
if docker info >/dev/null 2>&1; then
  :
elif command -v sudo >/dev/null 2>&1 && sudo -n docker info >/dev/null 2>&1; then
  docker_prefix=(sudo -n)
else
  fail docker_access_unavailable
fi
"${docker_prefix[@]}" docker compose version >/dev/null 2>&1 || fail docker_compose_unavailable

if [[ "$(id -u)" -ne 0 ]]; then
  command -v sudo >/dev/null 2>&1 || fail passwordless_sudo_required
  sudo -n true >/dev/null 2>&1 || fail passwordless_sudo_required
fi

for path in "$runtime_root" "$secret_root"; do
  [[ ! -L "$path" ]] || fail "symbolic_path_${path//\//_}"
  parent="$(dirname "$path")"
  while [[ ! -e "$parent" && "$parent" != / ]]; do
    parent="$(dirname "$parent")"
  done
  [[ -d "$parent" ]] || fail "missing_parent_${path//\//_}"
done

docker_root="$("${docker_prefix[@]}" docker info --format '{{.DockerRootDir}}')"
[[ "$docker_root" == /* && -d "$docker_root" ]] || fail docker_root_unavailable
available_kib="$("${docker_prefix[@]}" df -Pk "$docker_root" 2>/dev/null | awk 'NR==2 {print $4}')"
[[ "$available_kib" =~ ^[0-9]+$ ]] || fail docker_disk_capacity_unknown
(( available_kib >= 8388608 )) || fail docker_disk_below_8GiB

mem_available_kib="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
[[ "$mem_available_kib" =~ ^[0-9]+$ ]] || fail memory_capacity_unknown
(( mem_available_kib >= 3145728 )) || fail memory_below_3GiB

resolved="$(getent ahostsv4 supe.codestra.media | awk '{print $1}' | sort -u)"
grep -qx "$expected_host" <<<"$resolved" || fail superset_dns_not_bound_to_expected_host

issuer_file="$(mktemp)"
auth_file="$(mktemp)"
cleanup() {
  rm -f -- "$issuer_file" "$auth_file"
}
trap cleanup EXIT

curl --fail --silent --show-error --location \
  --connect-timeout 10 --max-time 30 \
  https://auth.codestra.co/realms/codestra/.well-known/openid-configuration \
  >"$issuer_file" || fail keycloak_discovery_unavailable
python3 - "$issuer_file" <<'PY' || fail keycloak_issuer_mismatch
import json
import sys
from pathlib import Path
value = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
raise SystemExit(0 if value.get("issuer") == "https://auth.codestra.co/realms/codestra" else 1)
PY

challenge='AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
auth_status="$(curl --silent --show-error \
  --connect-timeout 10 --max-time 30 \
  --output "$auth_file" --write-out '%{http_code}' \
  --get 'https://auth.codestra.co/realms/codestra/protocol/openid-connect/auth' \
  --data-urlencode 'client_id=superset-analytics' \
  --data-urlencode 'redirect_uri=https://supe.codestra.media/oauth-authorized/keycloak' \
  --data-urlencode 'response_type=code' \
  --data-urlencode 'scope=openid profile email roles' \
  --data-urlencode 'code_challenge_method=S256' \
  --data-urlencode "code_challenge=${challenge}")" || fail keycloak_authorization_probe_failed
[[ "$auth_status" =~ ^(200|302|303)$ ]] || fail "keycloak_authorization_status_${auth_status}"
if grep -Eqi 'client[ _-]*(not found|invalid)|invalid[ _-]*redirect|invalid parameter' "$auth_file"; then
  fail keycloak_superset_client_rejected
fi

route_status="$(curl --silent --show-error \
  --connect-timeout 10 --max-time 30 \
  --output /dev/null --write-out '%{http_code}' \
  https://supe.codestra.media/health)" || fail superset_tls_or_route_unavailable
case "$route_status" in
  200|301|302|401|403|502|503) ;;
  404) fail caddy_superset_route_missing ;;
  *) fail "unexpected_caddy_route_status_${route_status}" ;;
esac

if ss -H -ltn "sport = :${loopback_port}" | grep -q .; then
  compose_projects="$("${docker_prefix[@]}" docker ps \
    --filter "publish=${loopback_port}" \
    --format '{{.Label "com.docker.compose.project"}}' | sed '/^$/d' | sort -u)"
  grep -qx 'codestra-superset-corporate' <<<"$compose_projects" || \
    fail loopback_port_owned_by_other_process
  existing_status="$(curl --silent --show-error --connect-timeout 3 --max-time 5 \
    --output /dev/null --write-out '%{http_code}' \
    "http://127.0.0.1:${loopback_port}/health" || true)"
  [[ "$existing_status" == 200 ]] || fail existing_superset_loopback_unhealthy
  printf 'SUPERSET_EXISTING_LOOPBACK_HEALTH=PASS\n'
else
  printf 'SUPERSET_LOOPBACK_PORT_AVAILABLE=PASS\n'
fi

for network in codestra-analytics codestra-observability; do
  if "${docker_prefix[@]}" docker network inspect "$network" >/dev/null 2>&1; then
    printf 'SUPERSET_NETWORK_%s=EXISTS\n' "${network//-/_}"
  else
    printf 'SUPERSET_NETWORK_%s=CREATE_ON_DEPLOY\n' "${network//-/_}"
  fi
done

printf 'SUPERSET_PRODUCTION_PREFLIGHT=PASS\n'
printf 'SUPERSET_TARGET_HOST=%s\n' "$expected_host"
printf 'SUPERSET_LOOPBACK_PORT=%s\n' "$loopback_port"
printf 'SUPERSET_CADDY_ROUTE_STATUS=%s\n' "$route_status"
printf 'SUPERSET_KEYCLOAK_CLIENT_PROBE=PASS\n'
printf 'SUPERSET_DOCKER_ROOT=%s\n' "$docker_root"
printf 'SUPERSET_DOCKER_DISK_AVAILABLE_KIB=%s\n' "$available_kib"
printf 'SUPERSET_MEMORY_AVAILABLE_KIB=%s\n' "$mem_available_kib"
