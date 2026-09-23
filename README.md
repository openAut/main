# openAut Agent

> ## ⚠️ Learning project — not for production
>
> This is a **development and learning project** whose purpose is to explore how AI agents can be
> applied to building management. It is **not a product** and is **not intended for live or
> production environments**.
>
> - The skills are runbooks and **reference scripts**. Two equipment-specific read-only Modbus
>   integrations have been exercised on physical hardware in an isolated POC. This does not validate
>   the generic drivers, other equipment, field writes or a production NemoClaw deployment.
> - **Do not** connect these to live HVAC, energy, or safety-critical systems, or to occupied
>   buildings. A wrong setpoint or control write can damage equipment or affect people.
> - Anything that writes to field devices must stay a **human-confirmed** action, and should only be
>   exercised in a lab/test rig you fully control.
> - Use this to **learn** — read the architecture, study the security model, experiment in an
>   isolated sandbox. For real deployments, engage qualified controls, security, and compliance
>   professionals and validate everything independently.

## What this repo is

`openAut/main` is the **agent workbench and shared skill layer** for the openAut project.

It is meant to be used primarily from **OpenCode**, while remaining compatible with other coding
agents that support Agent Skills or can consume `SKILL.md` runbooks directly.

The repo gives agents the domain knowledge, workflows, reference scripts, architecture contracts,
and safety constraints needed to help build and operate the rest of openAut: the core framework,
role agents, security posture, edge integrations, lab environments, dashboards, documentation, and
future proof-of-concept deployments.

This is not the openAut product runtime. It is the project's **executable knowledge base**: a place
where agents can read, reason, generate, test, document, and evolve the surrounding repositories
without inventing the architecture from scratch.

The repository provides agent-agnostic **skills, runbooks, contracts, and reference scripts** that
let **OpenCode** — or another compatible coding agent — understand the openAut architecture and help
create the rest of the project safely.

These skills do **not** reimplement NemoClaw. NemoClaw already ships the bootstrap
(`curl … nemoclaw.sh | bash`), the Landlock + seccomp + netns sandbox, inference routing,
and lifecycle CLI. The skills here **orchestrate that documented CLI over SSH**. The openAut
architecture has two intended defaults; communication migration status is described below:

| Default | Choice | Why |
|---|---|---|
| **Communication protocol** | **Matrix — an open communication protocol** | Users choose a Matrix-compatible chat client, such as Element. A self-hosted Matrix server (homeserver) can handle messages and rooms within the organisation's own infrastructure. |
| **Inference** | **Remote NVIDIA Nemotron 3.5 Lightning 30B-A3B-NVFP4** on a separate machine, **egress-locked + TLS** | Keeps inference on a dedicated GPU system (e.g. ASUS Ascent GX10), reachable only from the sandbox over an encrypted, allow-listed link. |

### Communication via Matrix

**Matrix is the protocol**, the **chat client** is the user's application, and the **homeserver**
handles messages and rooms. Advisor is reached through Matrix rooms; Security observes authorised
operations rooms and sends alerts to a separate, access-restricted security room. Engineer is
accessed through OpenCode, not through Matrix. Clients and bots connect to the selected homeserver
over HTTPS using the Matrix Client-Server API. Federation and room access settings determine
whether messages can reach other homeservers.

**Migration status:** Matrix is the intended communication standard. The existing
[`config.env.example`](config.env.example), [`webhook bridge`](bridges/teams-webhook/README.md),
and linked skills and architecture documents still contain the earlier Teams integration and
`TEAMS_*` settings. These are legacy migration material, not a working Matrix integration.
The configuration, provisioning, sandbox policies, and runbooks still need to be migrated and
verified before the Matrix path can be treated as implemented. The skill summaries below describe
the intended Matrix architecture.

For inference, configure `NEMOTRON_*` in `config.env` using the existing configuration example.
Matrix connection settings must be documented with the integration; the current example does not
yet define them.

## First milestone: agent-led integration POC

The goal is for a user with limited AI knowledge to start with a documented 64 GB Windows
workstation, opencode, an attached LLM, and a startup prompt using a pinned project revision, then
build an integration lab with agent assistance. Local opencode performs user-led engineering work;
the two priority Ubuntu VMs host platform services and Advisor. The journey covers POC services,
a physical read-only integration, dashboards, and manuals in Forgejo that Advisor can use for
evidence-backed troubleshooting in a Matrix-compatible chat client.

See [Milestone 1 — Agent-led integration POC](docs/MILESTONE-1.md) for scope, delivery workstreams,
and acceptance criteria. This is a delivery target; the complete fresh-install journey is not yet
verified.

This proposed lab profile defers dedicated Engineer containment; its acceptance tests do not prove
the full production trust model. The [M1 implementation profile](docs/M1-IMPLEMENTATION-PROFILE.md)
sets out the candidate two-VM budget and staged delivery plan.

## Skills

**Agent tier — create the NemoClaw agents:**

| Skill | What it does |
|---|---|
| [`nemoclaw-provision`](skills/nemoclaw-provision/SKILL.md) | SSH preflight → run the NemoClaw installer → onboard a sandbox pointed at the **remote NVIDIA Nemotron 3.5 Lightning 30B-A3B-NVFP4** endpoint → connect Advisor via **Matrix** → verify. The Matrix connection step remains a migration target for this install runbook. |
| [`nemoclaw-sandbox-policy`](skills/nemoclaw-sandbox-policy/SKILL.md) | Manage the four sandbox layers after creation: **deny-by-default egress**, TLS verification, and a hardening review mapped to IEC 62443 / NIS2 / CRA. The Matrix migration target is an explicit allow-list for the selected homeserver + Nemotron host + local Forge, with room and action permissions enforced separately. |
| [`advisor-engineer-workflow`](skills/advisor-engineer-workflow/SKILL.md) | Define the openAut trust domains: **Advisor** is read-only and accessible via Matrix; **Engineer** has SSH/deploy capability through OpenCode and is not exposed to Matrix; **Security** is a separate read-only watch instance ([`security-instance`](skills/security-instance/SKILL.md)). Per ADR 0001 §5 and [ADR 0003](docs/adr/0003-engineer-runtime-containment.md), Advisor and Engineer run on **different software stacks** — Advisor on **NemoClaw**, Engineer on **OpenCode** — in separate runtime sandboxes on separate hosts. Actions move through approved cases in the Systemdatabas. |
| [`nemoclaw-agent-workflow`](skills/nemoclaw-agent-workflow/SKILL.md) | Define the three openAut **operator personas** (jobs-to-be-done) — **Driftstekniker**, **Energisamordnare**, **Förvaltare** — as NemoClaw agent workflows, communicating via Matrix using a compatible chat client, each granted only the runtime skills it needs. Personas are served chiefly by **Advisor** (read-only); writes/deploys go through **Engineer** via an approved case, while **Security** watches across both. A persona is not itself a trust domain. |

**Data backbone & edge — what the agents read from:**

| Skill | What it does |
|---|---|
| [`mqtt-tls-broker`](skills/mqtt-tls-broker/SKILL.md) | EMQX broker with a **mutual-TLS** listener, a per-edge-node **client-certificate PKI**, a CN-bound **ACL** topic schema, and TLS verification. The encrypted ingest backbone. |
| [`timeseries-stack`](skills/timeseries-stack/SKILL.md) | **TimescaleDB + PostgreSQL** — telemetry hypertable, system schema, MQTT→DB ingest, retention + continuous aggregates, and **least-privilege roles** (ingest write, agent read-only). |
| [`system-database`](skills/system-database/SKILL.md) | The richer **Systemdatabas** contract: equipment, points, protocol mappings, documents, cases, approvals, generated artifacts, and audit events. This is the handoff model between Advisor, Engineer, Security, dashboards, and Power BI. |
| [`edge-iot2050`](skills/edge-iot2050/SKILL.md) | Provision a **Siemens IOT2050** edge node: field-protocol poller → EMQX over mutual TLS with the node's cert, **store-and-forward** buffering, resilient systemd service. |
| [`engineer-integration`](skills/engineer-integration/SKILL.md) | The **manual → integration → edge deploy → documentation** workflow for Engineer: read a manufacturer manual, extract protocol/register details, deploy after approval, verify MQTT/TimescaleDB, and write generated docs back. |

**Local forge & documentation authority:**

| Skill | What it does |
|---|---|
| [`forge-stack`](skills/forge-stack/SKILL.md) | Provision local **Forgejo** in the AI/management zone: TLS, backups, runners, storage, agent access, and sandbox egress. |
| [`documentation-store`](skills/documentation-store/SKILL.md) | Define how manuals, runbooks, generated docs, point maps, and AI-readable source material live in Forge and link to `documents.uri` / `documents.sha256`. |
| [`manual-ingest`](skills/manual-ingest/SKILL.md) | Convert technical product manuals to traceable Markdown, assign stable product/document identities, validate source hashes, and generate the `openaut/manuals` catalog. |
| [`forge-governance`](skills/forge-governance/SKILL.md) | Define branch protection, PR review, CODEOWNERS, commit/artifact signing, CI gates, and scoped agent permissions. |

**Security instance — what watches the deployment:**

| Skill | What it does |
|---|---|
| [`security-instance`](skills/security-instance/SKILL.md) | Define the separate **openAut Security** instance: read-only SSH, listen-only observation of authorised Matrix operations rooms, passive MQTT/log monitoring, prompt/social-engineering detection, OT anomaly detection, alerts to a separate access-restricted Matrix room, and compliance reporting. Reading rooms requires membership, read permissions and, for encrypted rooms, the necessary decryption keys. |

**Runtime capabilities — what each agent persona carries:**

| Group | Skills |
|---|---|
| Field protocols | [`bacnet`](skills/bacnet/SKILL.md) · [`modbus`](skills/modbus/SKILL.md) · [`mbus`](skills/mbus/SKILL.md) · [`knx`](skills/knx/SKILL.md) · [`dali`](skills/dali/SKILL.md) · [`lorawan`](skills/lorawan/SKILL.md) |
| Analytics | [`fdd`](skills/fdd/SKILL.md) · [`energy-optimization`](skills/energy-optimization/SKILL.md) · [`anomaly-correlation`](skills/anomaly-correlation/SKILL.md) |
| Compliance | [`nis2`](skills/nis2/SKILL.md) · [`cra`](skills/cra/SKILL.md) · [`ai-act`](skills/ai-act/SKILL.md) · [`iso27001`](skills/iso27001/SKILL.md) · [`iec62443`](skills/iec62443/SKILL.md) |

The personas in [`nemoclaw-agent-workflow`](skills/nemoclaw-agent-workflow/SKILL.md) are each granted
a **least-privilege subset** of these (e.g. read-only protocols + analytics for the energy role).

The [`advisor-engineer-workflow`](skills/advisor-engineer-workflow/SKILL.md) maps the same
capabilities onto the openAut architecture's stricter **Advisor / Engineer / Security**
trust boundaries.

Supporting:

- [`CONTEXT.md`](CONTEXT.md) — the canonical glossary: **persona** vs. **agent / trust domain** vs. **runtime skill**.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — the full openAut four-layer diagram and where each skill fits.
- [`docs/LAB.md`](docs/LAB.md) — a local verification path for the MQTT/topic/database contracts.
- [`docs/EDGE-INTEGRATION-LIFECYCLE.md`](docs/EDGE-INTEGRATION-LIFECYCLE.md) — physical integration,
  identity migration, field health, offline runtime and evidence lessons from the isolated POC.
- [`docs/HYPERV-CI-BOUNDARY.md`](docs/HYPERV-CI-BOUNDARY.md) — host-enforced isolation for an
  untrusted Forgejo CI VM on Hyper-V management/NAT networks.
- [Matrix documentation](https://matrix.org/docs/) — the open communication protocol, clients, homeservers, and rooms.
- [`config.env.example`](config.env.example) — current configuration template; Matrix settings are pending migration as described above.

## Using these skills

**OpenCode** — place the skill folders in `.opencode/skills/` for a project, or in
`~/.config/opencode/skills/` for global use. OpenCode also supports compatible skill locations such
as `.claude/skills/` and `.agents/skills/`.

Each skill lives in its own directory with a `SKILL.md` file and optional supporting scripts,
references, and other resources. OpenCode automatically discovers available skills and exposes them
to the agent, which can load the relevant skill on demand through its native skill mechanism.

The `SKILL.md` files use YAML frontmatter for discovery metadata such as the skill name and
description. The skill bodies are plain Markdown and may reference self-contained shell or Python
scripts stored alongside the skill.

Because the openAut skills follow this portable directory-based structure, they can also be used by
other agents that support the Agent Skills convention or, where automatic discovery is unavailable,
by explicitly pointing the agent to the relevant `SKILL.md`.

## Scope

This repository contains the openAut skill layer: reusable knowledge, workflows, guardrails, and
technical capabilities that AI agents can load when working with an openAut deployment.

The skill set covers three main areas:

- **Agent and infrastructure workflows** — provisioning, sandbox policy, deployment, diagnostics,
  documentation, and role-specific workflows.
- **Data backbone and edge infrastructure** — MQTT/TLS, TimescaleDB/PostgreSQL, edge devices such as
  the IOT2050, and the surrounding data flow.
- **Runtime and engineering capabilities** — field protocols, analytics, automation engineering,
  documentation, and compliance references used by agents working with building automation systems.

Protocol and analytics skills are designed to be vendor- and site-agnostic. They provide guidance,
workflows, reference material, and reusable scripts, but live behaviour must still be validated
against the actual hardware, network, control system, and data backbone of a deployment.

In the openAut architecture, this repository sits upstream of much of the implementation work. It
provides agents with shared technical context and operating rules before they generate code,
documentation, deployment configurations, integrations, or new repositories.

The repository is therefore not the openAut application itself. Dashboards, APIs, integrations,
control applications, and other deployed services belong to their respective implementation
repositories. These skills help agents build, operate, diagnose, and extend those systems.

## Source references

- OpenCode skills: <https://opencode.ai/docs/skills>
- OpenCode: <https://opencode.ai/>
- NemoClaw docs: <https://docs.nvidia.com/nemoclaw/user-guide/openclaw/home>
- OpenClaw docs: <https://docs.openclaw.ai/>
- Agent Skills specification: <https://agentskills.io/>
