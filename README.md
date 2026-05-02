# openAut

> Open-source integration and AI advisory platform for building automation systems.

openAut connects field-level equipment — PLCs, DDCs, chillers, air handling units, and energy meters — to a local AI layer that provides fault diagnostics, energy optimization, and alarm management. No central control. No cloud dependency. No vendor lock-in.

---

## What it does

Commercial and public-sector buildings run complex automation systems from dozens of manufacturers, speaking incompatible protocols, generating data that mostly goes unanalyzed. Facility operators respond to alarms reactively, energy optimization is manual, and troubleshooting relies on individual expertise that is hard to retain.

openAut sits between the field and the people who operate it:

- **Edge nodes** collect data from field equipment over standard protocols and buffer it locally
- **A local AI layer** on dedicated hardware analyzes trends, correlates alarms, suggests root causes, and identifies energy savings — all on-premises
- **Operators interact** via familiar messaging apps (Telegram, Signal, Slack) powered by [OpenClaw](https://openclaw.ai)

No data leaves the building. No subscription required. No proprietary runtime.

---

## Architecture

```
Field Layer                Edge Layer              AI Layer
──────────────────         ────────────────────    ─────────────────────

PLC (IEC 61131-3)  ──────▶                        
DUC / DDC          ──────▶  openAut Edge Node      NVIDIA DGX Spark
Chiller            ──────▶  ─────────────────  ──▶ ──────────────────
AHU (integrated)   ──────▶  Protocol drivers        OpenClaw Gateway
Energy meters      ──────▶  OPC UA server           Nemotron (local)
Heat pumps         ──────▶  Local time-series        BAS Tool Server
VRF systems        ──────▶  buffer                  
                            MQTT forwarder          
                                                    
                            No write-back           Operator via
                            to field equipment      Telegram / Signal
```

The edge node is **read-only**. All regulation and control remains with the field devices. openAut observes, collects, and advises — it does not command.

---

## Supported protocols

| Protocol | Role |
|---|---|
| **Modbus RTU / TCP** | Chillers, AHUs, heat pumps, VFDs |
| **BACnet MS/TP / BACnet IP** | DDCs, PLCs, supervisory controllers |
| **OPC UA** | PLCs, modern SCADA integration |
| **OPC classic (via gateway)** | Legacy installations |
| **M-Bus** | Energy and heat meters |
| **MQTT** | Internal transport, edge → AI layer |

---

## Key capabilities

**Data collection**
- Unified data model across all protocols and manufacturers
- Local ring buffer (minimum 72 hours) survives network outages
- Semantic tagging compatible with [Project Haystack](https://project-haystack.org) and [Brick Schema](https://brickschema.org)

**AI advisory (on-premises)**
- Fault detection and diagnostics via conversational interface
- Alarm correlation and root cause suggestions
- Energy KPI monitoring and anomaly detection
- Equipment-specific context: make, model, operating ranges, alarm limits
- All inference runs locally on dedicated hardware — no API calls to external services

**Operator interface**
- Natural language queries via Telegram, Signal, Slack, or web chat
- Powered by [OpenClaw](https://openclaw.ai) (MIT licensed)
- Responses include referenced data points and trend context
- Configurable per-user access control

**Integration-ready**
- OPC UA server on edge node — any OPC UA client can subscribe
- MQTT broker compatible with standard tooling (Node-RED, Grafana, InfluxDB)
- REST API for custom integrations

---

## Designed for public sector

openAut is built with Swedish and European public-sector requirements in mind:

- **Open standards throughout** — no proprietary protocols or runtimes in the core
- **Data stays on-premises** — GDPR and NIS2 compliant by architecture
- **Auditable** — full audit log of AI advisory actions and operator interactions
- **Vendor-neutral** — qualifying under LOU criteria for open and interoperable systems
- **Documented** — all APIs and data models are openly specified

---

## Hardware reference

**Edge node** — any Linux computer with serial and Ethernet interfaces
- Raspberry Pi 5, Siemens IoT2050, Odyssey x86, or equivalent industrial mini-PC
- Minimum: 4 GB RAM, 32 GB storage, RS-485 interface, Gigabit Ethernet

**AI node** — [NVIDIA DGX Spark](https://www.nvidia.com/en-us/products/workstations/dgx-spark/) (recommended)
- GB10 Grace Blackwell Superchip, 128 GB unified memory
- Runs Nemotron 70B–120B locally for full-context diagnostics
- Ubuntu 24.04 LTS (ARM64)
- Smaller GPU systems supported for reduced model sizes

---

## Status

> ⚠️ Early development. Not production-ready.
> APIs, data models, and configuration formats will change.
> Contributions and feedback welcome.

| Component | Status |
|---|---|
| Edge node — Modbus driver | 🔧 In progress |
| Edge node — BACnet driver | 🔧 In progress |
| Edge node — OPC UA server | 📋 Planned |
| Edge node — M-Bus driver | 📋 Planned |
| Local time-series buffer | 🔧 In progress |
| MQTT forwarder | 📋 Planned |
| OpenClaw integration | 📋 Planned |
| BAS Tool Server | 📋 Planned |
| Semantic data model | 📋 Planned |

---

## License

MIT — see [LICENSE](LICENSE)

---

## Contributing

openAut is early-stage and welcomes contributors with experience in:

- Building automation protocols (Modbus, BACnet, OPC UA, M-Bus)
- Field integration (PLCs, DDCs, chillers, AHUs)
- Python, Node.js
- OT/IT security
- Swedish public sector procurement (LOU)

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## Related projects

- [OpenClaw](https://openclaw.ai) — self-hosted AI agent gateway (MIT)
- [NVIDIA NemoClaw](https://github.com/NVIDIA/NemoClaw) — secure OpenClaw deployment on DGX hardware
- [Project Haystack](https://project-haystack.org) — semantic modeling for building data
- [Brick Schema](https://brickschema.org) — building metadata ontology
- [open62541](https://github.com/open62541/open62541) — open-source OPC UA stack (MIT)
- [BAC0](https://github.com/ChristianTremblay/BAC0) — BACnet Python library
- [pymodbus](https://github.com/pymodbus-dev/pymodbus) — Modbus Python library
