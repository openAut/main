---
name: dali
description: Control and monitor lighting over DALI / DALI-2 (IEC 62386) via a DALI gateway — set levels and scenes, address individual fittings or groups, read ballast/driver status and energy, and detect lamp failures. Use when integrating lighting control into openAut, commissioning DALI short addresses, or bridging DALI status to MQTT. Covers addressing (short/group/broadcast), arc-power levels, and DALI-2 features.
---

# dali — DALI lighting control

Control and monitor lighting over **DALI / DALI-2 (IEC 62386)**. DALI is the standard digital lighting
bus for commercial buildings; this skill sets levels and scenes, reads driver status and energy, and
flags failures for openAut.

> **Edge context:** DALI is reached through a **DALI gateway** (DALI↔IP/Modbus/BACnet, or a USB DALI
> master) on the [`edge-iot2050`](../edge-iot2050/SKILL.md) node. Many gateways expose DALI as Modbus
> or BACnet objects — in that case use the [`modbus`](../modbus/SKILL.md)/[`bacnet`](../bacnet/SKILL.md)
> skills against the gateway and treat this skill as the DALI concept reference.

## Addressing

A DALI line carries up to **64 control gear** (short addresses 0–63), 16 **groups**, and 16 **scenes**:

- **Short address** (0–63) — one fitting/driver. Assigned at commissioning.
- **Group** (0–15) — a fitting can belong to several groups; address a whole group at once.
- **Broadcast** — all gear on the line.

DALI-2 also defines **control devices** (input devices: sensors, push-buttons) on the same line,
addressed separately from control gear.

## Levels and scenes

- **Arc power level** 0–254 (plus 255 = "MASK"/no change). The mapping to perceived brightness is
  **logarithmic** (dim curve) — level 254 = max, ~85 ≈ ~10 %, 0 = off.
- **Fade time/rate** controls how fast a level change happens.
- **Scenes** (0–15) store a preset level per fitting; recalling a scene is one command to many gear.
- Min/max level, power-on level and system-failure level are configurable per driver.

## Status & monitoring (DALI-2)

Query gear for:

- **Lamp failure** / **control gear failure** flags — drives maintenance alerts.
- **Actual level** and **status byte**.
- **Energy & power reporting** (IEC 62386-252/253) on capable drivers — feeds energy reporting.

## Workflow

1. **Connect** to the DALI gateway (native API, or Modbus/BACnet object map it exposes).
2. **Commission** (if needed): run address assignment so each gear has a unique short address; record
   the address↔luminaire map as the point map.
3. **Monitor** status/levels and any energy registers → publish failures and consumption.
4. **Control** (owner-confirmed): set group/scene levels with an appropriate fade.

## Writing (control) — safe practice

- Control is **owner-confirmed** via the Driftstekniker path, not autonomous.
- Prefer **group/scene** commands over per-fitting writes for predictable behaviour.
- Respect the design's **system-failure level** so lights fail to a safe state on bus loss.
- Test on one short address before broadcasting.

## Tips & troubleshooting

- **Gear not responding:** unaddressed (no short address) or bus power/length limits exceeded; DALI
  lines have a max cable length and a bus-power budget.
- **Brightness "wrong":** remember the logarithmic dim curve — level is not linear percent.
- **Mixed DALI-1/DALI-2:** input devices and energy reporting need DALI-2 gear and a DALI-2 master.

> **Live behaviour is unverified until DALI hardware/gateway is connected.** Gateway abstractions vary
> widely; the addressing model, logarithmic levels, scenes, and status flags are the durable part.
