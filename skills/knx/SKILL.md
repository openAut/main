---
name: knx
description: Read and control KNX building-automation installations over KNXnet/IP — lighting, blinds/shading, HVAC actuators, room controllers. Use when integrating a KNX bus into openAut, reading or writing group addresses, decoding KNX datapoint types (DPT), or bridging KNX telemetry to MQTT. Covers group-address structure, KNXnet/IP tunnelling vs routing, and safe write practices.
---

# knx — KNX building automation

Read and control **KNX** installations via **KNXnet/IP**. KNX is common for lighting, shading, room
HVAC and presence in European buildings; this skill subscribes to bus telemetry, reads/writes group
addresses, and decodes datapoint types into engineering values for openAut.

> **Edge context:** KNX access runs on the [`edge-iot2050`](../edge-iot2050/SKILL.md) node via a
> **KNXnet/IP gateway/router** on the LAN (no special serial hardware needed). Use `xknx` (async
> Python) or `knxd` in the edge venv. The poller maps decoded group-address values to
> `openaut/<site>/<node>/<system>/<metric>`.

## Group addresses

KNX devices talk via **group addresses**, not unicast — a sensor writes to a GA and every actuator
bound to it reacts. Three-level form `main/middle/sub` (e.g. `1/2/3`), conventionally:

- **Main** = function/floor (e.g. lighting, blinds, HVAC)
- **Middle** = area/room group
- **Sub** = the individual datapoint

You need the project's **group-address list** (exported from ETS) to know what each GA means — there
is no discovery of *meaning*, only of traffic. Treat the ETS export as the point map.

## Datapoint types (DPT)

Every GA carries a typed value; decode with the DPT, never raw bytes:

| DPT | Type | Example |
|---|---|---|
| 1.001 | bool | switch on/off |
| 5.001 | 0–100 % (1 byte) | dimming level, valve position |
| 9.001 | 2-byte float | temperature °C |
| 9.004 | 2-byte float | lux |
| 13.x / 14.x | 4-byte int/float | energy, power |
| 3.007 | dimming step | relative dim |

## KNXnet/IP modes

- **Tunnelling** — point-to-point to one gateway; one tunnel connection. Good for a single edge node
  reading/writing. Some gateways allow few concurrent tunnels — don't exhaust them.
- **Routing** — multicast across IP backbone (`224.0.23.12`); sees all line traffic. Use for
  monitoring many GAs; needs a KNX IP **router**, not just an interface.

## Workflow

1. **Connect** to the KNXnet/IP gateway (tunnelling) or join routing multicast.
2. **Load** the ETS group-address export as the point map (GA → name + DPT).
3. **Monitor** GA writes for telemetry; **GroupValueRead** for current values that aren't broadcast.
4. **Decode** each value with its DPT and unit.
5. **Map & publish** via the edge poller.

## Writing (control) — safe practice

- Writes are **owner-confirmed** (Driftstekniker path), never autonomous — same rule as BACnet/Modbus.
- Send `GroupValueWrite` to the **correct GA and DPT**; a wrong DPT can mis-scale (e.g. write 1 to a
  percent DPT = 1 %, not on).
- Prefer writing to a setpoint/scene GA the design intends for external control, not directly onto
  a feedback/status GA.
- Test on non-critical loads (a single light) before touching HVAC or shading groups.

## Tips & troubleshooting

- **No traffic seen:** tunnelling sees only what you read/subscribe; for full bus visibility use
  routing or a busmonitor-capable interface.
- **Wrong values:** almost always a DPT mismatch — verify against the ETS export.
- **Gateway refuses connection:** tunnel slots exhausted, or IP/secure (KNX Secure) required — you
  may need the gateway's credentials/keyring.

> **Live behaviour is unverified until a KNX gateway is connected.** Library and gateway specifics
> vary; the group-address/DPT model and the ETS-export-as-point-map contract are the durable part.
