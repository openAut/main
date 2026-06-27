# ADR 0001 — Delivery & runtime trust model: Main as source, a signed release across the air gap, opencode as Engineer

- **Status:** Proposed (design draft — for review, nothing wired yet)
- **Date:** 2026-06-27
- **Builds on:** #15 / #16 (persona vs. Advisor/Engineer/Security trust domains), [`CONTEXT.md`](../../CONTEXT.md), [`skills/advisor-engineer-workflow`](../../skills/advisor-engineer-workflow/SKILL.md), [`skills/security-instance`](../../skills/security-instance/SKILL.md)

## Context

openAut is developed in **Main** by cloud coding agents (Claude Code + Codex). That environment is internet-connected and carries a prompt-injection surface; it must never touch sensitive OT data.

Production runs in a **closed / air-gapped environment** on a **local Nemotron 3 Ultra** endpoint. (The GX10 / Nemotron 3 Super box is for Bertil/test only; production is Ultra.)

We need to settle three things:

1. How vetted artifacts cross the trust boundary into the sensitive environment.
2. What assistant helps an admin install and troubleshoot inside that environment.
3. How that relates to the three runtime trust domains (Advisor / Engineer / Security).

We explored a separate **"Core"** concept for (1) and (2) and found it carried two unrelated roles — a *delivery bundle* and an *actor* — and was redundant once each role is placed correctly.

## Decision

**1. No separate Core repo or Core agent.** Main is the single source of truth: David's own skills + a **manifest** (bill of materials) of external components + the release/build tooling. Main does **not** vendor copies of third-party skills/programs in git.

**2. The crossing artifact is a signed release of Main — not Main HEAD.** A curated, reviewed, **pinned, self-contained, signed** release (with an SBOM) is the *only* thing that crosses the air gap. The development environment never reaches into the perimeter; updates ride in as new signed releases. ("Core", if the word survives at all, means only this release artifact.)

**3. Assembly is two phases, so freshness and reproducibility don't fight:**
   - **`refresh` (online, human-reviewed):** check upstreams, present a diff of version bumps (old pin → new pin + changelog/advisory), human accepts → updates pins in the manifest. This is the only path to newer upstream versions, and the natural place to pull in security fixes.
   - **`build` (deterministic, offline-capable):** runs from the **verified cache/material produced by `refresh`, not live upstreams** — `refresh` is the only step that touches the internet. It assembles the *exact* pinned versions, verifies hashes/signatures, vendors a self-contained snapshot (skills + pinned externals + opencode binary + provisioning runbooks), signs it, and emits an SBOM. Same manifest → same release, every time.

**4. Engineer = opencode** (open source, MIT) running on the local Nemotron Ultra endpoint, on the management plane, **propose-then-confirm** via opencode's per-tool `ask`/`allow`/`deny` permissions (reads auto-allow, consequential writes/deploys gated, dangerous patterns denied). There is **one** opencode actor; "install/bootstrap" vs "day-2 ops" are *permission profiles / session contexts*, not separate agents. opencode bootstraps and provisions Advisor and Security from the signed release.

   opencode's `ask`/`allow`/`deny` permissions are **one layer, not the hard security boundary.** The real envelope also includes: a dedicated OS user / service account, sudoers / SSH forced-command restrictions, network ACLs, signed/allowlisted deploy-wrapper scripts, a read-only release bundle, the Systemdatabas case discipline, and Security audit emitted outside Engineer's control.

**5. The three trust domains stay separate.** Advisor (NemoClaw chat, read-only, Teams-facing), Engineer (opencode, SSH/deploy, **no Teams**, watched by Security), Security (watch-only; audits Engineer; cannot be silenced by it). Using *different software stacks* for the chat surface (Advisor) and the deploy surface (Engineer) is deliberate defense in depth.

**6. Human-in-the-loop is the primary control on the privileged actor.** Backstops: deterministic interlocks for life-safety (independent of the agent, see #13), Security audit emitted outside the agent's control, and deny-by-default egress.

**7. Dependency & ingress — controlled, never edge-initiated.** All runtime dependencies are resolved at build time into a pinned, integrity-verified set vendored into the signed release. The perimeter fetches **nothing** from the public internet; at most it pulls from an **internal mirror populated only through the same controlled ingress**. Internal instances reaching public upstreams is rejected — it reopens egress (exfiltration + malicious-package ingress) and destroys reproducibility / SBOM / attestation. OS-/security-patch, GPU-driver, and model-weight updates travel as **separate controlled channels**, not bundled into the Main release (which would make the release both too heavy and accountability-unclear).

**8. Release packaging & governance.** The crossing is gated by a **protected, signed release tag in Main** plus a **separate artifact / release registry** carrying the bundle, SBOM, attestations, and checksums — a clean ledger of *what* crossed, *who* reviewed it, *which* pins and signature.

**9. Authorization profiles & feedback are structural, not prompt-level.** Engineer's *case-driven deploy* vs *break-glass admin* are **separate signed permission profiles**, ideally separate OS accounts / service contexts with separate audit — not merely different prompts. Findings flowing back out of the perimeter (incl. Security audit) go through an explicit **sanitized export case** in the Systemdatabas, never informal copy/paste.

## Consequences

- Fewer bespoke components; an off-the-shelf, signed, reproducible-build opencode beats a custom Engineer agent and simplifies verification of what crosses the boundary.
- Engineer becomes a *general* shell-capable agent. Its effective authority is bounded by the permission file + Security oversight + the Systemdatabas case discipline — not by being a narrowly-built tool. This trade-off is acceptable only while that envelope holds.
- The **release gate** (tag + review + signature + pinned bundle + SBOM) is mandatory. Dropping it — e.g. copying Main's working tree across, or fetching "latest" at build time — loses supply-chain integrity.
- Because the perimeter fetches nothing, the release bundle must carry everything needed to run offline.

## Alternatives considered

- **Separate Core repo/agent.** Rejected as redundant. Governance/audit clarity (a clean ledger of what crossed) is achievable with protected, signed release tags + an artifact registry in Main.
- **Claude Code in production via an Anthropic-API-emulating proxy in front of Ultra.** Rejected for production: prefer an open, model-agnostic tool; Claude Code is cloud-bound and adds a translation layer to vet. (opencode is the open equivalent.)
- **Blindly fetch "latest" from upstream at build time.** Rejected: non-reproducible and a supply-chain risk straight into a sensitive environment. Replaced by the reviewed `refresh` → pin step.
- **Two opencode instances (Engineer + Core).** Rejected: re-splits a role we deliberately merged; the distinction is a permission profile, not a second agent.

## Compliance alignment (CRA / NIS2)

*Working aid, not legal advice; verify against the legal texts before binding decisions.*

The controlled-ingress model (decision 7) is the one that aligns with both regimes — internal instances fetching from the public internet does not:

- **CRA (Reg (EU) 2024/2847):** Annex I Part II expects an **SBOM**, component knowledge, and an **authenticated, integrity-protected update mechanism** — a signed release delivers exactly that, whereas edge-initiated fetching makes the SBOM non-deterministic and undermines "no known exploitable vulnerabilities at release" (Annex I Part I). Applicability is uncertain: openAut as a learning / open-source project is likely **not** "placed on the market" (Art. 2 + the open-source regime), so this is adopted as good practice / future-proofing, not an assumed legal obligation.
- **NIS2 (Dir (EU) 2022/2555):** Art. 21.2(d) supply-chain security and 21.2(e) security in acquisition/development/maintenance favour a single reviewed ingress + SBOM over instances reaching arbitrary upstreams; segmentation / deny-by-default and Art. 23 incident reporting (which needs deployment provenance) point the same way. openAut itself is not a NIS2 entity, but the **deployment target — a public-sector building operator (energy / water / public administration) — plausibly is**, so the delivery model is built to let the customer stay compliant.

## Open questions

- **Internal mirror mechanism:** whether to run an in-perimeter package mirror / artifact repo, or rely solely on the vendored release snapshot.
- **Hardware:** Nemotron 3 Ultra sizing inside the perimeter (Ultra is larger than the Super-120B that runs on the GX10 today).
- **Tool-calling reliability** of Nemotron via vLLM with opencode — pilot against the existing GX10/Super endpoint (already configured with `--enable-auto-tool-choice --tool-call-parser qwen3_coder`) before Ultra/production; keep aider as a diff-based fallback if tool-calling proves flaky.
