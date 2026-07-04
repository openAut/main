# Credential/signing proxy: key-rotation runbook

Closes the "credential/signing proxy needs an operational 90-day key-rotation runbook" follow-up item
named in [ADR 0004](../adr/0004-edge-control-writes-and-continuity.md) decision 6, split from #13 as
issue #41. Distinct from [`cert-reissuance-plan.md`](cert-reissuance-plan.md) (PR #33), which covers
MQTT edge-node **client certs**; this plan covers the credential/signing proxy's own **command-envelope
signing key** — a different credential, different risk, different owner path. Not a live migration —
openAut is concept-stage with no deployed fleet yet — this is the decided procedure for when a real
fleet exists.

## Scope

- The signing key the credential/signing proxy uses to sign the mediated MQTT write endpoint's command
  envelopes (ADR 0004 decisions 2 and 6).
- Not MQTT client certs (`cert-reissuance-plan.md`) and not the CA/root of trust that anchors those
  client certs (`ca-rotation-plan.md`).
- No new runtime code — ADR 0004 decision 6 already decided the rotation *policy*; this is the
  *procedure* that executes it, the same relationship `cert-reissuance-plan.md` has to its own
  ADR decision.

## Two distinct paths — do not conflate them

ADR 0004 decision 6 is explicit that these are **two separate paths with opposite overlap behaviour**,
not one policy with an exception case. Getting this backwards (treating the emergency path as if it
had the routine path's grace period) would keep honoring a compromised key for up to 14 more days —
exactly the gap the ADR splits the two paths to close.

### 1. Routine rotation (non-compromised key, planned)

- Maximum **90-day cadence**.
- Generate a new active signing key at the credential/signing proxy.
- The proxy signs new envelopes only with the new active key.
- The verifier (edge node) accepts **both the active key and the immediately-previous key** for a
  short overlap — **target 14 days, or until no in-flight command references the old key, whichever
  is shorter.** This overlap exists purely to drain commands signed moments before rotation; it is
  **not a general-purpose grace period** and does not apply to a compromised key (see path 2).
- After the overlap ends (time-boxed or drained, whichever first), the previous key is removed from
  the verifier's trust set.
- The **trust anchor** (public key/key-set) is distributed via the same signed-artifact pipeline as
  code deploys ([ADR 0001](../adr/0001-delivery-and-trust-model.md)); the **private operational key
  never leaves the credential/signing proxy** (ADR 0004 decision 2 — Engineer never has raw signing
  key access).

### 2. Emergency revocation (suspected compromise, controlling-contractor change, or contract end)

- The old key is **removed from the verifier's trust set immediately** — **no 14-day overlap, no
  "immediately-previous key" exception.** This is the opposite of path 1's overlap, not a shorter
  version of it.
- A revocation is a **separate, signed key-set-version artifact** riding the same signed-artifact
  pipeline as the trust anchor — not "rotate early" using path 1's mechanism, which would silently
  fall back into the routine-rotation overlap and keep honoring the compromised key.
- Any command already in flight, signed with the revoked key, that a node has not yet verified is
  **rejected** once the node picks up the new key-set. This is a deliberate fail-closed tradeoff: a
  legitimate in-flight command can be resubmitted; a compromised one cannot be un-published.

## Roles and governance

Both paths are **PAP-/governance-owned, signed release configuration** (ADR 0004 decision 6) — the
same non-self-grant rule as ADR 0004 decision 5's audit window. Concretely:

- **Owner/governance authority** (asset owner or owner-appointed release authority): the only party
  that triggers, delays, or widens either path. Neither Engineer nor the mediated MQTT write endpoint
  can self-trigger a rotation or revocation.
- **Engineer**: may execute case-scoped technical steps under an approved Systemdatabas case (e.g.
  deploying the new signed key-set artifact), but never mints, holds, or edits key material directly,
  and never modifies PAP/permission-profile configuration to grant itself rotation authority.
- **Security**: read-only/watch-only. Consumes rotation and revocation events from the append-only
  audit sink (ADR 0003 §4); cannot trigger, delay, or silence either path.

## Steps

### Routine rotation

1. **Trigger.** Owner/governance authority initiates rotation at or before the 90-day cadence limit.
2. **Generate.** Credential/signing proxy generates a new active key; the trust anchor (public
   key/key-set) is published via the signed-artifact pipeline (ADR 0001).
3. **Cut over signing.** Proxy signs all new envelopes with the new active key.
4. **Overlap window.** Verifier(s) accept both active and immediately-previous key for ≤14 days or
   until no in-flight command references the old key, whichever is shorter.
5. **Drain confirmation.** Confirm no outstanding commands reference the previous key before the
   overlap ends.
6. **Retire previous key.** Remove the previous key from the verifier's trust set once the overlap
   ends.
7. **Audit.** Log to the append-only sink: who triggered, key IDs (old/new), activation timestamp,
   overlap start/end, retirement timestamp.

### Emergency revocation

1. **Trigger.** Owner/governance authority declares compromise, contractor change, or contract end.
2. **Generate + publish revocation artifact.** A new active key is generated, and a signed
   key-set-version artifact recording the revocation rides the signed-artifact pipeline — this is not
   the routine-rotation mechanism run early.
3. **Immediate removal.** The compromised key is removed from the verifier's trust set as soon as the
   node picks up the new key-set — no overlap.
4. **In-flight handling.** Any command signed with the revoked key that a node has not yet verified is
   rejected (fail-closed); the sender may resubmit a legitimate command under the new key.
5. **Audit.** Log to the append-only sink: who declared the revocation, reason category (compromise /
   contractor change / contract end), key IDs (revoked/new), and the timestamp the revoked key was
   confirmed removed from every reachable node's trust set.

## Controls before/after

- No raw signing key material appears in this runbook, in logs, or in issue/PR text — ever. The
  private operational key never leaves the credential/signing proxy (routine or emergency path alike).
- Engineer has no direct access to key material under either path; all access is mediated by the
  credential/signing proxy per ADR 0004 decision 2.
- Verify, after any rotation or revocation, that old envelopes still correctly fail
  freshness/range/case checks and cannot become a replay path once their signing key is retired.
- Do not confuse this runbook's scope with the edge-node/MQTT-broker client-cert topology
  (`cert-reissuance-plan.md`) or the CA rotation covered in `ca-rotation-plan.md` — different
  credential, different procedure.

## Out of scope here

- MQTT edge-node client certs (`cert-reissuance-plan.md`).
- The CA/root of trust (`ca-rotation-plan.md`).
- Building the actual key-generation/rotation tooling — this is the procedure; scripting it is
  separate follow-on work once there's a real fleet and a deployed credential/signing proxy to run it
  against.
