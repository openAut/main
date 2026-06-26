---
name: forge-stack
description: Provision the local openAut Forgejo stack as the self-hosted, open-source forge for code, manuals, runbooks, generated documentation, and agent-readable project knowledge. Use when installing or operating the local GitHub-like forge, placing it in the AI/management zone, configuring TLS, backups, runners, package/LFS storage, egress allow-lists, or making Forgejo available to Codex/Claude/openAut agents.
permissions:
  knowledge_only: false
  exec: "node-provisioned deploy/operate commands (docker, systemctl, TLS, backups)"
  network: "local Forgejo (AI/management zone) over TLS"
  files: "read-write (forge data + backups on the node)"
  credentials: "TLS + scoped forge tokens (node-provisioned, not in repo)"
---

# forge-stack - local Forgejo service

openAut Forge is the local, free, open-source software forge for the project. It is not the telemetry
store and not the case database. It is the versioned file system of record for code, manuals,
runbooks, generated docs, migrations, releases, and signed deployable artifacts.

Use **Forgejo** unless there is a strong site-specific reason not to. Keep it in Layer 3, the
AI/management zone: reachable by agents and humans on the management network, not internet-facing,
and not installed on edge nodes.

## Target placement

| Item | Default |
|---|---|
| Zone | AI / management zone |
| Exposure | LAN/VPN only; no public internet listener |
| TLS | internal CA certificate or private ACME endpoint |
| Storage | Git repos + LFS/package storage on backed-up volume |
| Runner | local Forgejo Actions runner on a separate low-privilege host or VM |
| Egress | allow from agent sandboxes to Forge only on the chosen HTTPS/Git endpoint |

## Minimum service layout

- `forgejo` web/API service behind a TLS reverse proxy.
- PostgreSQL database for Forgejo metadata.
- Repo/LFS/package storage on a volume included in backups.
- Forgejo Actions runner registered with a least-privilege token.
- Admin account controlled by a human operator, not an agent.
- Per-agent service accounts and scoped tokens.

## Provisioning workflow

1. Allocate a host in the AI/management zone.
2. Install Forgejo using the site's preferred packaging model.
3. Put TLS in front of the web/API endpoint; do not expose plaintext HTTP across the network.
4. Configure backups for database, repositories, LFS/package storage, configuration, and secrets inventory.
5. Create the base organization `openaut`.
6. Create `openaut/control-<site>`, `openaut/manuals`, `openaut/generated-docs`, `openaut/runbooks`, and `openaut/system-db`.
7. Register the Actions runner and run a trivial CI job.
8. Add the Forge endpoint to the NemoClaw sandbox egress allow-list.
9. Verify Advisor, Engineer, and Security tokens with the access matrix in [`forge-governance`](../forge-governance/SKILL.md).

## Acceptance checks

- Forge is reachable from the management network over TLS.
- Forge is not reachable from the public internet.
- Agent sandboxes can reach only the approved Forge endpoint, not arbitrary Git hosts.
- A non-admin agent token cannot create users, change branch protection, or issue new tokens.
- Backups can be restored into a clean lab instance.
- CI can run without granting the runner broad host or network privileges.

> **Live behaviour is unverified.** This is the deployment contract for a future local Forgejo
> installation, not a production hardening guide.
