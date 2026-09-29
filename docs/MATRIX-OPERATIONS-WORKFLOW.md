# Matrix operations and troubleshooting cases

Matrix is openAut's intended communication protocol; Element is one possible client and a
homeserver stores/synchronizes rooms and events. This document records the isolated POC workflow,
with a [reference implementation](../examples/matrix-case-workflow/README.md) and
[bounded verification evidence](MATRIX-CASE-POC-VERIFICATION.md).

## Operator journey

1. **Common operations room:** admitted technicians and Advisor share alarm awareness. An
   authorized new alarm gets a short analysis, uncertainty/evidence and a stable case ID.
2. **Assignment:** a technician posts `Jag tar F-…` as a new room message. A transaction assigns
   the case to one eligible actor. A competing claim reports the existing owner; model prose does
   not establish responsibility. The current POC requires the explicit ID for this accepted path.
3. **Private investigation:** Advisor creates one encrypted, invite-only room per case with the
   assigned technician. The operator accepts the invitation. Separate cases use separate rooms
   and sessions even for the same technician. This is conversation isolation inside Advisor,
   not another trust domain or persona.
4. **Evidence-led dialogue:** the case tool supplies existing context and experience cases;
   the reader tool supplies operational measurements and verified source documents. Record
   who reported a check, when, what was observed and which hypotheses remain unconfirmed.
   Ask one useful next question at a time. A suggestion is not a performed action.
5. **Draft:** Advisor prepares a report and lessons learned. Observation references must refer to
   the case's technician observations. An alarm, an earlier AI answer and a physical measurement
   are different evidence. An unresolved case may legitimately retain `cause_status=unknown`.
6. **Human confirmation:** the assigned technician reviews the full draft and confirms its exact
   hash in that private room. Any new observation invalidates the old draft. The model has no
   confirm/approve tool. The case can then close and publish a short status in the original alarm
   thread, while the detailed private dialogue stays in the case store.
7. **Knowledge reuse:** retrieve a confirmed report/lesson with its source case, evidence, hash,
   reviewer and limits. One experience case is not a general rule. Synthetic experience must not
   appear as a real equipment fault in live searches.

## Trust and data boundaries

The glossary in [CONTEXT.md](../CONTEXT.md) remains authoritative: personas describe the human
job, trust domains describe authority, permission profiles bind actors to scoped permissions, and
runtime skills are capabilities. Matrix replaces a communication surface, not these distinctions.

| Component | Responsibility |
|---|---|
| Advisor | Read operational data, explain evidence, help with case context and report drafts. |
| Human technician | Take responsibility, report real checks accurately, review and confirm a specific report. |
| Engineer | Perform separately approved engineering/deployment/field actions through its controlled management path. |
| Security | Independent observation/audit; needs explicit room/key access to observe encrypted content. |
| PAP / asset owner | Own identities, allowed equipment, room/actor policy and release authority. |

Keep Advisor, Engineer and Security on their separate hosts/trust boundaries. Neither Matrix text
nor case assignment gives Advisor SSH/deployment/field-write authority. Report confirmation is not
an Engineer execution approval. A contractor's scoped Engineer permission profile is not admission
to an Advisor room or the PAP.

For the initial POC, all admitted technicians share the same explicitly authorized lab-equipment
scope. Per-tenant/site isolation needs its own tested authorization mapping before adding those
users. Host-provided Matrix user/account/room facts authorize actions; display names, pasted JSON,
case IDs and model-selected tool arguments do not.

E2EE protects the Matrix transport. Advisor necessarily sees decrypted content and may submit it
to the configured model provider. A self-hosted homeserver does not make inference local. Server
administration alone also does not give Security the room keys needed for content observation.

## Document authority

The POC uses a local case ledger and immutable hashed document blobs. The confirmed case is
retrievable as `technician_confirmed_case`, with its human confirmation kept separate from the
original draft snapshot. Raw private chat is not a publishable report by default.

The canonical target remains [Forge-backed documentation](../skills/documentation-store/SKILL.md)
with metadata and approval state in the [Systemdatabas](../skills/system-database/SKILL.md).
POC exports start in quarantine with independent blob hashes. Human confirmation of an experience
report does not skip Forge review, create a verified equipment manual, or grant a deploy approval.
The local case statuses are a troubleshooting state machine, not replacements for the canonical
engineering approval states.

## Acceptance ladder

Check these separately; a lower step does not prove a later one:

1. Valid config and loaded plugins, including the native Matrix installation record in the
   **service's** registry and explicit conversation access for the local workflow's relevant hooks.
2. Healthy running channel, not merely Gateway HTTP 200.
3. Readable encrypted human/bot dialogue, with device trust checked separately.
4. Alarm analysis completion and a correlated delivery receipt for the intended room.
5. Deterministic assignment before model dispatch, then a correctly bound private room/session.
6. Actual successful `openaut_case` calls, not a model's assertion that it used or lacked a tool.
7. Reviewed revision/hash, authenticated human confirmation, closed case and correct group thread.
8. Hash-valid report/lesson retrieval and exclusion of synthetic cases from live experience.
9. A **new** synthetic alarm through the corrected automatic callback without manual recovery.

The [reported lab run](MATRIX-CASE-POC-VERIFICATION.md) reached the case-closure/retrieval checks
with documented recovery steps. Step 9 and live Matrix alarm routing remain unverified/off.

## Review and operational stop condition

Use a scoped revision and acceptance criteria. Fix only confirmed defects blocking the agreed POC
or violating its minimum trust/isolation boundaries. One initial review and at most one focused
follow-up of fixes is the default budget; optional hardening does not start another round.
When the scoped checks pass, stop. Unknown delivery is a reconciliation task, not an automatic
retry. A later new synthetic run is a separate acceptance case, not a replay of the closed one.
