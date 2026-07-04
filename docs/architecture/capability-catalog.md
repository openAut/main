# Proposed capability catalog

This catalog supports [ADR 0004](../adr/0004-mcp-gateway-capability-boundary.md). It sketches the
first capabilities openAut should reason about before building an MCP Gateway implementation.

The catalog is intentionally small. It is a review target, not a complete product backlog.

## Capability metadata

Each capability should eventually have at least:

| Field | Meaning |
|---|---|
| `id` | Stable capability identifier |
| `version` | Schema/policy version |
| `level` | `read`, `propose`, or `write` |
| `owner` | Accountable trust domain or governance owner |
| `risk` | `low`, `medium`, `high`, or `critical` |
| `allowed_agents` | Which trust domains may request it |
| `requires_case` | Whether a Systemdatabas case is required |
| `requires_approval` | Whether explicit approval is required |
| `side_effects` | Expected side effects |
| `backing_skill` | Skill/runbook that informs implementation |
| `audit_required` | Whether gateway audit is mandatory |
| `rollback` | Rollback or compensating-action expectation |

## Initial catalog

| Capability | Level | Risk | Allowed requesters | Purpose |
|---|---|---|---|---|
| `get_equipment_context` | read | low | Advisor, Engineer, Security | Read equipment, point, site, and relationship data from the Systemdatabas. |
| `query_timeseries` | read | low | Advisor, Engineer, Security | Query telemetry windows for diagnosis, energy analysis, and verification. |
| `read_verified_document` | read | low | Advisor, Engineer, Security | Retrieve verified manuals, runbooks, point maps, and generated docs from Forge/document store. |
| `read_mqtt_health` | read | medium | Advisor, Engineer, Security | Inspect broker/topic/client health without publishing. |
| `read_field_point` | read | medium | Advisor, Engineer | Read a field point through an approved edge/protocol adapter. |
| `create_case_note` | propose | low | Advisor, Engineer, Security | Append an observation, finding, or operator-facing explanation to a case. |
| `create_work_order` | propose | medium | Advisor, Engineer | Create a work order or task proposal for human review. |
| `propose_setpoint_change` | propose | high | Advisor, Engineer | Propose a setpoint/control change with evidence, expected impact, and approval path. |
| `draft_edge_deploy_plan` | propose | high | Engineer | Produce a deploy plan, diff, validation plan, and rollback plan for an edge change. |
| `open_change_pr` | propose | medium | Engineer | Open a Forge/PR change for reviewed code, config, docs, or deployment artifacts. |
| `deploy_edge_config` | write | high | Engineer | Deploy approved edge configuration to in-scope nodes. |
| `publish_mqtt_command` | write | critical | Engineer | Publish a validated command envelope to an approved MQTT command topic. |
| `enroll_edge_node` | write | critical | Engineer | Enroll a new edge node, credentials, topic scope, and Systemdatabas records. |
| `rotate_node_certificate` | write | high | Engineer | Rotate a node certificate through the approved PKI and rollout plan. |
| `emit_security_alert` | propose | medium | Security | Send an isolated security alert without operational write authority. |
| `read_ot_asset_inventory` | read | medium | Security, Advisor, Engineer | Read approved OT inventory data for BMS/SCADA, controllers, gateways, edge nodes, certificates, and network zones. |
| `read_ot_security_events` | read | medium | Security | Read OT security-relevant logs and events from gateway audit, MQTT, edge, network, Forge, and identity sources. |
| `create_compliance_gap` | propose | medium | Security | Record a suspected AI Act, NIS2, CRA, IEC 62443, or ISO 27001 control gap for human review. |
| `propose_ot_risk_treatment` | propose | high | Security | Propose mitigations for asset, vulnerability, access-path, segmentation, or change-control risk without executing changes. |

## Example YAML shape

```yaml
id: propose_setpoint_change
version: 1
level: propose
owner: Engineer
risk: high
allowed_agents:
  - Advisor
  - Engineer
requires_case: true
requires_approval: true
side_effects: none
backing_skill:
  - fdd
  - energy-optimization
audit_required: true
rollback: not_applicable_until_write
```

```yaml
id: publish_mqtt_command
version: 1
level: write
owner: Engineer
risk: critical
allowed_agents:
  - Engineer
requires_case: true
requires_approval: true
side_effects: publishes_command_to_ot_path
backing_skill:
  - mqtt-tls-broker
audit_required: true
rollback: required_compensating_action
```

## Review questions

- Are `read_field_point` and `query_timeseries` separate enough, or should all live field reads go
  through telemetry first?
- Should `open_change_pr` be considered propose-only even when it creates a branch in Forge?
- Should `publish_mqtt_command` exist at all in the first production architecture, or should writes
  be limited to edge deploy plans until interlocks are mature?
- Which capabilities need Security-readable audit events before implementation starts?
- Which capability ids should POC1 and POC2 use first?
- Which OT estate sources should openAut Security read first: inventory, network logs, certificates,
  supplier access, vulnerability data, or change records?
