# Physical edge integrations — isolated POC report

- Date: 2026-09-11
- Scope: two equipment-specific read-only Modbus profiles on one Siemens IOT2050 in an isolated lab
- Transport: Systemair CU27-C over RTU and FlaktGroup/Climatix POL638 over TCP
- Field writes: none; the exercised profiles used FC04 only
- Evidence source: operator-confirmed local POC execution and verification records

This report summarizes lab observations, not a public CI run or a production qualification. Local
addresses, equipment labels, SSH identities, secret paths and manufacturer manual content are
deliberately omitted. The generic public field-reader scaffold is still a stub; the exercised
equipment-specific deployments are distinct artifacts.

## Observed in the running lab

- Both profiles produced physical telemetry through certificate-bound mTLS MQTT, ingest and
  TimescaleDB. Grafana health, datasource access, dashboards, read-only database permissions and
  loopback-only UI binding passed the local verifier.
- Producers had distinct services, ClientIDs and SQLite spools. After publication both spools were
  empty and both services remained active.
- Identity migrations preserved historical raw counts and timestamp bounds, refreshed affected
  aggregates, updated dashboards and left no old telemetry identities in the migrated scope.
- A subsequent metadata reconciliation retained stable equipment keys while aligning display
  names and telemetry metadata, retaining aliases and appending audit evidence.
- The edge clock was corrected against a synchronized, interface-scoped lab time source. Fresh
  timestamps and continued operation of both services were then verified.
- Reliability updates added stable event IDs before spooling and separate field-protocol health,
  last-success and consecutive-error metrics. Checked post-update rows contained canonical IDs
  with no missing or duplicate IDs in the observed window.
- Climatix dependencies were built from an independent hash lock and imported on target Python
  3.13.5. The service no longer imported or executed from the Systemair runtime.
- Final checks found synchronized time, healthy field reads, zero consecutive errors, empty
  spools, no automatic service restarts and a successful Grafana verification.

## Verified with tests rather than induced physical faults

- Local Python 3.12 tests exercised event-ID parsing, spool behavior and transport-error handling.
- Disposable TimescaleDB 2.29.2/PostgreSQL 16 verification exercised replay deduplication under the
  narrow ingest privilege and equipment-metadata migration/rollback.
- Both revised unit files passed `systemd-analyze verify` on the node.
- The Systemair repeated-exception close path and connection-exception handling were unit-tested.
  No physical serial fault was deliberately induced to prove automatic recovery.

## Remaining evidence gaps

The intermittent serial I/O fault's root cause remains unresolved. Long broker outages, automatic
recovery from the physical RTU fault, full backup restoration, certificate rotation, queue capacity
under pressure and production sizing were not proven by this exercise. Zero duplicate IDs in a
normal-operation window is not a live outage/replay experiment or proof of lossless delivery.

These observations validate only the exercised profiles and configuration. They do not validate
other hardware, firmware, writable points, analytics accuracy or a production agent deployment.

The resulting reusable rules are in [the integration lifecycle](../EDGE-INTEGRATION-LIFECYCLE.md).
