# deploy/advisor-agent — Advisor, ready to run

This is where the Advisor **contract** (`skills/advisor-engineer-workflow/SKILL.md`) becomes an
**actual OpenClaw agent**. Three layers, each doing a different job — don't collapse them:

| Layer | File(s) | Job |
|---|---|---|
| Contract | `../../skills/advisor-engineer-workflow/SKILL.md` | The trust-boundary definition: what Advisor is, the Advisor/Engineer/Security split, case states. Read on trigger, not every turn. |
| Enforcement | `openclaw.json` | `agents.entries.advisor` — workspace, `tools.deny`, `skills` allowlist, Teams channel binding. This is OpenClaw's own tool-visibility layer. |
| Behavior | `workspace/AGENTS.md`, `workspace/SOUL.md`, `workspace/TOOLS.md` | Injected every turn. Day-to-day procedure, identity/boundaries, and tool-usage notes. |

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
   (repo root) — see `nemoclaw-provision` Step 5 for how to get them.
3. Copy this whole `deploy/advisor-agent/` directory to the sandbox host as a unit (e.g.
   `/opt/openaut/advisor-agent/`), then merge its `openclaw.json` into the sandbox's OpenClaw config
   (or point `OPENCLAW_CONFIG_PATH` at a file that imports it). `"workspace": "./workspace"` is
   relative to wherever the merged config is loaded from — moving `openclaw.json` without its
   `workspace/` sibling breaks the reference; keep them together, or replace the relative path with
   an absolute one for your deployment.
4. Fill in `[site or portfolio]` placeholders in `workspace/AGENTS.md` and `workspace/SOUL.md`.
5. Run the [Verification](../../skills/advisor-engineer-workflow/SKILL.md#verification) checklist
   in the contract skill before any live use — none of it is assumed true just because these files
   exist. Confirm from the running agent (not just by reading config) which workspace files it
   actually loaded, since a broken path fails silently rather than erroring.

## What's still open, on purpose

- The `msteams` **inbound** path (direct exposure vs. a DMZ relay) — see
  [`bridges/teams-webhook`](../../bridges/teams-webhook/README.md) and `nemoclaw-sandbox-policy`.
- A matching bundle for Engineer does not exist yet. Per [ADR 0001](../../docs/adr/0001-delivery-and-trust-model.md)
  §4-5 and [ADR 0003](../../docs/adr/0003-engineer-runtime-containment.md), Engineer is **not**
  another OpenClaw `agents.entries` — it runs **opencode**, on its own host and its own sandbox, a
  deliberately different software stack from Advisor/NemoClaw. When that bundle is built, it
  belongs in opencode's own config format, not folded into this folder's `openclaw.json`.
- Advisor's granted tools (`read`, `message` — see `openclaw.json`) have no write path into the
  Systemdatabas. `create_case_note` / `create_work_order` (referenced in `advisor-engineer-workflow`'s
  `openaut-backing-capabilities` metadata) are not implemented tools here; no capability gateway
  exists yet (see that skill's frontmatter). Until one does, treat this bundle as a **demonstration
  configuration**: when `workspace/AGENTS.md` says "open a case," a human must actually create it in
  the Systemdatabas — Advisor cannot, and nothing here should be read as claiming otherwise.
