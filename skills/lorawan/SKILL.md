---
name: lorawan
description: Integrate LoRaWAN sensors into openAut via a network server (e.g. ChirpStack) — onboard devices with OTAA/ABP, decode uplink payloads, manage device classes and downlinks, and bridge decoded measurements to MQTT. Use when adding long-range battery sensors (temperature, humidity, CO₂, occupancy, leak, energy) to a building, setting up a LoRaWAN gateway/network server, or writing payload decoders. EU868 focus.
permissions:
  knowledge_only: false
  network: "LoRaWAN network server (e.g. ChirpStack) + MQTT bridge"
  exec: "operator-provisioned payload decoders/tooling, allowlisted"
  files: "read-only"
  control_writes: "downlinks owner-confirmed (Class C actuators), never autonomous"
---

# lorawan — LoRaWAN sensor integration

Bring **LoRaWAN** sensors into openAut. LoRaWAN is a low-power wide-area network for battery sensors
(temperature, humidity, CO₂, occupancy, leak, sub-metering) across a building or campus on one
gateway. This skill onboards devices, decodes uplinks, and bridges measurements to MQTT.

> **Architecture:** unlike the wired field buses, LoRaWAN terminates at a **network server** (commonly
> **ChirpStack**, self-hosted on-prem to stay air-gap-friendly), fed by one or more **gateways**. The
> network server exposes an **MQTT integration** — so openAut subscribes to ChirpStack's MQTT and
> re-publishes decoded values onto the `openaut/<site>/<node>/<system>/<metric>` schema. No serial
> hardware on the edge node; the gateway is the bridge.

## Activation (joining)

- **OTAA** (over-the-air activation, preferred) — device holds **DevEUI**, **JoinEUI/AppEUI**, and
  **AppKey**; it negotiates session keys on join. More secure, supports rejoin/rekey.
- **ABP** (activation by personalisation) — session keys (DevAddr, NwkSKey, AppSKey) burned in; no
  join. Simpler but weaker key management and frame-counter pitfalls. Use OTAA unless forced.

Onboard each device in the network server with its keys and a **device profile** (region, MAC
version, class).

## Device classes

| Class | Downlink behaviour | Use |
|---|---|---|
| **A** | downlink only in two short windows after an uplink | most battery sensors (lowest power) |
| **B** | scheduled downlink slots (beaconed) | sensors needing periodic downlink |
| **C** | continuously listening | mains-powered actuators (low latency downlink) |

Most openAut sensors are **Class A** — accept that downlinks (config changes) only land after the
device next transmits.

## Payload decoding

LoRa payloads are tiny, packed bytes — **decode, don't guess**:

- Use the vendor's **codec** (often a JS `decodeUplink()` for ChirpStack/TTN) per device profile.
- The decoder turns bytes into named fields with units (e.g. `{temperature: 21.4, humidity: 55, co2: 780}`).
- Map those fields to metrics; keep the **unit** in the published payload.

## EU868 / radio notes

- Region **EU868**: duty-cycle limited (typically 1 % per sub-band) — devices and downlinks are
  rate-limited by regulation; don't expect frequent downlinks.
- **Spreading factor (SF7–SF12)** trades range for airtime/battery; **ADR** (adaptive data rate) lets
  the network optimise it. Leave ADR on for static sensors.
- Coverage is about gateway placement and SF, not wiring — one well-placed gateway can cover a
  building; thick plant rooms may need a second.

## Workflow

1. **Stand up** the network server (ChirpStack) + gateway on-prem; point the gateway at it.
2. **Add device profiles** (region EU868, class, MAC version) and the **uplink codecs**.
3. **Onboard devices** (OTAA: DevEUI/JoinEUI/AppKey) and confirm joins.
4. **Enable the MQTT integration**; subscribe to decoded uplinks.
5. **Re-map & publish** decoded fields onto the openAut topic schema (a small bridge consumer, like
   the [`timeseries-stack`](../timeseries-stack/SKILL.md) ingest pattern).

## Tips & troubleshooting

- **Device won't join (OTAA):** wrong AppKey/DevEUI, region mismatch, or out of gateway range; check
  the join-request in the network server logs.
- **Garbled values:** wrong/missing codec for that profile — fix the decoder, not the data.
- **Sparse data:** expected for Class A + duty cycle; set sensible uplink intervals on the device.
- **Downlink "ignored":** Class A only receives after an uplink; queue it and wait.

> **Live behaviour is unverified until a gateway + network server are running.** Vendor codecs and
> ChirpStack specifics vary; OTAA/class/duty-cycle constraints and the network-server-MQTT bridge
> contract are the durable part.
