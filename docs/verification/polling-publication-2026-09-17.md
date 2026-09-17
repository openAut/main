# Polling/publication separation — isolated lab evidence, 2026-09-17

## Scope and provenance

An operator-approved local POC change updated two existing read-only FC04 integrations on one
IOT2050: an RTU air handler at 9600 baud/8E1 and a TCP air handler. Each retained its own service,
configuration, dependencies, MQTT ClientID, queue and rollback. The lab is isolated from live
buildings, occupied spaces and safety-critical equipment. Deployment was sequential with one
brief restart per integration and node-local backups; no field register writes were introduced.

This report summarizes observations of **equipment-specific local code**, not a runtime test of
the extracted public `PublicationPolicy` helper. Local operator authorization is not retrospective
GitHub review. Machine addresses, identities, credentials and deployment/rollback paths are omitted.

Authorization followed the explicit isolated-lab exception in
[Proportionate POC scope](../EDGE-INTEGRATION-LIFECYCLE.md#proportionate-poc-scope): a lightweight
local case, human confirmation of the exact action, hash-checked artifacts, verification and
rollback. This experiment was outside the production governed runtime/release path. It does not
claim a Systemdatabas approval or a PAP-issued Engineer permission profile; production delivery
requirements in ADR 0001/0002 remain applicable and are not replaced by operator confirmation.

## Change and observed results

| Measurement | RTU integration | TCP integration |
|---|---:|---:|
| Analog polling before → after | 600 → 15 s | 60 → 15 s |
| Analog publication minimum | 600 s | 60 s |
| Analog metrics verified | 14 | 13 |
| Observed database spacing | 601 s | 60–61 s |
| Samples per analog metric in observation window | 2 | 11 |
| Analog and COV rounds per minute after startup | 4 each | 4 each |
| Maximum observed single-tier duration | 0.319 s | 0.298 s |
| Field-success timestamp publication spacing | 30–31 s | 30–31 s |
| Automatic service restarts / final queued rows | 0 / 0 | 0 / 0 |

Verification covered one complete 600-second analog publication interval (approximately eleven
minutes overall). Queries checked all analog metrics, not just one temperature. Both services
remained active, clocks synchronized, protocol health true and consecutive errors zero; no Modbus
errors were logged in that window. Unchanged mode/alarm/health values had only the initial snapshot.
Tier timings include processing/enqueue work; they are not pure wire latency or whole-cycle times.

The local deployment passed 25 relevant Python 3.12 tests, target syntax/config checks and matching
staged/installed hashes. An overbroad local test selection also encountered eight unrelated Forge
test import failures due to Windows application control blocking a database-client DLL; this report
does not claim a clean full-repository local test run. Public extraction tests and CI are separate
evidence, attached to the PR revision.

## Limits

- The observation is short-duration commissioning evidence, not endurance or capacity proof.
- Physical transport faults and broker outages were not induced in this change. Error/recovery
  behavior was tested with fake transports; this does not prove physical serial recovery.
- Values remain instantaneous samples; intermediate reads are not retained as history, aggregates
  or FDD events. Startup snapshots can occur sooner than a normal publication interval.
- The existing register maps, baud rate, dependencies and MQTT/database schema were retained.
- The opt-in public helper does not deploy these lab services or make the generic edge stub a driver.

See [polling/publication guidance](../../skills/modbus/references/polling-publication.md) for the
reusable contract and [integration lifecycle](../EDGE-INTEGRATION-LIFECYCLE.md) for acceptance.
