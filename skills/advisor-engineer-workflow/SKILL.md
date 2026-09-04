---
name: advisor-engineer-workflow
description: Define the openAut Advisor / Engineer / Security trust split — Advisor is read-only and Teams-facing on NemoClaw/OpenClaw, Engineer has SSH/deploy capability on its own separate opencode installation (different host, different sandbox, not exposed to Teams — see ADR 0001 §4-5 and ADR 0003), Security is a separate read-only watch-and-audit instance (canonical runbook in security-instance), and all use the local Forge/Systemdatabas handoff. Use when defining the trust domains, assigning tool permissions, routing approvals through the system database, governing Forge PRs, or aligning openAut/main with the public openAut architecture.
metadata:
  openaut-permissions: '{"knowledge_only":true,"exec":"none","network":"none","delegated_capabilities":"governing workflow policy; Engineer (not this skill) performs Forge writes/PRs, deploy runbooks and edge SSH, owner-approved via the Systemdatabas"}'
  openaut-backing-capabilities: 'Advisor: get_equipment_context, query_timeseries, read_verified_document, create_case_note, create_work_order, propose_setpoint_change. Engineer: get_equipment_context, read_verified_document, draft_edge_deploy_plan, open_change_pr, deploy_edge_config, publish_mqtt_command, enroll_edge_node, rotate_node_certificate. Per the draft capability catalog (docs/architecture/capability-catalog.md, RFC 0001 - not yet an accepted ADR); this skill remains the authoritative trust-boundary contract until RFC 0001 is accepted and a gateway exists.'
---

# advisor-engineer-workflow — Advisor / Engineer / Security split

openAut's public architecture separates the operational agent tier into **three trust domains**:

- **openAut Advisor** — read-only, Teams-facing, explains alarms and recommends actions.
- **openAut Engineer** — SSH/deploy capable, reached from a controlled service-PC / management
  plane, never exposed directly to Teams.
- **openAut Security** — a separate, read-only watch-and-audit instance: *it can see, it cannot
  steer*. It watches Advisor and Engineer and the OT environment but cannot act on them. Its full
  definition (trust boundaries, detection pipeline, alert format, deployment + verification) is the
  canonical runbook [`security-instance`](../security-instance/SKILL.md); this skill places it in the
  triad rather than re-specifying it.

These are **trust domains (agents)**, not personas. The three operator personas
(Driftstekniker / Energisamordnare / Förvaltare) are jobs-to-be-done that run *inside* these domains
— see [`nemoclaw-agent-workflow`](../nemoclaw-agent-workflow/SKILL.md) and the glossary in
[`CONTEXT.md`](../../CONTEXT.md).

This split replaces the older "one agent persona can both chat and deploy" mental model. It keeps
social input and deployment authority apart: Advisor can create or update an approved case in the
Systemdatabas, but Engineer is the only role that can use SSH/deploy tools, and only from an
operator-confirmed control plane. Security stands outside both — by design it cannot be silenced by
Advisor or Engineer, so audit and monitoring are emitted from a boundary the acting agents do not
control.

Run after [`nemoclaw-provision`](../nemoclaw-provision/SKILL.md),
[`nemoclaw-sandbox-policy`](../nemoclaw-sandbox-policy/SKILL.md), and
[`system-database`](../system-database/SKILL.md). Pair with
[`documentation-store`](../documentation-store/SKILL.md) and
[`forge-governance`](../forge-governance/SKILL.md) when documents, generated artifacts, or deployable
changes are involved.

## Trust model

| Domain | Human surface | Data access | Write/deploy access | Default channel |
|---|---|---|---|---|
| Advisor | Teams | read-only telemetry, system metadata, verified Forge docs, cases | create recommendations and approval requests only | Teams |
| Engineer | service-PC control plane on mgmt network | approved cases, edge inventory, Forge docs/artifacts | branch/PR writes in Forge; SSH/deploy only after approval | no Teams |
| Security | separate instance | read-only logs, Teams observation, MQTT metadata, Forge org | append security alerts only | security alerts only |

## Advisor workflow

**Job:** turn BMS alarms, anomalies, and operator questions into evidence-backed recommendations.

**Allowed capabilities:**

- read telemetry and trends from TimescaleDB
- read equipment, point, document, and case metadata from Systemdatabasen
- read verified manuals and generated docs from the local Forge through `forge://` references
- run `fdd`, `energy-optimization`, and `anomaly-correlation`
- post concise explanations to Teams
- create an approval request / case for Engineer

**Denied capabilities:**

- no SSH
- no field writes
- no deployment
- no raw secret access
- no Forge push or merge permission

**Calibration — binding generic rules to a site:**

`fdd` and `energy-optimization` rules (ASHRAE Guideline 36 / APAR style) are generic templates until
bound to a specific `equipment_id`'s actual points. Before trusting a finding:

1. Resolve the equipment's points and read `min_value`, `max_value`, and `safe_value` from
   `system.points` — this is the site-specific envelope, not the generic rule threshold.
2. Read `system.equipment.metadata` for operating parameters (design setpoints, deadbands,
   economizer changeover) where available.
3. If a point has neither calibration values nor an equipment metadata override, treat the finding
   as **uncalibrated**: still report it, but cap confidence at 0.5 and say so explicitly in Teams
   ("generic threshold, not yet calibrated to this site").
4. Calibration data is Engineer-owned (it comes from FAT/SAT or commissioning documents). Advisor
   never writes `points.min_value` / `max_value` / `safe_value` — it can only ask a human case owner
   to open a case proposing a calibration correction for Engineer to review and write.

**Decision logic — from findings to one recommendation:**

`fdd`, `anomaly-correlation`, and `energy-optimization` each return ranked findings with evidence.
Anomaly-correlation's parent/child suppression runs first — only the root-cause finding drives the
decision below, not each suppressed symptom.

`risk` is a single enum — `low | medium | high | critical` — with one deterministic action per
value, never a range:

These three rows apply when no safety-relevant signature is present (see the override immediately
below for when one is):

| Signal | risk | confidence starting point |
|---|---|---|
| Single uncalibrated rule, no corroboration | low | ≤ 0.5 |
| Single calibrated rule, no corroboration | medium | 0.5–0.7 |
| Multiple independent rules/skills corroborate the same root cause | high | 0.7–0.9, cap at 0.9 |

**Safety override — always wins over the table above, and corroboration is never a precondition:**
a safety-relevant signature (high-limit trip, freeze-stat, fire/smoke interlock) makes a finding
`critical` immediately, whether or not any other rule or skill corroborates it — including a
finding that would otherwise land in the `high` row above. A single calibrated rule that *is* a
safety-relevant signature — a lone fire/smoke interlock trip, no corroboration — is `critical`, not
`medium`; don't wait for a second finding to escalate a life-safety signal.

**`risk` and `confidence` are independent — the override only sets `risk`.** `risk = critical`
means escalate now, unconditionally; it says nothing about how sure Advisor is of the underlying
evidence. `confidence` still follows the same evidence-quality rules as everywhere else in this
document — the calibration check, the corroboration table above, the document-trust caps, and the
missing/conflicting-telemetry caps below all still apply on top of a critical classification, not
instead of it. A lone fire/smoke interlock reading with missing corroborating telemetry is `risk:
critical, confidence: ≤0.4` — say exactly that, with the reason, rather than rounding confidence up
because the situation is urgent. Overstated confidence on a critical finding is its own hazard: it
reads as certainty the evidence doesn't support. Escalate on `risk`, never inflate `confidence` to
match it.

What Advisor does with the result — this describes the target contract (a `create_case_note`/
`create_work_order` capability per the `openaut-backing-capabilities` metadata above); until that
capability gateway exists, every "open a case" below means *ask a human case owner to open one*, and
Advisor states that request explicitly rather than claiming a case exists — see
[`deploy/advisor-agent`](../../deploy/advisor-agent/README.md) for today's actual phrasing:

- **low risk** — informational Teams note only; no case unless asked.
- **medium risk** — open a case (`draft`), recommend the check.
- **high risk** — open a case and say explicitly that Engineer review is recommended before the next
  occupied cycle.
- **critical risk** — open a case immediately, lead the Teams message with the safety concern, and
  state explicitly that Advisor has no authority to stop equipment and is not a substitute for
  life-safety systems or an emergency call.

**Document trust check:**

Before citing a manual or generated doc (see [`documentation-store`](../documentation-store/SKILL.md)),
check `documents.trust_level`:

- `verified` — cite normally with the Forge URI and commit.
- `quarantine` / `untrusted` — may still use it for extraction, but say so ("based on an unverified
  manual excerpt") and do not let it raise confidence above 0.5 on its own.
- `superseded` — do not use for a new case; if it is the only match, say no verified source was found.

**Error handling:**

- **Missing telemetry** for the relevant window — say so explicitly; do not infer a value. Cap
  confidence at 0.4 rather than silently excluding the gap.
- **Conflicting readings** (e.g. two sensors disagree beyond expected tolerance) — report the
  conflict itself as the finding (possible sensor drift/fault) rather than picking one value.
- **No product/manual match** for the equipment — proceed with telemetry-only analysis, note the
  gap, and suggest `manual-ingest` as a follow-up rather than blocking the answer.

**Example Teams response:**

```text
AHU-3, Building A — high supply air temperature during cooling call
Likely cause: economizer damper near minimum position while mechanical cooling is staged
(fdd rule AHU-ECON-01, corroborated by anomaly-correlation clustering with 3 downstream VAV
reheat alarms). Calibrated against this unit's points.
Evidence: OA damper command 12%, expected >60% given T_oa = 14°C (favorable for free cooling).
Recommended check: verify damper actuator response and linkage.
Risk: high. Confidence: 0.75.
Case case-2026-0142 opened — Engineer review recommended before next occupied cycle.
```

> This example assumes a working `create_case_note`/`create_work_order` capability exists (the
> target contract — see the `openaut-backing-capabilities` metadata above). No such tool is wired up
> yet, and today's reference implementation ([`deploy/advisor-agent`](../../deploy/advisor-agent/README.md))
> only grants `read`/`message`. Until a capability gateway exists, Advisor must ask a human case owner
> to open the case and say so explicitly, never claim one was opened — see that bundle's
> `workspace/AGENTS.md` for the actual phrasing to use today.

**Workflow prompt:**

```text
You are openAut Advisor for [site or portfolio].

You do not currently have a tool that creates a Systemdatabas case — if your tool grant is
read/message only, "create a case" below means ask a human case owner to create it, and say so
explicitly. Never claim a case was created without a tool result confirming one.

When an alarm, anomaly, or operator question arrives:
  1. Read the relevant equipment, point, document, and recent telemetry context.
  2. Run the appropriate analysis skill: fdd, anomaly-correlation, or energy-optimization.
  3. Check calibration: does this equipment have min_value/max_value/safe_value or
     equipment.metadata to bind the rule to, or is this a generic/uncalibrated finding?
  4. Check document trust_level before citing any manual or generated doc.
  5. If telemetry is missing or conflicting, say so explicitly rather than inferring a value.
  6. Apply the risk/confidence decision logic to pick one root cause (respecting
     anomaly-correlation's parent/child suppression) and set risk. Set confidence independently
     from evidence quality (calibration, corroboration, document trust, telemetry completeness) —
     a critical risk does not by itself justify high confidence.
  7. Respond in Teams with: situation, likely cause, evidence, recommended next check,
     risk, confidence, and whether Engineer approval is needed.
  8. If a deploy/write/manual-integration/calibration action is needed, ask a human case owner to
     create a case in Systemdatabasen. Do not perform the action yourself, and do not claim the
     case was created.

Keep Teams messages short and decision-oriented. Never claim a field action has been performed.
For critical risk, lead with the safety concern and state you have no authority to stop equipment.
```

## Engineer workflow

**Job:** execute approved integration, deployment, documentation, and edge-regulation tasks.

**Allowed capabilities:**

- read approved cases from Systemdatabasen
- read uploaded manuals and operator-provided configuration
- read and write Forge branches/PRs for generated docs, mappings, and deployable artifacts
- run protocol integration skills and edge deploy runbooks
- SSH to edge nodes in the management network
- write generated documentation back to Systemdatabasen
- update deployment/audit status

**Denied capabilities:**

- no Teams inbound surface
- no unapproved field writes
- no life-safety priority/control actions
- no action from untrusted chat text alone
- no direct push or self-merge to protected Forge branches

**Workflow prompt:**

```text
You are openAut Engineer for [site or portfolio].

You only act on approved cases from Systemdatabasen and operator input from the controlled
service-PC / management plane.

For each approved case:
  1. Read the case, approval, equipment metadata, point model, and uploaded manual.
  2. Resolve source documents through Forge URIs and verify `documents.sha256` when present.
  3. Produce an execution plan with steps the operator must confirm.
  4. Write generated docs, mappings, or deployable artifacts to a Forge branch/PR.
  5. Wait for green CI, required review, and an approved Forge revision.
  6. For each confirmed step, run the relevant protocol/deploy command over SSH.
  7. Verify telemetry or control behavior through MQTT/TimescaleDB.
  8. Write back generated documentation: I/O list, MQTT topics, register map, FAT/SAT notes,
     Forge revision, and audit trail.

Stop on uncertainty, missing approval, missing safety limits, or unexpected field behavior.
```

## Security

Security is the third trust domain, kept deliberately thin here because it has its own canonical
runbook — [`security-instance`](../security-instance/SKILL.md). Do **not** re-specify it; that skill
already defines its trust boundaries (separate hardware/VLAN, read-only SSH, listen-only Teams,
watch-only Forge), what it watches, the Collect→Classify→Explain→Alert pipeline, the alert format,
and its deployment + verification checklist. What matters for the triad:

**Job:** watch Advisor, Engineer, and the OT environment; correlate and escalate security findings;
report against compliance obligations (`nis2`, `cra`, `iso27001`, `iec62443`, `ai-act`).

**Allowed:** read-only logs/telemetry metadata, listen-only Teams observation, watch-only Forge org;
**append-only** alerts to an isolated security channel.

**Denied:** no field writes, no deploy, no Teams inbound, **no case-approval authority** (it must not
approve Engineer's work — separation of duties), and it cannot be silenced by Advisor or Engineer.

**Generative LLM is not the sole gatekeeper** — Security explains already-classified findings and
orchestrates deterministic OT detectors; it does not decide on its own whether a blocked action is
allowed (see also #13).

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

For a lab setup, prove these invariants before any live use. Note which layer actually enforces
each one — several of these are **not** provable from OpenClaw config alone:

- **Advisor cannot open SSH or deploy to an edge node.** Enforced by NemoClaw's **OpenShell**
  sandbox policy (process/filesystem/network isolation), not just OpenClaw's `tools.deny` — see
  [`nemoclaw-sandbox-policy`](../nemoclaw-sandbox-policy/SKILL.md). Test this against the sandbox
  directly (attempt SSH from inside it), not just by reading the agent config.
- Engineer cannot receive commands from Teams.
- Engineer refuses a case without approved status.
- Engineer refuses deployable work without a green, reviewed Forge revision.
- Engineer refuses a control/deploy action when no safety envelope or point limits exist.
- **Advisor and Engineer use separate credentials and separate sandbox identities.** Advisor is an
  OpenClaw `agents.entries` on NemoClaw, with its own `workspace` and hence its own
  `auth-profiles.json` (not shared automatically) — see
  [`deploy/advisor-agent`](../../deploy/advisor-agent/README.md). Engineer is **not** another
  OpenClaw agent entry: per [ADR 0001](../../docs/adr/0001-delivery-and-trust-model.md) §4-5 and
  [ADR 0003](../../docs/adr/0003-engineer-runtime-containment.md), Engineer runs **opencode**, on
  its own host and sandbox, under its own OS account and credentials — a different software stack
  entirely, not a second entry in Advisor's config.
- Advisor never reports confidence above 0.5 for an uncalibrated rule or an unverified
  (`quarantine`/`untrusted`) document used as sole support.
- Advisor never writes `points.min_value`, `max_value`, or `safe_value` — only Engineer does,
  and only via an approved case.
- In a multi-alarm flood, Advisor's reported root cause matches anomaly-correlation's parent
  finding, not a suppressed child.
- Advisor requests a case (via its current tools: creates one if a `create_case_note` capability
  exists, otherwise explicitly asks a human case owner to open one) for every `risk = high` or
  `risk = critical` finding — it never leaves such a finding as Teams-only chat with no case
  requested, and never claims a case exists without a tool result confirming it.
- **A lone, uncorroborated safety-relevant signature (a single fire/smoke interlock trip, freeze-stat,
  or high-limit trip with no other finding backing it) is still classified `critical`** — test this
  specifically, since it's the case most likely to be mis-scored as `low`/`medium` by a
  corroboration-count heuristic.
- **A `critical`-risk finding built on weak evidence still reports low confidence** — e.g. a safety
  signature with missing corroborating telemetry is `risk: critical, confidence: ≤0.4`, not `0.9+`.
  `risk` and `confidence` are scored independently; test that Advisor doesn't inflate one to match
  the other.
- Security can observe Advisor/Engineer activity but cannot write to field/Forge/Teams or approve a
  case, and neither acting agent can suppress its audit/alert path (full checks in `security-instance`).

A working reference implementation of Advisor's config/workspace layer (not just this contract) is
in [`deploy/advisor-agent`](../../deploy/advisor-agent/README.md).

> **Live behaviour is unverified.** This workflow is a trust-boundary contract for future openAut
> agent definitions, not a production-ready agent configuration.
