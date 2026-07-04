---
name: fdd
description: Fault detection and diagnosis for building HVAC systems — apply rule-based AFD (ASHRAE Guideline 36 / APAR-style) to air handlers, VAV boxes, chillers, heat pumps and hydronic loops using the openAut telemetry store, separate symptoms from root causes, and rank likely faults with evidence. Use when an alarm needs root-cause analysis, when diagnosing comfort/energy complaints, or when building automated fault rules over time-series data.
permissions:
  knowledge_only: true
  exec: none
  network: none
  data_access: "read-only (openAut telemetry store)"
---

# fdd — fault detection & diagnosis (HVAC)

Diagnose building-system faults from telemetry. This skill is the analytical core behind the
**Driftstekniker** agent: given an alarm or a complaint, pull the relevant points from the openAut
store, apply deterministic fault rules, separate symptom from root cause, and return a ranked
diagnosis with the evidence that supports it.

Reads from [`timeseries-stack`](../timeseries-stack/SKILL.md) as the read-only agent role
(`$TSDB_AGENT_RO_USER`). Never writes to field devices — control actions stay a human-confirmed path
via the Driftstekniker agent.

## Method: rule-based AFD

openAut uses **rule-based** automated fault detection (transparent, explainable, no training data
needed) as the baseline, following the spirit of **ASHRAE Guideline 36** sequences and the **APAR**
(AHU Performance Assessment Rules) family. Each rule is a boolean expression over measured points and
operating mode; a firing rule is evidence, not a verdict — several rules together localise the fault.

### Operating-mode awareness

Always classify the unit's mode first; a "fault" in one mode is normal in another:

- **Heating** — heating coil active, cooling off, economizer at minimum OA.
- **Cooling with economizer** — OA damper modulating, mechanical cooling staged.
- **Free cooling** — economizer fully open, mechanical cooling off.
- **Mechanical cooling** — economizer at minimum, cooling active.

## Example fault rules (AHU)

| Rule | Condition (mode) | Likely fault |
|---|---|---|
| Supply temp too high | `T_supply > T_supply_sp + Δ` for N min (heating) | heating coil/valve stuck, undersized, low flow |
| Sensor disagreement | `|T_return − T_supply|` implausible vs load | sensor drift/fault |
| Economizer not economizing | OA damper min while `T_oa < T_return` (cooling) | damper stuck, bad OA sensor, control logic |
| Simultaneous heat & cool | heating valve >0 **and** cooling valve >0 | sequencing fault, leaking valve (energy waste) |
| Low ΔT (hydronic) | coil `ΔT` far below design at high load | low flow, fouling, valve authority, bypass |
| Fan runs, no flow | fan command on, `Δp` ≈ 0 | belt/coupling, blocked damper, sensor |
| Short cycling | compressor/heat-pump starts > X/hour | oversizing, refrigerant, control deadband |

The full openAut HVAC reference methodology (Swedish regulations, system types, commissioning) is a
companion knowledge body — fold in an `hvac_analysis`-style reference set if you maintain one.

## Workflow

1. **Scope the window** — take the alarm/complaint timestamp ± a window; identify the unit and its
   points (`openaut/<site>/<node>/<system>/<metric>`).
2. **Pull data** — query `telemetry.readings` (raw) and `telemetry.readings_hourly` (trend) for those
   metrics over the window and a baseline period.
3. **Classify mode** per timestamp.
4. **Evaluate rules** for that mode; record which fired, with the values.
5. **Separate symptom from cause** — "cold room" (symptom) may be airflow imbalance, not a heater
   fault. Trace the airflow/water path and control sequence.
6. **Rank causes** — most likely → possible → less likely, each tied to the firing rules.
7. **Recommend measurements** to confirm before any intervention (measure before acting).
8. **Output** in the Driftstekniker format: situation → likely causes → checks/measurements →
   recommended actions (no-cost → maintenance → controls → component) → energy impact → risks.

## Querying the store (read-only)

```sql
-- raw points around an alarm
SELECT ts, metric, value FROM telemetry.readings
WHERE node = :node AND system = :system
  AND metric IN ('supply_temp','supply_temp_sp','heating_valve','cooling_valve','oa_damper')
  AND ts BETWEEN :start AND :end
ORDER BY ts;
```

## Principles

- **Deterministic and explainable** — every diagnosis cites the rule(s) and values that fired.
- **Measure before acting** — recommend verification; don't propose replacement on a single signal.
- **Safety** — refer refrigerant, combustion, electrical, mould/legionella and fire-damper work to
  qualified personnel.
- **Energy lens** — simultaneous heating/cooling, bypassed heat recovery, and short cycling are both
  faults and waste; flag them for the Energisamordnare agent too.

## Runtime discipline

The LLM explains findings; it is not the authority for diagnosis, classification, decisions, or actions. The rule-based FDD logic above
produces the finding and evidence deterministically — the LLM may summarize evidence, explain likely
causes, and draft recommendations for human review, but generated text is never the authority for
classification, control action, setpoint write, or deployment. Any future path that lets an `fdd`
finding trigger a write, deploy, or override must go through the Driftstekniker → Advisor → approved
Systemdatabas case → Engineer path (see
[`advisor-engineer-workflow`](../advisor-engineer-workflow/SKILL.md)), not a widened permissions block
here. This mirrors the discipline [`security-instance`](../security-instance/SKILL.md) already states
("the LLM is not the sole gatekeeper").

> **Live behaviour is unverified until field data flows.** Thresholds (Δ, N minutes, starts/hour) are
> site-specific — calibrate against each unit's baseline. The rule structure and mode-awareness are
> the durable part.
