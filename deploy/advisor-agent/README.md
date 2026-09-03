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
3. Merge `openclaw.json` here into the sandbox's OpenClaw config (or point `OPENCLAW_CONFIG_PATH`
   at a file that imports it).
4. Fill in `[site or portfolio]` placeholders in `workspace/AGENTS.md` and `workspace/SOUL.md`.
5. Run the [Verification](../../skills/advisor-engineer-workflow/SKILL.md#verification) checklist
   in the contract skill before any live use — none of it is assumed true just because these files
   exist.

## What's still open, on purpose

- The `msteams` **inbound** path (direct exposure vs. a DMZ relay) — see
  [`bridges/teams-webhook`](../../bridges/teams-webhook/README.md) and `nemoclaw-sandbox-policy`.
- `deploy/engineer-agent/` (the matching bundle for Engineer, on its own host per ADR 0001 §5 /
  ADR 0003) does not exist yet — don't put Engineer's `agents.entries` in this folder's
  `openclaw.json` when you build it; keep the two trust domains in physically separate config the
  same way they're in separate sandboxes.
