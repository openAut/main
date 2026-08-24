#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "usage: forgejo_api.sh <token-file> <curl-args...>" >&2
  exit 2
fi

token_file="$1"
shift
test -s "$token_file"

umask 077
config="$(mktemp)"
trap 'rm -f "$config"' EXIT
token="$(cat "$token_file")"
if [[ ! "$token" =~ ^[A-Za-z0-9_-]+$ ]]; then
  echo "Forgejo token contains unexpected characters." >&2
  exit 1
fi
printf 'header = "Authorization: token %s"\n' "$token" > "$config"
unset token

curl --config "$config" "$@"
