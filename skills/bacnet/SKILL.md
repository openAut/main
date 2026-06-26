---
name: bacnet
description: Discover and communicate with BACnet/IP devices for building automation and HVAC — thermostats, air handlers, VAV boxes, energy meters, lighting and chillers. Use when finding devices (Who-Is), reading object properties (temperature, setpoints, status), writing values with the priority array, or enumerating a device's objects. Feeds the openAut edge poller.
permissions:
  knowledge_only: false
  exec: "allowlisted (BAC0 edge venv scripts)"
  network: "outbound BACnet/IP (UDP 47808)"
  files: "read-only"
  control_writes: "owner-confirmed (Driftstekniker path), never autonomous"
---

# bacnet — BACnet/IP building automation

Communicate with **BACnet** devices — the dominant open protocol for HVAC and building automation.
Read sensors and status, and (owner-confirmed) write setpoints and commands.

> **Edge context:** BACnet/IP runs on the [`edge-iot2050`](../edge-iot2050/SKILL.md) node over the LAN
> (UDP/47808). Use `BAC0`/`bacpypes3` in the edge venv. The poller maps each object's value to
> `openaut/<site>/<node>/<system>/<metric>`. A quick sweep without the library:
> `nmap -sU -p 47808 --script bacnet-info <subnet>`.

## Objects and properties

Devices expose **objects**; you read/write their **properties** (usually `presentValue`):

| Object type | Use |
|---|---|
| `analogInput` | sensors (temp, pressure, flow) |
| `analogOutput` | control outputs (valve, damper position) |
| `analogValue` | setpoints, calculated values |
| `binaryInput` / `binaryOutput` / `binaryValue` | status / on-off control / mode |
| `multiState*` | enumerated modes/positions |
| `device`, `trendLog`, `schedule`, `loop` | device itself, history, time control, PID |

Common properties: `presentValue`, `objectName`, `units`, `statusFlags` (in-alarm/fault/overridden/
out-of-service), `outOfService`, `reliability`. Always check `statusFlags` for data quality.

## Addressing

- IP address (`192.168.1.50`), device id (`device:1001`), or `network:mac` form.
- **Who-Is / I-Am** discovers devices; allow 10–20 s, and try direct addressing for devices that
  don't answer broadcast. Discovery needs broadcast reachability (watch routers/firewalls on 47808).

## Write priority array (1–16)

BACnet writes go to a **priority array**; lowest number wins:

| Priority | Use |
|---|---|
| 1–2 | manual life safety |
| 3–4 | automatic life safety |
| 5 | critical equipment |
| 6 | minimum on/off |
| **8** | **manual operator (use for overrides)** |
| 16 | scheduling (lowest) |

Release an override by writing **NULL** to that priority level. Don't use life-safety priorities
(1–4) for routine control.

## Workflow

1. **Discover** devices (Who-Is) or address directly.
2. **Enumerate** a device's object list when the map is unknown.
3. **Read** `presentValue` (+ `units`, `statusFlags`).
4. **Map & publish** via the edge poller.
5. **Write** (owner-confirmed) at priority 8, verifying object and range first.

## Writing (control) — safe practice

- Owner-confirmed via the Driftstekniker path, never autonomous.
- Confirm the correct object/instance; some properties are read-only.
- Use priority 8 for manual overrides; release with NULL; test on non-critical equipment.

## Tips & troubleshooting

- **No devices found:** broadcast blocked (UDP 47808), different subnet, or slow device — increase
  timeout, try direct addressing.
- **Can't write:** read-only property, wrong object, or device access control; check `statusFlags`.

> **Live behaviour is unverified until BACnet hardware is connected.** Object maps are per-device; the
> object/property model and priority-array rules are the durable part.
