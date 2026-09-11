# Small POC recovery test matrix

Follow-up to [issue 75](https://github.com/openAut/main/issues/75). This is a proposed test plan,
not a record of executed tests. Start with synthetic events in a disposable stack. A lightweight
local case records the selected target, operator confirmation, artifact hashes, result and rollback.
Physical fault injection needs separate confirmation of the exact reversible action.

## Fixed baseline

- One synthetic event/second, unique event ID, immutable JSON payload and source UTC timestamp.
- Dedicated test spool, capacity 300 events, no production or physical-service spool modification.
- Record monotonic elapsed time as well as UTC. Verify clock synchronization first.
- Record initial/final ID sets and counts at creation, persistence, broker receipt and database commit.
  Broker PUBACK is not a database commit; deduplication is not a guarantee against event loss.
- Reconnect within 60 seconds and drain a 120-event backlog within 120 seconds after recovery.
- Preserve the management path and keep sibling services running. Abort if either is affected.

## Run one failure at a time

| Test | Action and duration | Pass/fail |
|---|---|---|
| Broker unavailable | Disconnect the test producer for 120 seconds while sampling continues. | All 120 scheduled events accounted for in spool; unchanged payloads replay; reconnect/drain within baseline limits; DB has one row per ID. |
| Producer restart | Repeat broker test; restart producer once at 60 seconds. | Every committed pre-restart spool event survives byte-identically; separately count any samples missed during downtime; do not label missed sampling lossless. |
| Ingest stopped | Stop disposable ingest for 60 seconds, leaving broker up. | Count broker receipts versus DB commits after recovery. Any missing ID fails an end-to-end at-least-once claim and is recorded as a limitation. |
| Database unavailable | Deny disposable ingest DB access for 60 seconds. | Same accounting as ingest test; record acknowledgement behavior explicitly. Do not assume automatic recovery means no event loss. |
| Spool limit | Offline synthetic runs of 299 and 301 events into fresh 300-event spools. | Retain all 299 below capacity; above capacity, retain 300 and record the single oldest-event drop under the configured policy. No lossless claim for overflow. |
| Exact replay | Submit one identical event twice, then same timestamp/value with a different ID. | First ID has one row; second ID has its own row. Legacy no-ID events are checked separately and have no deduplication guarantee. |

For each test, restore the single changed condition, collect counts/ID differences, and discard the
test stack only after saving results. A failed acceptance criterion is useful POC evidence; it does
not justify quietly widening permissions or adding infrastructure during the test.

## Separate physical follow-up

After the synthetic tests, confirm a reversible serial disconnect on the isolated RTU test rig.
Use the existing 15-second polling schedule; stale means last-success age strictly greater than
60 seconds (`> 60 s`). Disconnect for 90 seconds and require stale to be observed and logged before
restoration. If it is not observed, restore at 90 seconds and mark that criterion failed rather
than extending the outage indefinitely. Require bounded transport close/reopen and a
valid FC04 response within 90 seconds after restoration without a process restart. Verify sibling
service health, management access, fresh timestamps and draining spool. Restore the connection and,
if automatic recovery fails, use the case's controlled service restart as rollback, recording the
automatic-recovery test as failed. No electrical fault injection or field writes are included.

Publish a short sanitized result table with artifact hashes, observed timings and counts, pass/fail,
rollback outcome and unresolved gaps. The lab may use hash-checked local artifacts rather than a
signed production release; record that POC exception explicitly instead of claiming release compliance.
