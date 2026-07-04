# Physical/PLC interlock — reference pattern

> Split from #13 (checklist item 2), resolved by [ADR 0004](../adr/0004-edge-control-writes-and-continuity.md)
> decision 3 and closed out here as issue #40.

## Scope: safety-relevant writable points, not every writable point

[ADR 0004](../adr/0004-edge-control-writes-and-continuity.md) decision 3 decided the requirement:

> The backstop against an unsafe held value is a physical/PLC interlock independent of the software
> that issued the command — never a network mechanism. [...] HLV without an independent interlock is
> not an acceptable end state for any **safety-relevant** writable point — not every writable point
> needs one (a comfort-tuning setpoint with no safety consequence doesn't).

ADR 0004 explicitly left open which of the two scopes — "every writable point" (#13's original
wording) or "safety-relevant" (the decided requirement) — is broader in practice, and kept #13 open
for that question. This document closes it: **the practical scope is every safety-relevant writable
point**, defined as one where Hold Last Value could hold a value that is unsafe absent an independent
interlock. A comfort setpoint (e.g. a zone temperature deadband) is writable but not safety-relevant,
and does not need one. This is a decision, not a discovery — if a future integration finds a point
that's ambiguous, the default is to treat it as safety-relevant until an engineer records the
rationale otherwise (see `safety_relevance_rationale` below).

This document does **not** invent or specify physical/PLC hardware — that stays per-equipment
engineering, decided at commissioning by whoever designs the equipment's control sequence. What this
document standardizes is **what openAut expects to see documented** for every writable point, so a
reviewer (human or Security) can tell, from the point/register-map metadata alone, whether the
interlock question was actually considered.

## Point metadata block

Add this block to the point/register-map entry (`edge-iot2050`'s point map today; the same shape
applies wherever a `modbus`/`bacnet`/`m-bus` writable point is declared) for every writable point:

```yaml
writable: true
continuity_mode: hlv            # hlv | fail_safe | device_native
safety_relevant: true
unsafe_hlv_hazard: "Could overheat supply air coil"
interlock_required: true
interlock_reference: "PLC-AHU-01: clamp SAT max 45C + high-temp cutout TS-17"
interlock_type: "plc_clamp + physical_limit"
interlock_owner: "asset-owner / commissioned controls contractor"
commissioning_evidence: "FAT-2026-xx-xx / SAT-2026-xx-xx"
comm_loss_restart_behavior: "DDC holds BACnet priority array value until timeout; PLC clamp remains active"
reviewed_in_case: "Systemdatabas case id"
```

For a point assessed as **not** safety-relevant, the interlock fields are replaced by an explicit,
reviewable rationale — silence is not an acceptable way to say "not applicable":

```yaml
writable: true
continuity_mode: hlv
safety_relevant: false
safety_relevance_rationale: "Comfort-only zone setpoint; bounded by local DDC min/max, no hazard if held"
```

### Field reference

| Field | Meaning |
|---|---|
| `continuity_mode` | What happens to this point on comms loss — `hlv` (ADR 0004 decision 2's default), or a documented deviation (`fail_safe`, `device_native`) with its own equipment-profile justification. **This document's interlock requirement below applies to `continuity_mode: hlv` specifically** — `fail_safe` reverts to a defined safe default on its own and `device_native` delegates continuity to the field device's own logic, so neither carries the same "a held value could be unsafe" hazard HLV does. Either still needs `safety_relevant` assessed and, if true, its own recorded justification for why the deviation from HLV is safe (reuse `unsafe_hlv_hazard`'s slot to record *why fail-safe/device-native is the safe choice here* instead). |
| `safety_relevant` | The scope decision above, made explicit per point, independent of `continuity_mode`. |
| `unsafe_hlv_hazard` | For `continuity_mode: hlv`: what could go wrong if HLV holds a bad value with no interlock — the reason `interlock_required` is true. For `fail_safe`/`device_native`: repurposed to record why that deviation is the safe choice for this point. |
| `interlock_required` | Whether an independent physical/PLC interlock is required — true whenever `safety_relevant: true` **and** `continuity_mode: hlv`. |
| `interlock_reference` | Required when `interlock_required: true`. Points at the actual independent mechanism (limit switch, PLC clamp, high-limit cutout, VFD-native trip) — not a description of intent, a reference to what exists. |
| `interlock_type` | Required when `interlock_required: true`. Short classification of the mechanism (e.g. `plc_clamp`, `physical_limit`, `vfd_native_trip`), for filtering/auditing across many points without parsing `interlock_reference`'s free text. |
| `interlock_owner` | Required when `interlock_required: true`. Who is accountable for the mechanism existing and being tested — an asset-owner or commissioned contractor, not Advisor/Engineer/Security (they're trust domains, not accountable parties; see [`docs/operations/spof-risk-register.md`](../operations/spof-risk-register.md) for the same convention). |
| `commissioning_evidence` | Required when `interlock_required: true`. FAT/SAT record that the interlock was actually tested, not just specified. |
| `comm_loss_restart_behavior` | Optional but recommended for `hlv`/`device_native` points: what the field device or edge node actually does across a restart during comms loss (e.g. "DDC holds BACnet priority array value until timeout"), so the documented behaviour can be checked against reality at commissioning. |
| `safety_relevance_rationale` | Required when `safety_relevant: false`, in place of the interlock fields above — see the non-safety-relevant example below. |
| `reviewed_in_case` | Always required. Ties the point's safety assessment to a Systemdatabas case, so it's audited like any other approved change, not a standing exception. |

## Gating rule

A writable point must not be activated for Engineer write/deploy until:

1. `safety_relevant` has been assessed (not left blank/default), for every `continuity_mode`,
2. where `safety_relevant: true` **and** `continuity_mode: hlv`: `interlock_required: true`,
   `interlock_reference`, `interlock_type`, `interlock_owner`, and `commissioning_evidence` are all
   filled in,
3. where `safety_relevant: true` **and** `continuity_mode` is `fail_safe` or `device_native`: the
   equipment-profile justification for why that deviation is safe is recorded (reusing
   `unsafe_hlv_hazard`'s slot, per the field table above) — this document does not require the same
   physical-interlock fields for these modes, since the HLV-specific hazard doesn't apply, but it does
   require the deviation to be explicit and reviewed, not silently assumed safe,
4. where `safety_relevant: false`: `safety_relevance_rationale` is filled in,
5. in every case, the assessment is tied to a `reviewed_in_case`.

Engineer executes an approved case; it does not get to waive or self-certify the interlock
requirement — that decision belongs to whoever owns the equipment profile and the Systemdatabas case
approval, consistent with [ADR 0002](../adr/0002-access-control-and-roles.md)'s separation between
who executes an operational workflow and who owns policy.

## What this pattern is not

- Not a claim that openAut is a safety controller. The interlock lives in the field — PLC, DDC,
  VFD, or a hardware limit device — independent of the software issuing the command.
- Not a specification of which hardware to use. That's per-equipment engineering, same as today.
- Not a runtime enforcement mechanism. Nothing here parses or validates this metadata block yet; it's
  a documentation contract for what commissioning and review must produce. Automated validation is
  future follow-on work, not part of closing #40.
