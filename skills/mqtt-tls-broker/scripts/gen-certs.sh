#!/usr/bin/env bash
# Minimal PKI for openAut MQTT mutual TLS.
#   gen-certs.sh ca                        -> internal CA under $PKI_DIR/ca
#   gen-certs.sh broker <hostname-or-ip>   -> server cert under $PKI_DIR/broker
#   gen-certs.sh client <site> <node-id>   -> client cert (CN=<site>/<node-id>) under $PKI_DIR/clients
# CN is the combined site/node identifier EMQX's ${cert_common_name} ACL placeholder keys
# on (see skills/mqtt-tls-broker/assets/acl.conf, ADR 0004 decision 1, and
# docs/verification/emqx-mqtt5-cmd-verification.md) -- each segment is validated below
# before it is ever put in a certificate; an unvalidated segment is a proven
# wildcard-injection vector, not a theoretical one.
# Sources ../../../config.env for PKI_DIR. Uses openssl. Keys are chmod 600.
set -euo pipefail

# Canonical-id pattern (ADR 0004 decision 1, precondition 3): 1-63 lowercase ASCII
# alnum chars, with '.', '_', '-' allowed only singly between two alnums -- never
# leading, trailing, or consecutive. Rejects MQTT wildcards (+, #), '/', whitespace,
# control chars, and a leading '$' by construction.
validate_id() {  # validate_id <value> <label, e.g. "site" or "node">
  local val="$1" label="$2"
  if [ "${#val}" -lt 1 ] || [ "${#val}" -gt 63 ]; then
    echo "invalid $label '$val': must be 1-63 characters" >&2
    exit 1
  fi
  if [[ ! "$val" =~ ^[a-z0-9]+([._-][a-z0-9]+)*$ ]]; then
    echo "invalid $label '$val': must match ^[a-z0-9]+([._-][a-z0-9]+)*\$ (lowercase ascii letters/digits, '.', '_', '-' only, never leading/trailing/consecutive)" >&2
    exit 1
  fi
}

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
    [ -n "${2:-}" ] && [ -n "${3:-}" ] || { echo "usage: gen-certs.sh client <site> <node-id>" >&2; exit 1; }
    ca
    validate_id "$2" site
    validate_id "$3" node
    cn="$2/$3"      # combined <site>/<node> -- what ${cert_common_name} substitutes in acl.conf
    name="$2-$3"    # filename can't contain '/'
    leaf clients "$name" "$cn" "DNS:$name" ;;
  *)
    echo "usage: gen-certs.sh {ca | broker <host> | client <site> <node-id>}" >&2; exit 1 ;;
esac
