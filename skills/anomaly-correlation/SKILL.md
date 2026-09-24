---
name: anomaly-correlation
description: Explain related HVAC alarms and anomalies using event timing, source health, documented dependencies and competing causes. Use for alarm floods, recurring alarms, suspected common causes, or silent signal changes; preserve individual alarms and distinguish correlation from proven causation.
permissions:
  knowledge_only: true
  exec: none
  network: none
  data_access: "read-only (openAut telemetry store)"
---

# anomaly-correlation — evidence-led incident grouping

Help the **Driftstekniker persona through Advisor** understand which observations may belong together,
which may be consequences, and what would discriminate possible common causes. Pair with
[`fdd`](../fdd/SKILL.md) for component-level troubleshooting. Answer the operator in Swedish.

**Correlation is not causation.** A single root cause is an outcome to substantiate, not a requirement.
Keep independent incidents separate; “common cause not established” is a useful result.
The LLM explains findings; it is not the authority for diagnosis, classification, decisions, or actions.
This knowledge skill installs no detector, poller, deduplicator or notification route.

## Read-only contract and meaning of grouping

Use only host-granted read tools. In the Advisor POC use `openaut_read` for discovered equipment,
source health, latest/alarms, bounded history and verified documents. No direct SQL, shell, SSH or
field-protocol access is granted here. A topic prefix, nearby unit name or chat assertion grants no access.

**Grouping changes the explanation only.** Preserve original alarm identifiers, individual states,
timestamps and source priorities. Do not acknowledge, clear, shelve, suppress, delete or reprioritize
source alarms. Do not hide an independent or protective alarm under a speculative common cause.
Changes follow Advisor → approved Systemdatabas case → Engineer under the
[`trust-domain workflow`](../advisor-engineer-workflow/SKILL.md).

## 1. Build a small evidence ledger

Scope one incident window and authorized equipment. Collect only fields that exist; mark others unknown.

| Field | Interpretation |
|---|---|
| Equipment + source alarm/metric identity | Stable identity, not display text alone. |
| Origin | Real observation, deterministic finding, human report or synthetic fixture. |
| State / transition | Active, returned, unknown; acknowledgment/latching only if explicitly provided. |
| Times | Source/change, receipt/publication and query times with stated semantics. |
| Quality | Source health, clock uncertainty, missing intervals, truncation and initial state. |
| Priority / response | Preserve configured priority and known required response; otherwise unknown. |
| Evidence | Raw values, applicable source passages and dependency provenance. |

Keep three layers separate: **data-path health**, **equipment process state**, and **message delivery**.
A reader failure is not proof of a fan failure. Communication recovery is not process recovery.
An accepted analysis job is not proof that its message was delivered. A source alarm that predates a
communication outage remains relevant even when current state cannot be verified.

Repeated snapshots with the same active state are not separate activations. A real return followed
by a new activation is a recurrence, not a delivery duplicate. If the previous state is unavailable,
say “first observed active”; do not invent a transition time or duration.

## 2. Establish what the timeline can actually order

- Prefer source event time for physical ordering only when its meaning and clock quality are known.
  Arrival order can reflect buffering, retries or a backlog released after reconnection.
- Account for polling interval, alarm delay/debounce, timestamp resolution and clock skew.
  Describe an onset interval between last-known-normal and first-observed-active where possible.
  Overlapping onset intervals do not establish which event came first.
- A single timestamp shared by several polled values gives no sub-poll physical sequence.
  COV timestamps describe changes/publications, not a continuously sampled process.
- Split around gaps and mode changes. Do not treat missing rows as returns to normal, interpolate
  binary alarm states, or use truncated first/last rows as complete incident boundaries.
- Choose a justified window for the mechanism: electrical events can be fast, thermal effects slower.
  State the chosen interval and limits; there is no universal 60-second causal window.

## 3. Form candidate groups, then test their explanations

Use progressively stronger relationships; never promote a weak relationship silently.

| Relationship | Evidence required | Allowed conclusion |
|---|---|---|
| Temporal proximity | Compatible times and window | Co-occurrence, mechanism unproven. |
| Same equipment | Stable identity + plausible sequence | Candidate within-unit relationship. |
| Physical dependency | Verified feeds/serves relation and applicable flow/sequence | Possible upstream effect; check lag and contradictory observations. |
| Shared dependency | Documented shared pump, power feed, controller or data path | Candidate common cause; examine dependency evidence and unaffected peers. |
| Discriminating corroboration | Independent observation consistent with mechanism and alternatives tested | Stronger support; state exactly what is verified. |

An equipment inventory or MQTT hierarchy is not by itself a physical topology. A documented network
dependency is not a hydraulic dependency. Record relation type, direction, source/version and
applicability before reasoning across equipment. If topology is absent, group within the unit and
list other simultaneous events separately; request the missing relation rather than invent it.

Test at least these alternatives when relevant:

1. One upstream process disturbance with expected downstream effects.
2. Several independent faults or a shared operating change (schedule/weather/setpoint).
3. One acquisition problem making several observations unavailable or apparently simultaneous.

Do not chain A-near-B and B-near-C into one unlimited incident. Recheck every member against the
candidate mechanism and bounded interval. Break a group when direction, time or contradictory
measurements no longer support it. A consequence may persist after its initiating event has returned.

## 4. Explain the group and preserve urgency

Retain a compact member list with current/last-known states, ungrouped alarms and unresolved links.
Use **possible**, **supported**, or **not established** with reasons for the causal link; these are
evidence labels, not calibrated probabilities. An alarm derived from a point is not independent
confirmation of that point. A second LLM repeating the explanation adds no evidence.

Present documented time-critical/protective conditions first. Then use configured priority, impact
and required response time where available. Show diagnostic uncertainty separately; do not multiply
severity by confidence and thereby bury a potentially serious but poorly understood alarm.

One concise summary per supported group is a presentation target, not a guarantee of one incident,
one alert or exactly-once delivery. Delivery deduplication, routing and escalation belong to the
operator-managed watcher/outbox. Never replay an uncertain delivery to test this skill.

## 5. Silent anomalies: only with a defensible baseline

First gate on valid units, comparable operating mode/load, coverage and sampling semantics. Prefer
time-regular or explicitly time-weighted data over raw COV event counts. Record baseline interval,
sample count, exclusions, statistic and calculation provenance. A baseline is not automatically healthy.
Exclude the evaluated interval from the reference baseline; explain any unavoidable overlap.

| Check | Evidence needed | Counterexample to rule out |
|---|---|---|
| Drift / level shift | Comparable earlier operation and reproducible residual/statistic | Weather, occupancy, schedule, sensor replacement. |
| Flat signal | Resolution, expected excitation, valid acquisition and independent response | Stable setpoint/process, quantization, COV silence. |
| Peer difference | Comparable design, mode, load and sensor location | Different duties or a shared sensor bias. |
| Repeated toggling | Actual active/return transitions with coverage | Duplicate publications, counter reset, truncation. |

For an explicitly calculated robust screening statistic:

```text
m = median(baseline)
MAD = median(abs(baseline_i - m))
M = 0.6745 * (observed - m) / MAD
```

NIST discusses `abs(M) > 3.5` as **potential outlier labelling**, not an HVAC fault or a site alarm
threshold. Do not enable it automatically. If MAD is zero/near measurement resolution, or the
baseline is too small/unrepresentative, do not divide by zero or report infinite certainty: mark the
score not evaluable and use a documented physical tolerance or seek a better baseline. Account for
autocorrelation and multiple comparisons; repeated dependent samples are not independent confirmations.
No calculation tool/result means no claim that a statistical detector ran. Simple shown arithmetic
may illustrate a hypothesis but is not a deterministic production finding.

## 6. Handoff and follow-up

Pass `fdd` the equipment identities, interval and timing limits, source health, member alarm states,
proposed mechanism, relation sources, contradictions, and the single most useful next observation.
Do not pass a hypothesis as a confirmed root cause.

On new evidence, revise or split the group and explain why. Distinguish source return-to-normal,
acknowledgment, latched state, technician-reported repair and verified recovery. Verify each affected
member in comparable operation; no new notification does not establish clearance.

```text
Samlad bild: [possible common cause or several separate events]
Tidsförlopp: [what can be ordered; explicit timing uncertainty]
Ingår: [alarm identities/states and observed effects; other alarms remain visible]
Belägg / talar emot: [source references, documented links, competing explanation]
Nästa kontroll: [one observation that could confirm, weaken or split the group]
Prioritet: [source priority/response if known; uncertainty stated separately]
```

Show date/time in Europe/Stockholm using host-converted values, retaining offset where needed.
Separate synthetic, historical and current events throughout the answer.

## Sources and evaluation

Source basis: HSE operator-oriented alarm management, OPC Foundation's state/time/quality concepts,
NIST robust statistics and autocorrelation, and NIST/LBNL HVAC research. OPC UA is a conceptual
reference here, not an added protocol or a claim about the POC's available fields.

- [Source review and design decisions](../../docs/ADVISOR-DIAGNOSTICS-RESEARCH-20260923.md)
- [Offline evaluation cases and acceptance criteria](../../docs/ADVISOR-DIAGNOSTICS-EVALUATION.md)

No calibrated statistical detector or cross-equipment dependency graph is established by this file.
