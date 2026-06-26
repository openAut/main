---
name: modbus
description: Scan and communicate with Modbus TCP/RTU devices — PLCs, meters, drives, I/O modules and sensors common in HVAC and industrial plant. Use when enumerating slave/unit IDs, reading holding/input registers, coils and discrete inputs, decoding scaled or multi-register values, or writing setpoints/commands. Feeds the openAut edge poller.
permissions:
  knowledge_only: false
  exec: "allowlisted (pymodbus edge venv scripts)"
  network: "outbound Modbus TCP (port 502) / RTU serial"
  files: "read-only"
  control_writes: "owner-confirmed (Driftstekniker path), never autonomous"
---

# modbus — Modbus TCP/RTU

Communicate with **Modbus** devices — the most widespread industrial fieldbus, found on PLCs, energy
meters, VFDs, I/O modules and HVAC controllers. Read process data and (owner-confirmed) write
setpoints/commands.

> **Edge context:** Modbus reads run on the [`edge-iot2050`](../edge-iot2050/SKILL.md) node — TCP over
> the LAN, or RTU via an RS-485 serial adapter. Use `pymodbus` in the edge venv. The poller maps each
> decoded register to `openaut/<site>/<node>/<system>/<metric>`.

## Data model

Four register spaces; mind 0- vs 1-based addressing (docs often list 4xxxx references = holding):

| Space | Access | Typical use |
|---|---|---|
| **Coils** (0x) | read/write bit | on/off outputs (fan, pump enable) |
| **Discrete inputs** (1x) | read bit | status inputs (alarm, switch) |
| **Input registers** (3x) | read 16-bit | sensor measurements |
| **Holding registers** (4x) | read/write 16-bit | setpoints, config, many sensors too |

## Addressing & transport

- **TCP**: `host:502`, **unit id** still matters (gateways multiplex serial devices behind one IP).
- **RTU**: serial, **slave id 1–247**; all devices share `baud/parity/stopbits` — they must match.
- Scan a range of unit/slave ids to enumerate devices; expect timeouts on empty ids.

## Decoding values

Registers are 16-bit; real values often span or scale:

- **Scaling**: apply the device's factor (e.g. raw `225` × 0.1 = 22.5 °C). Read the register map.
- **32-bit** (float/int): two consecutive registers — watch **word order** (big/little-endian,
  word-swap). If a value looks wildly wrong, swap word order first.
- **Signed**: interpret two's complement where the map says signed.

## Workflow

1. **Connect** (TCP host:port or serial params).
2. **Enumerate** unit/slave ids if unknown.
3. **Read** the registers from the device's map (function 0x01–0x04).
4. **Decode** with scale, sign, and word order; attach the unit.
5. **Map & publish** via the edge poller on the node interval.

## Writing (control) — safe practice

- Writes are **owner-confirmed** (Driftstekniker path), never autonomous.
- Use function 0x06 (single) / 0x10 (multiple) for holding registers, 0x05/0x0F for coils.
- Verify the register is intended for external write (some are read-only/echo); test on non-critical
  points; respect valid ranges from the map.

## Tips & troubleshooting

- **Timeouts (RTU):** baud/parity mismatch, wrong slave id, A/B wiring swapped, missing termination.
- **Wrong numbers:** off-by-one addressing (1-based map vs 0-based API), or word order on 32-bit.
- **Gateway devices:** one IP, many unit ids — don't assume unit 1.

> **Live behaviour is unverified until Modbus hardware is connected.** Register maps are per-device;
> the data model, addressing and decoding rules are the durable part.
