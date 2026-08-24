#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this script with sudo." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y docker.io docker-compose-v2 mosquitto-clients postgresql-client
systemctl enable --now docker

if ! id -nG openaut | tr ' ' '\n' | grep -qx docker; then
  usermod -aG docker openaut
fi

docker --version
docker compose version
mosquitto_pub --help 2>&1 | head -n 1
psql --version

echo "Platform runtime installation complete. Reconnect SSH before using Docker as openaut."
