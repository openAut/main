# SPOF / reproducibility risk register

Split from #13 (checklist item 5, non-PKI part) as issue #43. Names single-point-of-failure and
reproducibility risks as explicit operational risks with human/organizational owners — this document
**accepts and surfaces** risk, it does not mitigate it (no HA, clustering, or new infrastructure is
introduced by writing this register). PKI-rotation risks are tracked separately: the credential/
signing proxy's key ([`credential-proxy-key-rotation-plan.md`](credential-proxy-key-rotation-plan.md)),
the CA itself ([`ca-rotation-plan.md`](ca-rotation-plan.md)).

This register does not replace a full threat model or risk analysis — it is an operational SPOF/
reproducibility list, reviewed and updated as the deployment evolves.

**Ownership convention:** `Advisor`, `Engineer`, and `Security` are trust domains defined in
`CONTEXT.md`, not accountable parties — they never appear as an "Owner" value below. Owners are
human/organizational roles: asset owner, driftansvarig (operations lead), platform/release-ansvarig,
säkerhetsansvarig, or an equivalent designated function at the deploying Region/Kommun.

## Register

| Risk | Component/topology | Environment | Current exposure | Operational consequence | Owner | Status | Next review | Linked issue/ADR |
|---|---|---|---|---|---|---|---|---|
| Single EMQX broker instance, no failover | MQTT broker (`claw`, lab/dev) | Lab/test | One instance; broker outage stops all telemetry ingest and command mediation | Telemetry gap; edge nodes fall back to store-and-forward (per `edge-iot2050`) until broker returns — no data loss, but no live visibility | driftansvarig | Accepted | At next architecture review | #13 |
| Single inference host, no failover — **environment-specific, see ADR 0001** | LLM inference | **Test/lab:** GX10 / Nemotron 3 Super. **Production:** Nemotron 3 Ultra endpoint | One instance per environment; inference outage loses Advisor/Engineer LLM capability in that environment | AI-generated insights, recommendations, and reports are affected. Regulation itself does **not** stop: per `CONTEXT.md`, the *reglercentral* or field device holds Hold Last Value / fail-safe behaviour independent of inference availability (ADR 0004 decision 2) — "control stops" is not the correct framing unless a specific writable point actually lacks local continuity | platform/release-ansvarig | Accepted | At next architecture review | ADR 0001 |
| `claw` co-locates gateway, broker, Telegraf, InfluxDB, Grafana on one host | Lab/dev infrastructure (`claw`) | Lab/test | Single host failure loses monitoring, alerting, and broker simultaneously | Full observability + control-plane gap in the lab environment until the host is restored | driftansvarig | Accepted | At next architecture review | #13 |
| Release reproducibility depends on the pinned-manifest/refresh/build/signing pipeline being maintained | Main release pipeline | All | `refresh` (online, human-reviewed) → `build` (deterministic, offline-capable) → signed release with SBOM is the only path across the air gap (ADR 0001 §2, §7). If this pipeline degrades or is bypassed, reproducibility and SBOM accuracy degrade with it | Loss of ability to reproduce exactly what was deployed, and of the CRA/NIS2-relevant SBOM/attestation trail. **Not** mitigated by letting internal instances reach public upstreams directly — ADR 0001 §7 explicitly rejects that as reopening egress and destroying reproducibility | platform/release-ansvarig | Accepted | At next architecture review | ADR 0001 §2, §7 |
| Forge as single point of truth for code/docs/CI, once built | Forge (not yet deployed) | Future (post-#42) | N/A — Forge doesn't exist yet | To be assessed once Forge topology is defined; flagged here so it isn't silently forgotten when #42 unblocks | platform/release-ansvarig | Not yet applicable | On Forge deployment | #42 |

## Notes on specific rows

- **Inference host row corrected against ADR 0001**: an earlier draft of this issue described "single
  GX10 inference host" as if it were the production risk. [ADR 0001](../adr/0001-delivery-and-trust-model.md)
  states production runs on **Nemotron 3 Ultra**; GX10/Super is explicitly "for Bertil/test only."
  Both are real SPOF rows, but they are **different environments with different owners and different
  blast radius** — conflating them would misstate which risk applies to a live deployment.
- **OT consequence wording is deliberate**: per `CONTEXT.md` and ADR 0004 decision 2, loss of inference
  affects AI-layer insight/reporting, not the regulated physical process itself (Hold Last Value /
  fail-safe is independent of inference availability). This register should not claim "control stops"
  unless a specific writable point is documented as lacking local continuity — see
  [`docs/patterns/physical-plc-interlock.md`](../patterns/physical-plc-interlock.md).
- **Reproducibility risk is scoped to pipeline maintenance, not upstream access**: ADR 0001 §7
  explicitly rejects "internal instances reaching public upstreams" as a fix for anything — this
  register must not be read as proposing that.

## Maintaining this register

- Update `Status` to `Mitigation planned` or `Mitigated` when an owner commits to or completes a
  concrete change — this document only starts everything at `Accepted`.
- Add a row whenever a new single-instance dependency is introduced (e.g. Forge, once deployed).
- Link each row to the ADR or issue that best documents the underlying architecture decision, so a
  reader can go from "this is a named risk" to "here's why the architecture accepted it."
