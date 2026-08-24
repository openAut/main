#!/usr/bin/env bash
set -euo pipefail

deploy="$HOME/openaut/deploy/platform-poc2"
secrets="$deploy/secrets"
token_file="$secrets/admin_bootstrap_token"
cleanup_file="$secrets/admin_cleanup_token"

cd "$deploy"
if [ ! -s "$cleanup_file" ]; then
  docker compose exec --no-TTY forgejo forgejo admin user generate-access-token \
    --username openaut-admin --token-name poc2-cleanup --raw --scopes all > "$cleanup_file"
  chmod 600 "$cleanup_file"
fi
cleanup_token="$(cat "$cleanup_file")"

delete_token() {
  local name="$1" code
  code="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
    --request DELETE --header "Authorization: token $cleanup_token" \
    "http://127.0.0.1:3000/api/v1/admin/users/openaut-admin/tokens/$name")"
  [ "$code" = "204" ] || [ "$code" = "404" ]
}

delete_token poc2-bootstrap
delete_token poc2-cleanup
unset cleanup_token
rm -f "$token_file" "$cleanup_file"
echo "Forgejo bootstrap and cleanup tokens revoked; local token files removed."
