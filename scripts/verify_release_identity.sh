#!/usr/bin/env bash
set -Eeuo pipefail

image="${1:?immutable Superset image identity is required}"
source_sha="${2:?protected Superset source SHA is required}"

[[ "$image" =~ ^ghcr\.io/appolon1908-hue/superset-superset@sha256:([0-9a-f]{64})$ ]]
expected_digest="sha256:${BASH_REMATCH[1]}"
[[ "$source_sha" =~ ^[0-9a-f]{40}$ ]]

# The caller must pull the exact digest and verify its keyless signature and
# provenance before this readback. This gate then binds the deployment inputs
# to the signed OCI label and the locally present canonical digest.
test "$(docker image inspect "$image" --format '{{index .Config.Labels "org.opencontainers.image.source"}}')" = \
  "https://github.com/appolon1908-hue/Superset"
test "$(docker image inspect "$image" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}')" = \
  "$source_sha"
test "$(docker image inspect "$image" --format '{{.Config.User}}')" = "10001:10001"
docker image inspect "$image" --format '{{json .RepoDigests}}' |
  python3 -c 'import json,sys; image=sys.argv[1]; values=json.load(sys.stdin); raise SystemExit(0 if image in values else 1)' "$image"

actual_digest="${image##*@}"
test "$actual_digest" = "$expected_digest"
printf '%s\n' "SUPERSET_RELEASE_IDENTITY=PASS source_sha=$source_sha image_digest=$actual_digest"
