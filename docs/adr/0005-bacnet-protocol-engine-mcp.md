# ADR 0005 — BACnet protocol engine and MCP integration

- **Status:** Proposed — evaluation only
- **Date:** 2026-10-15
- **Related:** [BACnet skill](../../skills/bacnet/SKILL.md), [edge-iot2050](../../skills/edge-iot2050/SKILL.md), [architecture](../ARCHITECTURE.md), [ADR 0004](0004-edge-control-writes-and-continuity.md)
- **Candidates:** [BACpypes3](https://github.com/JoelBender/BACpypes3), [BAC0](https://github.com/ChristianTremblay/BAC0)

## Context

The BACnet skill currently references BAC0/BACpypes3 for BACnet/IP access on edge nodes. The edge-iot2050 reference poller's field read remains a stub. openAut needs read-only telemetry collection and a separate, carefully mediated interface for AI-agent discovery and diagnostics.

BAC0 offers a higher-level Python API and uses BACpypes3; BACpypes3 provides lower-level protocol control. Native MCP capabilities, if any, must be verified against the upstream source and tested rather than assumed.

## Proposed direction (not an accepted decision)

1. Evaluate BACpypes3 as the primary BACnet protocol engine; retain BAC0 as an option until comparative tests are complete.
2. Keep continuous polling and MQTT publishing independent of agent-driven MCP requests. Preserve the existing edge MQTT/TLS and spool contracts.
3. Implement a narrow, read-only BACnet MCP adapter/service for discovery, object enumeration, ReadProperty and ReadPropertyMultiple, after validating the upstream MCP implementation and dependencies.
4. Deploy BACnet access on a field-side edge host. Do not grant Advisor unrestricted BACnet/OT network access. Explicitly design an authenticated, allowlisted, audited intermediary and review trust boundaries before enabling remote MCP calls.
5. Exclude writes, overrides and setpoint changes from this POC. Any future writable path requires a separate design aligned with ADR 0004 and its human approval, interlocks and continuity requirements.
6. Record protocol errors, timeouts, device identity, data quality and audit events without leaking credentials or sensitive network inventory.

## Evaluation criteria

- BACnet/IP Who-Is/I-Am discovery across realistic network boundaries; direct addressing where needed
- ReadProperty, ReadPropertyMultiple, objectList, units, statusFlags and reliability
- Device ID/address handling, timeouts, retries, concurrency, reconnect and load on DUC/PLC
- BAC0 versus direct BACpypes3 implementation complexity and operational reliability
- MCP server existence, maintained API, authentication, transport, dependency and sandbox compatibility
- IOT2050 resource footprint and offline dependency packaging
- Integration with existing point maps, MQTT topic schema, Systemdatabas and TimescaleDB
- Test isolation, read-only enforcement, threat model and negative security tests

## Acceptance criteria

A laboratory BACnet device can be discovered and queried read-only; readings map through the existing edge-poller path to MQTT; an approved agent can request narrowly scoped diagnostics via MCP; failures and denied operations are logged; no writable operation or direct Advisor-to-OT access is possible.

## Decision status

No library replacement or MCP deployment is approved by this ADR. Update the BACnet and edge skills, and the architecture document, only after the evaluation resolves the open questions.
