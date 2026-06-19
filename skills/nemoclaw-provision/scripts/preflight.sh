#!/usr/bin/env bash
# Preflight checks for a NemoClaw sandbox host.
# Verifies Ubuntu 24.04, an NVIDIA GPU, and Docker 28+ over SSH before installing.
# Sources ../../../config.env (repo root) for SANDBOX_HOST / SANDBOX_SSH_USER.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
# shellcheck disable=SC1091
set -a; . "$ROOT/config.env"; set +a

SSH="ssh ${SANDBOX_SSH_USER}@${SANDBOX_HOST}"
fail=0

echo "== Preflight: ${SANDBOX_SSH_USER}@${SANDBOX_HOST} =="

echo "-- OS (expect Ubuntu 24.04) --"
if $SSH "head -n 2 /etc/os-release"; then :; else echo "  ! cannot read /etc/os-release"; fail=1; fi

echo "-- GPU (expect an NVIDIA device) --"
if $SSH "nvidia-smi --query-gpu=name,driver_version --format=csv,noheader"; then
  :
else
  echo "  ! nvidia-smi failed — no usable GPU"; fail=1
fi

echo "-- Docker (expect 28.x+) --"
if ver="$($SSH "docker info --format '{{.ServerVersion}}'" 2>/dev/null)"; then
  echo "  docker ${ver}"
  major="${ver%%.*}"
  if [ "${major:-0}" -lt 28 ]; then echo "  ! Docker < 28"; fail=1; fi
else
  echo "  ! docker not reachable (permissions? daemon down?)"; fail=1
fi

if [ "$fail" -ne 0 ]; then
  echo "PREFLIGHT FAILED — fix the items above before running the installer." >&2
  exit 1
fi
echo "PREFLIGHT OK — host is ready for the NemoClaw installer."
