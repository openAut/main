#!/bin/sh
set -eu

usage() {
    echo "usage: install.sh CONFIG_DIR WHEELHOUSE" >&2
    exit 2
}

[ "$#" -eq 2 ] || usage
[ "$(id -u)" -eq 0 ] || { echo "install.sh must run as root" >&2; exit 1; }
[ -n "${OPENAUT_APPROVED_CASE:-}" ] || { echo "OPENAUT_APPROVED_CASE is required" >&2; exit 1; }
[ "${#OPENAUT_APPROVED_CASE}" -le 128 ] || { echo "OPENAUT_APPROVED_CASE is too long" >&2; exit 1; }
printf '%s\n' "$OPENAUT_APPROVED_CASE" | LC_ALL=C grep -Eq '^[A-Za-z0-9]+([._:-][A-Za-z0-9]+)*$' || {
    echo "OPENAUT_APPROVED_CASE is not a canonical case identifier" >&2
    exit 1
}
[ "${OPENAUT_CONFIRM_CASE:-}" = "$OPENAUT_APPROVED_CASE" ] || {
    echo "OPENAUT_CONFIRM_CASE must exactly match the approved case" >&2
    exit 1
}

CONFIG_DIR=$(CDPATH= cd -- "$1" && pwd)
WHEELHOUSE=$(CDPATH= cd -- "$2" && pwd)
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
RELEASE_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

for tree in "$RELEASE_DIR" "$CONFIG_DIR" "$WHEELHOUSE"; do
    unsafe=$(find "$tree" -xdev \( -type l -o ! -user root -o -perm /022 \) -print -quit)
    [ -z "$unsafe" ] || {
        echo "staged tree is not an immutable root-owned snapshot: $unsafe" >&2
        exit 1
    }
done

[ -f "$RELEASE_DIR/assets/release.sha256" ] || { echo "release is missing release.sha256" >&2; exit 1; }
(cd "$RELEASE_DIR" && sha256sum -c assets/release.sha256)
IDENTITY=$(python3 "$RELEASE_DIR/scripts/verify_bundle.py" "$CONFIG_DIR" "$RELEASE_DIR")
SITE=${IDENTITY%/*}
NODE_ID=${IDENTITY#*/}

openssl verify -purpose sslclient -CAfile "$CONFIG_DIR/ca.crt" "$CONFIG_DIR/node.crt" >/dev/null
openssl x509 -in "$CONFIG_DIR/node.crt" -checkend 0 -noout >/dev/null
SUBJECT=$(openssl x509 -in "$CONFIG_DIR/node.crt" -noout -subject -nameopt RFC2253)
[ "$SUBJECT" = "subject=CN=$SITE/$NODE_ID,O=openAut" ] || {
    echo "node.crt CN does not exactly match $SITE/$NODE_ID" >&2
    exit 1
}
CERT_PUBLIC=$(openssl x509 -in "$CONFIG_DIR/node.crt" -pubkey -noout | openssl pkey -pubin -outform DER | sha256sum)
KEY_PUBLIC=$(openssl pkey -in "$CONFIG_DIR/node.key" -pubout -outform DER | sha256sum)
[ "${CERT_PUBLIC%% *}" = "${KEY_PUBLIC%% *}" ] || { echo "node.key does not match node.crt" >&2; exit 1; }

if ! getent group openaut >/dev/null 2>&1; then
    groupadd --system openaut
fi
if ! id openaut >/dev/null 2>&1; then
    useradd --system --gid openaut --home-dir /var/lib/openaut --shell /usr/sbin/nologin openaut
fi

install -d -o root -g root -m 0755 /opt/openaut-edge /opt/openaut-edge/releases
install -d -o root -g openaut -m 0750 /etc/openaut /etc/openaut/releases
install -d -o openaut -g openaut -m 0750 /var/lib/openaut

NEW_RELEASE="/opt/openaut-edge/.new-$OPENAUT_APPROVED_CASE"
FINAL_RELEASE="/opt/openaut-edge/releases/$OPENAUT_APPROVED_CASE"
NEW_CONFIG="/etc/openaut/.new-$OPENAUT_APPROVED_CASE"
FINAL_CONFIG="/etc/openaut/releases/$OPENAUT_APPROVED_CASE"
NEW_RELEASE_LINK="/opt/openaut-edge/.current-$OPENAUT_APPROVED_CASE"
NEW_CONFIG_LINK="/etc/openaut/.current-$OPENAUT_APPROVED_CASE"
UNIT=/etc/systemd/system/openaut-edge.service
UNIT_BACKUP=$(mktemp /run/openaut-edge-unit.XXXXXX)

for path in "$NEW_RELEASE" "$FINAL_RELEASE" "$NEW_CONFIG" "$FINAL_CONFIG" \
    "$NEW_RELEASE_LINK" "$NEW_CONFIG_LINK"; do
    [ ! -e "$path" ] && [ ! -L "$path" ] || { echo "refusing existing deployment path: $path" >&2; exit 1; }
done
[ ! -e /opt/openaut-edge/current ] || [ -L /opt/openaut-edge/current ] || {
    echo "/opt/openaut-edge/current exists and is not a symlink" >&2
    exit 1
}
[ ! -e /etc/openaut/current ] || [ -L /etc/openaut/current ] || {
    echo "/etc/openaut/current exists and is not a symlink" >&2
    exit 1
}

PREVIOUS_RELEASE=$(readlink /opt/openaut-edge/current 2>/dev/null || true)
PREVIOUS_CONFIG=$(readlink /etc/openaut/current 2>/dev/null || true)
HAD_UNIT=0
WAS_ENABLED=0
WAS_ACTIVE=0
if [ -f "$UNIT" ]; then
    cp -p -- "$UNIT" "$UNIT_BACKUP"
    HAD_UNIT=1
fi
if systemctl is-enabled --quiet openaut-edge.service 2>/dev/null; then
    WAS_ENABLED=1
fi
if systemctl is-active --quiet openaut-edge.service 2>/dev/null; then
    WAS_ACTIVE=1
fi
COMMITTED=0
SUCCESS=0

cleanup() {
    rc=$?
    trap - EXIT HUP INT TERM
    set +e
    if [ "$COMMITTED" -eq 1 ] && [ "$SUCCESS" -ne 1 ]; then
        if [ -n "$PREVIOUS_RELEASE" ]; then
            rm -f -- "$NEW_RELEASE_LINK"
            ln -s "$PREVIOUS_RELEASE" "$NEW_RELEASE_LINK"
            mv -Tf "$NEW_RELEASE_LINK" /opt/openaut-edge/current
        else
            rm -f -- /opt/openaut-edge/current
        fi
        if [ -n "$PREVIOUS_CONFIG" ]; then
            rm -f -- "$NEW_CONFIG_LINK"
            ln -s "$PREVIOUS_CONFIG" "$NEW_CONFIG_LINK"
            mv -Tf "$NEW_CONFIG_LINK" /etc/openaut/current
        else
            rm -f -- /etc/openaut/current
        fi
        if [ "$HAD_UNIT" -eq 1 ]; then
            cp -p -- "$UNIT_BACKUP" "$UNIT"
        else
            rm -f -- "$UNIT"
        fi
        systemctl daemon-reload || true
        if [ -n "$PREVIOUS_RELEASE" ] && [ -n "$PREVIOUS_CONFIG" ] && \
            [ "$HAD_UNIT" -eq 1 ] && [ "$WAS_ACTIVE" -eq 1 ]; then
            systemctl restart openaut-edge.service || true
        else
            systemctl stop openaut-edge.service || true
        fi
        if [ "$WAS_ENABLED" -eq 0 ]; then
            systemctl disable openaut-edge.service || true
        fi
    fi
    if [ "$SUCCESS" -ne 1 ]; then
        rm -rf -- "$FINAL_RELEASE" "$FINAL_CONFIG"
    fi
    rm -rf -- "$NEW_RELEASE" "$NEW_CONFIG"
    rm -f -- "$NEW_RELEASE_LINK" "$NEW_CONFIG_LINK" "$UNIT_BACKUP"
    exit "$rc"
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

install -d -o root -g root -m 0755 "$NEW_RELEASE/scripts" "$NEW_RELEASE/assets"
python3 -m venv "$NEW_RELEASE/venv"
"$NEW_RELEASE/venv/bin/pip" install \
    --no-index \
    --find-links "$WHEELHOUSE" \
    --require-hashes \
    -r "$RELEASE_DIR/assets/requirements.lock"
install -o root -g root -m 0755 "$RELEASE_DIR/scripts/edge_agent.py" "$NEW_RELEASE/scripts/edge_agent.py"
install -o root -g root -m 0644 "$RELEASE_DIR/assets/requirements.lock" "$NEW_RELEASE/assets/requirements.lock"

install -d -o root -g openaut -m 0750 "$NEW_CONFIG" "$NEW_CONFIG/certs"
install -o root -g openaut -m 0640 "$CONFIG_DIR/points.json" "$NEW_CONFIG/points.json"
install -o root -g openaut -m 0640 "$CONFIG_DIR/edge.env" "$NEW_CONFIG/edge.env"
install -o root -g openaut -m 0644 "$CONFIG_DIR/ca.crt" "$NEW_CONFIG/certs/ca.crt"
install -o root -g openaut -m 0644 "$CONFIG_DIR/node.crt" "$NEW_CONFIG/certs/$NODE_ID.crt"
install -o root -g openaut -m 0640 "$CONFIG_DIR/node.key" "$NEW_CONFIG/certs/$NODE_ID.key"

mv "$NEW_RELEASE" "$FINAL_RELEASE"
mv "$NEW_CONFIG" "$FINAL_CONFIG"
ln -s "releases/$OPENAUT_APPROVED_CASE" "$NEW_RELEASE_LINK"
ln -s "releases/$OPENAUT_APPROVED_CASE" "$NEW_CONFIG_LINK"
COMMITTED=1
mv -Tf "$NEW_RELEASE_LINK" /opt/openaut-edge/current
mv -Tf "$NEW_CONFIG_LINK" /etc/openaut/current

install -o root -g root -m 0644 "$RELEASE_DIR/assets/openaut-edge.service" "$UNIT"
systemctl daemon-reload
systemd-analyze verify "$UNIT"
rm -f -- /var/lib/openaut/mqtt.ready
systemctl enable openaut-edge.service
systemctl restart openaut-edge.service

attempt=0
while [ "$attempt" -lt 60 ]; do
    if systemctl is-active --quiet openaut-edge.service && [ -s /var/lib/openaut/mqtt.ready ]; then
        SUCCESS=1
        break
    fi
    attempt=$((attempt + 1))
    sleep 1
done
[ "$SUCCESS" -eq 1 ] || { echo "service did not reach MQTT readiness; rolling back" >&2; exit 1; }

rm -f -- "$UNIT_BACKUP"
trap - EXIT HUP INT TERM
echo "installed case $OPENAUT_APPROVED_CASE for $IDENTITY; MQTT readiness confirmed"
