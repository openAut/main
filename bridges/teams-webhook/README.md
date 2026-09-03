# Teams ↔ OpenClaw — retired approach, see msteams plugin

> **This bridge is retired.** It relied on Microsoft Teams' **Incoming Webhook** (an Office 365
> Connector). Microsoft retired Office 365 Connectors in Teams in a rollout that completed
> **2026-05-22** — `TEAMS_INCOMING_WEBHOOK_URL` posts to `webhook.office.com` no longer work.
> Do not deploy this bridge. Kept only as a historical record of the earlier design.

## What replaced it

OpenClaw ships a **native, bundled Microsoft Teams channel plugin** (`msteams`, Bot Framework /
Azure Bot based). The original premise for this bridge — "NemoClaw/OpenClaw has no native Teams
channel" — was incorrect. Use the native plugin instead:

- Config lives in `channels.msteams` in `openclaw.json` (or `MSTEAMS_APP_ID`/`MSTEAMS_APP_PASSWORD`/
  `MSTEAMS_TENANT_ID` env vars — see `config.env.example`).
- Setup: [`nemoclaw-provision`](../../skills/nemoclaw-provision/SKILL.md) Step 5.
- Egress/network implications: [`nemoclaw-sandbox-policy`](../../skills/nemoclaw-sandbox-policy/SKILL.md).
- Persona channel bindings: [`nemoclaw-agent-workflow`](../../skills/nemoclaw-agent-workflow/SKILL.md).

## The open design question

Unlike this retired bridge (outbound-only: the gateway posted *out* to Teams, and Teams called an
Outgoing Webhook only on @mention), the native `msteams` plugin needs Teams' cloud to reach **your**
endpoint (`/api/messages`) — that's an **inbound** requirement, not just another egress allow-list
entry. That cuts against openAut's deny-by-default, outbound-only sandbox posture and is a real
architectural cost, not a config detail.

**This is intentionally left open for now** — proceed with the native plugin for a dev/lab setup
only, e.g. behind a `devtunnel`/`tailscale funnel` tunnel. Those tunnels are a lab convenience, not
a hardened answer: they still terminate an endpoint that accepts untrusted Teams-sourced input, and
neither is a substitute for verifying Bot Framework's own request authentication, a proxy/DMZ
boundary, rate limiting, and logging on that endpoint. Do not treat the inbound path design (direct
exposure vs. a DMZ relay that re-terminates into the sandbox) as decided, and do not deploy this
past a dev/lab setup — see the repo-level "learning project, not for production" notice — until
that design and those controls are verified. Revisit before any production or live-BMS deployment.

## Why this bridge existed (historical)

Before Teams' native OpenClaw support was confirmed, this bridge mapped:

```
Teams channel  --(Outgoing Webhook, HMAC-signed)-->  bridge /teams  --> OpenClaw gateway
OpenClaw gateway --(local POST)--> bridge /to-teams --(Incoming Webhook)--> Teams channel
```

The Incoming Webhook half is now dead (see above). The Outgoing Webhook half (Teams → bridge, only
on @mention) is a separate, older Teams feature not directly affected by the Connector retirement,
but building new production infrastructure on it is not recommended given Microsoft's clear
direction away from all classic webhook-style Teams integration toward Bot Framework and Workflows.
