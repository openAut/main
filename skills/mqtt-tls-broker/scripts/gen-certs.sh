#!/usr/bin/env bash
# Minimal PKI for openAut MQTT mutual TLS.
#   gen-certs.sh ca                      -> internal CA under $PKI_DIR/ca
#   gen-certs.sh broker <hostname-or-ip> -> server cert under $PKI_DIR/broker
#   gen-certs.sh client <node-id>        -> client cert (CN=node-id) under $PKI_DIR/clients
# Sources ../../../config.env for PKI_DIR. Uses openssl. Keys are chmod 600.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
# shellcheck disable=SC1091
set -a; . "$ROOT/config.env"; set +a

PKI="${PKI_DIR:-$ROOT/pki}"
DAYS=825

ca() {
  mkdir -p "$PKI/ca"; chmod 700 "$PKI/ca"
  [ -f "$PKI/ca/ca.crt" ] && { echo "CA already exists at $PKI/ca"; return; }
  openssl genrsa -out "$PKI/ca/ca.key" 4096
  openssl req -x509 -new -nodes -key "$PKI/ca/ca.key" -sha256 -days 3650 \
    -subj "/O=openAut/CN=openAut Internal CA" -out "$PKI/ca/ca.crt"
  chmod 600 "$PKI/ca/ca.key"
  echo "CA -> $PKI/ca/ca.crt"
}

leaf() {  # role dir, name, CN, extfile-SAN
  local dir="$1" name="$2" cn="$3" san="$4"
  mkdir -p "$PKI/$dir"
  openssl genrsa -out "$PKI/$dir/$name.key" 2048
  openssl req -new -key "$PKI/$dir/$name.key" -subj "/O=openAut/CN=$cn" -out "$PKI/$dir/$name.csr"
  printf 'subjectAltName=%s\n' "$san" > "$PKI/$dir/$name.ext"
  openssl x509 -req -in "$PKI/$dir/$name.csr" -CA "$PKI/ca/ca.crt" -CAkey "$PKI/ca/ca.key" \
    -CAcreateserial -days "$DAYS" -sha256 -extfile "$PKI/$dir/$name.ext" -out "$PKI/$dir/$name.crt"
  chmod 600 "$PKI/$dir/$name.key"
  rm -f "$PKI/$dir/$name.csr" "$PKI/$dir/$name.ext"
  echo "$dir cert -> $PKI/$dir/$name.crt (CN=$cn)"
}

case "${1:-}" in
  ca) ca ;;
  broker)
    [ -n "${2:-}" ] || { echo "usage: gen-certs.sh broker <hostname-or-ip>" >&2; exit 1; }
    ca
    if [[ "$2" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then san="IP:$2"; else san="DNS:$2"; fi
    leaf broker "$2" "$2" "$san" ;;
  client)
    [ -n "${2:-}" ] || { echo "usage: gen-certs.sh client <node-id>" >&2; exit 1; }
    ca
    leaf clients "$2" "$2" "DNS:$2" ;;  # CN = node id; EMQX ACL keys on this
  *)
    echo "usage: gen-certs.sh {ca | broker <host> | client <node-id>}" >&2; exit 1 ;;
esac
