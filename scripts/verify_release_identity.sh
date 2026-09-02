#!/usr/bin/env bash
set -Eeuo pipefail

image="${1:?immutable Superset image identity is required}"
source_sha="${2:?protected Superset source SHA is required}"

[[ "$image" =~ ^ghcr\.io/appolon1908-hue/superset-superset@sha256:([0-9a-f]{64})$ ]]
expected_digest="sha256:${BASH_REMATCH[1]}"
[[ "$source_sha" =~ ^[0-9a-f]{40}$ ]]

# Signature, provenance, and SBOM verification precede this readback. This gate
# binds deployment inputs to the exact locally pulled OCI object and protected
# source revision emitted by the signed release workflow.
test "$(docker image inspect "$image" --format '{{index .Config.Labels "org.opencontainers.image.source"}}')" = \
  "https://github.com/appolon1908-hue/Superset"
test "$(docker image inspect "$image" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}')" = \
  "$source_sha"
test "$(docker image inspect "$image" --format '{{.Config.User}}')" = "10001:10001"

docker image inspect "$image" --format '{{json .RepoDigests}}' |
  python3 -c '
import json
import sys
expected = sys.argv[1]
values = json.load(sys.stdin)
raise SystemExit(0 if isinstance(values, list) and expected in values else 1)
' "$image"

actual_digest="${image##*@}"
test "$actual_digest" = "$expected_digest"
printf '%s\n' \
  "SUPERSET_RELEASE_IDENTITY=PASS source_sha=$source_sha image_digest=$actual_digest"
