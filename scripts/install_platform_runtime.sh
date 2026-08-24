#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this script with sudo." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl docker.io docker-compose-v2 iproute2 jq mosquitto-clients openssl postgresql-client
systemctl enable --now docker

# Lab-only convenience: membership in the Docker group is effectively host-root access.
# This is not the production Engineer containment model from ADR 0001/0003.
if ! id -nG openaut | tr ' ' '\n' | grep -qx docker; then
  usermod -aG docker openaut
fi

docker --version
docker compose version
mosquitto_pub --help 2>&1 | head -n 1
psql --version

echo "WARNING: the openaut user has lab-only Docker access, which is host-root equivalent."
echo "Platform runtime installation complete. Reconnect SSH before using Docker as openaut."
