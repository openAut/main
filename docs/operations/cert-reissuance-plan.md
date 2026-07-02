# Cert reissuance rollout plan: legacy node certs -> ADR 0004 CN format

Closes the last open item on issue #24. Not a live migration in progress -- openAut is concept-stage
with no deployed fleet yet -- this is the decided procedure for when a real fleet exists, so rollout
isn't designed ad hoc under time pressure later.

## Scope: which certs need reissuing

[`skills/mqtt-tls-broker`](../../skills/mqtt-tls-broker/SKILL.md)'s documented convention (as of this
writing) issues client certs with **CN = node id only** (e.g. `CN=iot2050-ahu-01`), no site segment.
[ADR 0004](../adr/0004-edge-control-writes-and-continuity.md) decision 1, verified against a live
broker (`docs/verification/emqx-mqtt5-cmd-verification.md`), requires CN to be the combined,
structurally-validated `<site>/<node>` identifier before a node can be granted `cmd/#`. Any cert
issued under the old convention -- which is every cert issued by `gen-certs.sh` today -- needs
reissuing before its node can receive setpoint writes. Telemetry (`openaut/#` publish) is unaffected;
that's the separate, lower-severity, already-tracked gap in issue #29.

## Principle: reissuance is a signed release event, not an ad-hoc admin action

Per [ADR 0001](../adr/0001-delivery-and-trust-model.md), trust state only changes through a signed
release from the owner-controlled build pipeline -- no operator (Advisor, Engineer, or a node itself)
mints or edits certificates directly. A new cert request is approved via a Systemdatabas case (the
same asset-owner flow that already governs node onboarding), the CA signs it as part of the normal
`refresh` -> `build` -> signed-release cycle, and what reaches the edge node is that release artifact,
never a cert an operator generated and copied over by hand.

## Steps

1. **Inventory.** Enumerate existing node certs and their current CN -- from the CA's issued-certificate
   log if one exists, or by reading `${cert_common_name}` off each broker session if it doesn't. Cross-reference
   against Systemdatabas's node registry to get each node's canonical `site`/`node` values.
2. **Validate target identifiers.** For each node, confirm its `site`/`node` pair from Systemdatabas
   passes issue #25's per-segment canonical-id pattern *before* it's used to build a new CN. This is
   the exact injection surface the live verification proved exploitable (an unvalidated `+` granted
   cross-tenant read access) -- validate here, not just at the broker.
3. **Issue new certs.** Mint one new client cert per node with `CN=<site>/<node>` (single literal `/`,
   both segments individually valid), signed by the existing CA -- no new PKI needed. Issued through
   the case-approved release pipeline, not a one-off `gen-certs.sh` run by an operator.
4. **Overlap window.** Deploy the new cert to the node alongside the old one; both stay valid for a
   bounded window (a normal maintenance window is enough -- there's no technical reason it needs to be
   long). During overlap:
   - the *old* cert can still be used for telemetry, same as today -- unaffected, tracked separately in issue #29;
   - the *old* cert never gets `cmd/#` access, under any circumstances -- this isn't a special-case
     rule to remember, it falls out automatically: `cmd/#` is only ever granted to a cert whose CN
     already passes the two-segment structural check (ADR 0004 decision 1, precondition 3), and an
     old-format cert never will.
5. **Cutover verification.** Before decommissioning the old cert, run the same positive/negative test
   pattern from `docs/verification/emqx-mqtt5-cmd-verification.md` against the node's *new* cert
   (own-scope allowed, cross-scope denied, ClientID-spoofing denied) -- confirm it actually works, not
   just that it was installed.
6. **Revoke the old cert.** Once the new cert is confirmed working and the node is confirmed running on
   it, revoke the old one and log the revocation to the append-only audit sink.
7. **Security visibility.** Security (the audit trust domain) should be able to see at any time which
   nodes are migrated and which are pending -- a query against the CA's issued-cert log / Systemdatabas,
   not new tooling.

## Failure mode

If a node's new-cert deployment fails, it falls back to its old cert for telemetry only -- it never
had `cmd/#` to lose, so there's no operational cliff. It just stays in "pending migration" until the
deployment issue is fixed and retried.

## Out of scope here

- The interlock mechanism (tracked in issue #13).
- The telemetry-side ACL gap itself (tracked in issue #29) -- this plan only confirms old-format certs
  stay confined to it during overlap, it doesn't fix the gap.
- Building the actual inventory/issuance tooling -- this is the procedure; scripting it is separate
  follow-on work once there's a real fleet to run it against.
