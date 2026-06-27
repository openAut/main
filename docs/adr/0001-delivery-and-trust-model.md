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
   - **`build` (deterministic, offline-capable):** fetch the *exact* pinned versions, verify hashes/signatures, vendor a self-contained snapshot (skills + pinned externals + opencode binary + provisioning runbooks), sign it, emit an SBOM. Same manifest → same release, every time.

**4. Engineer = opencode** (open source, MIT) running on the local Nemotron Ultra endpoint, on the management plane, **propose-then-confirm** via opencode's per-tool `ask`/`allow`/`deny` permissions (reads auto-allow, consequential writes/deploys gated, dangerous patterns denied). There is **one** opencode actor; "install/bootstrap" vs "day-2 ops" are *permission profiles / session contexts*, not separate agents. opencode bootstraps and provisions Advisor and Security from the signed release.

**5. The three trust domains stay separate.** Advisor (NemoClaw chat, read-only, Teams-facing), Engineer (opencode, SSH/deploy, **no Teams**, watched by Security), Security (watch-only; audits Engineer; cannot be silenced by it). Using *different software stacks* for the chat surface (Advisor) and the deploy surface (Engineer) is deliberate defense in depth.

**6. Human-in-the-loop is the primary control on the privileged actor.** Backstops: deterministic interlocks for life-safety (independent of the agent, see #13), Security audit emitted outside the agent's control, and deny-by-default egress.

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

## Open questions

- **Governance of the crossing:** protected/signed release tags in Main vs. a separate artifact registry.
- **Ingress scope:** does the release also carry Nemotron Ultra model updates and OS/security patches, or are those separate controlled channels? (Air-gapped systems still need CVE patching.)
- **Feedback path:** how do findings from the perimeter (incl. Security audit) get back to Main without leaking sensitive data — a sanitized, human-mediated channel.
- **Engineer authorization split:** case-driven deploy vs. break-glass admin — how the two permission profiles are enforced in opencode.
- **Hardware:** Nemotron 3 Ultra sizing inside the perimeter (Ultra is larger than the Super-120B that runs on the GX10 today).
- **Tool-calling reliability** of Nemotron via vLLM with opencode — pilot against the existing GX10/Super endpoint (already configured with `--enable-auto-tool-choice --tool-call-parser qwen3_coder`) before Ultra/production; keep aider as a diff-based fallback if tool-calling proves flaky.
