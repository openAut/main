# Read-only edge integration lifecycle

This runbook captures lessons from physical integrations in an isolated POC. Apply it with
[`engineer-integration`](../skills/engineer-integration/SKILL.md), the selected protocol skill,
and the applicable case and approval process. The three trust domains use separate hosts in this lab;
deployment is Engineer work, never a direct Teams-to-SSH path. The POC must not connect to a live
building, occupied space, or safety-critical equipment.

## Proportionate POC scope

For this isolated lab, a lightweight local case, explicit operator confirmation, pinned/hash-checked
artifacts, verification and rollback are sufficient for the described experiments. Separate hosts
describe the lab topology; the trust-domain identities and permissions remain distinct.

This lab exception is not an alternative production delivery path. Under
[ADR 0001](adr/0001-delivery-and-trust-model.md), persistent delivery across the production air gap
uses only the reviewed, pinned, self-contained signed Main release with SBOM. Dependency material
comes from the verified `refresh` cache and is included by `build` in that release. Standalone vendor
staging below is an isolated POC procedure; these tools do not implement release attestation.

## Commissioning sequence

1. Scope the equipment, edge node, transport, function-code allow-list, point-map revision, service,
   telemetry namespace, artifact revision, verification and rollback. Confirm the exact action
   before persistent deployment; a read-only field protocol does not make installation read-only.
2. Preserve management connectivity. A dedicated field segment has no unintended gateway, DNS,
   forwarding, bridge or public fallback. A successful TCP connection proves transport only.
3. Verify synchronized time, source and offset before accepting telemetry. NTP must be restricted
   to the intended interface and segment. A large clock correction needs a plan for source
   timestamps, TLS, queued events, aggregates and sibling services.
4. Prove one documented read. Record raw value, decoded value, function code, unit/slave ID,
   manual reference, zero-based API offset, signedness, width, scale and unit.
5. Review the full point map. Exclude absent sensors and ambiguous zero values until verified;
   successful decoding alone does not establish that a sensor exists or a value is plausible.
6. Build reviewed, hash-locked dependencies offline, install the scoped service, and verify the
   entire field-read → mTLS MQTT → ingest → database → dashboard path.

Modbus change-of-value publication still requires polling. Record the analog sampling interval,
digital polling interval and publication policy separately. An unchanged digital point may have
an old event timestamp while polling continues successfully; point age alone is not its health.

## Identity is a cross-system contract

| Identity | Meaning and lifecycle |
|---|---|
| Equipment ID | Stable relational key; preserve it across presentation changes. |
| Display name | Mutable asset-owner label shown to humans. |
| Telemetry system | Canonical MQTT/TimescaleDB segment, changed through an explicit migration. |
| Certificate CN | Site/node authorization scope. |
| MQTT ClientID | Unique connection/session identifier; not authorization. |
| Dashboard UID | Normally stable to preserve links, even if its original name becomes historical. |

Choose final identities before collecting history. Record old names and telemetry systems as
aliases. A display-name change alone should not rewrite telemetry or primary keys.

For a required telemetry migration:

1. Stop only the affected producer. Drain or explicitly account for queued old-identity events.
2. Verify a backup and record source count, time bounds and unaffected scope.
3. Reject an occupied destination unless a separately reviewed merge is intended.
4. Update the exact site/node/system scope, preserving timestamps and event IDs.
5. Refresh all affected aggregate windows, including history outside automatic refresh policies.
6. Reconcile Systemdatabas metadata and point/topic mappings, edge configuration, dashboards,
   variables, alerts, verifier assertions and documentation.
7. Restart and prove preserved history, no unexpected old rows, fresh new data, spool drainage
   and healthy sibling services. Record audit evidence.

Raw-row updates and continuous-aggregate refresh may be separate failure points. Plan recovery
from each intermediate state and pair data rollback with metadata, configuration and dashboard
rollback. A rollback must refuse to overwrite intervening unrelated changes.

## Health must be observable at each layer

An active systemd service, an MQTT connection and an empty spool can coexist with failed field
reads. Verify these separately:

- process state and restart count;
- latest successful field read, consecutive errors and expected protocol function codes;
- per-point validity, including partially failed register blocks;
- MQTT authorization, connectivity and PUBACK-aware spool drainage;
- ingest persistence and recent source timestamps;
- dashboard queries, datasource permissions and intended listener binding.

Local freshness uses monotonic time so clock corrections do not alter elapsed-time decisions.
Published last-success timestamps use synchronized UTC time. A stored `healthy=true` must always
be interpreted with current freshness; it can outlive the process that published it. Successful
reads from one block do not prove that every point or alarm word is available.

An RTU transport may require close/reopen after a bounded run of transport exceptions. Ordinary
Modbus exception responses prove an exchange occurred and should not cause serial reopen churn.
Catch connection-establishment errors as well as read errors. A restart that restores readings
is recovery evidence, not proof that the underlying adapter fault has been fixed.

## Delivery identity and durability

The public reference publisher already creates `event_id` before spooling, and ingest deduplicates
on `(ts, node, event_id)`. Apply the same rule to every equipment-specific bridge: generate one
cryptographically generated 32-character lowercase hexadecimal ID per newly created event (for
example `secrets.token_hex(16)`; the existing publisher uses OS-random `uuid.uuid4().hex`), store the
complete payload,
and replay its original bytes after reconnect or process restart. Do not regenerate IDs during
queue draining or derive them from timestamp/value, which can collapse distinct observations.

Legacy events without IDs remain compatible but are not deduplicated. For the reference ingest's
explicit `ON CONFLICT (ts, node, event_id) DO NOTHING` statement, the tested PostgreSQL 16/TimescaleDB
configuration uses INSERT plus column-level SELECT on that conflict key. Preserve those tested
permissions in initialization and existing-volume migrations; do not infer table-wide SELECT or
UPDATE privileges from this example. Reverify permissions if the SQL statement changes.
PostgreSQL 16's [INSERT reference](https://www.postgresql.org/docs/16/sql-insert.html), under
`index_column_name`, explicitly states: "SELECT privilege on index_column_name is required."
This applies to our explicit conflict target even with `DO NOTHING`; it is not a `DO UPDATE` grant.

PUBACK proves broker receipt, not database commit. Event deduplication does not by itself make the
entire chain exactly-once or lossless; ingest failure, broker persistence and bounded-queue overflow
need their own acceptance tests and documented loss policy.

## Independent offline runtimes

Each integration owns its service, configuration, ClientID, spool, installation root, dependency
directory and rollback. Sharing a node certificate within its scope does not justify sharing another
service's Python environment. Define one owner or explicit aggregation semantics for node `$status`.

Preflight the target Python version, architecture, stable serial by-id path and executable paths.
A node can lack both `venv` and `pip`: build a vendor directory on an approved build host using an
offline wheelhouse and hash lock, then import-test on the target without global/user-site fallback.
Do not describe a node-local override as a reproducible release until it is represented in the
reviewed artifacts. Verify sibling services after each independent upgrade or rollback.

## Evidence and closure

Record case, exact artifact hashes/revisions, methods, observed results, exclusions, rollback state
and unresolved faults. Keep dated reports separate from living capability guidance. A local
approval or test is not evidence of public pre-merge review.

See the [sanitized physical POC report](verification/physical-edge-integrations-2026-09-11.md).
The next experiments use the [small recovery test matrix](EDGE-POC-RECOVERY-TESTS.md).
