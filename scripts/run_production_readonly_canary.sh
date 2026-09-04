#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

source_sha="${1:?exact production source SHA is required}"
image="${2:?exact immutable image is required}"
image_digest="${3:?exact image digest is required}"
staging_evidence="${4:?bounded staging evidence is required}"
output_path="${5:?production canary evidence path is required}"

controller="${SUPERSET_CANARY_CONTROLLER:?SUPERSET_CANARY_CONTROLLER is required}"
controller_sha256="${SUPERSET_CANARY_CONTROLLER_SHA256:?SUPERSET_CANARY_CONTROLLER_SHA256 is required}"
percent="${SUPERSET_CANARY_PERCENT:-1}"
base_url="${SUPERSET_PRODUCTION_BASE_URL:-https://supe.codestra.media}"
readonly_token="${SUPERSET_READONLY_BEARER_TOKEN:-}"

fail() {
  printf 'SUPERSET_PRODUCTION_READONLY_CANARY=FAIL reason=%s\n' "$1" >&2
  exit 1
}

[[ "$source_sha" =~ ^[0-9a-f]{40}$ ]] || fail invalid_source_sha
[[ "$image_digest" =~ ^sha256:[0-9a-f]{64}$ ]] || fail invalid_image_digest
[[ "$image" == "ghcr.io/appolon1908-hue/superset-superset@${image_digest}" ]] || fail image_identity_mismatch
[[ "$controller" = /* && "$controller" != *..* && "$controller" != *//* ]] || fail unsafe_controller_path
[[ "$controller_sha256" =~ ^[0-9a-f]{64}$ ]] || fail invalid_controller_sha256
[[ "$base_url" =~ ^https://[A-Za-z0-9.-]+(:[0-9]{2,5})?$ ]] || fail unsafe_production_base_url
python3 - "$percent" <<'PY' || exit 1
from decimal import Decimal, InvalidOperation
import sys
try:
    value = Decimal(sys.argv[1])
except InvalidOperation as exc:
    raise SystemExit("invalid canary percentage") from exc
if not (Decimal("0") < value <= Decimal("1")):
    raise SystemExit("canary percentage must be greater than zero and no more than one")
PY

for command in curl jq python3 sha256sum stat; do
  command -v "$command" >/dev/null 2>&1 || fail "missing_command_${command}"
done
[[ -f "$staging_evidence" && ! -L "$staging_evidence" ]] || fail missing_staging_evidence
[[ -f "$controller" && -x "$controller" && ! -L "$controller" ]] || fail invalid_controller_file
[[ "$(stat -c '%u' "$controller")" = 0 ]] || fail controller_not_root_owned
mode="$(stat -c '%a' "$controller")"
(( (8#$mode & 8#022) == 0 )) || fail controller_group_or_world_writable
echo "${controller_sha256}  ${controller}" | sha256sum --check - >/dev/null || fail controller_checksum_mismatch

staging_sha256="$(sha256sum "$staging_evidence" | awk '{print $1}')"
python3 - "$staging_evidence" "$source_sha" "$image" "$image_digest" <<'PY' || exit 1
import json, sys
path, source_sha, image, digest = sys.argv[1:]
data = json.load(open(path, encoding="utf-8"))
required = {
    "schema": "codestra.superset-bounded-staging-evidence.v1",
    "source_sha": source_sha,
    "image": image,
    "image_digest": digest,
    "migration": "PASS",
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
for key, expected in required.items():
    if data.get(key) != expected:
        raise SystemExit(f"staging evidence mismatch: {key}")
PY

work_dir="$(mktemp -d)"
chmod 0700 "$work_dir"
before="$work_dir/before.json"
receipt="$work_dir/apply-receipt.json"
during="$work_dir/during.json"
rollback_receipt="$work_dir/rollback-receipt.json"
after="$work_dir/after.json"
applied=false
rolled_back=false

validate_status() {
  local path="$1"
  python3 - "$path" "$source_sha" "$image" "$image_digest" <<'PY'
import json, sys
path, source_sha, image, digest = sys.argv[1:]
data = json.load(open(path, encoding="utf-8"))
if data.get("schema") != "codestra.superset-readonly-canary-status.v1":
    raise SystemExit("invalid status schema")
if data.get("source_sha") != source_sha:
    raise SystemExit("status source mismatch")
if data.get("image") != image or data.get("image_digest") != digest:
    raise SystemExit("status image mismatch")
if data.get("write_requests") != 0:
    raise SystemExit("write request counter moved")
if data.get("external_deliveries") != 0:
    raise SystemExit("external delivery counter moved")
if data.get("live_effects_enabled") is not False:
    raise SystemExit("live effects are enabled")
value = data.get("runtime_state_hash")
if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
    raise SystemExit("invalid runtime state hash")
PY
}

rollback() {
  if [[ "$applied" != true || "$rolled_back" == true ]]; then
    return 0
  fi
  if "$controller" rollback \
      --source-sha "$source_sha" \
      --image "$image" \
      --receipt "$receipt" >"$rollback_receipt"; then
    python3 - "$rollback_receipt" "$source_sha" "$image" "$image_digest" <<'PY'
import json, sys
path, source_sha, image, digest = sys.argv[1:]
data = json.load(open(path, encoding="utf-8"))
if data.get("schema") != "codestra.superset-readonly-canary-rollback.v1":
    raise SystemExit("invalid rollback receipt schema")
if data.get("source_sha") != source_sha or data.get("image") != image or data.get("image_digest") != digest:
    raise SystemExit("rollback receipt identity mismatch")
if data.get("rolled_back") is not True:
    raise SystemExit("rollback was not confirmed")
PY
    rolled_back=true
  else
    return 1
  fi
}

cleanup() {
  local status=$?
  trap - EXIT INT TERM
  if [[ "$applied" == true && "$rolled_back" != true ]]; then
    rollback || status=1
  fi
  rm -rf -- "$work_dir"
  exit "$status"
}
trap cleanup EXIT INT TERM

"$controller" status \
  --source-sha "$source_sha" \
  --image "$image" \
  --json >"$before"
validate_status "$before"

"$controller" apply \
  --source-sha "$source_sha" \
  --image "$image" \
  --percent "$percent" \
  --methods GET,HEAD \
  --read-only \
  --staging-evidence-sha256 "$staging_sha256" >"$receipt"
applied=true

python3 - "$receipt" "$source_sha" "$image" "$image_digest" "$percent" "$staging_sha256" <<'PY' || exit 1
from decimal import Decimal
import json, sys
path, source_sha, image, digest, percent, staging_hash = sys.argv[1:]
data = json.load(open(path, encoding="utf-8"))
if data.get("schema") != "codestra.superset-readonly-canary-receipt.v1":
    raise SystemExit("invalid canary receipt schema")
expected = {
    "source_sha": source_sha,
    "image": image,
    "image_digest": digest,
    "methods": ["GET", "HEAD"],
    "read_only": True,
    "candidate_active": True,
    "writes_enabled": False,
    "staging_evidence_sha256": staging_hash,
}
for key, value in expected.items():
    if data.get(key) != value:
        raise SystemExit(f"canary receipt mismatch: {key}")
if Decimal(str(data.get("applied_percent"))) != Decimal(percent):
    raise SystemExit("canary percentage mismatch")
PY

headers=()
if [[ -n "$readonly_token" ]]; then
  headers=(-H "Authorization: Bearer ${readonly_token}")
fi
curl --fail --silent --show-error --connect-timeout 10 --max-time 30 \
  "${headers[@]}" "$base_url/health" >/dev/null
head_code="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
  --head --connect-timeout 10 --max-time 30 "${headers[@]}" "$base_url/health")"
[[ "$head_code" =~ ^(200|204|301|302|303|307|308)$ ]] || fail "unexpected_health_head_${head_code}"
login_code="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
  --connect-timeout 10 --max-time 30 "${headers[@]}" "$base_url/login/")"
[[ "$login_code" =~ ^(200|301|302|303|307|308)$ ]] || fail "unexpected_login_${login_code}"
csrf_code="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
  --connect-timeout 10 --max-time 30 "${headers[@]}" "$base_url/api/v1/security/csrf_token/")"
[[ "$csrf_code" =~ ^(200|401|403)$ ]] || fail "unexpected_csrf_${csrf_code}"
swagger_code="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
  --connect-timeout 10 --max-time 30 "${headers[@]}" "$base_url/swagger/v1")"
[[ "$swagger_code" = 404 ]] || fail "swagger_expected_disabled_${swagger_code}"

"$controller" status \
  --source-sha "$source_sha" \
  --image "$image" \
  --json >"$during"
validate_status "$during"

rollback || fail rollback_failed
"$controller" status \
  --source-sha "$source_sha" \
  --image "$image" \
  --json >"$after"
validate_status "$after"

python3 - "$before" "$after" <<'PY' || exit 1
import json, sys
before = json.load(open(sys.argv[1], encoding="utf-8"))
after = json.load(open(sys.argv[2], encoding="utf-8"))
if before["runtime_state_hash"] != after["runtime_state_hash"]:
    raise SystemExit("runtime state was not restored exactly")
PY

OUTPUT_PATH="$output_path" SOURCE_SHA="$source_sha" IMAGE="$image" \
IMAGE_DIGEST="$image_digest" STAGING_SHA256="$staging_sha256" \
PERCENT="$percent" HEAD_CODE="$head_code" LOGIN_CODE="$login_code" \
CSRF_CODE="$csrf_code" SWAGGER_CODE="$swagger_code" \
BEFORE="$before" DURING="$during" AFTER="$after" RECEIPT="$receipt" \
ROLLBACK_RECEIPT="$rollback_receipt" python3 - <<'PY'
import json, os
from pathlib import Path

def load(name):
    return json.load(open(os.environ[name], encoding="utf-8"))

payload = {
    "schema": "codestra.superset-production-readonly-canary-evidence.v1",
    "source_sha": os.environ["SOURCE_SHA"],
    "image": os.environ["IMAGE"],
    "image_digest": os.environ["IMAGE_DIGEST"],
    "staging_evidence_sha256": os.environ["STAGING_SHA256"],
    "applied_percent": os.environ["PERCENT"],
    "methods": ["GET", "HEAD"],
    "read_only": True,
    "write_requests_sent": False,
    "public_health_get": "PASS",
    "public_health_head_status": int(os.environ["HEAD_CODE"]),
    "oidc_login_status": int(os.environ["LOGIN_CODE"]),
    "csrf_read_status": int(os.environ["CSRF_CODE"]),
    "swagger_disabled_status": int(os.environ["SWAGGER_CODE"]),
    "before": load("BEFORE"),
    "during": load("DURING"),
    "after": load("AFTER"),
    "apply_receipt": load("RECEIPT"),
    "rollback_receipt": load("ROLLBACK_RECEIPT"),
    "runtime_restored_exactly": True,
    "live_effect_counter_movement": False,
    "production_readonly_canary": "PASS",
}
Path(os.environ["OUTPUT_PATH"]).write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY

echo SUPERSET_PRODUCTION_READONLY_CANARY=PASS
