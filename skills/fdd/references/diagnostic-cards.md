# HVAC diagnostic cards — hypotheses, not automatic fault rules

Read the relevant card after the quality/mode checks in [fdd](../SKILL.md).
These cards are openAut engineering synthesis. Sources and their limits are recorded in the
[research review](../../../docs/ADVISOR-DIAGNOSTICS-RESEARCH-20260923.md), especially R1, R2 and R3.
Every suggested signal is a **required input if that inference is made**, not a claim that it exists.
Documented manufacturer sequences and limits take precedence over these generic mechanisms.

## F1 — Supply-temperature tracking

**Need:** actual supply temperature and contemporaneous active supply-temperature setpoint, time/quality,
mode and sufficient settled history. Prefer available fan/flow, heating/cooling demand, inlet
temperatures and actuator feedback. Do not substitute room/extract setpoint for supply setpoint.

Define `eT = T_supply - T_supply_setpoint` (K); show the values and sign. No generic alarm limit is
implied. Account for sensor accuracy and the unit's documented settling/persistence criteria.

| Observation in eligible operation | Competing explanations | Discriminating evidence |
|---|---|---|
| `eT < 0` in heating | Insufficient delivered heat, cold inlet/inadequate recovery, excess airflow, biased temperature | Upstream temperature, commanded vs actual heat response, water temperatures/flow if available, independent temperature at the same location. |
| `eT > 0` with heating expected to reduce | Unwanted heating, sensor bias, sequence/setpoint transition, excess recovered heat | Low heat command with persistent temperature rise across the coil; verify sensor location and applicable sequence. |
| `eT > 0` in cooling | Insufficient delivered cooling, warm inlet, excess load/flow, sensor bias | Cooling demand/feedback and entering/leaving air/water conditions. |
| Error oscillates | Changing setpoint/load, mode switching, actuator response or loop interaction | Order setpoint, command, feedback and temperature; do not prescribe PID tuning from one trace. |

Undersized heating or insufficient hot-water flow does not normally explain overheating by itself.
High command with poor response does not isolate the valve from supply, flow, actuator or sensor issues.
Normal tracking may hide compensation; compare demand at equivalent load rather than declare fault-free.

**Next question example:** “Finns en oberoende temperaturavläsning vid samma givarläge?”
Agreement shifts attention toward the process; disagreement toward sensing/mapping. If this observation
is not accessible, identify the next available read instead of inventing a measurement.

## F2 — Airflow, filter pressure and fan

**Need:** operating state and demand, actual airflow where available, pressure measurement location,
fan command versus feedback/speed, and an equivalent-flow baseline or applicable manufacturer limit.
A filter alarm bit alone is not a measurement of pressure or proof of fouling.

- High **filter** differential pressure at comparable airflow supports increased filter resistance,
  but wet/wrong media, installation or pressure tubing/sensor errors remain alternatives.
- A variable-speed fan can maintain airflow while speed/power rises. Unchanged flow therefore does
  not exclude a dirty filter. At its limit flow can fall; fan power need not always rise (R2).
- Low airflow with high demand can be restriction, closed damper, drive/mechanical limitation or
  erroneous flow measurement. Compare independent indicators before localizing the restriction.
- Low airflow with low demand may be normal schedule, pressure reset, defrost or an interlock.
- Low filter Δp with low flow does not prove a clean filter. Near-zero duct static pressure is not
  equivalent to zero flow. Distinguish fan pressure rise, duct static, filter Δp and flow pickup Δp.
- Flow derived from a differential-pressure sensor is not independent evidence from that same sensor.
  Do not apply a universal square-law correction without the filter/flow model and its valid range.

**Next question example:** “Har filtertrycket jämförts med en oberoende avläsning vid samma driftpunkt?”
If independent pressure is normal but the reported pressure is high, increase sensing/tubing suspicion.
If both are high, restriction remains plausible; its precise location still needs evidence.
Physical inspection follows the equipment procedure; do not request opening a running fan section.

## F3 — Heat recovery, bypass and free cooling

**Need:** exchanger type, verified sensor positions, incoming outdoor/supply and extract temperatures,
temperature immediately after recovery (before other heat inputs), airflow conditions, bypass/wheel
state and recovery demand. Check free cooling, defrost, frost protection and setpoint limitation first.

For a dry sensible comparison, a supply-side temperature ratio can be illustrated as:

```text
eta_T_supply = (T_after_recovery - T_before_recovery)
               / (T_extract_entering_recovery - T_before_recovery)
```

Report it as a temperature ratio, not certified efficiency or total/latent recovery. If inlet
temperatures are too close relative to measurement uncertainty, the ratio is not interpretable.
Avoid it if sensor positions/times are unverified. Supply after an active reheat coil is not
`T_after_recovery`. Unbalanced airflows, condensation, leakage, bypass and fan heat affect interpretation;
R3 explicitly models flow-capacity effects and operating controls.

**Alternatives:** normal reduced recovery/free cooling/defrost, commanded bypass, wheel/drive failure,
fouling/frost, flow imbalance or temperature-sensor/mapping error. A 100% command is not proof of rotor
rotation. Compare command with feedback and actual heat transfer where available.

**Next question example:** “Visar återvinningens återkoppling drift samtidigt som den begärs?”
Absent feedback is an evidence gap, not confirmation of a stopped rotor. Follow the manufacturer's
inspection method if physical confirmation is needed.

## F4 — Sensor bias, stuck values and mapping

**Need:** physical location/quantity, unit/scaling and signal type, acquisition health, resolution and
an independent reference or predictable process response under comparable conditions.

- Supply and extract temperatures are expected to differ; their difference alone cannot diagnose bias.
- A setpoint or stable COV value can be flat while healthy. Without excitation and valid acquisition,
  flatness does not establish a frozen sensor.
- Repeated “latest” requests are not new independent samples. A shared bad sensor can make several
  derived values agree incorrectly.
- Mixing-box temperature plausibility applies only to a documented mixing section without unaccounted
  heat transfer, with adequate mixing and valid sensor positions; do not apply it to a recovery AHU.
- Implausible values may be mapping/unit/time errors. Use already-normalized telemetry as reported;
  request verification instead of silently repairing or rescaling it.

**Next question:** independent reading at the same physical position/time. Record uncertainty and
operator provenance. Do not recommend calibration or replacement before differentiating mapping,
installation and actual sensor error.

## F5 — Simultaneous heating and cooling

**Need:** actual sequence, operating mode and overlapping commands/feedback at the same equipment,
preferably corroborated heat-transfer evidence and humidity/dehumidification demand.

Dehumidification with reheat, frost protection, separate zones or short transitions may explain
simultaneous requests. Nonzero valve commands do not prove simultaneous heat transfer. Conversely,
a leaking valve can transfer heat with a zero command; the command alone cannot exclude leakage.
Investigate unintended overlap only after checking these contexts and persistence.

**Next question:** “Är avfuktning med återvärmning aktiv enligt den tillämpliga driftsekvensen?”
If yes, assess against that sequence. If no, compare command/feedback and coil temperature response.
Do not label all overlap as waste or calculate savings without energy/flow evidence.

## F6 — Hydronic low/high ΔT

**Need:** correctly placed entering/leaving water sensors, heating/cooling sign convention, actual
load and water flow (if making a flow claim), valve/bypass arrangement and valid contemporaneous data.

For sensible water-side heat transfer, `abs(Q_dot) = m_dot * cp * abs(ΔT)`.
Use kg/s, J/(kg·K) and K for W. Fluid properties depend on temperature/glycol mixture. At **fixed heat
transfer**, less flow gives a larger ΔT; actual heat transfer can change with flow, so this is not a
universal inverse diagnostic rule.

Low ΔT can reflect low load, high flow relative to load, bypass/mixing, reduced coil heat transfer,
control behavior or sensing error. It does not prove low flow. High ΔT can be consistent with restricted
flow at a given load but also with a different load or measurement conditions. R2 describes coil
fouling with reduced capacity and/or increased flow and low ΔT; that is not a unique signature.

**Next question:** “Finns verifierat vattenflöde och samtidig last för intervallet?”
If unavailable, report ΔT without claiming capacity, flow failure or pump intervention.

## F7 — Cycling, hunting and recurrence

**Need:** actual on/off or mode transitions, initial state, sufficiently fine timing, complete window,
documented minimum on/off times and a comparable load context. Counters need reset/rollover semantics.

Count confirmed starts, not active snapshots or retried messages. Missing initial state makes the
count a lower bound; gaps make duration uncertain. Changing occupancy, demand, defrost and staging can
explain cycles. Distinguish a controller oscillation from slow thermal variation and quantized reporting.
No universal starts/hour threshold applies across compressors, heat pumps and fans.

**Next question:** which changes first in adequately resolved data — setpoint/demand or equipment state?
If timing cannot resolve it, request a suitable read-only trace rather than blame PID settings or
refrigerant charge. After reported repair, verify behavior in comparable operation without forcing cycles.
