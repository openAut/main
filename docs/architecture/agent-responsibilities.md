# Agent responsibilities and enforcement boundaries

This document supports [ADR 0004](../adr/0004-mcp-gateway-capability-boundary.md). It is a proposed
responsibility map, not an implementation contract.

## Summary

openAut should keep OpenClaw and opencode, but avoid making either one the final security boundary.
The name **openAut** still covers the broader OT/AI control architecture, not just the agent runtime.

```text
Teams / UI / operators
        |
        v
OpenClaw / Advisor runtime
dialog, role behavior, planning, recommendations
        |
        v
MCP Gateway / capability gateway
policy, schemas, approvals, audit, rate limits
        |
        v
Certified capabilities
read, propose, write operations with owners and risk classes
        |
        v
MQTT, Systemdatabas, Forge, edge nodes, field protocols, dashboards
```

Engineer is the privileged change actor, backed by opencode, but it also requests external actions
through governed capabilities. Security is still **openAut Security**; its watch-only scope extends
across the openAut deployment and the wider OT estate.

## Responsibility table

| Component | Responsible for | Not responsible for |
|---|---|---|
| OpenClaw / Advisor runtime | Dialog, planning, memory/context, persona behavior, recommendations, human explanation, workflow orchestration | Final authorization, raw OT access, secrets, rate limiting, durable audit root |
| opencode / Engineer | Code/config/deploy work, diffs, PRs, troubleshooting, approved edge integration, signed-release and case-bound operational work | Bypassing gateway policy, changing its own permission profile, direct unsupervised OT writes |
| openAut Security | Independent observation across openAut and the wider OT estate, passive monitoring, compliance evidence, alerting, audit review, prompt/social-engineering detection | Operational writes, muting Engineer, changing PAP policy |
| PAP / governance authority | Role definitions, signed permission profiles, capability policy authorship, approval rules | Runtime tool execution, agent reasoning, day-2 troubleshooting |
| MCP Gateway / capability gateway | Tool routing, schema enforcement, policy decisions, approval checks, rate limits, audit, target scoping, capability versioning | Agent planning, natural-language dialog, business reasoning |
| Capabilities | Narrow operations such as read point, query telemetry, propose setpoint, create work order, publish validated command | Broad system access, hidden side effects, self-authorizing permissions |
| Skills | Runbooks, implementation references, protocol knowledge, backing logic for selected capabilities | Authority grants, direct production tool permissions |

## Read, propose, write

Use these levels consistently when describing agent powers:

| Level | Meaning | Examples | Default control |
|---|---|---|---|
| Read | Observe data or state without side effects | `query_timeseries`, `read_bacnet_point`, `get_case`, `read_verified_manual` | Least privilege, audited |
| Propose | Create a recommendation or request without field side effects | `propose_setpoint_change`, `create_work_order`, `draft_deploy_plan`, `open_pr` | Case-bound, reviewable |
| Write | Change runtime state, deploy code, enroll assets, publish commands | `publish_mqtt_command`, `deploy_edge_config`, `enroll_edge_node`, `rotate_node_cert` | Explicit approval, validation, rollback plan, Security audit |

## Practical rules

1. Say "agent requests a capability", not "agent controls the system".
2. Advisor can propose operational changes, but cannot execute OT writes.
3. Engineer can execute approved changes, but cannot widen its own authority.
4. Security observes independently and must not depend on Engineer-controlled logs.
5. Capabilities should be small enough that their side effects can be understood in one review.
6. Any broad tool should be split before it reaches production architecture.
7. Gateway denial is a normal outcome and should be visible to the user as a safe stop, not a system
   error.
8. openAut Security should monitor the OT context around openAut, not only openAut's own agent and
   gateway events.

## First-slice responsibility target

For the first RFC/ADR implementation slice, keep the scope small:

- Read-only telemetry and equipment lookup through the gateway.
- Propose-only work-order and setpoint recommendation capabilities.
- No production write capability.
- Capability audit events modeled in the Systemdatabas before real writes.
- Existing skills unchanged except for documentation that maps them to future capabilities.
- openAut Security reads enough OT inventory, network, certificate, vulnerability, supplier-access,
  and change evidence to reason about compliance and risk beyond openAut-internal services.
