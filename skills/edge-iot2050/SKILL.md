---
name: edge-iot2050
description: Provision a Siemens SIMATIC IOT2050 edge node for openAut — install a field-protocol poller, publish readings to the central EMQX broker over mutual TLS with the node's client certificate, buffer locally (store-and-forward) when the broker is unreachable, and run it as a resilient systemd service. Use when setting up IOT2050 or other Linux edge nodes, bridging BACnet/Modbus/M-Bus field data to MQTT, or adding store-and-forward edge buffering.
---

# edge-iot2050 — Siemens IOT2050 edge node

openAut Layer 2 keeps existing field equipment unchanged and puts a small Linux **edge node** next to
it. The node polls field protocols (BACnet/Modbus/M-Bus/…), normalises readings to the openAut topic
schema, and publishes them to the central **EMQX** broker over **mutual TLS**, buffering locally when
the network is down so no data is lost.

Depends on [`mqtt-tls-broker`](../mqtt-tls-broker/SKILL.md) (issues the node's client cert and defines
the topic schema). Assumes `config.env` is sourced.

## Step 1 — Issue and deploy the node's client certificate

The broker skill generates a per-node cert whose **CN = `$EDGE_NODE_ID`**:

```bash
bash skills/mqtt-tls-broker/scripts/gen-certs.sh client "$EDGE_NODE_ID"
```

Copy the CA + the node's cert/key to the IOT2050 (keys stay 600, owned by the service user):

```bash
ssh "$EDGE_SSH_USER@$EDGE_HOST" "mkdir -p /etc/openaut/certs && chmod 700 /etc/openaut/certs"
scp "$MQTT_CA_CERT" "$PKI_DIR/clients/$EDGE_NODE_ID.crt" "$PKI_DIR/clients/$EDGE_NODE_ID.key" \
    "$EDGE_SSH_USER@$EDGE_HOST:/etc/openaut/certs/"
```

The node authenticates to EMQX **with this cert** — the broker ACL then confines it to
`openaut/$EDGE_SITE/$EDGE_NODE_ID/#`. A stolen node can never publish as another node.

## Step 2 — Install the edge agent

Copy the poller/publisher and its point map, install Python deps in a venv:

```bash
scp -r skills/edge-iot2050/scripts skills/edge-iot2050/assets \
    "$EDGE_SSH_USER@$EDGE_HOST:/opt/openaut-edge/"
ssh "$EDGE_SSH_USER@$EDGE_HOST" \
  "cd /opt/openaut-edge && python3 -m venv venv && \
   ./venv/bin/pip install paho-mqtt && \
   echo 'add pymodbus / BAC0 / etc. for the protocols this node reads'"
```

## Step 3 — Configure the point map

`assets/points.example.json` defines what to read and how to map it to topics:

```json
{
  "site": "karsamala",
  "node": "iot2050-ahu-01",
  "interval_s": 15,
  "points": [
    {"system": "ahu", "metric": "supply_temp", "protocol": "modbus",
     "address": {"host": "192.168.1.60", "unit": 1, "register": 100, "type": "holding", "scale": 0.1},
     "unit": "degC"}
  ]
}
```

Field reads are delegated to the protocol skills (`modbus`, `bacnet`, `m-bus`); this map is the glue
between a point and its MQTT topic `openaut/<site>/<node>/<system>/<metric>`.

## Step 4 — Store-and-forward buffering

`edge_agent.py` publishes with QoS 1 and **persists unsent readings to a local SQLite spool** when the
broker is unreachable, draining the spool on reconnect. The node also sets an MQTT **Last-Will** on
`openaut/<site>/<node>/$status` so the AI tier sees it drop offline. This makes the edge resilient to
WAN/broker outages — a core openAut requirement (local buffering on the edge).

Set `OPENAUT_SPOOL_MAX_ROWS` to bound disk use during long outages. The reference default is 100,000
queued readings; older rows are dropped first if that cap is reached.

## Step 5 — Run as a systemd service

```bash
scp skills/edge-iot2050/assets/openaut-edge.service "$EDGE_SSH_USER@$EDGE_HOST:/tmp/"
ssh "$EDGE_SSH_USER@$EDGE_HOST" \
  "sudo mv /tmp/openaut-edge.service /etc/systemd/system/ && \
   sudo systemctl daemon-reload && sudo systemctl enable --now openaut-edge.service"
```

`Restart=always` + the spool means a reboot or transient network loss self-heals.

## Step 6 — Verify

```bash
ssh "$EDGE_SSH_USER@$EDGE_HOST" "systemctl status openaut-edge.service --no-pager"
# From the broker skill: confirm readings land over TLS
bash skills/mqtt-tls-broker/scripts/verify-tls.sh
# From the storage skill: confirm rows arrive
bash skills/timeseries-stack/scripts/verify-db.sh
```

End-to-end success = a field value appears as a row in `telemetry.readings` within `interval_s`.

## Security review (openAut frameworks)

| Control | Check | Framework |
|---|---|---|
| Strong device identity | per-node client cert, CN-bound ACL | IEC 62443 SR 1.x |
| Encryption in transit | publishes only over `:8883` mutual TLS | IEC 62443 SR 4.1, CRA |
| Availability / no data loss | store-and-forward spool + LWT status | NIS2 (availability), openAut edge buffering |
| Key custody | certs 600, owned by the service user, on-device only | ISO 27001 A.8 |
| Field isolation | node reads field bus, publishes one prefix; no inbound control path by default | IEC 62443 zones/conduits |

> **Live behaviour is unverified until IOT2050 hardware and field devices are connected.** Protocol
> client libraries and the IOT2050 base image differ per deployment — the cert identity, topic
> mapping, and store-and-forward contract are the durable part. Control writes back to field devices
> (setpoints) should remain a human-confirmed path via the Driftstekniker agent, not the edge poller.
