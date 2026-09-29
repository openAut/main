# Matrix case POC — bounded verification record

**Evidence date: 2026-09-29.** One synthetic troubleshooting case was closed and checked in the
isolated lab. This public record omits live room/event IDs, account names, document hashes,
addresses, credentials and machine-specific commands. Detailed receipts remain in the local journal.

## Exercised setup and outcome

The lab used OpenClaw **2026.9.4**, Node **24.21.0**, the official Matrix plugin **2026.9.4**,
Synapse **1.161.0**, PostgreSQL **16.14** and Element Web **1.12.28**. Advisor used the configured
OpenAI GPT-6 Astra model via OAuth. These results do not validate the target Nemotron inference
stack, NemoClaw containment or a complete fresh installation.

The synthetic event described a false→true alarm transition on one authorized air handler.
No physical process fault was asserted or introduced. The technician reported no physical checks
or corrective actions, and the report retained **unknown physical cause**.

The accepted path was a shared-room alarm, a new explicit-ID assignment message, a separate
encrypted case room, a private context request, a report/lesson draft, human hash confirmation
and a group-thread closure notice. Seventeen final read-only checks passed:

| Check | Result |
|---|---|
| Case status closed | Pass |
| Expected equipment, technician, private room and original alarm binding | Pass |
| Exact reviewed revision/document hash | Pass |
| Cause remains unknown and case remains synthetic | Pass |
| Human confirmation metadata | Pass |
| Unique matching confirmation audit event | Pass |
| Frozen evidence references match technician observations | Pass |
| Report and lesson fields present | Pass |
| Confirmed synthetic lesson retrievable through the actual store search | Pass |
| Synthetic case excluded from live search results | Pass |
| All six case outbox jobs sent | Pass |
| Encrypted human confirmation from the assigned technician | Pass |
| Unique closure-notice receipt | Pass |
| Encrypted bot closure event in the correct operations room | Pass |
| Exact closure body in the original alarm thread | Pass |
| Successful, correlated `openaut_case context` tool results | Pass: two calls |
| Successful, correlated `openaut_case draft` tool result | Pass: one call |

No `lessons` model-tool call was claimed: retrieval was verified by executing the real store
search read-only. The six sent jobs were alarm, private-room creation, assignment notice,
private introduction, draft review and closure. Confirmation changed metadata, not the frozen
draft bytes; retrieval correctly returned `technician_confirmed_case`.

## Corrections required during the run

These were observed integration defects, not evidence of comparative model capability:

- A restrictive installer umask removed group traversal from a plugin directory. Explicit mode
  setting and a check as the real service identity corrected it.
- Copying the native Matrix package did not create the official installation record. The channel
  could load but could not start its trusted state helper. Official installation in the service
  registry, removal of a shadowing path and an explicit writable npm cache corrected that path.
- The case completion hook required `hooks.allowConversationAccess=true`. Its absence left a
  completed analysis outside the case outbox. A separately approved, hash-bound reconciliation
  recovered the **existing** response; no replacement model analysis was fabricated.
- The local workflow incorrectly used the Gateway RPC runtime reserved for trusted official or
  bundled plugins. A pinned-SDK test reproduced rejection before dispatch. The sender was changed
  to the public Matrix outbound adapter, and one approved outbox attempt was resumed after checks.
- Normal room messages needed `before_dispatch`, canonical command content and its flat reply
  contract. Merely registering `inbound_claim` did not intercept the ordinary Advisor dialogue.
- The private turn did expose the case tool, but older workspace instructions still asserted that
  only the reader tool existed. A guarded text correction aligned instructions with actual scope.

Uncertain deliveries were preserved for investigation. None of these interventions authorizes
blind replay, a new blanket permission, or marking a local plugin as trusted-official.

## What is and is not established

The case journey, human confirmation, report integrity, closure delivery and local synthetic
knowledge retrieval were verified for **one case with the above interventions**. The automatic
analysis-to-case callback still needs a separate new synthetic case without manual reconciliation.
Real Matrix alarm routing remained **disabled** at the final check.

The knowledge bank is local POC state (`local-poc-pending-forge`), not completed Forge/Systemdatabas
publication or indexing. No occupied building, safety-critical equipment, field-write behavior,
physical repair, multi-tenant rollout, contractor onboarding, mobile push or Security content
observer was validated by this run.

## Relationship to the public reference

[`examples/matrix-case-workflow`](../examples/matrix-case-workflow/README.md) contains the extracted
case/store/transport logic and offline tests. The entry uses operator-supplied paths, portable
imports and explicit lifecycle cleanup; fixtures use example identities. Local installers,
diagnostics, one-shot recovery code, infrastructure secrets and old case state are deliberately
not deployment inputs for this reference. Fresh installation of this exact public package is
**not** established by the local run. Re-run its bounded acceptance ladder before activation.

## Bounded learning proposals

**Observation:** metadata saying “loaded” or “allowed” was weaker evidence than a running channel,
actual tool calls and correlated delivery receipts. **Observation:** prose instructions can
contradict technically exposed tools and cause a model to refuse a valid operation.

**Next experiment:** run a new synthetic case through the corrected automatic callback, using
the same pinned runtime and recording the model/settings. Success requires one case/alarm,
deterministic assignment, case-tool access only in the correct private room, hash-confirmed
closure, and retrievable synthetic knowledge without a manual handoff repair or a field action.
Only then propose enabling live Matrix alarm routing.

**Smaller-model hypothesis:** explicit current-tool guidance plus a deterministic case state
machine should reduce dependence on model interpretation of responsibility and approval. Evaluate
with a named model and the same tasks, including competing claim, wrong-room access, stale hash
and unknown cause. Measure successful outcomes and unauthorized-action refusals; no comparison
between model sizes has been established by this single POC.
