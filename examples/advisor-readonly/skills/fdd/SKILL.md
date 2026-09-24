---
name: fdd
description: Evidence-led HVAC troubleshooting for authorized Advisor equipment. Use for temperature, airflow, filter, heat-recovery or sensor complaints; load this complete read-only guidance with openaut_read operation=guidance skill=fdd.
permissions:
  knowledge_only: true
  exec: none
  network: none
  data_access: "read-only via the host-granted openaut_read tool"
---

# FDD — Advisor read-only methodology, revision 2026-09-23

Help the Driftstekniker persona through Advisor in Swedish. This file is self-contained because
guidance can read only the two approved SKILL.md files, not linked references. It installs no FDD
detector or thresholds. The LLM explains evidence and drafts hypotheses; it is not the authority for
fault classification or action. Use only openaut_read for operational data.

## 1. Scope and evidence

1. Discover the unit with list_equipment; follow next_after using after. Use the returned stable
   equipment_id for equipment, health and latest. Never infer permission from a name or document.
2. Separate current observations, historical events, human reports and synthetic scenarios. A fixture
   does not prove that a real alarm occurred. Do not blend fixture values with live observations.
3. Read points and documents. An empty registry is not a physical point map. Distinguish commands,
   feedback, derived readings and independent measurements. Do not scale normalized values twice.
4. Use document_search then document_passage for exact mode/alarm meaning and relevant instructions.
   Cite document, commit, passage lines/section and original spreadsheet cells when applicable.
   Verified source content does not confirm installed firmware applicability; extraction may be
   unreviewed. Do not borrow another unit's manual or invent enum/bit meanings.
5. Read bounded history for the actual available metrics: at most 8 metrics, 7 days and 500 rows per
   request. Use hours or start/end with explicit offsets, not both. Narrow a truncated window.
   Stop when you have the next useful check; do not repeatedly request unchanged evidence.

## 2. Quality and mode before diagnosis

- Distinguish stale communication, source-clock error and process alarms. A healthy heartbeat is
  not a new timestamp or independent quality guarantee for each point. On failed reads report the
  evidence gap and last-known state; do not declare the equipment healthy or failed.
- COV times are change/publication times, not continuous samples. Missing rows are not zeros or
  alarm clearances. Do not infer a dead sensor from COV silence or form an unqualified time average.
- Compare contemporaneous valid values; identify gaps, truncation, time uncertainty and unknown initial
  state. Two isolated samples do not prove continuous deviation between them. Do not interpolate across
  outages or mode changes. Use the tool's Swedish local times and distinguish query from source time.
- Mode is reported with a documented mapping, inferred with stated evidence, or unknown. Check stop,
  startup/shutdown, changed setpoint, heating/cooling, recovery/bypass, defrost/frost protection,
  dehumidification/reheat, overrides and interlocks. Not all AHUs have recirculation/economizers.
- No commissioned FDD thresholds are established by this guidance. Use applicable manufacturer/site
  limits and settling times only when retrieved; otherwise explain observations, not automatic faults.
  A proposed check is condition met, condition not met, or not evaluable. Unknown is not healthy.
  Ineligible steady-state checks do not hide an active protective alarm.

## 3. Choose the relevant diagnostic track

**Temperature:** compare supply_temp with supply_setpoint_temp only if both are actually present and
their meanings are verified. Use the contemporaneous active setpoint; show the sign of
`eT = supply - setpoint` in K. Low supply in heating can fit insufficient delivered heat, cold inlet,
airflow/load or sensor error. High supply with reduced heating demand can fit unwanted heat, recovery,
transition or sensor error. Insufficient heating capacity alone does not explain overheating.
High supply in cooling needs cooling-demand/response evidence before attributing a component fault.
Normal tracking can mask compensation; high command does not prove actuator position or capacity.

**Filter/airflow/fan:** distinguish actual airflow, filter differential pressure, fan pressure rise
and duct static pressure. A filter bit is not a measured pressure. Compare at equivalent airflow.
An obstructed filter may coexist with normal flow while the fan compensates at greater speed; at
its limit flow can fall. Low flow alone does not isolate the filter, fan, damper or flow sensor.
Pressure-derived flow and its source pressure are not independent confirmations. Low demand may be
intentional. A new filter does not exclude wrong installation, wet media or sensing/tubing faults.

**Heat recovery:** first check design, recovery demand, bypass/free-cooling and defrost. A wheel command
is not proof of rotation. Never calculate recovery efficiency using final supply after active reheat.
Only with verified sensor locations and valid comparable readings may you illustrate
`(T_after_recovery - T_before_recovery) / (T_extract_in - T_before_recovery)` as a supply temperature
ratio, not certified/total efficiency. Near-equal inlet temperatures make it unreliable. Flow imbalance,
condensation and other heat inputs constrain interpretation; no fixed failure ratio is assumed.

**Sensor/mapping:** preserve exact source labels and units. Supply/extract differences can be normal.
A flat setpoint or COV value is not proof of a frozen sensor. Seek independent same-location/time
measurement or a predictable process response; distinguish sensor, mapping and data-path hypotheses.

**Heat and cool together:** check dehumidification/reheat, protection and transitions first. Valve
commands alone do not prove opposing heat transfer; zero command does not exclude valve leakage.

**Water-side ΔT:** low difference alone does not prove low flow. For fixed heat transfer,
`abs(Q_dot) = m_dot * cp * abs(ΔT)` implies lower flow gives higher ΔT; actual load can change too.
Low load, excess flow relative to load, bypass/mixing, reduced transfer or sensor error are alternatives.
Without water-flow/load evidence, report the difference without claiming capacity or a pump fault.

**Cycling:** count real start/stop transitions, not repeated active snapshots. Require initial state,
coverage and applicable equipment limits; gaps yield bounds/uncertainty, not a precise starts/hour claim.
Do not diagnose PID tuning or refrigerant charge from a coarse trace.

## 4. Rank, ask one question, revise

Separate observations, source alarms, deterministic findings (only if a tool actually supplies a
versioned rule result), diagnostic hypotheses and confirmed causes. A source alarm proves the reported
state, not its physical cause. No automatically firing rules are installed by this file.

Present up to three plausible explanations, each with evidence for, evidence against/missing, and a
check that would distinguish it. Do not count an alarm and its underlying sensor as independent proof.
Do not turn anomaly-correlation's proposed common cause into a verified diagnosis. Multiple faults
can coexist; “går inte att skilja ut ännu” is valid. Do not invent confidence percentages.

Ask ONE least-disruptive question that separates the leading alternatives and explain why. For example,
an independent filter-pressure reading at the same operating point can separate real pressure loss
from a sensing-path problem. Prefer existing reads and ordinary operator observations. On the reply,
label it human-reported with time, revise the ranking and explain what changed. Stop once the next
useful check is clear. After reported repair, seek comparable operation and explicit alarm state;
absence of messages or restored communication alone does not prove process recovery.

## 5. Compact Swedish answer

Läge → belägg (value/unit/time/source) → bedömning (hypothesis + alternative + uncertainty) →
EN nästa kontroll → observed/possible impact and evidenced urgency. Include relevant manual citations.
Show Europe/Stockholm date and 24-hour time from tool conversions; retain offset where needed.
Distinguish measured facts, calculations with assumptions, and possibilities. Do not invent affected
zones, energy savings or manufacturer service instructions.

No shell, SQL, general file/web access, SSH, field writes, acknowledgments, overrides, deployment or
permission changes are granted by this skill. Hand required changes to the human/approved Engineer
path; claim no case mutation without an explicitly authorized case tool result. Physical checks on
electrical, moving, refrigerant or fire/smoke equipment require the applicable qualified procedure;
do not propose bypassing protections or forcing actuators as a chat diagnostic step.

Method provenance (bibliographic only, not runtime web instructions): NISTIR 6964 (2003, APAR and
observability); EnergyPlus 24.2 Engineering Reference, Operational Faults and Heat Exchangers; Lin,
Kramer & Granderson (2020), DOI 10.1016/j.buildenv.2019.106505 (evaluation). This is openAut synthesis,
not a manufacturer procedure or a claim of standards conformance.
