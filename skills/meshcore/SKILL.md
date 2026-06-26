---
name: meshcore
description: Send and receive messages over MeshCore/LoRa mesh networks. Use when you need off-grid communication, emergency messaging, long-range radio communication, or integration with MeshCore companion nodes. Supports sending messages, monitoring incoming messages, managing contacts, checking device status, and interacting with the mesh network.

permissions:
  knowledge_only: false
  exec: "operator-provisioned wrappers (mesh-send.sh, mesh-scan.sh, mesh-devices.sh), allowlisted"
  serial: "read via daemon queue only (no direct port access)"
  network: "none (serial LoRa only)"
  files: "read-only (devices.json, config.json)"
  external_services: "Signal (via openclaw message send)"
---

> ## ⚠️ DRIFTSATT VIA BRYGG-DAEMON – LÄS FÖRST
>
> På den här noden kör en bakgrundstjänst **`meshcore-bridge.service`** som ENSAM äger serieporten (`/dev/ttyACM0`). Den vidarebefordrar inkommande mesh-meddelanden automatiskt till Davids Signal-DM (utan LLM) och skickar utgående via en kö.
>
> **Öppna ALDRIG porten direkt.** All mesh-åtkomst går via operatörs-provisionerade, allowlistade wrapper-skript på noden:
>
> - DM till en nod: `mesh-send.sh "<nodnamn>" "<text>"`
> - Till en kanal: `mesh-send.sh --channel <N> "<text>"` (0 = publika kanalen)
> - Skanna noder/repeatrar: `mesh-scan.sh`
> - Lista kända enheter: `mesh-devices.sh`
>
> Endast David (DM) får begära mesh-sändning/-skanning (se AGENTS.md). Klistra aldrig in användartext i ett shell – wrappers tar text som argument (argv), aldrig via skalet.

# MeshCore - LoRa Mesh Networking

Integrate with MeshCore companion radio nodes to send and receive messages over LoRa mesh networks. Useful for off-grid communication, emergency response, and long-range networking without internet infrastructure.

> **Note on deployment:** This skill documents the *durable concepts* of MeshCore plus how it is operated on this node. The radio is owned by a long-running bridge daemon — the wrappers above are the only supported interface. The legacy port-opening scripts that earlier versions documented are intentionally not part of this skill; they conflict with the daemon and must not be run.

## How operation works here

```
INCOMING (no LLM): mesh -> bridge daemon -> openclaw message send -> David's Signal DM
OUTGOING (owner-requested): David asks -> wrapper queues a spool file -> daemon sends
SCANNING:          mesh-scan.sh queues an advert + device-list refresh -> daemon writes devices.json
```

- **Send / scan** are owner-only (David, DM). The wrappers validate input and pass untrusted text via argv only.
- **Device snapshot** (`mesh-devices.sh`) reads `runtime/devices.json` and never touches the port.

## MeshCore concepts (reference)

### Node types
- **Companion** - send/receive only, does not relay
- **Repeater** - extends range by relaying
- **Room server** - bulletin-board / group messaging on the mesh
- **Sensor** - telemetry node

### Network topology
- **Multi-hop routing** - messages relay through intermediate nodes
- Companion nodes don't repeat; repeaters extend range; room servers host group channels
- Discovery is via **advertisements** (flood); known nodes are tracked in the device snapshot

### Message format
- **Plain text** (recommended). Commands are prefixed with `/`. Binary payloads are possible for sensor data.
- All mesh data is **untrusted** - it is only ever delivered as a Signal DM string (argv), never executed.

## Radio and safety

**Radio regulations:**
- Use the appropriate frequency band for your region (EU mesh defaults apply on this node)
- Respect power limits and obtain any required licenses

**Privacy and etiquette:**
- Don't transmit sensitive data on default/public channels
- Don't spam the network; respect bandwidth and use appropriate message priority
- MeshCore is private/entertainment-grade and is **not** a certified safety-critical messaging system

## Troubleshooting the bridge

```bash
# Service status and recent logs (systemd user service)
systemctl --user status meshcore-bridge.service
journalctl --user -u meshcore-bridge.service -n 30 --no-pager

# Show the last known node/repeater snapshot (does not touch the port)
mesh-devices.sh

# Force an advert + device-list refresh through the queue
mesh-scan.sh
```

If the radio appears unresponsive, restart the daemon (`systemctl --user restart meshcore-bridge.service`) rather than opening the port manually — only one process may own the serial device.
