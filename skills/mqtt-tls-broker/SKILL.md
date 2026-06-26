---
name: mqtt-tls-broker
description: Stand up the openAut MQTT data backbone — an EMQX broker with a mutual-TLS listener, a per-edge-node client-certificate PKI, an ACL-enforced topic schema, and verification with mosquitto over TLS. Use when setting up EMQX, securing MQTT with TLS/client certs, defining the building telemetry topic schema, or connecting edge nodes to the central broker.
permissions:
  knowledge_only: false
  exec: "allowlisted scripts (gen-certs.sh, verify-tls.sh)"
  network: "MQTT/TLS broker (EMQX) on the node"
  files: "read-write (PKI dir; private keys chmod 600)"
  credentials: "generates/handles TLS CA + broker/client certs (node-local)"
---

# mqtt-tls-broker — EMQX with mutual TLS

The openAut AI tier ingests all field telemetry over **encrypted MQTT**. This skill provisions an
**EMQX** broker with a **mutual-TLS** listener (client certificates, not just username/password), a
small **PKI** that issues one cert per edge node, and an **ACL** that scopes each node to its own
topics. Plaintext `:1883` is never exposed.

NemoClaw does not provide this — it is openAut Layer 3 infrastructure that the agents and edge nodes
both depend on. Assumes `config.env` is sourced.

## Topic schema

One namespace per site and node, JSON payloads with a timestamp:

```
openaut/<site>/<node>/<system>/<metric>     e.g. openaut/karsamala/iot2050-ahu-01/ahu/supply_temp
openaut/<site>/<node>/$status               node online/offline (LWT)
```

- `<site>` = `$EDGE_SITE`, `<node>` = `$EDGE_NODE_ID`.
- Payload: `{"value": <number|bool>, "ts": <unix_epoch>, "unit": "<str>"}`.
- This maps cleanly onto the TimescaleDB hypertable in [`timeseries-stack`](../timeseries-stack/SKILL.md)
  and is published by [`edge-iot2050`](../edge-iot2050/SKILL.md).

## Step 1 — Generate the PKI

One internal CA, a broker server cert, and a client cert per edge node. The helper script creates
them under `$PKI_DIR` (keep that directory out of git — it is in `.gitignore`):

```bash
bash skills/mqtt-tls-broker/scripts/gen-certs.sh ca
bash skills/mqtt-tls-broker/scripts/gen-certs.sh broker "$EMQX_HOST"
bash skills/mqtt-tls-broker/scripts/gen-certs.sh client "$EDGE_NODE_ID"
```

The client cert's **Common Name = the edge node id** — EMQX uses that CN as the MQTT client identity
the ACL keys on. Distribute the client cert + key to the node via [`edge-iot2050`](../edge-iot2050/SKILL.md).

## Step 2 — Install EMQX

```bash
ssh "$EMQX_SSH_USER@$EMQX_HOST" \
  "curl -fsSL https://www.emqx.com/en/downloads | true; \
   sudo apt-get update && sudo apt-get install -y emqx && sudo systemctl enable --now emqx"
```

(Use EMQX's current documented install for your OS — package name and repo setup vary; the steps
below are version-stable.)

## Step 3 — Configure the mutual-TLS listener

Copy the CA + broker cert to the host and point an SSL listener at them with **`verify = verify_peer`**
and **`fail_if_no_peer_cert = true`** so only nodes with a valid client cert can connect:

```bash
ssh "$EMQX_SSH_USER@$EMQX_HOST" "sudo mkdir -p /etc/emqx/certs"
scp "$MQTT_CA_CERT" "$PKI_DIR/broker/$EMQX_HOST.crt" "$PKI_DIR/broker/$EMQX_HOST.key" \
    "$EMQX_SSH_USER@$EMQX_HOST:/tmp/"
ssh "$EMQX_SSH_USER@$EMQX_HOST" "sudo mv /tmp/ca.crt /tmp/$EMQX_HOST.crt /tmp/$EMQX_HOST.key /etc/emqx/certs/"
```

Listener config (see `assets/emqx-ssl-listener.hocon` for the full snippet to merge into
`/etc/emqx/emqx.conf`):

```hocon
listeners.ssl.openaut {
  bind = "0.0.0.0:8883"
  ssl_options {
    cacertfile = "/etc/emqx/certs/ca.crt"
    certfile   = "/etc/emqx/certs/<host>.crt"
    keyfile    = "/etc/emqx/certs/<host>.key"
    verify     = verify_peer
    fail_if_no_peer_cert = true
  }
}
```

Disable or firewall the default plaintext `:1883` listener. Reload: `ssh … "sudo emqx ctl listeners"`
to confirm `ssl:openaut` is running and `tcp:default` is stopped/blocked.

## Step 4 — ACL: scope each node to its own topics

Use cert-CN-based authorization so `iot2050-ahu-01` can only publish under
`openaut/<site>/iot2050-ahu-01/#`, and the AI-tier consumer can subscribe to `openaut/#` read-only.
See `assets/acl.conf`:

```
%% edge nodes: publish only under their own node prefix (CN = client id)
{allow, all, publish, ["openaut/${site}/${clientid}/#"]}.
%% telemetry consumer (TimescaleDB ingest) and agents: subscribe read-only
{allow, {user, "ingest"}, subscribe, ["openaut/#"]}.
{deny, all}.
```

## Step 5 — Verify over TLS

```bash
bash skills/mqtt-tls-broker/scripts/verify-tls.sh
```

It publishes a test message as the node's client cert and subscribes as the consumer — both over
`:8883` with `--cafile`. A plaintext connect to `:1883` must be refused.

## Security review (openAut frameworks)

| Control | Check | Framework |
|---|---|---|
| Encryption in transit | only `:8883` mutual-TLS reachable; `:1883` closed | IEC 62443 SR 4.1, CRA Annex I |
| Strong device identity | per-node client cert, CN-bound ACL | IEC 62443 SR 1.x, NIS2 Art. 21 |
| Least privilege | nodes publish own prefix only; consumer read-only | IEC 62443 SR 7.x |
| Key custody | CA/keys in `$PKI_DIR`, gitignored, 600 perms | ISO 27001 A.8 |

> **Live behaviour is unverified until an EMQX host is available.** EMQX install/listener syntax
> differs across 5.x releases — the invariants (mutual TLS, CN-bound ACL, no plaintext) are what to
> preserve.
