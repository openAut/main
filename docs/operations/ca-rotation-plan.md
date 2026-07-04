# CA rotation plan

Split from #13 (checklist item 5, PKI-rotation part) as issue #44. Covers the **root/intermediate CA
itself** that signs the MQTT client certs [`cert-reissuance-plan.md`](cert-reissuance-plan.md)
reissues — a different, higher-blast-radius credential than any single node's cert. Distinct from
[`credential-proxy-key-rotation-plan.md`](credential-proxy-key-rotation-plan.md) (the command-envelope
signing key). Not a live migration — openAut is concept-stage with no deployed fleet or CA yet — this
is the decided procedure for when a real CA and fleet exist.

**Forge/Systemdatabas TLS rotation is explicitly not covered here** — the Forge and its Systemdatabas
(`openaut/system-db`, #42) don't exist yet, so a TLS-rotation procedure for infrastructure that isn't
built would be invented, not decided. That piece stays blocked on #42/Forge deployment; see
"Out of scope here" below.

## Rotation objects

- Root CA (or root + intermediate, if a two-tier PKI is adopted at broker deployment time).
- Intermediate CA, if used.
- Trust bundles distributed to the broker, edge nodes, and management-plane components that verify
  against this CA.
- Downstream effect only, not this plan's procedure: every client cert the CA has issued (that's
  `cert-reissuance-plan.md`'s scope, triggered as a consequence of CA rotation, not repeated here).

## Cadence

- **Routine rotation**: a planned cadence (e.g. 12–24 months, decided at deployment time based on the
  chosen CA software's defaults and the site's risk assessment — not fixed here, since no CA exists
  yet to size this against).
- **Emergency rotation**: triggered immediately on suspected CA compromise, regardless of where the
  routine cadence currently stands.

## Ownership

Per [ADR 0002](../adr/0002-access-control-and-roles.md), the CA is not an Engineer-operational
concern — it is policy/trust-anchor material. Ownership here follows the same shape as
[ADR 0004](../adr/0004-edge-control-writes-and-continuity.md) decision 6's ownership of the
credential/signing proxy's key-rotation policy (owner/governance-triggered, non-self-grant) — an
analogy for consistency, not a claim that decision 6 itself decides CA rotation; decision 6's actual
scope is the command-envelope signing key, covered separately in
[`credential-proxy-key-rotation-plan.md`](credential-proxy-key-rotation-plan.md). The CA's ownership
rule below rests on ADR 0002's PAP/non-self-grant model directly:

- **Owner/governance authority** (asset owner or owner-appointed release authority): the only party
  that triggers, approves, or widens a CA rotation.
- **Engineer**: may execute case-scoped technical steps (e.g. deploying a new trust bundle to a
  broker or edge node) under an approved Systemdatabas case, but never generates, holds, or
  self-signs a new trust anchor, and never grants itself CA access.
- **Security**: read-only/watch-only, consuming CA-operation events from the append-only audit sink;
  cannot trigger or silence a rotation.

Long-lived CA private key material never sits in Engineer's or opencode's context — if a
credential/signing proxy or equivalent mediating service is used for CA operations, it is a mediated
interface, not a raw key handed to an operational actor.

## Re-anchoring without a fleet-wide outage

1. **Publish new trust anchor first.** Distribute the new (intermediate or root) CA's public
   certificate into every verifier's trust bundle — broker, edge nodes, management components —
   *before* anything is signed by it, via the same signed-artifact pipeline used for code deploys
   ([ADR 0001](../adr/0001-delivery-and-trust-model.md)).
2. **Dual-trust overlap.** During the transition, verifiers trust **both** the old and new CA
   simultaneously — a bounded window, sized to how long batch reissuance (step 3) is expected to take,
   not left open-ended.
3. **Batch reissuance.** Reissue client certificates under the new CA in batches (per
   `cert-reissuance-plan.md`'s inventory-driven approach — Systemdatabas's node registry as the
   primary source, not a snapshot of currently-connected sessions), verifying each batch before moving
   to the next.
4. **Per-site/node verification.** Confirm each reissued node authenticates successfully under the new
   CA before considering it migrated.
5. **Retire the old CA.** Only after all nodes are confirmed migrated: remove the old CA from every
   verifier's trust bundle. Dual-trust (step 2) ends here, not before.

This mirrors `cert-reissuance-plan.md`'s overlap-then-cutover shape at one layer up (CA instead of
per-node cert), for the same reason: a hard cutover with no overlap risks an operational cliff if any
node's reissuance is delayed.

## Rollback and revocation

- **Routine rotation, rollback:** if the new CA/trust-bundle rollout fails partway, verifiers keep
  trusting the old CA (dual-trust from step 2) — no node is stranded, since the old CA was never
  removed from the trust bundle until step 5.
- **Confirmed CA compromise, no rollback:** a compromised CA cannot be "rolled back to" — the new CA
  becomes the sole trust anchor immediately (emergency path), and every certificate the compromised CA
  issued must be treated as untrustworthy pending reissuance, not just the ones known to be affected.
- **Revocation propagation — routine rotation only.** During a *routine* rotation's dual-trust overlap
  (step 2), CRL/OCSP (or equivalent) endpoints, if used, should reflect the new trust state before
  dual-trust ends, as ordinary overlap hygiene — a verifier that only checks the trust bundle and not
  revocation status could otherwise accept an old-CA-issued certificate that was separately revoked
  for an unrelated reason during the overlap window.
- **CA compromise is not a revocation-propagation problem — do not rely on CRL/OCSP for it.** On
  confirmed or suspected CA compromise, the compromised CA is removed as a trusted anchor immediately
  (per "Confirmed CA compromise, no rollback" above) — full stop, not conditional on CRL/OCSP being
  up to date. Waiting for or depending on revocation status while continuing to trust the compromised
  CA would mean relying on leaf-certificate revocation to contain a **root-of-trust** compromise, which
  it cannot do: the compromised CA can mint new, unrevoked leaf certificates faster than any CRL/OCSP
  process can catch them. Dual-trust never continues on the strength of "revocation looks current" once
  compromise is confirmed.

## Audit

Every CA operation writes to the append-only audit sink (ADR 0003 §4), the same discipline
`cert-reissuance-plan.md` and `credential-proxy-key-rotation-plan.md` already require:

- key generation (new CA/intermediate)
- trust-bundle distribution (publish, and later, retirement)
- signing operations performed by/for the CA
- revocation or decommission of the old CA
- who (owner/governance authority) triggered each step, and under which case/incident record

## Controls before/after

- Long-lived CA keys never appear in opencode/Engineer context, in this runbook, or in logs.
- Trust-bundle updates are signed and delivered via the same controlled release/configuration channel
  as other perimeter changes (ADR 0001) — never a live fetch from an unauthenticated source.
- Confirm dual-trust is actually removed at the end of rollout — a rotation that never retires the old
  CA (step 5 skipped) leaves a stale trust anchor active indefinitely, silently widening the trust set.

## Out of scope here

- **Forge/Systemdatabas TLS rotation** — blocked on #42 (Forge/`openaut/system-db` don't exist yet).
  Once Forge's topology is defined, a follow-up decision is needed on: DNS/service naming, whether the
  TLS surface is internal-only or externally exposed, whether mTLS is used, the cert source (this CA,
  or a separate one scoped to Forge), and a rotation/reload procedure that doesn't require downtime.
  Tracked back on #44/#13 until Forge exists — not decided speculatively here.
- Individual MQTT client cert reissuance (`cert-reissuance-plan.md`).
- The credential/signing proxy's own signing key (`credential-proxy-key-rotation-plan.md`).
- Building the actual CA-operations tooling — this is the procedure; scripting it is separate
  follow-on work once a real CA exists.
