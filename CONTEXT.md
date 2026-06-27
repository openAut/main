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

## agent / trust domain

An **agent** with its own identity, credentials, sandbox, and tool allow-list, defined by
*what behaviour it is permitted*. openAut has three: **Advisor** (read-only, Teams-facing),
**Engineer** (SSH/deploy capable, not exposed to Teams), and **Security** (separate,
read-only watch-and-audit instance that can see but cannot steer). The trust boundaries and
the Systemdatabas approval handoff are defined in
[`skills/advisor-engineer-workflow`](skills/advisor-engineer-workflow/SKILL.md); the
Security domain's canonical runbook is [`skills/security-instance`](skills/security-instance/SKILL.md).

## runtime skill

A **capability** an agent *carries* (not a persona and not a trust domain) — e.g.
`bacnet`, `modbus`, `fdd`, `energy-optimization`, `anomaly-correlation`, and the compliance
references (`nis2`, `cra`, `ai-act`, `iso27001`, `iec62443`). Each persona/agent is granted a
**least-privilege subset** of runtime skills.

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
