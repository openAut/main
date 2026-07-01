# ADR 0003 — Engineer runtime containment: a dedicated sandbox, not Advisor's OpenShell

- **Status:** Proposed (design draft — for review, nothing wired yet)
- **Date:** 2026-06-28
- **Builds on:** [`0001-delivery-and-trust-model`](0001-delivery-and-trust-model.md) (§4 the Engineer envelope, §5 different stacks), `0002-access-control-and-roles` (PAP; no self-granted authority) — **pending in PR #18; merge #18 first** so the cross-references resolve — and the `secure-agent-workspace` reference (NVIDIA Secure Agent Workspace, Phase II)

## Context

ADR 0001 §4 set Engineer = **opencode** behind an envelope (dedicated OS account, sudoers / SSH forced-commands, network ACLs, signed/allowlisted deploy wrappers, per-tool `ask`/`allow`/`deny`, Security audit outside its control) and stated that `ask`/`allow`/`deny` is *one layer, not the hard boundary*. §5 made it deliberate that Advisor (NemoClaw) and Engineer (opencode) use **different software stacks**, and the topology already runs them on **separate servers** (chat/data plane vs. management plane).

That leaves an open question: should opencode be sandboxed the way NemoClaw is — NemoClaw runs its tool execution inside **OpenShell** (Landlock + seccomp + netns)? The tempting move is to drop opencode into the same OpenShell.

But Advisor's OpenShell profile is built to **contain a chat agent** — deny egress, restrict syscalls, lock the filesystem. Engineer's whole job is the opposite: SSH out to edge nodes, deploy code, run shell. Reusing Advisor's *profile* would force so many holes that containment stops meaning anything; nesting opencode in Advisor's *instance* would also collapse the stack/plane separation 0001 §5 created on purpose.

## Decision

**1. Engineer runs in its own runtime sandbox, on its own host / management plane — not inside Advisor's OpenShell instance and not under Advisor's profile.** Reuse the same kernel **primitives** (Landlock + seccomp + netns), with an **Engineer-specific signed policy bundle** — same mechanism, different policy.

**2. The Engineer policy is deny-by-default and tuned to the job:**
   - **Egress:** reachable = **the edge VLAN / nodes in the active case scope**, plus exactly four **narrow, policy-owned, case-bound** infrastructure endpoints needed to function: the **credential proxy**, the **mediated inference endpoint** (Nemotron Ultra gateway), the **append-only audit sink** (§4), and the **mediated MQTT write endpoint** (added by [`0004-edge-control-writes-and-continuity`](0004-edge-control-writes-and-continuity.md) §1 — setpoint writes to edge nodes, short-lived credential minted per case, same shape as the credential proxy). Everything else is denied — the public internet, the MQTT broker itself, and the Advisor, Security, and PAP networks. These four exceptions are defined in the signed policy, not by Engineer, and are the *only* off-VLAN destinations.
   - **Filesystem:** writes confined to a **work dir**; **read-only** access to the **signed release bundle** (its write-protection is a core 0001 invariant); system binaries and auto-executed persistence paths protected (no agent-created persistence).
   - **Process scope** limited to what deploy/troubleshoot actually needs.

**3. Credentials via a credential proxy, never raw in opencode's context.** SSH/deploy secrets stay in the enterprise store; the sandbox receives **scoped, short-lived capabilities** bound to the case / permission profile, with audit on use. The Nemotron Ultra inference path is mediated the same way, not handed raw.

**4. The sandbox is one layer of the §4 envelope, not the boundary.** It is paired with the dedicated OS account, SSH forced-commands, signed/allowlisted deploy wrappers, and network ACLs. **Audit flows *outward* to an append-only sink / external collector that Engineer cannot disable, mute, or read back** — observation does **not** rely on a direct Engineer → Security egress path (which §2 denies); Security consumes the sink, Engineer only writes to it. No single layer carries the security.

**5. No self-granted authority, no agent-controlled lifecycle.** The signed policy and the sandbox lifecycle (create / kill / upgrade) belong to the **asset owner / owner-appointed governance authority / PAP** — explicitly **not** Engineer, and **not** any actor running an Engineer permission profile — consistent with ADR 0002. Engineer cannot widen its own sandbox or policy.

**6. The purpose is blast-radius containment, not stopping legitimate work.** Troubleshooting reads **untrusted field data** (logs, device banners) inside the perimeter — a prompt-injection surface (flagged in 0002). The Engineer-tuned sandbox caps what a *hijacked* Engineer session can reach: at worst it disturbs its own in-scope nodes; it cannot reach the internet, Advisor, Security, or the PAP.

## Consequences

- The most privileged actor gets meaningful containment **without being crippled** — the sandbox permits its narrow legitimate actions and denies the rest.
- Added ops cost: a second sandbox profile + a credential proxy to build and maintain. Justified by reducing the blast radius of the one actor that can SSH and deploy.
- Reusing OpenShell's **primitives but not its policy** keeps tooling familiar while preserving the deliberate stack/plane separation (0001 §5).
- The Engineer policy bundle becomes a signed, attestable artifact that must ride the same `refresh` → `build` pipeline as the rest of the release (0001), with a rollback path.

## Alternatives considered

- **Put opencode inside Advisor's OpenShell instance/profile.** Rejected: purpose mismatch (the profile denies exactly what Engineer must do) and it collapses the different-stack / different-plane separation (0001 §5).
- **No runtime sandbox — rely only on OS account + SSH forced-commands + `ask`/`allow`/`deny`.** Rejected: misses in-host blast-radius containment for prompt injection during troubleshooting; the most privileged actor is where a Phase-II runtime sandbox earns its keep.
- **A single shared sandbox/host for Advisor + Engineer.** Rejected: co-residency of two trust domains on one substrate.

## Compliance alignment (IEC 62443 / secure-agent-workspace)

*Working aid, not legal advice; verify against the source texts before binding decisions.*

- **IEC 62443:** zone segmentation and restricted data flow (FR5 RDF), system integrity (FR3), and least privilege — a scoped egress allowlist + filesystem confinement is a concrete realisation.
- **secure-agent-workspace (Phase II) invariants** upheld: deny-by-default in-runtime egress, credential proxy (no raw secrets in agent context), no self-granted authority, no agent-controlled lifecycle, no suppressed audit.

## Open questions

- **Enforcement substrate:** namespaces + LSM (Landlock/seccomp, as OpenShell) vs a **microVM** (Firecracker / Kata) for stronger isolation of the privileged actor — traded against SSH/deploy latency and complexity.
- **Credential proxy:** where it runs, and how short-lived capabilities are minted and bound to an active Systemdatabas case.
- **Policy build/attest:** how the signed Engineer policy bundle is produced and attested in the two-phase `refresh` → `build` pipeline (0001), and its rollback path.
- **Egress granularity:** per-site VLAN vs per-node allowlisting, and how the allowlist is derived from the active case scope at session start.
