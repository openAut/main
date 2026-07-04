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

### 2. Emergency revocation (suspected compromise, external control contractor / styrentreprenör change, or contract end)

This trigger list is verbatim from ADR 0004 decision 6, not this document's own addition. Treating an
external control contractor change or contract end the same as suspected compromise is a deliberate
credential-hygiene decision — it does not imply the proxy's signing key was necessarily exposed by a
routine contractor change. A contractor change also separately triggers the ordinary PAM/permission-
profile revocation for that contractor's own case-scoped JIT access (per ADR 0002/`CONTEXT.md`'s
styrentreprenör model) — that is a different, narrower action than this document's scope (the
proxy's own signing key) and happens regardless of whether this path is triggered.

- The old key is **removed from the verifier's trust set immediately** — **no 14-day overlap, no
  "immediately-previous key" exception.** This is the opposite of path 1's overlap, not a shorter
  version of it.
- A revocation is a **separate, signed key-set-version artifact** riding the same signed-artifact
  pipeline as the trust anchor — not "rotate early" using path 1's mechanism, which would silently
  fall back into the routine-rotation overlap and keep honoring the compromised key.
- Any command already in flight, signed with the revoked key, that a node has not yet verified is
  **rejected** once the node picks up the new key-set. This is a deliberate fail-closed tradeoff: a
  legitimate in-flight command can be resubmitted; a compromised one cannot be un-published.
- **Unreachable/stale nodes are not exempt, and "rejected on reconnect" only covers commands the node
  hadn't processed yet.** A node that hasn't picked up the new key-set still holds the compromised key
  in its trust set for as long as it's unreachable — during that window it can still verify and
  **execute** a command signed with the compromised key, not just receive one it later rejects. These
  are two different problems, not one:
  - **Pending/in-flight commands** (not yet executed by the node): rejected once the node picks up the
    new key-set, as above.
  - **Already-executed commands** signed with the compromised key, that a node ran *before* it
    reconnected and updated: key rotation does **not** undo these. Treat any command a node executed
    while still trusting the compromised key as a potential incident requiring case-by-case assessment
    (what was commanded, was it plausible/authorized, does the physical/PLC interlock backstop from
    [`docs/patterns/physical-plc-interlock.md`](../patterns/physical-plc-interlock.md) bound the
    consequence) — rotation closes the door on *future* abuse of that key, it does not retroactively
    validate or invalidate what already happened.
  - Until a node confirms the current key-set version, it is **unsafe for writes** with concrete
    containment, not just a flag: the mediated MQTT write endpoint excludes it from its send list; any
    retained/pending MQTT messages destined for it are cleared rather than left queued; broker-side
    credentials or ACL entries scoped to that node are reviewed for rotation alongside the signing key
    if the compromise scope is unclear; and it is not returned to the send list until it confirms the
    current key-set version via a **monotonic version check** — a node never accepts a key-set older
    than the highest version it has already seen, and the write endpoint never resumes sending to a
    node that hasn't proven it's on the current version, however long that takes.

## Roles and governance

Both paths are **PAP-/governance-owned, signed release configuration** (ADR 0004 decision 6) — the
same non-self-grant rule as ADR 0004 decision 5's audit window. **The two paths' bounds are themselves
fixed by ADR 0004 decision 6, not set per-incident by whoever triggers them**: routine rotation's
overlap is capped at 14 days (or drain, whichever is shorter) and can't be widened; emergency
revocation has no overlap and can't be delayed or given one. Owner/governance authority decides
*whether* and *when* to trigger a path within those fixed bounds — it does not get to loosen the
bounds themselves, which would defeat the reason the two paths are split in the first place.

- **Owner/governance authority** (asset owner or owner-appointed release authority): the only party
  that triggers routine rotation or declares emergency revocation. Neither Engineer nor the mediated
  MQTT write endpoint can self-trigger either path.
- **Engineer**: may execute case-scoped technical steps under an approved Systemdatabas case (e.g.
  deploying the new signed key-set artifact), but never mints, holds, or edits key material directly,
  and never modifies PAP/permission-profile configuration to grant itself rotation authority.
- **Security**: read-only/watch-only. Consumes rotation and revocation events from the append-only
  audit sink (ADR 0003 §4); cannot trigger, delay, or silence either path.

## Steps

### Routine rotation

1. **Trigger.** Owner/governance authority initiates rotation at or before the 90-day cadence limit.
2. **Generate.** Credential/signing proxy generates a new active key, but does not itself authorize
   verifiers to trust it — the proxy exports only the new **public** key/key ID.
3. **Version and sign the key-set artifact.** Owner/governance authority (or an owner-appointed
   release authority acting as PAP) creates the new key-set-version artifact from that public key,
   version-numbered monotonically, and signs it via the same signed-artifact pipeline as code deploys
   ([ADR 0001](../adr/0001-delivery-and-trust-model.md)). The proxy never self-authorizes its own key
   into verifiers' trust sets — this mirrors ADR 0002/0003's non-self-grant rule for the same reason
   Engineer can't widen its own sandbox policy.
4. **Deploy.** Engineer deploys the signed key-set artifact to verifiers under an approved
   Systemdatabas case — a case-scoped technical step, not an authorization decision.
5. **Cut over signing.** Proxy signs all new envelopes with the new active key.
6. **Overlap window.** Verifier(s) accept both active and immediately-previous key for ≤14 days or
   until no in-flight command references the old key, whichever is shorter. Verifiers only ever accept
   monotonically increasing key-set versions — never an older or equal version than the highest they've
   already seen, regardless of who presents it.
7. **Drain confirmation.** Confirm no outstanding commands reference the previous key before the
   overlap ends — query the append-only audit sink (or the credential/signing proxy's own signing log)
   for envelopes signed with the previous key's ID that haven't yet reached a terminal
   accepted/rejected state.
8. **Retire previous key.** Remove the previous key from the verifier's trust set once the overlap
   ends.
9. **Audit.** Log to the append-only sink: who triggered, key IDs (old/new) and version numbers,
   activation timestamp, overlap start/end, retirement timestamp.

### Emergency revocation

1. **Trigger.** Owner/governance authority declares compromise, external control contractor
   (styrentreprenör) change, or contract end. Declaring emergency revocation is itself what starts the
   fixed no-overlap procedure below — there is no separate decision to add or skip an overlap.
2. **Generate + publish revocation artifact.** The proxy generates a new active key and exports only
   the public key/key ID, same as routine rotation step 2. Owner/governance authority (or
   owner-appointed release authority) creates and signs the new key-set-version artifact — a
   monotonic version increment recording the revocation — via the signed-artifact pipeline; this is
   not the routine-rotation mechanism run early, and the proxy does not self-authorize its own key
   into trust sets here either.
3. **Immediate removal.** The compromised key is removed from the verifier's trust set as soon as the
   node picks up the new key-set — no overlap.
4. **In-flight handling.** Any command signed with the revoked key that a node has not yet verified is
   rejected (fail-closed); the sender may resubmit a legitimate command under the new key.
5. **Unreachable-node handling.** Nodes that haven't picked up the new key-set are flagged
   unsafe-for-writes in Systemdatabas and excluded from the mediated MQTT write endpoint's send list
   until they confirm the current key-set version (monotonic check) — not assumed safe just because
   they were unreachable during the incident.
6. **Audit.** Log to the append-only sink: who declared the revocation, reason category (compromise /
   external-control-contractor change / contract end), key IDs (revoked/new), the timestamp the
   revoked key was confirmed removed from every *reachable* node's trust set, and the list of nodes
   still pending confirmation (this list, not just the reachable count, is what closes the incident).

## Controls before/after

- No raw signing key material appears in this runbook, in logs, or in issue/PR text — ever. The
  private operational key never leaves the credential/signing proxy (routine or emergency path alike).
- Engineer has no direct access to key material under either path; all access is mediated by the
  credential/signing proxy per ADR 0004 decision 2.
- Verify, after any rotation or revocation, two separate things rather than treating them as one
  check: (1) an envelope signed with a retired or revoked key is rejected by **key/trust-set
  validation** specifically, not incidentally by freshness/range/case checks, and (2) an envelope that
  *is* still signed by a trusted key (e.g. legitimately re-signed during routine overlap) still has to
  separately pass freshness/range/case validation — trust in the signing key is necessary, not
  sufficient, and must not be conflated with the command's own validity.
- Do not confuse this runbook's scope with the edge-node/MQTT-broker client-cert topology
  (`cert-reissuance-plan.md`) or the CA rotation covered in `ca-rotation-plan.md` — different
  credential, different procedure.

## Out of scope here

- MQTT edge-node client certs (`cert-reissuance-plan.md`).
- The CA/root of trust (`ca-rotation-plan.md`).
- Building the actual key-generation/rotation tooling — this is the procedure; scripting it is
  separate follow-on work once there's a real fleet and a deployed credential/signing proxy to run it
  against.
