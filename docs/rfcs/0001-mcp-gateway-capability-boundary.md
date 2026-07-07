# RFC 0001 - MCP Gateway and governed capability boundary

- **Status:** RFC / discussion draft (not an accepted architecture decision - nothing wired yet)
- **Date:** 2026-07-04
- **Note:** originally drafted as an ADR 0004 candidate; moved to RFC form during the #52
  stabilization pass because ADR 0004 was already taken by
  [`0004-edge-control-writes-and-continuity`](../adr/0004-edge-control-writes-and-continuity.md),
  and this proposal had not yet gone through review. If and when this direction is accepted, it
  should be promoted to the next free ADR number (currently ADR 0005).
- **Builds on:** [`0001-delivery-and-trust-model`](../adr/0001-delivery-and-trust-model.md), [`0002-access-control-and-roles`](../adr/0002-access-control-and-roles.md), [`0003-engineer-runtime-containment`](../adr/0003-engineer-runtime-containment.md), [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md)

## Context

openAut already separates the runtime trust domains across the wider OT estate:

- **Advisor** is read-only, Teams-facing, and primarily NemoClaw/OpenClaw-backed.
- **Engineer** is opencode-backed, SSH/deploy capable, case-scoped, and not exposed to Teams.
- **Security** is watch-only and independent from operational control. Its scope is the openAut
  deployment **and the wider OT estate**: BMS/SCADA, edge nodes, gateways, network zones, accounts,
  certificates, firmware/software versions, supplier access paths, and evidence for security and
  regulatory controls.

The current architecture also defines skills for field protocols, analytics, compliance, the
Systemdatabas, local Forge, edge provisioning, and the MQTT/TLS backbone. Those skills are useful
runbooks and implementation references, but they do not by themselves define a hard enterprise
boundary between agent reasoning and system execution.

For an OT-adjacent building-management project, that boundary must be explicit before write paths
mature. An agent should not gain direct access to field systems, databases, MQTT command topics, SSH
deploy paths, Teams actions, or Forge operations merely because it can load a skill. Skills should
back narrowly approved capabilities, and all external tool use should pass through a governed
enforcement point.

## Decision

**1. Introduce an MCP Gateway / capability gateway as the required tool boundary.** All agent access
to external systems goes through a governed gateway that exposes versioned capabilities with typed
schemas, policy enforcement, audit, rate limits, and approval checks. Direct agent-to-system access is
allowed only for local development experiments explicitly marked outside the production architecture.

**2. Treat capabilities as the unit of authority.** A capability is a narrow, versioned operation such
as `query_timeseries`, `read_bacnet_point`, `create_work_order`, `propose_setpoint_change`, or
`publish_mqtt_command`. Capabilities are cataloged with owners, risk class, allowed agents, side
effects, approval requirements, schemas, and audit fields. See
[`docs/architecture/capability-catalog.md`](../architecture/capability-catalog.md).

**3. Reframe skills as backing implementations, not free agent tools.** Protocol and runtime skills
remain valuable, but they do not grant authority. For example, the Modbus skill can back selected
Modbus read capabilities exposed by the gateway; it does not mean an agent may freely read or write
Modbus registers.

**4. Keep OpenClaw and opencode, but narrow their responsibility.** OpenClaw remains the agent
runtime/orchestration layer for dialog, planning, role behavior, memory, and workflow. Engineer
remains opencode-backed for code, configuration, deployment, and troubleshooting work. Neither
OpenClaw nor opencode is the final authorization boundary for external systems; both request
capabilities through the gateway. See
[`docs/architecture/agent-responsibilities.md`](../architecture/agent-responsibilities.md).

**5. Separate read, propose, and write.**

- **Read:** observe telemetry, documents, status, logs, and configuration through least-privilege
  capabilities.
- **Propose:** create recommendations, work orders, control plans, pull requests, and approval
  requests without direct field side effects.
- **Write:** change configuration, deploy code, publish commands, enroll nodes, or affect OT/IT
  systems only through high-risk capabilities with case binding, approval, validation, audit, and a
  rollback or compensating-action plan.

**6. Make OT writes gateway-enforced.** Any capability that can affect field devices, MQTT command
topics, edge configuration, credentials, or deployment state requires explicit approval and command
validation. Advisor may propose. Engineer may execute only under a PAP-authored permission profile,
active Systemdatabas case, and gateway-enforced capability policy.

**7. Log capability use as first-class evidence.** Gateway audit must include agent identity,
permission profile, user/case attribution, capability id/version, input hash or redacted input,
policy decision, approval reference, target asset scope, output status, and links to Security's
append-only audit stream where applicable.

**8. Keep the name openAut for the estate-wide control function.** The gateway boundary does not
turn openAut into a narrow agent component. openAut remains the name for the broader architecture
spanning agents, gateway, capabilities, telemetry, edge, OT inventory, governance, and security
evidence. "openAut Security" is the independent Security trust domain for that whole architecture,
not a separate product name and not a monitor limited to openAut-internal services.

## Consequences

- The openAut architecture becomes capability-centered rather than agent-centered. Agents can reason
  broadly, but they act only through narrow, governed operations.
- The gateway becomes a critical security component. It must be designed, tested, versioned, and
  audited with the same care as the MQTT/TLS broker, Systemdatabas, and release pipeline.
- OpenClaw is not removed. It becomes cleaner: agent runtime and orchestration above the gateway,
  instead of also carrying authorization, secrets, audit, and backend integration concerns.
- opencode remains the right substrate for Engineer, but it cannot bypass gateway policy for
  external systems. Its local shell/deploy authority is still bounded by ADR 0001 and ADR 0003.
- Existing skills remain useful, but their documentation should gradually say which capabilities
  they back and whether those capabilities are read, propose, or write.
- Security's scope becomes clearer: it monitors openAut-controlled actions and the surrounding OT
  environment they affect, so compliance and anomaly detection are not limited to agent activity.
- More metadata is required before implementation: capability catalog entries, schemas, risk
  classes, policy mappings, and audit contracts.

## Migration path

1. Add the proposed capability catalog and responsibility map as reviewable documentation.
2. Identify the first 8-12 capabilities needed by POC1/POC2 and the Advisor/Engineer handoff.
3. Update relevant skills to name the capabilities they back, without changing their scripts yet.
4. Model capability requests, approvals, and audit events in the Systemdatabas contract.
5. Implement a thin gateway facade for read-only capabilities first.
6. Add propose-only capabilities for work orders, control plans, and PR/deploy requests.
7. Add write capabilities last, gated by case binding, approval, validation, and Security audit.

## Alternatives considered

- **Let agents call skills directly.** Rejected for production architecture: it makes each agent and
  skill carry too much security responsibility and blurs the boundary between reasoning and execution.
- **Make OpenClaw the gateway.** Rejected: OpenClaw should orchestrate agent behavior, not also be the
  policy enforcement point, secrets boundary, and audit root for all external systems.
- **Make opencode/Engineer the gateway for operational changes.** Rejected: Engineer is the most
  privileged operational actor and must be constrained by an independent capability boundary, not
  trusted as its own final enforcer.
- **Delay the gateway until after POCs.** Rejected as a default: POCs can stay local and marked
  non-production, but the architecture should name the boundary now so prototypes do not normalize
  direct system access.

## Compliance alignment

*Working aid, not legal advice; verify against source texts before binding decisions.*

- **IEC 62443:** capability policy and gateway enforcement support least privilege, restricted data
  flow, use control, and zone/conduit separation.
- **NIS2:** capability audit, approval, and controlled change paths support supply-chain and access
  control evidence for deployment targets that are in scope.
- **CRA:** versioned capabilities, SBOM-backed releases, and signed/attested gateway components
  support future product-security expectations if openAut components are later distributed.
- **AI governance:** an ADLC-style capability catalog gives evidence for risk, owners, tests,
  approvals, monitoring, and decommissioning.

## Open questions

- Should the first gateway be a thin MCP facade over existing tools, or a fuller policy engine from
  the beginning?
- Where should capability definitions live long-term: YAML in Main, Systemdatabas records, or both?
- How should gateway policy map to PAP-authored permission profiles from ADR 0002?
- Which exact POC1/POC2 capabilities should be the first implementation slice?
- What is the minimum audit schema needed before any write capability can exist?
- Should the gateway be colocated with the AI/management tier, or split into separate read/propose
  and write gateways?
