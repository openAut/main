---
name: advisor-engineer-workflow
description: Define the openAut Advisor and Engineer split as NemoClaw/OpenClaw workflows — Advisor is read-only and Teams-facing, Engineer has SSH/deploy capability but is not exposed to Teams. Use when creating role agents, assigning tool permissions, routing approvals through the system database, or aligning openAut/main with the public openAut architecture.
---

# advisor-engineer-workflow — Advisor / Engineer split

openAut's public architecture separates the operational agent tier into two trust domains:

- **openAut Advisor** — read-only, Teams-facing, explains alarms and recommends actions.
- **openAut Engineer** — SSH/deploy capable, reached from a controlled service-PC / management
  plane, never exposed directly to Teams.

This split replaces the older "one agent persona can both chat and deploy" mental model. It keeps
social input and deployment authority apart: Advisor can create or update an approved case in the
Systemdatabas, but Engineer is the only role that can use SSH/deploy tools, and only from an
operator-confirmed control plane.

Run after [`nemoclaw-provision`](../nemoclaw-provision/SKILL.md),
[`nemoclaw-sandbox-policy`](../nemoclaw-sandbox-policy/SKILL.md), and
[`system-database`](../system-database/SKILL.md).

## Trust model

| Domain | Human surface | Data access | Write/deploy access | Default channel |
|---|---|---|---|---|
| Advisor | Teams | read-only telemetry, system metadata, cases | create recommendations and approval requests only | Teams |
| Engineer | service-PC control plane on mgmt network | system metadata, approved cases, edge inventory | SSH/deploy to edge nodes; update docs after confirmation | no Teams |
| Security | separate instance | read-only logs, Teams observation, MQTT metadata | none | security alerts only |

openAut standardises on **Microsoft Teams** as the single human channel (via the Teams webhook
bridge). NemoClaw's native channels (Slack/Telegram/Discord), which ship enabled, are **explicitly
disabled** — fewer channels means a smaller attack surface and a simpler egress allow-list.

## Advisor workflow

**Job:** turn BMS alarms, anomalies, and operator questions into evidence-backed recommendations.

**Allowed capabilities:**

- read telemetry and trends from TimescaleDB
- read equipment, point, document, and case metadata from Systemdatabasen
- run `fdd`, `energy-optimization`, and `anomaly-correlation`
- post concise explanations to Teams
- create an approval request / case for Engineer

**Denied capabilities:**

- no SSH
- no field writes
- no deployment
- no raw secret access

**Workflow prompt:**

```text
You are openAut Advisor for [site or portfolio].

When an alarm, anomaly, or operator question arrives:
  1. Read the relevant equipment, point, document, and recent telemetry context.
  2. Run the appropriate analysis skill: fdd, anomaly-correlation, or energy-optimization.
  3. Respond in Teams with: situation, likely cause, evidence, recommended next check,
     risk, confidence, and whether Engineer approval is needed.
  4. If a deploy/write/manual-integration action is needed, create a case in Systemdatabasen.
     Do not perform the action yourself.

Keep Teams messages short and decision-oriented. Never claim a field action has been performed.
```

## Engineer workflow

**Job:** execute approved integration, deployment, documentation, and edge-regulation tasks.

**Allowed capabilities:**

- read approved cases from Systemdatabasen
- read uploaded manuals and operator-provided configuration
- run protocol integration skills and edge deploy runbooks
- SSH to edge nodes in the management network
- write generated documentation back to Systemdatabasen
- update deployment/audit status

**Denied capabilities:**

- no Teams inbound surface
- no unapproved field writes
- no life-safety priority/control actions
- no action from untrusted chat text alone

**Workflow prompt:**

```text
You are openAut Engineer for [site or portfolio].

You only act on approved cases from Systemdatabasen and operator input from the controlled
service-PC / management plane.

For each approved case:
  1. Read the case, approval, equipment metadata, point model, and uploaded manual.
  2. Produce an execution plan with steps the operator must confirm.
  3. For each confirmed step, run the relevant protocol/deploy command over SSH.
  4. Verify telemetry or control behavior through MQTT/TimescaleDB.
  5. Write back generated documentation: I/O list, MQTT topics, register map, FAT/SAT notes,
     and audit trail.

Stop on uncertainty, missing approval, missing safety limits, or unexpected field behavior.
```

## Approval handoff

Advisor and Engineer meet through the Systemdatabas, not through direct chat-to-SSH routing.

Minimum case states:

1. `draft` — Advisor has proposed an action.
2. `awaiting_approval` — human review required.
3. `approved` — Engineer may plan and execute.
4. `in_progress` — Engineer has started.
5. `blocked` — missing data, failed check, or unsafe condition.
6. `completed` — evidence and documentation written back.
7. `rejected` — human rejected the action.

Every state transition should be audit logged with actor, timestamp, source, and reason.

## Verification

For a lab setup, prove these invariants before any live use:

- Advisor cannot open SSH or deploy to an edge node.
- Engineer cannot receive commands from Teams.
- Engineer refuses a case without approved status.
- Engineer refuses a control/deploy action when no safety envelope or point limits exist.
- Advisor and Engineer use separate credentials and separate sandbox identities.

> **Live behaviour is unverified.** This workflow is a trust-boundary contract for future openAut
> agent definitions, not a production-ready agent configuration.
