---
name: "secure-agent-workspace"
description: "Design, review, or operationalize secure managed workspaces for autonomous agents using NVIDIA's Secure Agent Workspace reference pattern."

permissions:
  knowledge_only: true
  tools: "none"
  network: "none"
  exec: "none"
---

# Skill: secure-agent-workspace

## Description
Design, review, or operationalize secure managed workspaces for autonomous agents using NVIDIA's Secure Agent Workspace reference pattern.

## When to use
Use this skill when a user asks to:
- Design a secure environment for always-on/autonomous AI agents.
- Assess whether an agent workspace has adequate identity, network, credential, runtime, audit, and human-review controls.
- Translate an agent workflow into a governed blueprint with tools, allowed services, data scope, write gates, and logging.
- Compare maturity stages for secure agent execution: managed VM, brokered workspace, or signed-policy runtime sandbox.
- Plan deployment tiers for agent workspaces, from CPU VM proof-of-concept to fleet-managed enterprise rollout.
- Define requirements for access brokers, credential proxies, routed inference, runtime sandboxing, OCSF audit, revocation, or incident response.

Do not use this skill as a substitute for legal, compliance, or formal security certification advice. Treat it as architecture and implementation support grounded in NVIDIA's public reference design.

## Key concepts from the NVIDIA reference design

### Secure Agent Workspace pattern
- The user's endpoint is only a presentation layer: browser, terminal, IDE, agent app, or remote desktop.
- Agent execution happens in a managed remote workspace, typically a single-user VM that may be GPU-accelerated.
- The workspace is provisioned through an approved lifecycle, reached through a trusted broker, constrained by a runtime enforcement layer, and connected to enterprise systems through governed connectors.
- The workspace is not the same as the user session: the workspace can keep running while broker sessions are short-lived and re-authenticated.

### Threats the pattern is meant to reduce
- Unauthorized or accidental writes caused by operator error, prompt injection, or hijacked instructions.
- Data exfiltration to unlisted destinations, including exfiltration smuggled through writes.
- Prompt injection from untrusted documents, tickets, email, tool output, or upstream systems.
- Agent-as-attacker behavior such as scanning, exploitation, DoS, lateral movement, or connector abuse.
- In-VM compromise where the VM boundary helps protect the user's host, and Phase II controls reduce blast radius.

### Maturity model
- **Phase 0: enterprise managed-VM baseline** — configuration management, patching, vulnerability management, EDR/anti-malware, image governance, SOC telemetry, rebuild, and revocation.
- **Phase I: agent in a managed VM** — single-user governed workspace plus SSO/access broker, approved images, network-boundary allowlist, human review for sensitive writes, and workspace-edge audit logging.
- **Phase II: signed-policy runtime sandbox** — Phase I plus runtime sandbox enforcement at action boundaries: signed policy bundles, deny-by-default in-runtime egress, credential proxying, routed inference, filesystem/process scoping, policy attestation, and centrally signed policy distribution.

Phase II adds to Phase I; it does not replace Phase I.

### Architectural invariants
Preserve these invariants in every design review:
- No raw provider credentials reach the agent. A credential proxy exchanges scoped capabilities for provider credentials at egress.
- No self-granted authority. Agents cannot widen their own scope, tools, policy, or permissions; changes require control-plane policy/delegation changes.
- No connection to unlisted destinations. Platform egress and runtime egress should be deny-by-default and allowlist-driven.
- No tampering with system binaries or protected configuration paths. Runtime filesystem policy should confine writes to approved mutable areas.
- No agent-created persistence in shell hooks, startup files, MCP/agent configs, or similar auto-executed paths.
- No agent-controlled lifecycle. Sandbox creation, policy changes, image upgrades, and kill/revoke actions belong to the operator/control plane.
- No suppressed audit. Audit should be emitted from trust-boundary endpoints outside the agent's control.

### Seven-plane architecture summary
The reference design describes a managed workspace envelope around the usual agent loop. Important logical areas include:
- User endpoint: interface only; it attaches but does not execute the agent workload.
- Managed workspace VM: single-user execution and policy boundary.
- Runtime sandbox: kernel-level or equivalent runtime enforcement around agent operations.
- Workspace network boundary: brokered inbound access and governed outbound paths.
- Credential proxy/routed inference layer: secrets and model endpoint credentials stay outside agent context.
- Enterprise services: source control, ticketing, docs, SIEM, IdP, secret store, model services.
- Control plane: lifecycle, image governance, signed policies, delegation, revocation, and audit integration.

### Trusted access broker
The broker is an enterprise SSO-backed authentication and session-brokering service, not simply a VPN. It should:
- Authenticate users through enterprise IdP using OIDC/SAML, with no alternative login path.
- Issue short-lived browser-driven sessions; avoid long-lived tokens or client-side credential storage.
- Broker inbound user attach and multiplex per-session reverse tunnels for outbound corporate-network access.
- Emit OCSF-normalized session events to SIEM.
- Drop active sessions within seconds when SSO entitlement is revoked or a lifecycle kill switch is triggered.

### Network architecture
- No path into the workspace should bypass the trusted access broker.
- Corporate network resources should not be directly reachable from the workspace. The path should run through a reverse tunnel, trusted access broker, and corporate jump host/trust boundary.
- Internet egress should be deny-by-default and limited to approved destinations such as source repositories, partner agent endpoints, hosted inference, or approved SaaS.
- Phase I enforces allowlists at the platform/network boundary; Phase II also enforces them inside the runtime sandbox.
- Prefer protocol-aware/L7 controls where possible, constraining host, path, method, or equivalent attributes.

### Credential proxy and routed inference
- Credentials live in an enterprise secret store and are used only by the credential proxy.
- The agent receives a scoped, short-lived capability, never the raw OAuth token/API key/provider credential.
- The proxy resolves capabilities against the per-engagement delegation record, rewrites authorization at egress, and emits audit.
- Routed inference should follow the same capability model. The model endpoint is a dependency integrated through governed egress, not a workspace security feature by itself.
- Local inference and GPU acceleration are separate decisions. A workspace can use routed inference without a GPU, and a GPU can accelerate tools without hosting inference.

### Blueprint model
Blueprints are repeatable workflow templates on top of the workspace. Each blueprint should declare:
- Goal and intended user/sponsor.
- Required tools and integrations.
- Allowed services and destinations.
- Data classes and data scope.
- Autorun actions versus reviewed actions.
- Write boundaries and staging surfaces.
- Logging/audit expectations.
- Owner, review cadence, incident contact, and deprecation path.

A prompt is not a security boundary. Use hard deterministic controls — workspace perimeter, network allowlist, service auth, runtime sandbox, credential proxy, and human review — as the security boundary. Prompt hardening and LLM judges may complement but not replace those controls.

### Enterprise tool access model
Require three independent approvals before an agent can act:
1. **Network reach** — the destination is reachable from the workspace boundary and allowlisted.
2. **Per-service authentication** — service credentials are valid, scoped, and mediated by the proxy.
3. **Action class** — the blueprint permits the action type for the service and data scope.

Identity and authorization are separate:
- Identity chain: user/sponsor via SSO, workspace identity, logical agent identity, and per-call runtime credential.
- Authorization: a per-engagement delegation record that narrows the user's/sponsor's authority by task, scope, tools, duration, and approval mode.
- Delegation must be attenuating: child delegations can only narrow parent scope, never widen or reacquire dropped authority without fresh review and audit.

### Human review posture
- Read, search, summarize, and draft can often autorun when inputs are trusted and outputs are consumed by a human.
- Personal or ephemeral writes — scratch space, single-owner branches, private drafts, workspace-local notes — may be automated when reversible and low blast-radius.
- Shared, consequential, or hard-to-reverse writes require review: protected-branch merge, ticket state change, assignment, publish, send, delete, broadcast, package publish, data modification, or allowlist change.
- Realization pattern: agents write to private staging surfaces and propose changes for human approval rather than directly changing systems of record.

### Security and governance controls
The reference design groups controls into three necessary layers:
- Baseline managed-workspace controls: SSO broker, approved images/profiles, EDR, network allowlist, human review, lifecycle/session audit.
- Production runtime controls: kernel-level sandbox containment, deny-by-default egress, credential proxy, routed inference, filesystem/process controls, signed policies, OCSF audit, incident response, rollback path, identity/delegation enforcement.
- Signed-policy governance: centrally authored, signed, distributed, attested, and verified policy bundles.

A published data-classification policy is a prerequisite before enabling autonomous agents.

### Incident and revocation requirements
Prepare for compromise scenarios with:
- Per-workspace kill switch exposed via lifecycle API.
- Broker session termination and workspace stop/revoke.
- Delegation-record revocation to halt future capability issuance.
- Application token/session revocation where providers support it.
- Credential rotation for secrets held by the proxy, especially if the proxy is in-VM.
- Periodic VM image refresh/rebake to clear persistence.
- Central SSO entitlement revocation.
- Independent OCSF events from platform and runtime layers for SIEM correlation.
- Rollback path for runtime, connector, image, and policy releases.

### Operating properties
- Agents are owner- or sponsor-backed and operate under bounded per-engagement authority.
- Access is SSO-valid, portal-entitled, and broker-current; there is no workspace-grants-access fallback.
- Bootstrap the workspace before first terminal attach.
- The workspace profile is fixed at provisioning: image, OS family, resource/GPU shape, network profile, and policy bundle. Changing the profile requires reprovisioning.
- Workspaces are single-tenant. Collaboration happens through repos, tickets, docs, and chat, not by sharing a workspace.
- Workspace state is local and ephemeral relative to enterprise systems. Long-lived state belongs upstream; push frequently so rebuilds are not destructive.

### Deployment tiers
Choose the operational tier by scale and risk:
- CPU VM: starter POC for coding, documentation, and low-intensity workflows using routed inference.
- GPU VM/workstation: GPU-accelerated tools and test loops; routed inference remains default for frontier models.
- Deskside accelerated workstation: power users, researchers, local model options, or sensitive/sovereign contexts.
- Team shared system: shared hardware hosting separate per-user VMs/microVMs, never a shared workspace.
- Platform fleet: enterprise rollout with package channels, signed releases, policy distribution, telemetry, SIEM, rollback, support ownership, and incident process.

Sanitize GPUs and other stateful devices such as VRAM, caches, scratch storage, and local NVMe between users, usually by reprovisioning.

## Step-by-step procedure

### 1. Scope the agent workspace request
Ask or determine:
- What workflow will the agent perform?
- Who is the registered owner or sponsor?
- Which enterprise systems, datasets, model endpoints, and external services are needed?
- Which actions are read/search/summarize/draft versus consequential write/execute/publish/send/delete?
- Which data classifications are in scope?
- Is the agent expected to run while the user is offline?
- What is the required deployment scale: POC, team, regulated profile, or fleet?

If data classification is missing, mark the design blocked for autonomous operation until a classification policy exists.

### 2. Select the maturity target
Recommend the minimum acceptable phase:
- Phase 0 only: not sufficient for autonomous agents; use only as baseline prerequisite.
- Phase I: acceptable starting point for controlled pilots where workspace perimeter controls, allowlists, brokered access, human review, and audit are in place.
- Phase II: recommended for production autonomous agents, sensitive data, long-running unattended workflows, or where prompt injection / in-VM compromise blast radius must be reduced.

Document gaps between current and target phase.

### 3. Choose the deployment tier
Map the request to a tier:
- CPU VM for initial POC and most routed-inference coding/documentation flows.
- GPU VM/workstation when local acceleration helps tools/tests/notebooks.
- Deskside accelerated workstation for local model use or sensitive data that cannot leave the device.
- Team shared system only if each user gets a separate workspace VM/microVM and device state is sanitized between users.
- Platform fleet for broad rollout requiring centralized policy, telemetry, SIEM, budgets, package channels, support, and rollback.

State that routed inference is the default unless local inference is specifically justified.

### 4. Define the blueprint
Create a blueprint with:
- Name and goal.
- Owner/sponsor and incident contact.
- Tools and integrations.
- Allowed services and destinations.
- Data scope and data classes.
- Autorun actions.
- Human-reviewed actions.
- Staging surfaces for drafts and proposed changes.
- Audit events and retention expectations.
- Review cadence and deprecation path.

Keep defaults least-privilege and read-only where possible.

### 5. Define identity and delegation
Specify:
- SSO/IdP source for user or sponsor identity.
- Workspace identity and attestation expectation.
- Logical agent registration.
- Per-engagement delegation record: task, scope, tools, resources, duration, approval mode.
- Per-sandbox or per-call runtime credential rotation.
- Revocation path for delegation records.

Ensure child delegations only narrow scope.

### 6. Design network access
For each required destination:
- Classify it as corporate-network, approved internet/SaaS, model endpoint, or denied/out of scope.
- Add only required hosts/paths/methods/protocols to allowlists.
- Route corporate-network access through the broker/reverse tunnel/jump-host trust boundary.
- Enforce platform egress deny-by-default for Phase I.
- Add in-runtime deny-by-default egress for Phase II.
- Explicitly reject broad public-internet reach unless the task is moved to a separate public data sandbox.

### 7. Design credential and inference mediation
For each service/model endpoint:
- Keep provider credentials in the enterprise secret store.
- Route service calls through the credential proxy.
- Give the agent scoped short-lived capabilities, not raw secrets.
- Bind capability issuance to the delegation record.
- Emit audit for capability use.
- Prefer structured integrations: scoped MCP server over CLI client, CLI over ad-hoc script.
- Use routed inference through the same credential/capability model unless local inference is required and isolated from the agent runtime.

### 8. Define runtime filesystem/process controls
For Phase II or production designs, require:
- Runtime sandbox around all agent operations, including shell, code execution, hooks, MCP servers, and skills.
- Writes confined to allowed mutable workspace areas.
- Reads denied outside declared scope by default.
- Deny-write protections for startup files, shell hooks, MCP/agent configuration, and other persistence paths.
- Filesystem and process scoping backed by kernel, namespace, microVM, LSM, or equivalent enforcement.
- Runtime action decisions bound to signed policy.

### 9. Define human-review gates
Classify actions:
- Autorun: read, search, summarize, draft, run tests in workspace, write to private/reversible staging surfaces.
- Review required: merge to protected branch, publish docs, send/broadcast/reply-all, delete/archive, state change, assignment, package publish, data write/update/delete, allowlist change, unapproved endpoint, restricted data sent to model.

Design staging surfaces:
- Code: feature branch + MR/PR.
- Docs: draft or unpublished revision.
- Tickets: proposed comment/state change.
- Mail/chat: draft message, not sent.
- Data: proposed change record or reviewed job.

### 10. Define audit, monitoring, and revocation
Require:
- OCSF-normalized audit from broker/session, workspace lifecycle, runtime action, credential proxy, and human-review gates.
- SIEM correlation rules for anomalous egress, denied actions, unusual lifecycle calls, and repeated review overrides.
- Workspace lifecycle API with stop/revoke/rebake.
- Per-workspace kill switch.
- SSO entitlement revocation propagation.
- Delegation revocation that stops future capability issuance.
- Secret rotation and application session/token revocation plan.

### 11. Define release and rollback process
For policies, images, connectors, runtime, and blueprints:
- Use approved images and profiles only.
- Sign policy bundles and releases.
- Distribute through controlled channels.
- Attest policy at boot and verify per call where supported.
- Maintain rollback path for runtime, connector, image, and policy releases.
- Assign owner, support path, review cadence, and deprecation path.

### 12. Produce the review output
Return a concise architecture review containing:
- Recommended maturity phase and deployment tier.
- Blueprint summary.
- Required controls.
- Autorun versus human-reviewed action matrix.
- Network and credential mediation plan.
- Audit/revocation/incident response plan.
- Gaps, blockers, and assumptions.
- References used.

## Examples

### Example 1: Coding assistant pilot
**Request:** A team wants a coding agent that can read repositories, draft patches, run tests, and open pull requests.
**Recommended design:**
- Tier: CPU VM for POC, GPU VM only if tests or tooling benefit from local acceleration.
- Maturity: Phase I minimum; Phase II for production.
- Blueprint: coding assistant.
- Autorun: clone/read repo, inspect issues, create feature branch, draft patch, run tests inside sandbox, write branch in single-owner namespace.
- Review required: merge to protected branch, tag/release, change repository settings, publish package.
- Network: allowlist source control, package mirrors, CI logs, ticketing; no broad internet.
- Credentials: source control/package credentials held by credential proxy; agent gets scoped capabilities.
- Audit: branch writes, review requests, denied egress, credential use, session lifecycle.

### Example 2: Knowledge worker assistant
**Request:** An agent searches mail, chat, docs, and tickets to summarize context and draft responses.
**Recommended design:**
- Tier: CPU VM with routed inference.
- Maturity: Phase I for pilot; Phase II if mail/chat data includes sensitive classifications.
- Autorun: search/read within explicit mailbox/chat/doc scopes; summarize; create private drafts.
- Review required: send, forward, reply-all, delete/archive, broadcast/channel post, publish to shared docs.
- Credential model: mailbox/chat/docs connectors through scoped structured integrations; raw tokens never exposed to the agent.
- Human gate: drafts are private and reversible; sending is the consequential write.

### Example 3: Operations assistant
**Request:** An agent correlates alerts, reads logs, drafts remediation, and may execute runbooks.
**Recommended design:**
- Tier: CPU or GPU VM depending on log volume/tooling; platform fleet if broad operations rollout.
- Maturity: Phase II strongly recommended because the workflow touches operational systems.
- Autorun: read alerts/logs/runbooks, summarize, draft remediation steps, create proposed ticket update.
- Review required: execute remediation, change service state, close incident, alter monitoring rules, write to shared runbooks.
- Network: strict allowlists to log, ticket, runbook, and approved internal endpoints only.
- Incident response: kill switch, delegation revocation, credential rotation, SIEM correlation, rollback for connector/policy releases.

### Example 4: Research notebook assistant
**Request:** A researcher wants long-running notebooks over sensitive datasets.
**Recommended design:**
- Tier: GPU VM/workstation or deskside accelerated workstation if local acceleration or local inference is required.
- Maturity: Phase II for sensitive datasets.
- Data scope: explicit dataset allowlist and data-class policy.
- Autorun: query/read permitted datasets, run notebooks in sandbox, write workspace-local outputs.
- Review required: publish, export outside scope, write/update/delete shared data, send restricted data to non-default model endpoint.
- Operations: push long-lived state to approved storage; workspace state is ephemeral and rebuildable.

## Review checklist
Use this checklist before approving a secure agent workspace design:
- [ ] Registered owner/sponsor identified.
- [ ] Data classification policy exists.
- [ ] Per-engagement delegation record defined.
- [ ] Workspace is single-tenant.
- [ ] Approved image/profile selected.
- [ ] SSO-only trusted access broker required.
- [ ] No inbound path bypasses broker.
- [ ] Corporate resources route through broker/jump-host trust boundary.
- [ ] Egress is deny-by-default and allowlisted.
- [ ] Runtime sandbox covers shell, code, hooks, MCP servers, and skills.
- [ ] Credential proxy prevents raw secrets from reaching agent context.
- [ ] Routed inference or local inference path is mediated and allowlisted.
- [ ] Autorun and reviewed actions are explicitly separated.
- [ ] Shared/consequential writes require human review.
- [ ] Staging surfaces are private and reversible.
- [ ] OCSF audit goes to SIEM from broker, perimeter, runtime, and credential layers.
- [ ] Kill switch, delegation revocation, SSO revocation, token/session revocation, and secret rotation are defined.
- [ ] Policy/image/runtime/connector rollback path exists.
- [ ] Owner, review cadence, incident contact, and deprecation path exist for each blueprint.
- [ ] Device state sanitization is defined for shared GPU/stateful hardware.

## References
- NVIDIA, **Secure Agent Workspace Reference Design** index: https://docs.nvidia.com/enterprise-reference-architectures/secure-agent-workspace-reference-design/latest/index.html
- NVIDIA, **Always-on, Autonomous Agents, Now Safe for the AI Factory**: https://docs.nvidia.com/enterprise-reference-architectures/secure-agent-workspace-reference-design/latest/abstract.html
- NVIDIA, **Reference Architecture**: https://docs.nvidia.com/enterprise-reference-architectures/secure-agent-workspace-reference-design/latest/reference-architecture.html
- NVIDIA, **Agent Blueprint Patterns**: https://docs.nvidia.com/enterprise-reference-architectures/secure-agent-workspace-reference-design/latest/agent-blueprint-patterns.html
- NVIDIA, **Enterprise Tool Access Model**: https://docs.nvidia.com/enterprise-reference-architectures/secure-agent-workspace-reference-design/latest/enterprise-tool-access-model.html
- NVIDIA, **Security and Governance Model**: https://docs.nvidia.com/enterprise-reference-architectures/secure-agent-workspace-reference-design/latest/security-and-governance-model.html
- NVIDIA, **Operating Properties**: https://docs.nvidia.com/enterprise-reference-architectures/secure-agent-workspace-reference-design/latest/operating-properties.html
- NVIDIA, **Deployment Tiers**: https://docs.nvidia.com/enterprise-reference-architectures/secure-agent-workspace-reference-design/latest/deployment-tiers.html

## Notes for Skill Workshop conversion
If installed as an OpenClaw skill, keep the frontmatter concise:

```yaml
---
name: secure-agent-workspace
description: "Design or review secure managed workspaces for autonomous agents."
---
```

Keep this proposal as the detailed reference body. If the live skill must be shorter, move the longer examples/checklists into `references/secure-agent-workspace-reference.md` and keep only trigger guidance plus the main workflow in `SKILL.md`.
