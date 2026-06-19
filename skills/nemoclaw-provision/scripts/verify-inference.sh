#!/usr/bin/env bash
# Verify the sandbox host can reach the remote Nemotron 3 Super endpoint over TLS,
# with certificate verification against the configured CA, and that the model is served.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
# shellcheck disable=SC1091
set -a; . "$ROOT/config.env"; set +a

SSH="ssh ${SANDBOX_SSH_USER}@${SANDBOX_HOST}"

auth=()
[ -n "${NEMOTRON_API_KEY:-}" ] && auth=(-H "Authorization: Bearer ${NEMOTRON_API_KEY}")

echo "== Verify inference: ${NEMOTRON_BASE_URL}/models (TLS, CA=${NEMOTRON_CA_CERT}) =="

# Run curl ON the sandbox host so we test the path the sandbox will actually use.
# --cacert forces real verification; we deliberately do NOT pass -k / --insecure.
resp="$($SSH "curl -fsS --cacert '${NEMOTRON_CA_CERT}' ${auth[*]+${auth[*]}} '${NEMOTRON_BASE_URL}/models'")"

echo "$resp"

if echo "$resp" | grep -q "${NEMOTRON_MODEL}"; then
  echo "OK — '${NEMOTRON_MODEL}' is served and reachable over verified TLS."
else
  echo "FAIL — endpoint reachable but '${NEMOTRON_MODEL}' not listed. Check served-model-name." >&2
  exit 1
fi
