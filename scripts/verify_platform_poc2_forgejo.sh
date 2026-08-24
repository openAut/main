#!/usr/bin/env bash
set -euo pipefail

poc2="$HOME/openaut/deploy/platform-poc2"
base_url="http://127.0.0.1:3000/api/v1"
engineer_token="$(cat "$poc2/secrets/engineer_token")"

engineer_api() {
  curl --fail --silent --show-error -H "Authorization: token $engineer_token" "$@"
}

repo_count="$(engineer_api "$base_url/orgs/openaut/repos?limit=20" | jq 'length')"
private_count="$(engineer_api "$base_url/orgs/openaut/repos?limit=20" | jq '[.[] | select(.private == true)] | length')"
engineer_user="$(curl --fail --silent --show-error -H "Authorization: token $engineer_token" "$base_url/user")"
engineer_identity="$(echo "$engineer_user" | jq -r '.login')"
echo "$engineer_user" | jq -e '.active == true and .restricted == true and .is_admin == false' >/dev/null

for repo in system-db manuals generated-docs runbooks control-poc-lab; do
  engineer_api "$base_url/repos/openaut/$repo" >/dev/null
done

[ "$repo_count" = "5" ]
[ "$private_count" = "5" ]
[ "$engineer_identity" = "openaut-engineer" ]

unset engineer_token
echo "POC2_FORGE_ENGINEER_OK identity=$engineer_identity restricted=true admin=false private_repos=$private_count repo_access=$repo_count"
