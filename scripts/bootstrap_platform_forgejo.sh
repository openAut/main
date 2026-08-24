#!/usr/bin/env bash
set -euo pipefail

poc2="$HOME/openaut/deploy/platform-poc2"
secrets="$poc2/secrets"
base_url="http://127.0.0.1:3000/api/v1"
mkdir -p "$secrets"
chmod 700 "$secrets"

cd "$poc2"
if [ ! -s "$secrets/admin_bootstrap_token" ]; then
  docker compose exec --no-TTY forgejo forgejo admin user generate-access-token \
    --username openaut-admin --token-name poc2-bootstrap --raw --scopes all \
    > "$secrets/admin_bootstrap_token"
  chmod 600 "$secrets/admin_bootstrap_token"
fi
admin_token="$(cat "$secrets/admin_bootstrap_token")"

cleanup_admin_token() {
  local code
  [ -n "${admin_token:-}" ] || return 0
  code="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
    --request DELETE --header "Authorization: token $admin_token" \
    "$base_url/admin/users/openaut-admin/tokens/poc2-bootstrap" || true)"
  if [ "$code" = "204" ] || [ "$code" = "404" ]; then
    rm -f "$secrets/admin_bootstrap_token"
    admin_token=""
    return 0
  fi
  echo "Failed to revoke Forgejo bootstrap token (HTTP $code); token file retained for cleanup." >&2
  return 1
}
trap 'cleanup_admin_token || true' EXIT

api() {
  curl --fail --silent --show-error \
    -H "Authorization: token $admin_token" \
    -H "Content-Type: application/json" "$@"
}

if ! api "$base_url/orgs/openaut" >/dev/null 2>&1; then
  api -X POST "$base_url/orgs" \
    -d '{"username":"openaut","full_name":"openAut POC","visibility":"private"}' >/dev/null
fi

repos=(system-db manuals generated-docs runbooks control-poc-lab)
for repo in "${repos[@]}"; do
  if ! api "$base_url/repos/openaut/$repo" >/dev/null 2>&1; then
    api -X POST "$base_url/orgs/openaut/repos" \
      -d "{\"name\":\"$repo\",\"private\":true,\"auto_init\":true,\"default_branch\":\"main\"}" >/dev/null
  fi
done

if ! docker compose exec --no-TTY forgejo forgejo admin user list | grep -q 'openaut-engineer'; then
  docker compose exec --no-TTY forgejo forgejo admin user create \
    --username openaut-engineer --email engineer@openaut.local --restricted \
    --random-password --random-password-length 32 --must-change-password=false >/dev/null
fi
engineer_user="$(api "$base_url/users/openaut-engineer")"
echo "$engineer_user" | jq -e '.active == true and .restricted == true and .is_admin == false' >/dev/null

if [ ! -s "$secrets/engineer_token" ]; then
  docker compose exec --no-TTY forgejo forgejo admin user generate-access-token \
    --username openaut-engineer --token-name engineer-poc2 --raw \
    --scopes write:repository,read:organization,read:user > "$secrets/engineer_token"
  chmod 600 "$secrets/engineer_token"
fi

team_id="$(api "$base_url/orgs/openaut/teams" | jq -r '.[] | select(.name == "engineers") | .id' | head -n 1)"
if [ -z "$team_id" ]; then
  team_id="$(api -X POST "$base_url/orgs/openaut/teams" \
    -d '{"name":"engineers","description":"Scoped Engineer POC access","permission":"write","can_create_org_repo":false,"includes_all_repositories":false,"units":["repo.code","repo.issues","repo.pulls"]}' | jq -r '.id')"
fi
api -X PATCH "$base_url/teams/$team_id" \
  -d '{"name":"engineers","description":"Scoped Engineer POC access","permission":"write","can_create_org_repo":false,"includes_all_repositories":false,"units":["repo.code","repo.issues","repo.pulls"]}' >/dev/null
api -X PUT "$base_url/teams/$team_id/members/openaut-engineer" >/dev/null

for repo in "${repos[@]}"; do
  api -X PUT "$base_url/teams/$team_id/repos/openaut/$repo" >/dev/null
  protection='{
    "branch_name":"main",
    "enable_push":true,
    "enable_push_whitelist":true,
    "push_whitelist_usernames":["openaut-admin"],
    "enable_merge_whitelist":true,
    "merge_whitelist_usernames":["openaut-admin"],
    "required_approvals":1,
    "block_on_rejected_reviews":true,
    "dismiss_stale_approvals":true,
    "enable_status_check":false
  }'
  if ! api "$base_url/repos/openaut/$repo/branch_protections" | jq -e '.[] | select(.branch_name == "main")' >/dev/null; then
    api -X POST "$base_url/repos/openaut/$repo/branch_protections" -d "$protection" >/dev/null
  else
    api -X PATCH "$base_url/repos/openaut/$repo/branch_protections/main" -d "$protection" >/dev/null
  fi
done

member_count="$(api "$base_url/teams/$team_id/members" | jq '[.[] | select(.login == "openaut-engineer")] | length')"
[ "$member_count" = "1" ]
team="$(api "$base_url/teams/$team_id")"
echo "$team" | jq -e '.permission == "write" and .can_create_org_repo == false and .includes_all_repositories == false' >/dev/null
for repo in "${repos[@]}"; do
  protection="$(api "$base_url/repos/openaut/$repo/branch_protections" | jq '.[] | select(.branch_name == "main")')"
  echo "$protection" | jq -e '
    .required_approvals == 1 and
    .enable_push_whitelist == true and
    .push_whitelist_usernames == ["openaut-admin"] and
    .enable_merge_whitelist == true and
    .merge_whitelist_usernames == ["openaut-admin"]' >/dev/null
done

cleanup_admin_token
trap - EXIT
echo "FORGEJO_BOOTSTRAP_OK org=openaut repos=${#repos[@]} engineer_team=$team_id protected_main=${#repos[@]}"
