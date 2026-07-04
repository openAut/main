---
name: energy-optimization
description: Analyse building energy performance from the openAut telemetry store and recommend prioritised, low-risk savings — scheduling, setpoint and deadband tuning, economizer/free-cooling use, heat-recovery checks, simultaneous heating/cooling elimination, pump/fan (VFD) optimisation — with weekly reporting and IPMVP-style measurement and verification. Use for energy reports, consumption-increase explanations, or optimisation proposals.
permissions:
  knowledge_only: true
  exec: none
  network: none
  data_access: "read-only (openAut telemetry store)"
---

# energy-optimization — building energy analysis

Turn telemetry into prioritised, low-risk energy savings. This skill is the analytical core behind
the **Energisamordnare** agent: produce weekly reports, explain consumption changes, and propose
optimisations ordered from no-cost operational changes to capital measures.

Reads [`timeseries-stack`](../timeseries-stack/SKILL.md) read-only (`$TSDB_AGENT_RO_USER`),
preferring the `telemetry.readings_hourly` continuous aggregate over scanning raw data. Never writes
to field devices.

## What to look for (highest ROI first)

| Finding | Signature in data | Action |
|---|---|---|
| Simultaneous heating & cooling | heating + cooling active on same unit/zone | fix sequencing / leaking valve |
| Schedules not matched to occupancy | full operation outside occupied hours | tighten time schedules / optimal start-stop |
| Economizer/free-cooling underused | mechanical cooling while `T_oa` favourable | repair/enable economizer |
| Bypassed heat recovery | low recovery `ΔT` across the wheel/plate when it should run | service/enable HRV |
| Setpoint creep / narrow deadband | frequent reheat, tight deadband, hunting | widen deadband, tune setpoints |
| Pump/fan overcapacity | constant-speed or high VFD at low load | VFD, pressure-reset, pump trimming |
| Short cycling | many compressor starts/hour | staging/deadband, sizing review |
| Sensor drift | implausible baselines vs siblings | recalibrate (drift = phantom load) |

## Weekly report workflow (Energisamordnare)

1. **Aggregate** the last 7 days of energy/consumption series from `readings_hourly`.
2. **Compare** to a trailing baseline (prior weeks; degree-day normalise for weather where relevant).
3. **Decompose** the week-over-week delta into drivers (weather, occupancy, schedule, faults).
4. **Detect** the signatures above; cross-reference [`fdd`](../fdd/SKILL.md) and
   [`anomaly-correlation`](../anomaly-correlation/SKILL.md) findings.
5. **Quantify** estimated savings per measure (order-of-magnitude is fine; state assumptions).
6. **Post to Teams**: total consumption, Δ vs baseline, top-3 anomalies with probable cause, and the
   prioritised optimisation list.

## Measurement & verification (IPMVP)

When a measure is implemented, verify the saving rather than assuming it:

- Establish a **baseline** model (e.g. consumption vs degree-days / occupancy) before the change.
- After the change, compare **actual** against the baseline model adjusted for the same conditions
  (IPMVP Option C — whole-facility — or Option B — measured retrofit isolation).
- Report avoided energy with the routine-adjustment basis stated, not raw before/after.

## Key relationships

```
Ventilation heat loss:   Q_vent = ρ · c_p · V̇ · (T_in − T_out)
Transmission loss:       Q = U · A · ΔT
Fan/pump affinity:       P₂/P₁ ≈ (n₂/n₁)³   (why VFD speed cuts pay off)
Degree-day normalise:    compare kWh per (heating) degree-day, not raw kWh
```

## Principles

- **Optimise before replacing** — schedules, setpoints, balancing and cleaning beat new equipment.
- **No-regret first** — order recommendations no-cost → maintenance → controls → component → redesign.
- **Comfort and IAQ are constraints** — never trade required airflow or comfort for kWh; flag the
  conflict instead.
- **Explainable** — every number shows its inputs and assumptions.

## Runtime discipline

The LLM explains findings; it does not diagnose, decide, or act. The savings analysis above produces
the finding and evidence deterministically — the LLM may summarize evidence, explain likely drivers,
and draft recommendations for human review, but generated text is never the authority for
classification, control action, setpoint write, or deployment. Any future path that lets an
`energy-optimization` finding trigger a write, deploy, or override must go through the Driftstekniker
→ Advisor → approved Systemdatabas case → Engineer path (see
[`advisor-engineer-workflow`](../advisor-engineer-workflow/SKILL.md)), not a widened permissions block
here. This mirrors the discipline [`security-instance`](../security-instance/SKILL.md) already states
("the LLM is not the sole gatekeeper").

> **Live behaviour is unverified until metering data flows.** Savings figures are estimates until
> M&V confirms them. The analysis structure and the savings hierarchy are the durable part.
