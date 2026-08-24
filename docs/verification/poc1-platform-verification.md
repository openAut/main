# POC1 Platform verification

- **Date:** 2026-08-20
- **Scope:** isolated workstation lab; synthetic data only
- **Result:** synthetic POC1 acceptance gates passed

## Verified stack

| Component | Verified version |
|---|---|
| EMQX Community Edition | 5.8.9 |
| TimescaleDB | 2.29.2 |
| PostgreSQL | 16 |
| Python ingest runtime | 3.12 |
| Paho MQTT | 2.1.0 |
| psycopg | 3.3.4 |

Container base images are digest-pinned in `deploy/platform-poc1/compose.yaml` and the ingest
Dockerfile. Local passwords, PKI material, runtime copies, and `.env` are gitignored.

## Evidence

The verification script proved:

1. The EMQX mutual-TLS listener accepted a valid edge certificate.
2. The separate `ingest` certificate subscribed to `openaut/#`.
3. A publish outside the edge certificate's own `<site>/<node>` scope was not delivered.
4. The `ingest` service certificate could subscribe but could not publish telemetry.
5. A client without a certificate and a certificate from an untrusted CA were rejected.
6. Plain MQTT port 1883 was refused.
7. Synthetic telemetry and `$status` messages produced one matching row in each TimescaleDB
   hypertable.
8. TimescaleDB reported two telemetry hypertables.
9. `agent_ro` could SELECT and was denied INSERT and UPDATE.
10. The repository's 11 Python unit tests passed in the pinned Python 3.12 image.

The final script result was:

```text
POC1_OK telemetry=1 status=1 timescaledb=2.29.2 hypertables=2 agent_ro_select=allowed agent_ro_write=denied
```

## Lessons

- An EMQX container's shipped configuration must be extended rather than replaced; replacing it
  removes required node settings.
- EMQX ships additional TCP/WebSocket listeners. Unused plaintext and WebSocket listeners must be
  explicitly disabled rather than merely left unpublished by Compose.
- `deny_action = ignore` can make a publisher CLI exit successfully even though EMQX discards the
  message. Wrong-scope authorization must therefore be tested by proving non-delivery, not only by
  checking the publisher's exit code.
- Edge publisher and ingest subscriber need separate certificate identities. The original helper
  generated only site/node certificates and could not create the `ingest` identity used by the ACL.
- Compose file-backed secrets retain host file permissions. Non-root container UIDs must be able to
  read their mounted secret while the parent host directory remains inaccessible to other users.
- PostgreSQL initialization scripts run only for an empty data volume. Role-password remediation
  must be a separate idempotent operation after a partially failed first initialization.

## Not yet verified

- No certificate or publisher has been installed on the physical IOT2050.
- The edge protocol read remains synthetic; no BACnet or Modbus driver was exercised.
- Store-and-forward PUBACK semantics and prolonged outage recovery remain open.
- Host firewalling, backup/restore, certificate rotation, and stable addressing are not complete.
