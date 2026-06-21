---
name: forge-governance
description: Define governance for the local openAut Forgejo forge: branch protection, pull requests, CODEOWNERS, commit signing, CI gates, scoped agent tokens, artifact approval, and rules that prevent Advisor or Engineer from bypassing human review. Use when making Forge a deterministic authority for deployable code, generated docs, system-db migrations, or AI-created changes.
---

# forge-governance - review, CI, and agent permissions

The forge is a control point, not just storage. Anything that can become deployable code,
configuration, mappings, migrations, or trusted documentation must pass through reviewable Forge
history.

## Access matrix

| Actor | Forge access | Never allowed |
|---|---|---|
| Advisor | read-only manuals, generated docs, runbooks | push, merge, deploy, token admin |
| Engineer | branch/PR write to integration repos | self-merge protected branches, bypass CI |
| Security | read-only org-wide plus append-only security/audit repo | operational writes, branch protection changes |
| CI runner | read repo, write status/artifacts for scoped repos | admin, broad network, long-lived secrets |
| Human admin | branch protection, token issuance, protected merges | routine agent execution |

Use one identity per agent and one scoped token per purpose. Rotate tokens and record issuance in the
Systemdatabas audit trail or an append-only security log.

## Protected branch rules

For `main`, release branches, and deployable branches:

- require pull request review
- require at least one human reviewer who is not the author
- require passing CI
- require signed commits or signed release artifacts for deployable code/config
- block force pushes
- block direct pushes from agent identities
- require CODEOWNERS review for safety, security, and database migration paths

## CI gates

CI is the deterministic gate before a case can become executable.

Minimum checks:

- schema migrations apply and roll back in a clean database
- role/GRANT tests prove least privilege
- generated point/register maps pass plausibility checks
- tests/lints pass for edge code and scripts
- artifacts are signed or have recorded content hashes
- no obvious secrets, credentials, or private keys are committed

The Systemdatabas may move a case to `approved` or `in_progress` only when the referenced Forge
revision has a green pipeline, the required review, and a signed or hash-pinned artifact. This is a
future enforcement requirement for the `openaut/system-db` repo; do not describe it as implemented
until migrations or policy code exist.

## PR workflow for agents

1. Agent creates a branch named after the case ID or task.
2. Agent writes the change and links source documents, case ID, and Forge URIs.
3. Agent opens a PR/MR with purpose, safety impact, source documents, generated artifacts, and checks run.
4. CI runs deterministic checks.
5. Human reviewer approves or requests changes.
6. Merge creates the approved Forge revision used by Engineer or future deployment tooling.

## Security watchpoints

Security should alert on:

- agent pushing directly to protected branches
- branch protection changes
- new binary/LFS objects in deployable repos
- committed secrets or private keys
- deploy scripts changed without CODEOWNERS review
- CI runner token or webhook changes
- manual revisions that move from quarantine to verified without evidence

> **Live behaviour is unverified.** This skill is the governance contract for future Forgejo rules,
> CI, and Systemdatabas enforcement.
