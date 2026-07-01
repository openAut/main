# openAut — canonical glossary

The project deliberately keeps three concepts apart. They are orthogonal: a *persona*
describes **who** consumes an insight, an *agent / trust domain* describes **what the
system is allowed to do**, and a *runtime skill* is a **capability** an agent carries.
Earlier drafts called the personas "role agents", which conflated the first two; this
glossary is the single source of truth.

## persona (operatörsroll)

A human-facing **job-to-be-done**. Defined by *which insight* a person needs, not by any
permission. The three openAut personas are **Driftstekniker** (operations technician),
**Energisamordnare** (energy coordinator), and **Förvaltare** (technical manager). A
persona is **realised through** the trust domains (chiefly Advisor); a persona is *not*
itself an agent or a trust domain. See [`skills/nemoclaw-agent-workflow`](skills/nemoclaw-agent-workflow/SKILL.md).

## styrentreprenör (external control contractor)

An **external operator** a public-sector asset owner (Region / Kommun) procures to troubleshoot
and install edge nodes. Modelled as a **persona realised through Engineer** under a scoped,
time-bounded **external-contractor permission profile** (just-in-time / break-glass, PAM) — *not*
a fourth agent or trust domain. Distinct from the three internal insight-personas: its
job-to-be-done is engineering work, it is external and lower-trust, and edge-node onboarding
(which extends the perimeter) is gated behind asset-owner approval via a Systemdatabas case. It
can reach **only** its Engineer profile — never Advisor, Security, the PAP, or its own profile.
It is **one named instance of the general permission-profile pattern** (see *permission profile*);
internal operational roles bind to Engineer the same way, differing only in scope / trust /
duration.
_Avoid_: Core access, contractor agent, sub-admin.

## agent / trust domain

An **agent** with its own identity, credentials, sandbox, and tool allow-list, defined by
*what behaviour it is permitted*. openAut has three: **Advisor** (read-only, Teams-facing),
**Engineer** (SSH/deploy capable, not exposed to Teams), and **Security** (separate,
read-only watch-and-audit instance that can see but cannot steer). The trust boundaries and
the Systemdatabas approval handoff are defined in
[`skills/advisor-engineer-workflow`](skills/advisor-engineer-workflow/SKILL.md); the
Security domain's canonical runbook is [`skills/security-instance`](skills/security-instance/SKILL.md).

These three names are **descriptive**; their standard-vocabulary anchors (for procurement and
security review) are **Advisor ≈ Reader/Viewer**, **Engineer ≈ the SCADA/DCS "Engineer" tier
bounded by least privilege** (NIST SP 800-53 AC-6, IEC 62443 FR2 *Use Control*), and **Security
≈ Auditor**, the separation-of-duties oversight role (NIST AC-5). The model is **two orthogonal
axes** — an operational-privilege axis (Advisor *read* vs Engineer *write*) and an independent
oversight axis (Security / Auditor) — not a single ladder. See
[`docs/adr/0002-access-control-and-roles`](docs/adr/0002-access-control-and-roles.md).

## policy-authority point (PAP)

The boundary that **owns role definitions and signed permission profiles** — i.e. *what each
trust domain is allowed to do*. Named by its standard term, the **Policy Administration Point**
(XACML; "Policy Administrator" / control plane in NIST SP 800-207 Zero Trust). Only the **asset
owner or an owner-appointed governance / release authority** (not any operational contractor) may
write to it; **no operational role — Advisor, Engineer, or any actor running an Engineer profile —
may modify the PAP, including its own profile** (an enforcement point must never write the
administration point). The PAP is **not an agent** and **not** the retired "Core" delivery concept
(see [`docs/adr/0001`](docs/adr/0001-delivery-and-trust-model.md)).
_Avoid_: Core, policy engine, admin role.

## permission profile

The **general unit of authorization** under a trust domain: a **signed, scoped set of permissions**
a single actor runs under (per ADR 0001 §9 / 0002 §3). Every actor — internal or external — binds
to Engineer through a profile; profiles differ along **scope** (site / project / case), **trust
level**, and **duration** (standing vs just-in-time). Examples: **case-driven deploy**,
**break-glass admin**, **external-contractor**. A profile is **authored by the PAP**, ideally a
separate OS account / service context with its own audit, and **never self-edited**.
_Avoid_: role (reserved for trust domain), grant, scope.

## runtime skill

A **capability** an agent *carries* (not a persona and not a trust domain) — e.g.
`bacnet`, `modbus`, `fdd`, `energy-optimization`, `anomaly-correlation`, and the compliance
references (`nis2`, `cra`, `ai-act`, `iso27001`, `iec62443`). Each persona/agent is granted a
**least-privilege subset** of runtime skills.

## reglercentral (local control loop)

When an edge node runs the control algorithm itself in software — rather than relying on a field
device's own onboard DDC/controller — that loop is a **reglercentral**. It must be architecturally
decoupled from upstream connectivity: it acts on a **locally persisted, last-received** setpoint,
never a live inbound message, so regulation continues unaffected by an outage anywhere above it in
the communication chain. Not every writable point needs one — a field device with its own onboard
control (BACnet priority array, Modbus holding register on a DDC/VFD) already provides this
property natively. See [`skills/edge-iot2050`](skills/edge-iot2050/SKILL.md).
_Avoid_: control agent, edge controller (ambiguous with the physical field controller).

## Hold Last Value (HLV)

The chosen failure-mode principle for openAut's writable points: on loss of upstream
communication, a reglercentral or a previously-deployed setpoint keeps enforcing the **last
known-good value**, rather than reverting to a predetermined default. HLV is the default;
**fail-safe** (revert to a predetermined safe value) is used only where an independent
physical/PLC interlock requires it — the interlock is what makes an unsafe held value survivable,
not a network-level revocation. Standard SCADA/DCS terminology.
_Avoid_: fail-safe (opposite behaviour for the default case — do not conflate), default value.

## persona × trust domain

Every persona is served chiefly by **Advisor** (read-only). Only the Driftstekniker has a
writing path, and it never goes chat→SSH directly — it passes through **Engineer** via an
approved case in the Systemdatabas. **Security** is cross-cutting: it watches the other two
and is the audit/monitoring plane, deliberately outside their control.

| Persona | Realised through | Autorun (read / recommend) | Human-reviewed (write / deploy) |
|---|---|---|---|
| Driftstekniker | Advisor (+ Engineer via case) | read points, fdd / anomaly-correlation, recommend override | bacnet priority-8 override, deploy → Systemdatabas case |
| Energisamordnare | Advisor | weekly report, energy-optimization, anomaly-correlation | — (read-only) |
| Förvaltare | Advisor (+ dashboard) | status view, fdd forecast, notify on decision | — (read-only) |
| Styrentreprenör (extern) | Engineer (scoped JIT profile, via case) | read / diagnose within site scope | edge-node install & fixes → asset-owner case; **no** Advisor / Security / PAP access |
