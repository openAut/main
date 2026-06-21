# openAut improvement proposal — local forge, Teams-only, and deterministic authorities

> ⚠️ **Learning project — not for production.** This is a development/learning exploration of AI in
> building management, not a product. Do not use against live or safety-critical systems. See the
> [README](../README.md) for the full disclaimer.

> **Authored by Claude Code** (running locally on the service PC, repo access via `gh`), at David's
> request: fold a local open-source code/document store and a Teams-only channel decision into the
> architecture-review findings, as one coherent v0.2 direction. This is a **proposal for discussion**,
> not an implemented change — it adds no runtime and changes no behaviour.
>
> **Revised** per the Codex review on the PR: corrected the provenance model (commit SHA is a version
> pointer, not a content hash), made the locality claim precise (Teams is cloud), phrased CI
> enforcement as a requirement rather than achieved behaviour, added a Forge access matrix, and named
> the concrete follow-up skills.

## Why this proposal

A critical review of the current architecture found that openAut is **strong on structure** (trust
boundaries, sandbox isolation, deny-by-default egress, separating the chat channel from deploy
authority) but **weak on the things that must be true *inside* those boundaries**: every layer
disclaims being the final authority, yet the *deterministic* authorities it defers to — independent
verification, enforced least privilege, validated analytics, real safety engineering — are either
deferred or unspecified.

Two of David's requests turn out to fill exactly those gaps:

1. A **local, free, open-source forge** (a self-hosted GitHub equivalent) for code, manuals, and
   documentation, retrievable by both humans and AI — this is not just convenience; it supplies three
   of the missing deterministic authorities (independent CI verification, enforced RBAC, and
   provenance).
2. **Standardising on Microsoft Teams and removing Slack** — this shrinks the human-channel attack
   surface and simplifies the egress allow-list.

This document combines both with the remaining architecture-review hardening.

---

## 1. Add a local open-source forge as the "System of Record" for code + documents

**Recommendation: [Forgejo](https://forgejo.org)** — a community-governed fork of Gitea (GPLv3, fully
free, lightweight).

| Option | Assessment |
|---|---|
| **Forgejo** ✅ | Runs on modest hardware. Git + issues + wiki + releases + **package/LFS registry** + **Forgejo Actions (CI)** + full REST API. Community-governed, no open-core gating — philosophically aligned with openAut's "open, no lock-in" stance. |
| Gitea | Technically equivalent, but governance moved to a company; Forgejo is the cleaner community fork for this project's ethos. |
| GitLab CE | Open-*core* (features gated behind EE), heavy (wants 8 GB+ just to idle). Against the lean, air-gap-capable posture. Over-dimensioned here. |

### Placement in the topology

Layer 3, in the **AI / management zone** — **not** internet-facing, **not** on an edge node. The
forge and the System database together form the **System-of-Record services**. Critically, a forge on
the LAN **keeps the data plane on-prem**: agents fetch manuals and code from a local forge, never from
github.com. Add the forge host to the sandbox egress allow-list (now: model host + Teams bridge +
forge).

**Locality, stated precisely.** "Nothing leaves the building" is shorthand that over-claims, because
Teams is Microsoft cloud and human notifications do leave. The honest property — and the one that
survives critical review — is: **operational data, manuals, code, the AI index, and inference stay
on-prem; only decisions and notifications, with minimised metadata, transit to Teams (Microsoft
cloud).** The forge is part of what stays local; the only egress remains the model link (local
network), the Teams bridge, and the Teams webhook domain.

### Clear separation of stores (resolves an ambiguity in the current design)

- **Forge** = versioned *files*: edge control/poller code, ingested manufacturer manuals, generated
  documentation (I/O lists, register maps, MQTT topic schemas, FAT/SAT notes), runbooks, **and the
  System-database migrations themselves**.
- **System database (PostgreSQL)** = relational *operational state*: cases, approvals, points, audit.
- **TimescaleDB** = time-series telemetry.

They cross-reference, with a clean split between **version pointer** and **content integrity**:

- `documents.uri` / `generated_artifacts.content_uri` store a **forge reference** — repo + ref + path
  + commit, e.g. `forge://openaut/manuals/<path>?commit=<sha>` (or separate metadata fields). This
  gives version traceability.
- `documents.sha256` stays an **independent SHA-256 over the blob's bytes**, computed at ingest. A Git
  commit SHA hashes the commit object, and even a Git blob SHA is SHA-1 over `blob <len>\0<bytes>` —
  neither equals a content SHA-256, so they are *version pointers*, not *integrity hashes*. Keeping an
  independent content hash also buys **tamper-evidence if the forge itself is compromised**: a blob
  can be checked against its recorded hash regardless of what the forge claims.

### Human + AI retrieval

- **Humans:** web UI (browse code, render Markdown manuals, wiki, releases); Teams links to rendered
  doc pages.
- **AI:** REST API + raw blob + `git clone` with **scoped tokens per agent identity** — Advisor
  read-only, Engineer read/write to integration repos, Security read-only org-wide. A new
  `forge-access` skill wraps the API (analogous to the existing skills). **Trust level is expressed by
  repo/branch:** ingested manuals land on a *quarantine* branch (`trust_level = untrusted`) until
  verified — directly addressing the manual-as-injection-vector risk from the review.

### Suggested repository layout inside the forge

| Repo | Contents | Protection |
|---|---|---|
| `openaut/control-<site>` | edge control/poller code per site | protected branch, CI-gated, signed |
| `openaut/manuals` | ingested manufacturer manuals (LFS) | quarantine branch until verified |
| `openaut/generated-docs` | I/O lists, register maps, topic schemas, FAT/SAT | written by Engineer; `generated_artifacts` targets |
| `openaut/runbooks` | the skill pack / operational runbooks | review required |
| `openaut/system-db` | migrations + role/GRANT definitions | CI-tested, review required |

### Forge access matrix

Scoped access tokens per agent identity; **no agent holds admin**, and merges to protected branches
require a human reviewer who is not the author. This makes the forge a **control point, not just
storage**, and deliberately mirrors the [`system-database`](../skills/system-database/SKILL.md)
"Agent access" table so there is **one shared RBAC model**, not two divergent ones.

| Actor | Forge access | Mirrors System-database role |
|---|---|---|
| Advisor | read-only across manuals/docs/generated repos; no push | reads metadata, creates cases |
| Engineer | write via branch + PR to `control-<site>`, `generated-docs`, `system-db`; cannot self-merge protected branches | writes execution status, mappings, artifacts |
| Security | read-only org-wide + own append-only audit/log repo; watch-only | read-only metadata/logs + append alerts |
| Power BI / dashboards | read-only on report/rendered views | read-only reporting |
| Human admin | repo/branch protection, token issuance, merge of protected branches | the approval authority agents cannot assume |

### How the forge strengthens the security architecture

This is the point — the forge supplies three of the deterministic authorities the review said were
missing:

1. **CI as an independent machine gate** (addresses *"governance, not enforcement"* and the
   *self-audited FAT/SAT* problem). Forgejo Actions runs deterministic checks **before** an Engineer
   deploy: schema migrations, role tests, lint, unit tests, and **plausibility / safety-envelope
   validation of register maps**. The system **shall** require a green pipeline, a **signed artifact**,
   and an **approved forge revision** before the System database may move a case to
   `approved`/`in_progress` — a requirement for the future `system-db` policies/migrations, not a
   behaviour this proposal implements. The verifier is **not the same LLM** — exactly what the review
   asked for.
2. **Pull-request review + branch protection give approval real teeth** (addresses *"Advisor cannot
   approve its own case = only a convention"*). Anything that becomes *deployable code/config*
   requires a human reviewer who is not the author, on a protected branch. The two-person rule becomes
   concrete.
3. **Commit signing + versioning = reproducibility + audit provenance** (addresses the
   reproducibility/SPOF critique): you know exactly which control code ran, signed by whom/what.

### What the forge is NOT

Not the telemetry store, not the cases store (those are the DB layers). Large binaries (PDF manuals,
diagrams) go in **LFS / the package registry**, not raw git bloat. The forge becomes a **high-value
asset** on the management network → it is covered by the existing backup discipline, and **Security
watches it** (control-code pushes, API anomalies).

---

## 2. Standardise on Teams — remove Slack

| Where Slack appears today | Action |
|---|---|
| README: "FDD … in Teams **or Slack**" | → Teams only |
| [`advisor-engineer-workflow`](../skills/advisor-engineer-workflow/SKILL.md) trust table: Advisor surface "Teams / Slack" | → Teams only |
| NemoClaw native channels (Slack/Telegram/Discord ship enabled) | **explicitly disable** — keep only the Teams webhook bridge |

**Why this is an improvement, not just a preference:**

- **Smaller attack surface** — a single human channel in/out (the Teams bridge already HMAC-verifies).
- **Simpler egress** — one channel domain in the allow-list (`*.webhook.office.com`) instead of
  several.
- **Matches the Microsoft stack** the project already targets (Teams + Power BI).
- Security alerts go to an **isolated Teams channel** (`#openaut-security-alerts`), not a second
  platform.
- Note: NemoClaw has no *native* Teams channel → "keep Teams" means keep the bridge **and** explicitly
  disable the native channels that are otherwise open by default (least privilege).

---

## 3. Remaining hardening from the architecture review

The deterministic authorities the forge + CI do **not** cover:

- **Deterministic FDD / anomaly detection, with the LLM as *explainer*** — not diagnostician. The
  same discipline [`security-instance`](../skills/security-instance/SKILL.md) already applies ("the
  LLM is not the sole gatekeeper"), extended to the analytics personas.
- **Physical / PLC interlocks for every writable point** — a `safe_value` in a DB row is metadata,
  not an interlock. Writable control needs a hardware limit, not an application-layer check in the
  same system that issues the command.
- **Writable edge control as a signed, CI-approved artifact the node *pulls*** — plus an explicit
  decision on store-and-forward vs. central revocation (they currently conflict: a node designed to
  keep running during a network partition cannot be centrally revoked precisely when it matters most).
- **Security as the orchestrator of purpose-built OT detectors**, not the detector itself.
- **SPOF / reproducibility / PKI rotation** named as explicit operational risks with owners.

---

## Summary: improvement → weakness it addresses

| Improvement | Addresses (from the review) |
|---|---|
| Forgejo as System of Record | "AI has read the manual" gets a versioned, provenance-tracked home |
| Forge on LAN, in the egress allow-list | Reinforces the precise locality property (on-prem data plane) |
| **Forgejo CI as a deterministic gate** | "Governance, not enforcement"; self-audited FAT/SAT |
| **PR review / branch protection** | "Advisor-cannot-approve-its-own = only a convention" |
| Commit signing / versioning | Reproducibility, audit provenance |
| Quarantine branch for manuals | Manual-as-injection-vector |
| Remove Slack, Teams only | Attack surface + egress complexity |
| Deterministic FDD, PLC interlocks, OT detectors | The circularity: names the real authorities |

---

## Proposed next steps (not part of this PR)

These turn the proposal into concrete workbench building blocks — the same path PR #4 took for the
trust-boundary contracts. Sequencing (proposal-only now vs. building these immediately) is David's
call.

1. **`forge-stack` skill** — provision Forgejo on the AI/management host: install, TLS, backup,
   placement in the egress allow-list.
2. **`documentation-store` skill** — the retrieval contract: scoped tokens per agent, the repo
   layout, provenance (`forge://` reference + the independent `documents.sha256`), and the
   quarantine → verified flow for ingested manuals.
3. **`forge-governance` skill** — the CI gate, branch protection, and the access matrix as the
   *enforced* approval mechanism: a case may move to `approved`/`in_progress` only on a green
   pipeline, a signed artifact, and an approved forge revision.
4. **`openaut/system-db` repo** — the [`system-database`](../skills/system-database/SKILL.md)
   migrations + role/GRANT definitions, CI-tested (the first thing the forge gate proves).
5. Update [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) Layer-3 table and
   [`nemoclaw-sandbox-policy`](../skills/nemoclaw-sandbox-policy/SKILL.md) egress allow-list to include
   the forge.
6. Remove the residual Slack reference in
   [`advisor-engineer-workflow`](../skills/advisor-engineer-workflow/SKILL.md) (README is already
   Teams-only) and document disabling NemoClaw's native channels — small follow-up, handled
   separately.
7. Split writable edge control into its own scope decision (read/advise-only vs. functional-safety
   regime).

> **This is a proposal for review.** Nothing here is implemented; it changes no runtime behaviour and
> adds no executable code. It records a v0.2 direction for discussion.
