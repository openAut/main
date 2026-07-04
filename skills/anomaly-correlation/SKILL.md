---
name: anomaly-correlation
description: Reduce alarm floods to root cause by correlating events across time, space (system/zone topology) and signal behaviour — temporal clustering, parent/child suppression, common-cause grouping, and statistical anomaly detection on the openAut telemetry store. Use when many alarms fire at once, when distinguishing a root-cause alarm from its downstream symptoms, or when flagging silent drifts that never trip a fixed threshold.
permissions:
  knowledge_only: true
  exec: none
  network: none
  data_access: "read-only (openAut telemetry store)"
---

# anomaly-correlation — from alarm flood to root cause

When something fails, dozens of alarms can fire — most are downstream symptoms of one cause. This
skill groups and ranks them so the **Driftstekniker** gets *one* actionable root cause, not a wall of
notifications, and surfaces **silent anomalies** that fixed thresholds miss.

Reads [`timeseries-stack`](../timeseries-stack/SKILL.md) read-only. Pairs with [`fdd`](../fdd/SKILL.md)
(which explains *why* a unit is faulty) — this skill decides *which* event is the cause.

## Two jobs

1. **Alarm correlation / flood reduction** — cluster related alarms, suppress symptoms under their
   parent, present the root.
2. **Anomaly detection** — find deviations that never cross a static limit (drift, dead signals,
   changed patterns).

## Correlation dimensions

| Dimension | Signal | Use |
|---|---|---|
| **Temporal** | alarms within a short window (e.g. 60 s) | likely one event — cluster them |
| **Spatial / topology** | same node / system / supplied zone | parent (AHU) suppresses children (its VAVs) |
| **Causal / sequence** | known propagation (fan trips → flow loss → temp drift → zone alarms) | order cause → effect |
| **Common-cause** | shared dependency (power feed, pump, controller, network) | group by the dependency, not the symptom |

**Parent/child suppression:** if an AHU faults, its downstream VAV/zone temperature alarms are
expected — report the AHU, list the zones as impact, don't alert each separately.

## Anomaly detection (silent faults)

Static thresholds miss slow problems. Add lightweight statistical checks over `readings_hourly`:

- **Robust z-score / MAD** — flag points far from the metric's recent median (drift, spikes).
- **Sibling comparison** — a point diverging from identical units under the same conditions
  (one of four VAVs behaving differently → that one).
- **Stuck/dead signal** — variance ≈ 0 when the process should move (frozen sensor, lost comms).
- **Pattern change** — daily/weekly profile shifts vs its own history (schedule or load change).

Keep it explainable: report the metric, the expected band, the observed value, and the rule.

## Workflow

1. **Collect** the alarm set + the underlying points for the incident window.
2. **Cluster** temporally, then by topology and common-cause.
3. **Order** within each cluster by the causal sequence to find the head (root).
4. **Suppress** children under their parent; keep them as "impact".
5. **Rank** clusters by severity × confidence.
6. **Hand off** the root to [`fdd`](../fdd/SKILL.md) for diagnosis, then to the Driftstekniker as one
   Teams thread: root cause, the suppressed symptoms (as impact), evidence, recommended check.

## Topology input

Correlation needs to know what feeds what. Use the relational `system.devices` / zone mapping in the
storage tier (and the MQTT topic hierarchy `openaut/<site>/<node>/<system>/...`) as the parent/child
graph. Where a dependency isn't in the model (shared power/controller), capture it as a small
adjacency list in config and extend over time.

## Principles

- **One incident → one alert.** Symptoms travel with the root, never alone.
- **Confidence, not certainty** — show the cluster and why, so a human can override.
- **Explainable detection** — no opaque scores; every flag names its rule and expected band.

## Runtime discipline

The LLM explains findings; it does not diagnose, decide, or act. The correlation/anomaly logic above
produces the finding and evidence deterministically — the LLM may summarize evidence, explain likely
causes, and draft recommendations for human review, but generated text is never the authority for
classification, control action, setpoint write, or deployment. Any future path that lets an
`anomaly-correlation` finding trigger a write, deploy, or override must go through the Driftstekniker
→ Advisor → approved Systemdatabas case → Engineer path (see
[`advisor-engineer-workflow`](../advisor-engineer-workflow/SKILL.md)), not a widened permissions block
here. This mirrors the discipline [`security-instance`](../security-instance/SKILL.md) already states
("the LLM is not the sole gatekeeper").

> **Live behaviour is unverified until alarms and telemetry flow.** Windows, z-score thresholds and
> the dependency graph are site-specific; the correlation dimensions and parent/child suppression are
> the durable part.
