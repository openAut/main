---
name: edge-iot2050
description: Provision the openAut telemetry runtime on a Siemens SIMATIC IOT2050 — install the reference field-reader scaffold, publish readings to EMQX over mutual TLS, and buffer with PUBACK-aware store-and-forward. Use when preparing an approved IOT2050 deployment, integrating a read-only BACnet/Modbus/M-Bus reader, or testing resilient edge publishing.
permissions:
  knowledge_only: false
  exec: "owner-approved install.sh + node-provisioned edge agent (edge_agent.py) + systemd unit"
  network: "case-scoped SSH for deployment; outbound MQTT over mutual TLS to EMQX"
  files: "approved deployment writes /opt/openaut-edge and /etc/openaut; runtime writes /var/lib/openaut and reads certs"
  credentials: "TLS client cert/key + EnvironmentFile (node-provisioned, not in repo)"
  control_writes: "none"
---

# edge-iot2050 — Siemens IOT2050 edge node

openAut Layer 2 keeps existing field equipment unchanged and puts a small Linux **edge node** next to
it. The node polls field protocols (BACnet/Modbus/M-Bus/…), normalises readings to the openAut topic
schema, and publishes them to the central **EMQX** broker over **mutual TLS**, buffering locally when
the network is down within a configured, explicitly bounded local queue.

Use [`iot2050-device`](../iot2050-device/SKILL.md) first to identify the hardware variant, inspect the
installed image, and apply Siemens' model-specific operating constraints. This skill covers only the
openAut edge application.

Depends on [`mqtt-tls-broker`](../mqtt-tls-broker/SKILL.md) (issues the node's client cert and defines
the topic schema). The reference `read_point()` remains a stub: this is a tested MQTT/TLS and durable
spool scaffold, not a functioning field poller until one selected read-only protocol is implemented
and its point map is reviewed.

## Approval gate

Certificate issuance, file copying, package installation, service changes, and deployment are writes.
Before any of them, require all of the following:

1. An approved Systemdatabas case for the exact node, site, protocol, points, artifact revision, and
   maintenance window.
2. Explicit human confirmation for the deployment being performed now.
3. Engineer trust-domain execution through its case-scoped SSH and policy-owned deploy-wrapper path.
   Advisor never runs this flow.
4. A reviewed rollback plan and physical recovery access. Never deploy to a live building, occupied
   space, or safety-critical equipment from this POC.

`install.sh` verifies bundle integrity and requires matching case/confirmation strings, but it does
**not** query Systemdatabasen and cannot prove approval by itself. The policy-owned wrapper must verify
the active case and approved Forge revision before invoking it. Do not expose direct root execution as
an alternative approval path. Inventory remains read-only and follows `iot2050-device`. Do not treat
an empty or placeholder `config.env` as provisioned infrastructure.

## Step 1 — Model and runtime preflight

Confirm the device-tree model, OS image, free storage, clock synchronization, failed units, and
listeners using `iot2050-device`. For Basic, do not use the Advanced-only eMMC installation flow.
The deploy wrapper supplies the already-verified case identifier:

```bash
export OPENAUT_APPROVED_CASE='<approved-case-id>'
```

## Step 2 — Prepare reviewed artifacts

The broker skill generates a per-node cert whose **CN = the combined `$EDGE_SITE/$EDGE_NODE_ID`**
(the broker ACL keys on this whole CN via `${cert_common_name}`, not on MQTT ClientID):

```bash
bash skills/mqtt-tls-broker/scripts/gen-certs.sh client "$EDGE_SITE" "$EDGE_NODE_ID"
```

The PKI keeps **one directory per site, one file per node** at
`clients/<site>/<node>.{crt,key}`. Do not concatenate site and node with `-`: both segments may contain
hyphens, making that representation collision-prone.

Build an approved deployment directory outside the repository containing exactly these five files,
plus their canonical SHA-256 manifest:

```text
points.json
edge.env
ca.crt
node.crt
node.key
manifest.sha256
```

Create `manifest.sha256` only after the five files have been reviewed, then attach the manifest and
approved Forge revision to the case:

```bash
(cd "$APPROVED_EDGE_CONFIG" && sha256sum points.json edge.env ca.crt node.crt node.key > manifest.sha256)
```

Use `assets/points.example.json` and `assets/edge.env.example` only as templates. Replace every
placeholder, review every point as read-only, and never install the examples directly. Put the
approved `paho_mqtt-2.1.0-py3-none-any.whl` in a separate wheelhouse. Its SHA-256 must match
`assets/requirements.lock`; obtain the wheel through the approved Forge/CI artifact path, not by
giving the IOT2050 general internet egress. The release's committed `assets/release.sha256` detects
transfer corruption; the deploy wrapper remains responsible for binding the release to the approved
Forge revision.

The installer validates the manifest, fixed runtime paths, canonical identifiers, CA chain,
certificate validity, exact `CN=<site>/<node>`, and private-key match before changing the node.

## Step 3 — Stage and install

Stage the reviewed release, deployment directory, and wheelhouse. Do not place private keys in the
repository. The installer accepts only a root-owned tree with no symlinks or group/other-writable
content. In the current root-only lab alias the commands below create that snapshot directly; a
future non-root forced-command path must copy into an equivalent root-owned snapshot before invoking
the installer. First reject a stale case-specific staging directory:

```bash
printf '%s\n' "$OPENAUT_APPROVED_CASE" | LC_ALL=C grep -Eq \
  '^[A-Za-z0-9]+([._:-][A-Za-z0-9]+)*$' || exit 1
EDGE_STAGE="/tmp/openaut-edge-$OPENAUT_APPROVED_CASE"
ssh "$EDGE_SSH_USER@$EDGE_HOST" \
  "test ! -e '$EDGE_STAGE' && install -d -m 0700 \
   '$EDGE_STAGE/release' '$EDGE_STAGE/config' '$EDGE_STAGE/wheels'"
scp -r skills/edge-iot2050/scripts skills/edge-iot2050/assets \
  "$EDGE_SSH_USER@$EDGE_HOST:$EDGE_STAGE/release/"
scp -r "$APPROVED_EDGE_CONFIG/." "$EDGE_SSH_USER@$EDGE_HOST:$EDGE_STAGE/config/"
scp -r "$APPROVED_WHEELHOUSE/." "$EDGE_SSH_USER@$EDGE_HOST:$EDGE_STAGE/wheels/"
```

After the policy-owned wrapper has rechecked the active case, approved revision, manifest, target,
and human confirmation, it may invoke:

```bash
ssh "$EDGE_SSH_USER@$EDGE_HOST" \
  "OPENAUT_APPROVED_CASE='$OPENAUT_APPROVED_CASE' \
   OPENAUT_CONFIRM_CASE='$OPENAUT_APPROVED_CASE' \
   /bin/sh '$EDGE_STAGE/release/scripts/install.sh' \
   '$EDGE_STAGE/config' '$EDGE_STAGE/wheels'"
```

`install.sh` creates the non-login `openaut` service account, installs hash-verified offline
dependencies, and builds case-specific release/configuration directories. It switches `current`
symlinks only after all local validation succeeds, then requires the service to connect to EMQX and
write a fresh readiness marker within 60 seconds. A failed activation restores the previous symlinks
and systemd unit. Previous case directories remain for reviewed rollback and must be removed only by
the policy-owned deploy wrapper after case closure.

If the selected protocol needs a serial device, grant only its stable `/dev/serial/by-id/...` path
through the systemd device policy and add the narrow device group in the reviewed artifact. Do not
grant broad device access pre-emptively.

## Step 4 — Configure the point map

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

Field reads are delegated to the protocol skills (`modbus`, `bacnet`, `mbus`); this map is the glue
between a point and its MQTT topic `openaut/<site>/<node>/<system>/<metric>`.

This publisher accepts read-only telemetry points only. Both bundle validation and runtime reject
writable points. The future mediated setpoint channel proposed in
[ADR 0004](../../docs/adr/0004-edge-control-writes-and-continuity.md) is a separate capability and
must never be activated by extending this point map.

## Step 5 — Store-and-forward buffering

`edge_agent.py` assigns a stable `event_id` and persists each reading to SQLite **before** publishing
with QoS 1. It removes a row only
after Paho receives the broker's PUBACK. `connect_async()` and bounded reconnect delays retry the
initial connection and later outages. Paho retains each in-flight QoS 1 message across an automatic
reconnect while SQLite retains it across process restarts. Delivery is therefore at-least-once:
ingest deduplicates the same event after reconnect or restart using `(ts, node, event_id)`.
Apply `bash scripts/apply_platform_edge_event_id.sh` to an existing Platform data volume before
restarting ingest with this contract; fresh databases receive the same schema from
`timeseries-stack/assets/schema.sql`.

The node sets an MQTT Last-Will on `openaut/<site>/<node>/$status`. A will cannot contain the future
disconnect time, so the offline payload omits `ts`; ingest records when it observes the retained
offline state. This is an observation timestamp, not proof of the exact disconnect time. Online
status continues to carry the node timestamp.

Set `OPENAUT_SPOOL_MAX_ROWS` to bound disk use during long outages. The reference default is 100,000
queued readings. Once full, the oldest non-inflight row is dropped and an error is logged; this is an
explicit bounded-storage loss policy, not a claim of unlimited no-loss buffering. Size the cap from
poll rate, expected outage, available media, and write endurance.

## Step 6 — Verify and close the case

```bash
ssh "$EDGE_SSH_USER@$EDGE_HOST" "systemctl status openaut-edge.service --no-pager"
bash skills/mqtt-tls-broker/scripts/verify-tls.sh
bash skills/timeseries-stack/scripts/verify-db.sh
```

End-to-end success = a field value appears as a row in `telemetry.readings` within `interval_s`.
Also verify an approved broker-outage test: queue depth increases while disconnected, the client
reconnects without restart, rows remain until PUBACK, and the queue drains after recovery. Reboot the
node only if the approved test plan explicitly includes it. Attach results and artifact hashes to the
case before closure.

## Security review (openAut frameworks)

| Control | Check | Framework |
|---|---|---|
| Strong device identity | per-node client cert, CN-bound ACL | IEC 62443 SR 1.x |
| Encryption in transit | publishes only over `:8883` mutual TLS | IEC 62443 SR 4.1, CRA |
| Bounded outage tolerance | PUBACK-aware store-and-forward spool + LWT status | NIS2 (availability), openAut edge buffering |
| Key custody | private key 0640, root-owned and service-group-readable, on-device only | ISO 27001 A.8 |
| Field isolation | node reads field bus, publishes one prefix; no inbound control path | IEC 62443 zones/conduits |

> Read-only inventory has been exercised on IOT2050 hardware, but the reference field reader and a
> physical end-to-end publish remain unverified. This skill has no inbound MQTT subscription and no
> field-write path. Any future setpoint path must follow ADR 0004 and remain separate from this
> telemetry publisher.
