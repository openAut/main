# POC1 and POC2 scope

This document fixes the scope and acceptance gates for the first two openAut proofs of concept. Both
run only in an isolated lab and follow the contracts in [`LAB.md`](LAB.md).

## POC1: read-only edge telemetry

Prove a complete read-only data path:

```text
IOT2050 or synthetic publisher -> EMQX mutual TLS -> ingest -> TimescaleDB
```

POC1 permits telemetry and node-status publication only. It does not include field writes, commands,
setpoints, control loops, Teams, Advisor, dashboards, or production data.

### Acceptance gates

1. EMQX accepts MQTT only on the mutual-TLS listener at port 8883; plaintext port 1883 is closed.
2. A node certificate can publish only below its own `openaut/<site>/<node>/#` prefix.
3. The separate `ingest` certificate can subscribe to `openaut/#` but cannot publish telemetry.
4. Missing and untrusted certificates are rejected; a valid certificate's wrong-scope publication
   is denied by authorization and not delivered.
5. Synthetic telemetry and `$status` messages are stored in the expected TimescaleDB hypertables.
6. The `agent_ro` database role can read but cannot insert or update telemetry.
7. A read-only IOT2050 publisher is added only after the synthetic end-to-end path passes.
8. Broker or database failure does not cause a field write or affect local equipment operation.

The first IOT2050 milestone may publish synthetic values. A real BACnet or Modbus read is a separate
gate because the current reference edge agent has no hardware driver implementation.

## POC2: approved Engineer handoff

Prove that an Engineer action starts from reviewed state rather than chat or an untrusted prompt:

```text
human-created test case -> human approval -> Engineer/opencode -> Forgejo branch and PR -> audit
```

Advisor remains optional and may be represented by a fixture or human-created case. POC2 does not
permit a field write or deployment to the IOT2050.

### Acceptance gates

1. Migration-managed Systemdatabas tables exist for equipment, points, documents, cases, approvals,
   generated artifacts, and audit events.
2. A draft, rejected, expired, or unapproved case is refused by the Engineer workflow.
3. Forgejo is available only on the management network and uses a human-controlled admin account.
4. Engineer uses a scoped Forgejo identity that can create a branch and pull request but cannot
   change protection or self-merge the protected branch.
5. A reviewed Forge revision and independent document SHA-256 are linked to the approved case.
6. Case transitions and Forge evidence produce audit records.
7. No Teams endpoint, Advisor credential, Security credential, or field-write credential is present
   in Engineer's context.

## Deferred components

The following are outside POC1 and POC2: NemoClaw provisioning, Microsoft Teams, Security runtime,
Power BI/Grafana, production backup objectives, high availability, and any writable field point.

## Local verification status

Last updated: 2026-08-20. This is evidence from one isolated workstation lab, not a claim that the
same deployment has been reproduced elsewhere.

### POC1

- EMQX 5.8.9 CE, TimescaleDB 2.29.2/PostgreSQL 16, and the Python 3.12 ingest service run as
  digest-pinned containers on Platform.
- The broker exposes only its mutual-TLS listener on the field interface. Plain MQTT and WebSocket
  listeners are disabled; PostgreSQL and the EMQX dashboard are loopback-bound.
- Synthetic end-to-end verification passes: valid scoped publish, ingest subscription, rejected
  wrong-scope delivery, rejected cert-less connection, refused plaintext connection, telemetry and
  status rows in TimescaleDB, and denied `agent_ro` insert.
- Installing the client certificate and a read-only publisher on the physical IOT2050 is deliberately
  still pending human approval.

### POC2

- The migration-managed Systemdatabas tables and database roles are installed.
- Database verification passes: Engineer cannot start a draft case; a human-approved case can move
  to `in_progress`; request, approval, and start events are recorded in append-only audit data.
- Forgejo 16.0.2 runs rootless against a separate PostgreSQL database. Its HTTP and SSH listeners are
  bound to Platform loopback only, and the human admin has completed the forced password change.
- The private `openaut` organization has five repositories. Engineer is a restricted team member;
  all `main` branches allow only the human admin to push/merge and require one approval.
- TLS reverse proxy, secure delivery of the scoped Engineer token, and a complete branch/PR/audit
  evidence test remain pending. POC2 is therefore not yet accepted.

Detailed evidence and lessons are recorded in
[`verification/poc1-platform-verification.md`](verification/poc1-platform-verification.md) and
[`verification/poc2-systemdb-forgejo-verification.md`](verification/poc2-systemdb-forgejo-verification.md).
