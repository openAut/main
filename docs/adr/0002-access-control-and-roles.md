# ADR 0002 — Access-control model: standard role-naming anchors, the policy-authority (PAP) boundary, and external-contractor profiles

- **Status:** Proposed (design draft — for review, nothing wired yet)
- **Date:** 2026-06-28
- **Builds on:** [`0001-delivery-and-trust-model`](0001-delivery-and-trust-model.md) (esp. §4 one Engineer actor, §9 permission profiles), #15 / #16 (persona vs. Advisor/Engineer/Security), [`CONTEXT.md`](../../CONTEXT.md)

## Context

ADR 0001 settled the delivery model and the runtime trust domains, but it pictured **one trusted admin** who owns everything inside the perimeter. A concrete deployment breaks that assumption:

A public-sector asset owner (Region / Kommun) procures an external **control contractor (styrentreprenör)** and wants to grant them **Engineer** access to troubleshoot and install edge nodes — **without** the ability to change Security, Advisor, Engineer itself, or the policies that define any of them.

The moment there are **multiple operators of differing trust**, "the operator owns everything" no longer holds. We need an explicit authority boundary separating *who may author what a role can do* from *who may operate within a role*. We briefly considered resurrecting **"Core"** for this — but 0001 deliberately retired "Core" on the *delivery* axis, this is a *different* (access-control) axis, and reusing the word re-merges concepts we just separated. The boundary already has a standard name.

## Decision

**1. Anchor the three trust domains to recognised standards.** Keep the descriptive names; document the equivalence so a public-sector security reviewer recognises the model:
   - **Advisor ≈ Reader / Viewer** — operational read tier.
   - **Engineer ≈ the SCADA/DCS "Engineer" tier**, bounded by **least privilege** (NIST SP 800-53 **AC-6**; IEC 62443 **FR2 Use Control**).
   - **Security ≈ Auditor** — the **separation-of-duties** oversight role (NIST SP 800-53 **AC-5**), deliberately outside the operational plane.
   - The model is **two orthogonal axes**: operational privilege (Advisor *read* vs Engineer *write*) and independent oversight (Security / Auditor) — not a single ladder.

**2. Introduce an explicit policy-authority boundary, named the Policy Administration Point (PAP).** (XACML PAP/PDP/PEP; NIST SP 800-207 Zero Trust "Policy Administrator" / control plane.) The PAP **owns role definitions and signed permission profiles**. Only the **asset-owner / integrator tier** (Sense-IT / the building owner) may write to it. **No operational role — Advisor, Engineer, or an external contractor — may modify the PAP, including its own profile.** This is the privilege-escalation closure: an enforcement point must never write the administration point. The PAP is **not a new agent** and **not** the retired "Core".

**3. The external control contractor is an Engineer permission profile — not a new agent or trust domain.** It extends 0001 §9 (case-driven deploy vs break-glass admin) with a third, lower-trust profile:
   - **Scope:** per-site / per-asset; field troubleshooting + read within scope only.
   - **Edge-node onboarding is gated.** Installing a new edge node extends the perimeter (new attack surface, newly enrolled credentials) → it is the most privileged Engineer action and requires **asset-owner approval via a Systemdatabas case**, never autonomous.
   - **Time-bounded & revocable** (procurement rotates): **just-in-time** access (PAM), cleanly revoked at contract end; **no standing credentials**.
   - **Fully audited by Security**, like any Engineer session ("it can see, it cannot steer" applies to the contractor too).
   - **Cannot reach** Advisor, Security, the PAP, or its own profile (deny-by-default). The different software stacks already separating Advisor (NemoClaw) from Engineer (opencode) reinforce this.

**4. Naming hygiene.** "Core" stays retired. Use **PAP / policy-authority** for the authority-ownership concept, and **styrentreprenör / external contractor (an Engineer JIT profile)** for the external operator — never a fourth peer agent.

## Consequences

- The access model is **multi-tenant-ready**: an asset owner can delegate bounded Engineer work to a rotating external party without weakening the trust separation.
- The **PAP is now the single most authority-dense element**; it must itself be covered by Security audit and must never be operable by an LLM-driven role (consistent with 0001 §6, human-in-the-loop).
- **Standard anchors ease procurement / compliance**: the customer recognises Auditor, least privilege, PAP, and JIT, which shortens IEC 62443 / NIS2 / customer security-review conversations.
- **Prompt injection is unchanged but worth restating:** a contractor's Engineer session reads untrusted field data (logs, device banners) → the propose-then-confirm envelope and per-step approval from 0001 §4 apply as-is.

## Alternatives considered

- **Resurrect "Core" as the authority tier.** Rejected: re-merges the delivery concept 0001 retired and adds a third meaning to an overloaded word; **PAP** is the precise standard term.
- **A separate "Contractor" agent / trust domain.** Rejected: re-splits Engineer; the distinction is a **permission profile** (0001 §4 & §9), not a fourth agent.
- **Rename Advisor / Engineer / Security to the standard terms (Reader / Engineer / Auditor).** Rejected: the descriptive names carry domain meaning; document the equivalence instead of renaming.

## Compliance alignment (IEC 62443 / NIS2)

*Working aid, not legal advice; verify against the source texts before binding decisions.*

- **IEC 62443:** RBAC and least privilege under **FR1** (Identification & Authentication Control) and **FR2** (Use Control); the PAP boundary and contractor profile are a concrete realisation of authorization enforcement (SR 2.1) and least privilege.
- **NIST SP 800-53:** **AC-5** (Separation of Duties) maps to Security-as-Auditor and the PAP-vs-operator split; **AC-6** (Least Privilege) maps to the scoped contractor profile; **AC-2** account types / JIT to the time-bounded grant.
- **NIS2 (Dir (EU) 2022/2555):** supports the public-sector deployment target's access-control posture (Art. 21.2(i)) and supply-chain hygiene (21.2(d)); the gated, audited contractor path keeps deployment provenance intact for Art. 23 reporting. openAut itself is not a NIS2 entity, but the **building-operator customer plausibly is**.

## Open questions

- **Where the PAP physically lives:** inside the signed release, a separate in-perimeter governance store, or the Systemdatabas RBAC — and how profile *authorship itself* is audited.
- **How the contractor JIT profile is issued:** per-engagement at `build` / provision time, or granted dynamically in-perimeter — and if dynamic, what authority issues it without reopening egress.
- **Concrete enforcement mapping:** the contractor profile onto opencode `ask`/`allow`/`deny` + OS account / sudoers / SSH forced-command restrictions (the real envelope per 0001 §4), and what exactly counts as "within site scope".
