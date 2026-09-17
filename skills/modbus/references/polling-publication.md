# Separate field polling from publication

Read-only Modbus polling and MQTT/database publication have different purposes. Poll fast enough
to observe the process; publish at the reviewed history/event rate. Lowering a polling interval
in a bridge that enqueues every read also increases disk writes, MQTT traffic and database rows.
Filter **before event-ID creation and durable enqueue**, not after sending to the broker.

[`PublicationPolicy`](../scripts/publication_policy.py) is an opt-in reference extracted from a
physical lab implementation. It is tested with a fake FC04 client and the reference
[`ReadOnlyTransport`](../scripts/readonly_transport.py). It is not installed by the generic edge
installer; `edge_agent.read_point()` remains a stub. The published helper is not the exact deployed
equipment-specific bridge and has not itself been tested against physical controllers.

## Suggested starting profile, subject to equipment verification

| Signal | Poll | Publication |
|---|---:|---|
| Analog process value | 15 s | Fresh instantaneous sample every 60 or 600 s |
| Mode, counter, alarm word | 15 s | Startup and change of value |
| Field last-success timestamp | Updated on valid responses | Every 30 s |
| Field health/error state | Evaluate during polling | Startup and change of value |

These are lab starting values, not manufacturer limits or universal HVAC requirements. Measure
response and complete cycle times, retries, errors and other bus traffic. Keep RTU requests
sequential with one bus owner. Do not change baud rate or merge register blocks without device
documentation and a separate verification. After overruns, schedule the next poll without catch-up
bursts; bounded retries and backoff remain the transport/scheduler's responsibility.

## Integration contract

Construct one policy per integration in its single polling thread:

```python
import time

policy = PublicationPolicy(
    periodic={"supply_temp": 600, "field_protocol_last_success_unixtime": 30},
    on_change={"alarm_active", "field_protocol_healthy", "field_protocol_consecutive_errors"},
    enqueue=enqueue_event,
)

# Run this at every scheduled poll, even when publication is not due.
words = transport.read(temperature_offset, 1)  # explicit reviewed FC04 block
if words is not None:
    value = decode_and_validate_temperature(words[0])
    policy.submit("supply_temp", value, transport.last_success, "degC")

# Evaluate health even when process reads fail. Missing last-success stays omitted.
observation_epoch = int(time.time())  # synchronized UTC, once for this health snapshot
for metric, value in transport.health().items():
    unit = {"field_protocol_healthy": "bool",
            "field_protocol_consecutive_errors": "count",
            "field_protocol_last_success_unixtime": "unix_s"}[metric]
    policy.submit(metric, value, observation_epoch, unit)
```

Here `enqueue_event(metric, value, ts, unit)` creates the normal stable event ID and persists the
complete event in the integration's own spool. It **returns only after durable acceptance** and
raises on failure; it must not silently return false or start an asynchronous enqueue. If it
raises, the policy remains due. A crash after persistence can still produce another startup
snapshot: this is not a transactional/exactly-once filter. Replay existing queued events directly,
with original IDs and payloads, without passing them through this policy again.

The caller validates point values, units, timestamp and freshness. Use stable scalar values for
change-only metrics. Only submit fresh successful process reads, never a cached value after a
failed read. Health's last-success value is intentionally allowed to age: republishing it must
not advance that value. Consumers age the **embedded last-success epoch**, not just its enclosing
event timestamp. A healthy block does not establish freshness of all other blocks.

Periodic gates are independent per metric and use monotonic elapsed time measured from successful
durable acceptance (after the enqueue callback returns), including slow queue writes. Source timestamps remain
the observation's synchronized epoch. Publication intervals are **minimum spacing**, aligned to
the next successful poll; jitter/failure can delay publication. Choose polling no slower than the
desired publication interval. No background publication timer creates synthetic fresh samples.

Startup creates an initial snapshot even if the previous process published recently. COV changes
and health transitions bypass periodic limits, so total database rows are not a fixed quota.
Intermediate analog samples are discarded. Interval mean/min/max or local FDD require a separate,
explicit data contract; an instantaneous point must not silently become an average.

## Acceptance

Test with fake clocks and an actual polling path: reads continue while publications are suppressed;
points have independent gates; enqueue failure consumes neither interval nor change; wall-clock
adjustments do not bypass elapsed-time gates; failed reads create no synthetic values; unchanged
COV is suppressed while alarm and health transitions are immediate. Verify startup semantics.

Then verify the scoped deployment: actual poll counts/durations, protocol errors, timestamp sync,
spool drainage, sibling services and **every analog point's database spacing over at least the
longest publication interval**. State physical-fault tests separately from simulated failures.
See the [sanitized lab evidence](../../../docs/verification/polling-publication-2026-09-17.md).
