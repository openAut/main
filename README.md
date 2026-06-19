# openAut NemoClaw Skills

> ## ⚠️ Learning project — not for production
>
> This is a **development and learning project** whose purpose is to explore how AI agents can be
> applied to building management. It is **not a product** and is **not intended for live or
> production environments**.
>
> - The skills are runbooks and **reference scripts**; their live behaviour is **unverified** (every
>   `SKILL.md` says so). They have not been tested against real building hardware, control systems,
>   or a production NemoClaw deployment.
> - **Do not** connect these to live HVAC, energy, or safety-critical systems, or to occupied
>   buildings. A wrong setpoint or control write can damage equipment or affect people.
> - Anything that writes to field devices must stay a **human-confirmed** action, and should only be
>   exercised in a lab/test rig you fully control.
> - Use this to **learn** — read the architecture, study the security model, experiment in an
>   isolated sandbox. For real deployments, engage qualified controls, security, and compliance
>   professionals and validate everything independently.

Agent-agnostic **skills (runbooks)** that let a coding agent — **Claude Code** or **OpenAI Codex** —
securely connect to a server and provision **NemoClaw** agents that follow the
[openAut](https://openaut.io) reference architecture, as a hands-on way to learn the patterns.

These skills do **not** reimplement NemoClaw. NemoClaw already ships the bootstrap
(`curl … nemoclaw.sh | bash`), the Landlock + seccomp + netns sandbox, inference routing,
and lifecycle CLI. The skills here **orchestrate that documented CLI over SSH** and bake in two
openAut-specific defaults:

| Default | Choice | Why |
|---|---|---|
| **Communication channel** | **Microsoft Teams** (via webhook bridge) | openAut targets the Microsoft stack (Teams + Power BI). NemoClaw has no native Teams channel, so a small bridge maps Teams ↔ the OpenClaw gateway. |
| **Inference** | **Remote Nemotron 3 Super** on a separate machine, **egress-locked + TLS** | Keeps the heavy MoE model on a dedicated GPU box (e.g. ASUS Ascent GX10), reachable only from the sandbox over an encrypted, allow-listed link. |

> These defaults are configurable. Set `TEAMS_*` and `NEMOTRON_*` in `config.env` to point at
> your own bridge and inference host; every skill sources that file.

## Skills

**Agent tier — create the NemoClaw agents:**

| Skill | What it does |
|---|---|
| [`nemoclaw-provision`](skills/nemoclaw-provision/SKILL.md) | SSH preflight → run the NemoClaw installer → onboard a sandbox pointed at the **remote Nemotron 3 Super** endpoint → attach the **Teams** bridge → verify. The end-to-end install runbook. |
| [`nemoclaw-sandbox-policy`](skills/nemoclaw-sandbox-policy/SKILL.md) | Manage the four sandbox layers after creation: **deny-by-default egress** allow-listed to the Teams bridge + Nemotron host only, TLS verification, and a hardening review mapped to IEC 62443 / NIS2 / CRA. |
| [`nemoclaw-agent-workflow`](skills/nemoclaw-agent-workflow/SKILL.md) | Define the three openAut role agents — **Driftstekniker**, **Energisamordnare**, **Förvaltare** — as NemoClaw agent workflows, each defaulting to Teams, each granted only the runtime skills it needs. |

**Data backbone & edge — what the agents read from:**

| Skill | What it does |
|---|---|
| [`mqtt-tls-broker`](skills/mqtt-tls-broker/SKILL.md) | EMQX broker with a **mutual-TLS** listener, a per-edge-node **client-certificate PKI**, a CN-bound **ACL** topic schema, and TLS verification. The encrypted ingest backbone. |
| [`timeseries-stack`](skills/timeseries-stack/SKILL.md) | **TimescaleDB + PostgreSQL** — telemetry hypertable, system schema, MQTT→DB ingest, retention + continuous aggregates, and **least-privilege roles** (ingest write, agent read-only). |
| [`edge-iot2050`](skills/edge-iot2050/SKILL.md) | Provision a **Siemens IOT2050** edge node: field-protocol poller → EMQX over mutual TLS with the node's cert, **store-and-forward** buffering, resilient systemd service. |

**Runtime capabilities — what each agent persona carries:**

| Group | Skills |
|---|---|
| Field protocols | [`bacnet`](skills/bacnet/SKILL.md) · [`modbus`](skills/modbus/SKILL.md) · [`mbus`](skills/mbus/SKILL.md) · [`knx`](skills/knx/SKILL.md) · [`dali`](skills/dali/SKILL.md) · [`lorawan`](skills/lorawan/SKILL.md) |
| Analytics | [`fdd`](skills/fdd/SKILL.md) · [`energy-optimization`](skills/energy-optimization/SKILL.md) · [`anomaly-correlation`](skills/anomaly-correlation/SKILL.md) |
| Compliance | [`nis2`](skills/nis2/SKILL.md) · [`cra`](skills/cra/SKILL.md) · [`ai-act`](skills/ai-act/SKILL.md) · [`iso27001`](skills/iso27001/SKILL.md) · [`iec62443`](skills/iec62443/SKILL.md) |

The personas in [`nemoclaw-agent-workflow`](skills/nemoclaw-agent-workflow/SKILL.md) are each granted
a **least-privilege subset** of these (e.g. read-only protocols + analytics for the energy role).

Supporting:

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — the full openAut four-layer diagram and where each skill fits.
- [`bridges/teams-webhook/`](bridges/teams-webhook/README.md) — the minimal Teams ↔ gateway bridge the channel default depends on.
- [`config.env.example`](config.env.example) — copy to `config.env` and fill in.

## Using these skills

**Claude Code** — drop the `skills/` folders into `~/.claude/skills/` (or a project `.claude/skills/`).
Each `SKILL.md` carries YAML frontmatter so the agent auto-discovers it.

**OpenAI Codex** (and any other agent) — there is no skill auto-loader, so point the agent at the
relevant `SKILL.md` and tell it to follow it as a runbook. The bodies are plain Markdown +
self-contained shell/Python; nothing depends on the Anthropic skill mechanism.

## Scope

This pack is a full openAut skill set: the **agent tier** (provision, sandbox policy, role workflows),
the **data backbone + edge** (MQTT/TLS broker, TimescaleDB/PostgreSQL, IOT2050), and the **runtime
capabilities** the agents carry (six field protocols, three analytics skills, five compliance
references). The protocol and analytics skills are vendor- and site-agnostic guidance + reference
scripts; live behaviour is unverified until real hardware and the data backbone are connected (each
SKILL.md says so). What remains genuinely outside the pack is openAut's own application code (the
dashboards, Power BI, REST API of Layer 4) — these skills *operate* a deployment, they are not the
product itself.

## Source references

- NVIDIA DGX Spark playbook — NemoClaw: <https://github.com/NVIDIA/dgx-spark-playbooks/blob/main/nvidia/nemoclaw/README.md>
- NemoClaw docs: <https://docs.nvidia.com/nemoclaw/user-guide/openclaw/home>
- OpenClaw docs: <https://docs.openclaw.ai/>

> Tested against NemoClaw **v0.0.55** (June 2026). The installer's default model is
> `nvidia/Qwen3.6-35B-A3B-NVFP4`; these skills override it to Nemotron 3 Super on a remote host.
