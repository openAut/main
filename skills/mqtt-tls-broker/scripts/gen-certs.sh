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
# Reads only PKI_DIR from ../../../config.env. Uses openssl. Keys are chmod 600.
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

load_pki_dir() {
  local config="$ROOT/config.env"
  [ -f "$config" ] || return 0

  # Do not source config.env: it may contain unrelated secrets. Accept the
  # simple assignment forms used by config.env.example and intentionally avoid
  # shell expansion while extracting only PKI_DIR.
  PKI_DIR="$(
    awk '
      /^[[:space:]]*(export[[:space:]]+)?PKI_DIR[[:space:]]*=/ {
        sub(/^[[:space:]]*(export[[:space:]]+)?PKI_DIR[[:space:]]*=[[:space:]]*/, "")
        if ($0 ~ /^"/) {
          sub(/^"/, "")
          sub(/".*$/, "")
          print
          exit
        }
        if ($0 ~ /^'\''/) {
          sub(/^'\''/, "")
          sub(/'\''.*/, "")
          print
          exit
        }
        sub(/[[:space:]]+#.*$/, "")
        sub(/[[:space:]]*$/, "")
        print
        exit
      }
    ' "$config"
  )"
}

load_pki_dir

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
  # CSR subject is built via a config file, not `-subj "/O=.../CN=$cn"`. -subj parses '/' as the
  # RDN delimiter, so a CN containing a literal '/' (the <site>/<node> format ADR 0004 requires)
  # breaks CSR generation outright -- verified empirically (openssl 3.5.5: "Missing '=' after RDN
  # type string"), not a theoretical concern. A config file sets CN as one literal value with no
  # delimiter parsing, so it works the same whether or not the CN contains '/'.
  local cnf="$PKI/$dir/$name.csr.cnf"
  {
    printf '[req]\ndistinguished_name = dn\nprompt = no\nutf8 = yes\n\n[dn]\n'
    printf 'O = openAut\nCN = %s\n' "$cn"
  } > "$cnf"
  openssl req -new -key "$PKI/$dir/$name.key" -config "$cnf" -out "$PKI/$dir/$name.csr"
  printf 'subjectAltName=%s\n' "$san" > "$PKI/$dir/$name.ext"
  openssl x509 -req -in "$PKI/$dir/$name.csr" -CA "$PKI/ca/ca.crt" -CAkey "$PKI/ca/ca.key" \
    -CAcreateserial -days "$DAYS" -sha256 -extfile "$PKI/$dir/$name.ext" -out "$PKI/$dir/$name.crt"
  chmod 600 "$PKI/$dir/$name.key"
  rm -f "$PKI/$dir/$name.csr" "$PKI/$dir/$name.ext" "$cnf"
  echo "$dir cert -> $PKI/$dir/$name.crt (CN=$cn)"
}

case "${1:-}" in
  ca) ca ;;
  broker)
    [ -n "${2:-}" ] || { echo "usage: gen-certs.sh broker <hostname-or-ip>" >&2; exit 1; }
    # leaf() now writes $2 into an openssl config file, not just -subj -- reject anything that
    # could break out of the config file's CN line (newline, brackets, '=') or the filename it's
    # also used as, rather than assume this argument is trusted just because it's operator-supplied.
    if [ "${#2}" -lt 1 ] || [ "${#2}" -gt 253 ] || [[ ! "$2" =~ ^[A-Za-z0-9](-*[A-Za-z0-9.:])*$ ]]; then
      echo "invalid hostname-or-ip '$2': must be 1-253 chars, alnum/'.'/'-'/':' only, no leading '-' or control chars" >&2
      exit 1
    fi
    ca
    if [[ "$2" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then san="IP:$2"; else san="DNS:$2"; fi
    leaf broker "$2" "$2" "$san" ;;
  client)
    [ -n "${2:-}" ] && [ -n "${3:-}" ] || { echo "usage: gen-certs.sh client <site> <node-id>" >&2; exit 1; }
    ca
    validate_id "$2" site
    validate_id "$3" node
    cn="$2/$3"      # combined <site>/<node> -- what ${cert_common_name} substitutes in acl.conf
    # Per-segment validation allows up to 63+1+63=127 chars combined, but X.509 commonName is
    # capped at 64 chars (RFC 5280 ub-common-name) for interoperability -- some CAs/clients
    # enforce this strictly. Check the combined CN here rather than fail deep inside openssl.
    if [ "${#cn}" -gt 64 ]; then
      echo "invalid site/node combination '$cn': combined CN is ${#cn} chars, exceeds the 64-char X.509 commonName limit (RFC 5280)" >&2
      exit 1
    fi
    # One directory per site, one file per node -- not "$2-$3" concatenated into a single
    # filename. Both site and node may themselves contain '-' (validate_id allows it), so
    # concatenation is not injective: site=a-b/node=c and site=a/node=b-c both produce
    # "a-b-c", silently overwriting one node's cert/key with another's. A directory per site
    # is unambiguous because neither segment can contain '/' (validate_id rejects it).
    leaf "clients/$2" "$3" "$cn" "DNS:$2-$3" ;;
  *)
    echo "usage: gen-certs.sh {ca | broker <host> | client <site> <node-id>}" >&2; exit 1 ;;
esac
