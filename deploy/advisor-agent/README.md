# deploy/advisor-agent — Advisor reference configuration

> **This is a reference configuration, not a deployable Advisor.** The `openclaw.json` shape and
> prompt files are ready to merge as-is; the data connections and case-creation tool behind them are
> not (see "What's still open" below — no backing capabilities are wired up). Treat every claim
> Advisor makes about reading live data or opening a case as something to verify against what this
> bundle can actually do today, not the target contract in `advisor-engineer-workflow/SKILL.md`.

> **This directory configures Advisor only.** Everything under here — `openclaw.json`, `workspace/`
> — is OpenClaw config, because Advisor runs on NemoClaw/OpenClaw. **Engineer is not here and never
> belongs here**: per [ADR 0001](../../docs/adr/0001-delivery-and-trust-model.md) §4-5 and
> [ADR 0003](../../docs/adr/0003-engineer-runtime-containment.md), Engineer is a separate **opencode**
> installation on its own host and sandbox — a different software stack, not another OpenClaw agent
> entry. If you're building Engineer's equivalent bundle, it goes in opencode's own config format,
> not as a second `agents.entries` alongside this one.

This is where the Advisor **contract** (`skills/advisor-engineer-workflow/SKILL.md`) becomes an
**actual OpenClaw agent**. Three layers, each doing a different job — don't collapse them:

| Layer | File(s) | Job |
|---|---|---|
| Contract | `../../skills/advisor-engineer-workflow/SKILL.md` | The trust-boundary definition: what Advisor is, the Advisor/Engineer/Security split, case states. Read on trigger, not every turn. |
| Enforcement | `openclaw.json` | `agents.entries.advisor` — workspace, `tools.deny`, `skills` allowlist, Teams channel binding. This is OpenClaw's own tool-visibility layer. |
| Behavior | `workspace/AGENTS.md`, `workspace/SOUL.md`, `workspace/TOOLS.md` | Injected every turn. Day-to-day procedure, identity/boundaries, and tool-usage notes. |

`workspace/AGENTS.md` is not a summary of the contract skill — it duplicates its calibration check,
document-trust check, and risk/confidence decision table verbatim, because that's the file actually
injected into the running agent's prompt. If you change the decision logic in one, change it in the
other; they're checked for drift by inspection, not by tooling, so a change to one without the other
is a silent regression.

## What this does NOT do

`openclaw.json`'s `tools.deny` is **not** the hard security boundary — it's prompt-layer tool
visibility, and a compromised or confused model could in principle be steered around it. The actual
enforcement — the reason "Advisor cannot open SSH" is *true* rather than just *asked for* — is
NemoClaw's **OpenShell** sandbox policy (process/filesystem/network isolation at the kernel level).
See [`nemoclaw-sandbox-policy`](../../skills/nemoclaw-sandbox-policy/SKILL.md). Deploying this
folder without that policy applied gives you a well-behaved agent, not a safe one.

## Setup order

1. Provision and lock down the sandbox: [`nemoclaw-provision`](../../skills/nemoclaw-provision/SKILL.md),
   then [`nemoclaw-sandbox-policy`](../../skills/nemoclaw-sandbox-policy/SKILL.md).
2. Fill in `${MSTEAMS_APP_ID}` / `${MSTEAMS_APP_PASSWORD}` / `${MSTEAMS_TENANT_ID}` in `config.env`
   (repo root) — see `nemoclaw-provision` Step 5 for how to get them. **Filling in `config.env` does
   not, by itself, put those values in OpenClaw's process environment** — `${...}` substitution in
   `openclaw.json` only works if whatever runs `openclaw` actually has them set. If OpenClaw runs as
   a systemd service, add `EnvironmentFile=/path/to/config.env` (or a secret-store-backed drop-in) to
   its unit rather than assuming a shell `source` from some earlier session carries over. Restrict
   `config.env` to the service account (`chmod 600`, owned by that user) — it holds the Bot Framework
   app secret in plaintext. After merging, verify the substitution resolved (e.g. `openclaw config
   show` or equivalent) without printing `appPassword` to a log or terminal you don't control, and
   never copy the resolved secret value into a second file (including a "merged" copy of
   `openclaw.json`) — keep one source of truth for it.
3. Copy this whole `deploy/advisor-agent/` directory to the sandbox host as a unit (e.g.
   `/opt/openaut/advisor-agent/`), then merge its `openclaw.json` into the sandbox's OpenClaw config
   (or point `OPENCLAW_CONFIG_PATH` at a file that imports it). `"workspace": "./workspace"` is
   relative to wherever the merged config is loaded from — moving `openclaw.json` without its
   `workspace/` sibling breaks the reference; keep them together, or replace the relative path with
   an absolute one for your deployment.
4. Fill in `[site or portfolio]` placeholders in `workspace/AGENTS.md` and `workspace/SOUL.md`.
5. `channels.msteams.enabled` is `false` in the checked-in file on purpose. Before flipping it to
   `true`: narrow the `bindings` match from the wildcard (`accountId: "*"`, `peer.kind: "*"`) to
   your deployment's actually-approved channels/users, and resolve the msteams **inbound** path
   (next bullet) — do both first, not after. Flipping `enabled` without doing so puts a wildcard,
   untrusted-input-accepting endpoint live.
6. Run the [Verification](../../skills/advisor-engineer-workflow/SKILL.md#verification) checklist
   in the contract skill before any live use — none of it is assumed true just because these files
   exist. Confirm from the running agent (not just by reading config) which workspace files it
   actually loaded, since a broken path fails silently rather than erroring.

## What's still open, on purpose

- The `msteams` **inbound** path (direct exposure vs. a DMZ relay) — see
  [`bridges/teams-webhook`](../../bridges/teams-webhook/README.md) and `nemoclaw-sandbox-policy`.
- The Teams **binding** in `openclaw.json` matches every account/peer in the tenant — broad, not
  least-privilege, for an agent whose job is accepting untrusted Teams-sourced text. Narrow it to
  approved channels/users once you've confirmed the exact `match` shape your OpenClaw version
  supports (see the comment above the `bindings` block in `openclaw.json`).
- A matching bundle for Engineer does not exist yet. Per [ADR 0001](../../docs/adr/0001-delivery-and-trust-model.md)
  §4-5 and [ADR 0003](../../docs/adr/0003-engineer-runtime-containment.md), Engineer is **not**
  another OpenClaw `agents.entries` — it runs **opencode**, on its own host and its own sandbox, a
  deliberately different software stack from Advisor/NemoClaw. When that bundle is built, it
  belongs in opencode's own config format, not folded into this folder's `openclaw.json`.
- **No backing capabilities are wired up here — neither read nor write.** Advisor's granted tools
  (`read`, `message` — see `openclaw.json`) are OpenClaw's generic, local-file-scoped tools. The
  capabilities `workspace/AGENTS.md` instructs Advisor to use — `get_equipment_context`,
  `query_timeseries`, `read_verified_document` for reads, `create_case_note` / `create_work_order`
  for writes (all referenced in `advisor-engineer-workflow`'s `openaut-backing-capabilities`
  metadata) — are **not implemented as tools here**; no capability gateway exists yet (see that
  skill's frontmatter). Until one does, treat this bundle as a **demonstration configuration**: it
  shows the prompt/config shape, not a live-data-connected agent. `workspace/AGENTS.md`'s steps that
  say "read telemetry" or "read equipment context" assume that data has already been made available
  in context some other way (e.g. pasted into the conversation) — Advisor cannot fetch it itself
  yet, and when `AGENTS.md` says "ask a human to open a case," a human must actually do that — Advisor
  cannot, and nothing here should be read as claiming otherwise.
