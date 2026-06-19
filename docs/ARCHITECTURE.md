# openAut architecture & where these skills fit

> ⚠️ **Learning project — not for production.** This is a development/learning exploration of AI in
> building management, not a product. Do not use against live or safety-critical systems. See the
> [README](../README.md#️-learning-project--not-for-production) for the full disclaimer.

This pack provisions the **agent tier** of an [openAut](https://openaut.io) deployment. openAut is a
four-layer, on-premise building-management AI: field data flows up through edge nodes to an on-site
AI tier, and role-specific agents push insight back out to people. Nothing leaves the building.

## The four layers

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 4 — INTERFACE                                                           │
│   Microsoft Teams  ·  web dashboard  ·  Power BI  ·  REST API                 │
│        ▲                                                                      │
│        │  Teams webhook bridge  (bridges/teams-webhook)         ◀── DEFAULT   │
│        │                                                                      │
│ ┌──────┴───────────────────────────────────────────────────────────────────┐│
│ │ LAYER 3 — AI (on-prem)                                                     ││
│ │                                                                            ││
│ │   ┌──────────────── NemoClaw sandbox (DGX Spark / RTX) ─────────────────┐  ││
│ │   │  Landlock + seccomp + netns                                         │  ││
│ │   │                                                                     │  ││
│ │   │   Driftstekniker   Energisamordnare   Förvaltare   ◀── 3 role agents│  ││
│ │   │   (alarm RCA)      (weekly energy)    (status/forecast)             │  ││
│ │   │        │                  │                 │                       │  ││
│ │   │        └──── tool calls ──┴──── read/write ─┘                       │  ││
│ │   └─────────┬───────────────────────────────────────────┬─────────────┘  ││
│ │             │ inference (TLS, egress-locked)             │ data            ││
│ │             ▼                                            ▼                 ││
│ │   ┌──────────────────────┐                  ┌──────────────────────────┐  ││
│ │   │ Nemotron 3 Super box │                  │ EMQX (MQTT/TLS)          │  ││
│ │   │ vLLM + TLS proxy     │  ◀── DEFAULT     │ TimescaleDB · PostgreSQL │  ││
│ │   │ (separate machine)   │                  └────────────▲─────────────┘  ││
│ │   └──────────────────────┘                               │                ││
│ └──────────────────────────────────────────────────────────┼───────────────┘│
│                                                             │ encrypted MQTT │
│ ┌───────────────────────────────────────────────────────────┴──────────────┐│
│ │ LAYER 2 — EDGE                                                            ││
│ │   Siemens SIMATIC IOT2050 nodes · protocol drivers · local buffer        ││
│ └───────────────────────────────────────────────────────────┬──────────────┘│
│                                                              │               │
│ ┌────────────────────────────────────────────────────────────┴─────────────┐│
│ │ LAYER 1 — FIELD                                                           ││
│ │   sensors · meters · PLCs   ·   BACnet / Modbus / M-Bus / KNX / DALI /    ││
│ │                                  LoRaWAN   ·   Python edge regulation     ││
│ └──────────────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────────┘

◀── DEFAULT  = the two choices baked into this skill pack
```

## What this pack provisions

| Skill | Layer | Responsibility |
|---|---|---|
| [`nemoclaw-provision`](../skills/nemoclaw-provision/SKILL.md) | 3 | Install NemoClaw on the sandbox host; onboard a sandbox pointed at the **remote Nemotron 3 Super** endpoint; attach the **Teams** bridge; verify. |
| [`nemoclaw-sandbox-policy`](../skills/nemoclaw-sandbox-policy/SKILL.md) | 3 | Lock the sandbox: deny-by-default egress to **only** the Nemotron host + Teams bridge; TLS in front of vLLM; IEC 62443 / NIS2 / CRA review. |
| [`nemoclaw-agent-workflow`](../skills/nemoclaw-agent-workflow/SKILL.md) | 3→4 | Define the three openAut role agents, default them to Teams, scope each to least-privilege runtime skills. |
| [`bridges/teams-webhook`](../bridges/teams-webhook/README.md) | 4 | Map Teams ↔ the OpenClaw gateway (NemoClaw has no native Teams channel). |
| [`mqtt-tls-broker`](../skills/mqtt-tls-broker/SKILL.md) | 3 | EMQX mutual-TLS broker, per-node cert PKI, CN-bound ACL topic schema — the encrypted ingest backbone. |
| [`timeseries-stack`](../skills/timeseries-stack/SKILL.md) | 3 | TimescaleDB + PostgreSQL, MQTT→DB ingest, retention/aggregates, least-privilege roles. |
| [`edge-iot2050`](../skills/edge-iot2050/SKILL.md) | 2 | Siemens IOT2050 edge node: field poller → EMQX over mutual TLS, store-and-forward buffering. |

## The two defaults, and why

- **Microsoft Teams as the channel.** openAut targets the Microsoft stack (Teams + Power BI). NemoClaw
  ships Telegram/Discord/Slack but not Teams, so the pack adds a webhook bridge and points every
  persona at it. Swap it by editing `TEAMS_*` in `config.env`, or graduate to Azure Bot Service later
  without changing the agents.
- **Remote Nemotron 3 Super, egress-locked + TLS.** The 120B MoE model lives on a dedicated GPU box
  (e.g. ASUS Ascent GX10 running vLLM). The sandbox reaches it over TLS and is allowed to reach
  *nothing else* — turning "an agent with shell access" into "an agent that can only talk to its model
  and its channel". This is the control that satisfies the openAut NIS2 / IEC 62443 posture.

## Trust boundaries

1. **Field/edge → AI** — edge nodes publish over **encrypted MQTT (TLS)** to EMQX. Untrusted sensor
   data; validated before it reaches an agent.
2. **Agent → model** — sandbox → Nemotron over **TLS, single allow-listed destination**. No fallback
   to public LLM APIs (AI Act provider control).
3. **Agent → people** — only through the Teams bridge, which **HMAC-verifies** inbound Teams calls.
   Inbound Teams text is treated as untrusted (prompt-injection surface); the sandbox policy is the
   backstop.
4. **Sandbox kernel boundary** — Landlock (filesystem), seccomp (syscalls), netns (network) confine
   the agent regardless of what a prompt convinces it to attempt.

## Runtime capabilities the agents carry

The pack also includes the runtime skills each persona is granted (least-privilege) in
[`nemoclaw-agent-workflow`](../skills/nemoclaw-agent-workflow/SKILL.md):

- **Field protocols (Layer 1):** [`bacnet`](../skills/bacnet/SKILL.md),
  [`modbus`](../skills/modbus/SKILL.md), [`mbus`](../skills/mbus/SKILL.md),
  [`knx`](../skills/knx/SKILL.md), [`dali`](../skills/dali/SKILL.md),
  [`lorawan`](../skills/lorawan/SKILL.md) — read field data; the edge poller and agents use these.
- **Analytics (Layer 3):** [`fdd`](../skills/fdd/SKILL.md),
  [`energy-optimization`](../skills/energy-optimization/SKILL.md),
  [`anomaly-correlation`](../skills/anomaly-correlation/SKILL.md) — turn telemetry into diagnosis,
  savings, and root-cause alerts.
- **Compliance references:** [`nis2`](../skills/nis2/SKILL.md), [`cra`](../skills/cra/SKILL.md),
  [`ai-act`](../skills/ai-act/SKILL.md), [`iso27001`](../skills/iso27001/SKILL.md),
  [`iec62443`](../skills/iec62443/SKILL.md) — the legal/standards backdrop the design is built to.

## Genuinely out of scope

openAut's own Layer-4 application code — the web dashboard, Power BI models, REST API — is the product
itself. These skills *operate and secure* a deployment; they don't replace that application.
