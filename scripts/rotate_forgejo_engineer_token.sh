#!/usr/bin/env bash
set -euo pipefail

mode="${1:-rotate}"
if [ "$mode" != "rotate" ] && [ "$mode" != "--revoke-only" ]; then
  echo "usage: rotate_forgejo_engineer_token.sh [--revoke-only]" >&2
  exit 2
fi

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
forgejo_api="$HERE/forgejo_api.sh"
deploy="$HOME/openaut/deploy/platform-poc2"
secrets="$deploy/secrets"
admin_file="$secrets/engineer_rotation_admin_token"
engineer_file="$secrets/engineer_token"
base_url="http://127.0.0.1:3000/api/v1"

cd "$deploy"
if [ ! -s "$admin_file" ]; then
  docker compose exec --no-TTY forgejo forgejo admin user generate-access-token \
    --username openaut-admin --token-name engineer-token-rotation --raw --scopes all > "$admin_file"
  chmod 600 "$admin_file"
fi

cleanup_admin_token() {
  local code
  [ -s "$admin_file" ] || return 0
  code="$(bash "$forgejo_api" "$admin_file" --silent --show-error --output /dev/null \
    --write-out '%{http_code}' --request DELETE \
    "$base_url/admin/users/openaut-admin/tokens/engineer-token-rotation" || true)"
  if [ "$code" = "204" ] || [ "$code" = "404" ]; then
    rm -f "$admin_file"
    return 0
  fi
  echo "Failed to revoke rotation admin token (HTTP $code); token file retained for cleanup." >&2
  return 1
}
trap 'cleanup_admin_token || true' EXIT

delete_code="$(bash "$forgejo_api" "$admin_file" --silent --show-error --output /dev/null \
  --write-out '%{http_code}' --request DELETE \
  "$base_url/admin/users/openaut-engineer/tokens/engineer-poc2")"
[ "$delete_code" = "204" ] || [ "$delete_code" = "404" ]
rm -f "$engineer_file"

if [ "$mode" = "--revoke-only" ]; then
  cleanup_admin_token
  trap - EXIT
  echo "Forgejo Engineer token revoked and local token file removed."
  exit 0
fi

docker compose exec --no-TTY forgejo forgejo admin user generate-access-token \
  --username openaut-engineer --token-name engineer-poc2 --raw \
  --scopes write:repository,read:organization,read:user > "$engineer_file"
chmod 600 "$engineer_file"

identity="$(bash "$forgejo_api" "$engineer_file" --fail --silent --show-error "$base_url/user" | jq -r '.login')"
[ "$identity" = "openaut-engineer" ]

cleanup_admin_token
trap - EXIT
echo "Forgejo Engineer token rotated; standing lab token remains on Platform only."
