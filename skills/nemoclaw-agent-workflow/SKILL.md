---
name: nemoclaw-agent-workflow
description: Define the three openAut operator personas as NemoClaw agent workflows — Driftstekniker (operations technician), Energisamordnare (energy coordinator), and Förvaltare (technical manager) — each defaulting to Microsoft Teams and granted only the runtime skills it needs. These personas are jobs-to-be-done, not trust domains; the Advisor / Engineer / Security trust boundaries they run inside are defined in advisor-engineer-workflow. Use when creating openAut operator personas, writing NemoClaw agent workflow prompts, assigning per-agent tool permissions, or wiring a persona's output to a Teams channel.
metadata:
  openaut-permissions: '{"knowledge_only":true,"exec":"none","network":"none","delegated_capabilities":"agent-role design; the agents.entries/skills-allowlist config and cron jobs are operator/Engineer-executed, not performed by this skill"}'
---

# nemoclaw-agent-workflow — the openAut operator personas

NemoClaw agent setup is three steps: **(1) configure the security policy, (2) run the agent workflow
prompt, (3) personalise it.** Step 1 is [`nemoclaw-sandbox-policy`](../nemoclaw-sandbox-policy/SKILL.md).
This skill is steps 2–3 for the three openAut personas, each defaulting to **Microsoft Teams** as its
channel and each scoped to a least-privilege set of runtime skills.

These three personas describe **jobs to be done** — *who* needs which insight. They are **not**
trust domains and not "role agents". The trust boundaries they must run inside — read-only
**Advisor** vs. SSH/deploy **Engineer** vs. watch-only **Security**, with approvals through the
Systemdatabas — are defined in [`advisor-engineer-workflow`](../advisor-engineer-workflow/SKILL.md).
The canonical definitions of persona vs. trust domain vs. runtime skill live in
[`CONTEXT.md`](../../CONTEXT.md).

## Persona × trust domain

Every persona is served chiefly by **Advisor** (read-only). Only the Driftstekniker has a writing
path, and it never goes chat→SSH directly — it passes through **Engineer** via an approved case.
No persona is its own trust domain.

| Persona | Realised through | Autorun (read / recommend) | Human-reviewed (write / deploy) |
|---|---|---|---|
| Driftstekniker | Advisor (+ Engineer via case) | read points, fdd / anomaly-correlation, recommend override | bacnet priority-8 override, deploy → Systemdatabas case |
| Energisamordnare | Advisor | weekly report, energy-optimization, anomaly-correlation | — (read-only) |
| Förvaltare | Advisor (+ dashboard) | status view, fdd forecast, notify on decision | — (read-only) |

Run after [`nemoclaw-provision`](../nemoclaw-provision/SKILL.md) and `nemoclaw-sandbox-policy`.
Assumes `config.env` is sourced.

## Channel default: Teams

Every persona below addresses the user through OpenClaw's **native `msteams` channel plugin**
(Bot Framework / Azure Bot), not Telegram/Slack and not the retired webhook bridge — see
[`bridges/teams-webhook`](../../bridges/teams-webhook/README.md) for why. "Send to Teams" in a
workflow means: the agent's reply is delivered through its `msteams` channel binding (see
[Creating an agent](#creating-an-agent) below). Note the msteams plugin needs an **inbound** path
from Teams' cloud, which is a still-open design question — see
[`nemoclaw-sandbox-policy`](../nemoclaw-sandbox-policy/SKILL.md).

## Runtime skills the agents draw on

These are separate capability skills the agents *carry* (not part of this pack). Grant each persona
only what its job needs:

- `bacnet`, `modbus` — read field/HVAC data (writes/overrides are an **Engineer** capability run via an approved Systemdatabas case, never a persona tool)
- `fdd` — fault detection & diagnosis
- `energy-optimization`, `anomaly-correlation` — analytics
- compliance reference: `nis2`, `cra`, `ai-act`

## Persona 1 — Driftstekniker (Operations Technician)

**Job:** correlate alarms, find the root cause, push it to the on-call technician in Teams.

**Tools granted (read-only):** `bacnet` (read), `modbus` (read), `fdd`, `anomaly-correlation`.
**No** write/override tools — the priority-8 BACnet override is an **Engineer** capability, requested
via an approved Systemdatabas case (see [`advisor-engineer-workflow`](../advisor-engineer-workflow/SKILL.md)).
**No** energy-report tools.

**Workflow prompt (personalise the bracketed parts):**

```
You are openAut Advisor, serving the Driftstekniker persona, for [site name].
When an alarm arrives on [MQTT topic / EMQX subscription]:
  1. Pull the related points via bacnet/modbus around the alarm time window.
  2. Run fdd + anomaly-correlation to rank likely root causes.
  3. Post to Teams: the alarm, the single most likely root cause, the evidence
     (which points moved), and one concrete recommended action.
  4. If a control override is warranted (e.g. a priority-8 BACnet write), do NOT apply it and do
     not hold a write tool. Create an approval request / case in Systemdatabasen for Engineer to
     execute after explicit human approval. Recommend; never write.
Keep messages short and action-first. One alarm = one Teams message thread.
```

**Guardrails:** this persona is read-only; field writes happen only through **Engineer** after an
approved case, never directly from the Teams-facing persona; never touch life-safety priorities (1–4).

## Persona 2 — Energisamordnare (Energy Coordinator)

**Job:** automated weekly energy reports and anomaly analyses, delivered to Teams.

**Tools granted:** `modbus`/`bacnet` (**read-only**), `energy-optimization`, `anomaly-correlation`,
timeseries read access (TimescaleDB). **No** write/override tools.

**Workflow prompt:**

```
You are openAut Advisor, serving the Energisamordnare persona, for [site name].
On a weekly schedule [cron]:
  1. Query the last 7 days of energy/consumption series from TimescaleDB.
  2. Compare against the trailing baseline; flag anomalies and likely drivers
     via energy-optimization + anomaly-correlation.
  3. Post a weekly Teams summary: total consumption, week-over-week delta, the
     top 3 anomalies with probable cause, and recommended optimisations.
Read-only: you never write to field devices.
```

**Schedule:** `openclaw cron create --agent advisor-energisamordnare --schedule "0 7 * * 1" ...` — see
[Creating an agent](#creating-an-agent) below for the full command.

## Persona 3 — Förvaltare (Technical Manager)

**Job:** facility status overview and maintenance forecasts, primarily via a web dashboard, with
Teams notifications for items needing a decision.

**Tools granted:** timeseries read, `fdd` (forecast/trend mode), dashboard/report generation.
**Read-only** on field systems.

**Workflow prompt:**

```
You are openAut Advisor, serving the Förvaltare persona, for [portfolio/site].
  1. Maintain a facility-status view (equipment health, open faults, trends) for
     the web dashboard.
  2. Produce maintenance forecasts from fdd trend analysis.
  3. Notify Teams only when something needs a manager decision (budget, downtime,
     a forecast crossing a threshold) — not routine status.
Be concise and decision-oriented; route detail to the dashboard, decisions to Teams.
```

## Creating an agent

**These are not new trust domains.** Per [`CONTEXT.md`](../../CONTEXT.md)'s persona vs. trust-domain
glossary, a persona is *realised through* a trust domain — chiefly **Advisor** — and "is not itself
an agent or a trust domain." All three personas share Advisor's exact tool grant (`read`, `message`
only, everything else denied — see [`deploy/advisor-agent`](../../deploy/advisor-agent/README.md))
and none holds field-write authority; only their skill allowlist and channel binding differ.

OpenClaw's multi-agent config (see `docs.openclaw.ai/tools/multi-agent-sandbox-tools` and
`docs.openclaw.ai/tools/skills`) requires a separate `agents.entries.<id>` per distinct skill
allowlist / channel binding, so each persona still needs its own entry technically — but the ids
below are prefixed `advisor-` and the identical tool grant is repeated verbatim rather than varied,
specifically so nothing here reads as three independent agents. If your OpenClaw version supports
selecting a skill set per-binding on a single agent entry, prefer that over three entries — it
removes the ambiguity entirely.

The `bindings.match` blocks below must resolve to **disjoint** Teams scopes — OpenClaw needs some
way to tell which persona a given incoming message is for. Three entries all matching
`accountId: "*", peer: { kind: "*" }` (as an earlier draft of this file had) is not routable
config: nothing distinguishes them, so at best the first-registered binding wins and the other two
never fire, at worst it's rejected as a conflict. Route each persona to its **own Teams channel**
instead — one bot install per role-specific channel, or filed under a single Teams app bound to
distinct channel IDs — and treat the exact `bindings.match` shape (`peer.id` vs. a separate
`channelId` field, etc.) as unverified until checked against a live OpenClaw + Teams install:

```json5
{
  agents: {
    entries: {
      "advisor-driftstekniker": {
        workspace: "~/.openclaw/workspace-driftstekniker",
        tools: { allow: ["read", "message"], deny: ["exec", "write", "edit", "apply_patch", "process", "browser"] },
        skills: ["advisor-engineer-workflow", "bacnet", "modbus", "fdd", "anomaly-correlation"],
      },
      "advisor-energisamordnare": {
        workspace: "~/.openclaw/workspace-energisamordnare",
        tools: { allow: ["read", "message"], deny: ["exec", "write", "edit", "apply_patch", "process", "browser"] },
        skills: ["advisor-engineer-workflow", "modbus", "bacnet", "energy-optimization", "anomaly-correlation"],
      },
      "advisor-forvaltare": {
        workspace: "~/.openclaw/workspace-forvaltare",
        tools: { allow: ["read", "message"], deny: ["exec", "write", "edit", "apply_patch", "process", "browser"] },
        skills: ["advisor-engineer-workflow", "fdd"],
      },
    },
  },
  bindings: [
    // Each peer.id below must be that persona's own Teams channel ID for this deployment — three
    // identical wildcards is broken config, not a placeholder to copy verbatim.
    { agentId: "advisor-driftstekniker", match: { channel: "msteams", accountId: "*", peer: { kind: "channel", id: "${DRIFTSTEKNIKER_TEAMS_CHANNEL_ID}" } } },
    { agentId: "advisor-energisamordnare", match: { channel: "msteams", accountId: "*", peer: { kind: "channel", id: "${ENERGISAMORDNARE_TEAMS_CHANNEL_ID}" } } },
    { agentId: "advisor-forvaltare", match: { channel: "msteams", accountId: "*", peer: { kind: "channel", id: "${FORVALTARE_TEAMS_CHANNEL_ID}" } } },
  ],
}
```

Put each persona's workflow prompt into that workspace's `AGENTS.md` (loaded every turn — see
[`advisor-engineer-workflow`](../advisor-engineer-workflow/SKILL.md) for why AGENTS.md, not just
this skill, is the right home for day-to-day operating instructions). The `skills` allowlist above
enforces the "runtime skills the agents draw on" table earlier in this document — a non-empty
`skills` list *replaces* the default, it does not merge with it, so listing exactly the granted
skills is what keeps each persona least-privilege.

**Energisamordnare and Förvaltare's schedules use OpenClaw's real cron CLI**, not a placeholder:

```bash
openclaw cron create \
  --name "energisamordnare-weekly-report" \
  --agent advisor-energisamordnare \
  --schedule "0 7 * * 1" \
  --message "Run the weekly energy report workflow and post it to Teams." \
  --announce
```

```bash
openclaw cron create \
  --name "forvaltare-forecast-check" \
  --agent advisor-forvaltare \
  --schedule "0 6 * * *" \
  --message "Update the facility-status view and flag anything crossing a decision threshold." \
  --announce
```

`--announce` delivers the run's final reply to the agent's bound Teams channel; see
`docs.openclaw.ai/automation/cron-jobs` for retry, timeout, and delivery options.

> **What's confirmed vs. still to verify:** the `agents.entries`/`bindings`/`skills`-allowlist shape
> and the `openclaw cron create` flags are confirmed against OpenClaw's documentation as of this
> writing, and the channel is confirmed to be the native `msteams` plugin (the earlier
> webhook-bridge premise was wrong — see `bridges/teams-webhook`). Still open: the msteams **inbound**
> path (direct exposure vs. DMZ relay) is deliberately unresolved — see `nemoclaw-sandbox-policy` —
> and the exact `bindings.match` shape for msteams accounts/scopes should be checked against a live
> Teams app installation before copying the block above verbatim.

## Verify

For each persona: send a representative trigger (a test alarm / a manual weekly run / a threshold
crossing) and confirm the message arrives in the correct Teams channel with the right shape, and
that a direct write attempt by any persona is refused (field writes belong to Engineer via an approved case).

> **Live behaviour is unverified until a NemoClaw host and the openAut data backbone (EMQX,
> TimescaleDB) are connected.** The personas, tool grants, and guardrails are the durable part.
