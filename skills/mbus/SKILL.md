---
name: mbus
description: Read utility and energy meters over M-Bus (Meter-Bus, EN 13757) — wired and wireless (wM-Bus). Use when integrating heat, electricity, water, gas or cooling meters into openAut, scanning an M-Bus segment for devices, reading consumption/flow/temperature registers, or mapping meter data onto the MQTT telemetry schema. Covers primary/secondary addressing, baud negotiation, and decoding of M-Bus data records.
permissions:
  knowledge_only: false
  network: "M-Bus / wireless M-Bus segment + MQTT bridge"
  exec: "operator-provisioned meter-scan tooling, allowlisted"
  files: "read-only"
  control_writes: none
---

# mbus — Meter-Bus metering

Read consumption and process meters over **M-Bus (EN 13757)** and **wireless M-Bus**. Heat, water,
electricity, gas and cooling meters are the backbone of openAut energy reporting; this skill scans a
segment, reads meters, decodes the records, and hands values to the edge poller for publication.

> **Edge context:** M-Bus reads run on the [`edge-iot2050`](../edge-iot2050/SKILL.md) node (a USB or
> serial M-Bus level converter on the bus). The poller maps each decoded value to
> `openaut/<site>/<node>/<system>/<metric>`. Use `libmbus`/`mbus-serial` or `pyMeterBus` in the edge
> venv.

## Addressing

- **Primary address** (1–250): set per meter; fast to poll. 0 = unconfigured, 254 = broadcast,
  255 = broadcast-no-reply.
- **Secondary address**: the 8-byte fabrication number (ID + manufacturer + version + medium); used
  to select a meter regardless of primary address — essential when many meters share a bus.

## Bus basics

- Two-wire, polarity-independent; the master powers the bus. A segment supports a limited number of
  **unit loads** — long buses / many meters need a stronger level converter or repeaters.
- Common baud rates **2400** (default) and **9600**; meters auto-detect within a range. Start at 2400.
- **wM-Bus** (868 MHz in EU): modes S/T/C/N; meters transmit periodically — you receive rather than
  poll. Decryption (AES-128) needs the per-meter key.

## Workflow

1. **Scan** the segment for primary addresses (or do a secondary-address wildcard search for IDs).
2. **Request data** (REQ_UD2) from each meter → it returns an RSP_UD frame.
3. **Decode** the variable data records: each has a DIF/VIF (data + value information field) giving
   the unit, scaling exponent and storage number.
4. **Select metrics** that matter (energy, volume, flow, supply/return temperature, power).
5. **Map** to the telemetry schema and let the edge poller publish on the node's interval.

## Decoding cheatsheet

| Field | Meaning |
|---|---|
| **DIF** | data length & type, storage/tariff/subunit |
| **VIF** | physical unit + decimal scaling (e.g. energy Wh×10ⁿ, volume m³×10ⁿ, power W, temp °C) |
| **VIFE** | extensions/combinations of the VIF |

Always apply the VIF scaling exponent — a raw integer of `12345` with VIF energy ×10⁻³ is `12.345`
of the base unit. Record the **unit** alongside the value in the payload.

## Common meters

| Medium | Typical metrics |
|---|---|
| Heat (fjärrvärme) | energy (kWh/MWh), volume, flow, supply/return temp, power |
| Electricity | active energy, power, voltage, current |
| Water / gas | volume, flow |
| Cooling | cooling energy, flow, temps |

## Tips & troubleshooting

- **No response:** check polarity-independent wiring continuity, baud (try 2400 then 9600), and the
  converter's unit-load budget; one shorted meter can stall the bus.
- **Collisions on scan:** use secondary addressing if primaries clash (many meters ship as address 0).
- **wM-Bus silent:** confirm the mode (T vs C vs S) and that you have the AES key for encrypted meters.
- **Slow polling:** stagger reads; some meters need a pause between REQ_UD2 frames.

> **Live behaviour is unverified until M-Bus hardware is connected.** Converter and library specifics
> vary; the addressing, DIF/VIF decoding, and edge-mapping contract are the durable part.
