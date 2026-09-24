---
name: fdd
description: HVAC fault diagnosis from read-only evidence — check data quality and operating mode, distinguish symptoms from causes, rank competing hypotheses, and choose the next discriminating observation. Use for ventilation alarms, temperature/airflow complaints, heat-recovery problems, or suspected sensor and hydronic faults; pair with anomaly-correlation for multiple related events.
permissions:
  knowledge_only: true
  exec: none
  network: none
  data_access: "read-only (openAut telemetry store)"
---

# fdd — evidence-led HVAC troubleshooting

Help the **Driftstekniker persona through Advisor** explain an alarm or complaint and choose the
next useful check. Core coverage: ventilation/AHUs, heat recovery, sensors and water coils.
VAV, chiller and heat-pump investigations require their own applicable equipment sequences; do not
transfer an AHU rule to them solely because point names match. Answer the operator in Swedish.

**This is analysis guidance, not an installed detector.** Distinguish:

1. **Observation:** a value, source alarm or human report, with provenance and time.
2. **Rule finding:** an actual deterministic evaluator's result with rule version, prerequisites,
   thresholds, duration and input evidence. A controller alarm proves the reported alarm state,
   not the physical cause. A skill file does not prove that any rule has run.
3. **Diagnostic hypothesis:** an explanation with supporting and contradicting evidence.
4. **Confirmed cause:** corroboration that distinguishes alternatives; state who/what verified it.

The LLM explains findings; it is not the authority for diagnosis, classification, decisions, or
actions. Missing evidence is a valid outcome. Do not manufacture percentages of diagnostic certainty.

## Read-only contract

Use only tools already granted by the host. In the Advisor POC all operational reads go through
`openaut_read`; this skill grants no SQL, shell, SSH, browser or direct BACnet/Modbus access.
Use discovery's stable equipment identity and its allowed documents, not a guessed name or another
unit's manual. Follow the host's area and document trust controls.

Recommend observations and draft recommendations. Writes, overrides, resets and deployments go through
Advisor → approved Systemdatabas case → Engineer, under the
[`trust-domain workflow`](../advisor-engineer-workflow/SKILL.md). Do not claim an action or case
creation without an authorized tool result. A persona is not a trust domain.

## Workflow: scope → quality → mode → evidence → hypotheses → next check

### 1. Establish identity and the question

- Identify unit, site, affected service, complaint/alarm time and whether the input is synthetic,
  historical or current. Keep a synthetic scenario separate from actual telemetry.
- Read equipment, health and latest values before describing current state; then obtain points,
  applicable document passages and bounded history for the specific hypothesis.
- Source priority for applicability: verified installed configuration/sequence and manufacturer
  instructions, then commissioned site limits, then general methodology. Record conflicting sources
  instead of silently choosing. A verified file hash does not verify installed firmware applicability.
- An empty point registry means physical sensor placement is unverified. Preserve source labels
  (e.g. extract/return/exhaust); do not equate different positions in an air path.

### 2. Check whether the evidence supports the intended comparison

For each relevant signal record value/unit, source time meaning, quality, physical position and whether
it is a **command, feedback, derived value or independent measurement**. Normalized data is not scaled
again. A fan command is not proof of rotation, airflow or electric power.

- Separate source time, publication/change time, ingest time and query time when available.
  A recent heartbeat supports communication health, not fresh independent measurement of every point.
- With change-of-value (COV) history, an absent row is neither a zero value nor proof of a dead sensor. Event-weighted
  averages are not time averages. Do not silently interpolate across outages or mode changes.
- Align only samples whose timing/validity support comparison. State gaps, truncation, time skew and
  uncertainty. Narrow a truncated history window; do not call its first returned row the fault onset.
- Persistence requires valid coverage and an initial state. Two samples ten minutes apart do not
  establish ten continuous minutes of deviation unless the acquisition contract supports that claim.
- Invalid inputs block the affected inference, not visibility of the original alarm or an unrelated
  well-supported finding. Report last-known state explicitly if current state is unavailable.

### 3. Establish operating mode and eligibility

Read documented mode, schedule, fan state and available sequence signals. Mark the mode as
**reported**, **inferred** (with basis) or **unknown**. An undocumented integer is not a decoded mode.

| Context | Interpretation before applying a steady-state check |
|---|---|
| Off, standby or scheduled stop | Low flow may be expected; active protective alarms still matter. |
| Startup, shutdown, setpoint/mode change | Separate transient from settled operation; use the unit's settling criterion. |
| Heating or cooling | Check the sign of temperature error, actual demand and available capacity evidence. |
| Heat recovery / bypass / free cooling | Establish the real design; an outdoor-air AHU need not have a mixing box. |
| Defrost, frost protection, dehumidification/reheat | Apparent inefficiency or interrupted flow may follow the intended sequence. |
| Manual override, interlock or unknown mode | Identify the constraint; withhold checks whose prerequisites are unknown. |

Do not import a generic settling time, alarm delay or ΔT threshold as a commissioned limit.
For a proposed rule use three results: **condition met**, **condition not met**, **not evaluable**.
“Not evaluable” is not “healthy”; “condition met” alone is not a proven component failure.

### 4. Select a diagnostic track

Use the relevant [diagnostic card](references/diagnostic-cards.md); read only the card needed.

| Track | Distinguishing question |
|---|---|
| F1 Temperature tracking | Too high or too low relative to the contemporaneous active setpoint, in which mode? |
| F2 Airflow / filter / fan | Restriction, drive limitation, intended lower demand, or sensing error? |
| F3 Heat recovery | Wrong operating expectation, bypass/defrost, flow imbalance, drive fault or sensor placement? |
| F4 Sensor / mapping | Genuine process change, sensor bias, mapping error or data-path fault? |
| F5 Heating and cooling together | Intended reheat/protection or unwanted opposing heat transfer? |
| F6 Water-side ΔT | Load, flow, bypass/mixing, heat transfer or measurement error? |
| F7 Cycling / oscillation | Repeated actual transitions, changing demand, or reporting duplication? |

Normal controlled temperature does not exclude a fault: the controller may compensate with greater
fan speed or valve demand. Conversely, high demand does not prove saturation without documented limits.
For multiple alarms first use [`anomaly-correlation`](../anomaly-correlation/SKILL.md) to organize the
timeline. Its proposed common cause remains a hypothesis, not independent proof for this skill.

### 5. Rank competing explanations

Keep at most three useful hypotheses in the initial answer. Include a sensor/data or normal-sequence
alternative when evidence makes it plausible; do not pad the list mechanically.

| Hypothesis | Evidence for | Evidence against / missing | Observation that would distinguish it |
|---|---|---|---|
| Candidate mechanism | Referenced values/sequence | Contrary values, unknown mode or missing feedback | One concrete check and its possible outcomes |

Do not count a derived alarm and its underlying measurement as two independent confirmations.
Rank by explained evidence and contradictions, not by how familiar the fault is. Multiple faults may
coexist. Say “orsaken går ännu inte att skilja ut” when alternatives remain indistinguishable.

### 6. Ask one discriminating question, then update

Choose the least disruptive available observation that separates the leading alternatives. Explain
what each plausible answer would change. Prefer an existing read or normal operator observation.
Do not turn a diagnostic question into a command to force a valve, defeat an interlock or reset a trip.
Inspection involving electrical, moving, refrigeration or fire/smoke equipment belongs to qualified
personnel following the applicable procedure.

On reply, record the observation as human-reported with its time; revise the ranking and explicitly
say which hypothesis gained/lost support. “New filter” alone does not exclude wrong installation,
wet media or a sensing problem. Stop once the next discriminating check is clear; do not loop over
unchanged data. If an approved repair is later reported, compare operation in equivalent conditions
and read the alarm state; absence of notifications does not prove recovery.

## Response contract (Swedish)

Lead with the next check or the strongest supported conclusion. Keep the initial answer compact;
provide a detailed evidence table on request.

```text
Läge: [unit, mode, current/historical/synthetic, communication/data limitation]
Belägg: [value + unit + time + source; relevant manual passage/version]
Bedömning: [leading hypothesis; strongest alternative; what remains unknown]
Nästa kontroll: [one question/check and why its result separates the alternatives]
Påverkan: [observed impact; possible impact clearly labelled; urgency if evidenced]
```

Use host-provided Europe/Stockholm timestamps with date and 24-hour time, retaining offset where
needed. Do not invent energy savings, affected zones or a priority absent from the evidence.

## Research and evaluation

Method basis: NIST APAR's mode-dependent mass/energy-balance approach and observability limitations;
EnergyPlus fault/heat-recovery models; evidence-aware evaluation informed by LBNL. These are not
manufacturer service instructions or proof of ASHRAE Guideline 36 conformance.

- [Source review and design decisions](../../docs/ADVISOR-DIAGNOSTICS-RESEARCH-20260923.md)
- [Offline evaluation cases and acceptance criteria](../../docs/ADVISOR-DIAGNOSTICS-EVALUATION.md)

Any future automatic evaluator needs versioned point bindings, units, mode prerequisites,
quality/coverage rules, tolerance/uncertainty, persistence/reset behavior and a validated finding
contract. Threshold commissioning, executable detectors and live behavior are separate work.
