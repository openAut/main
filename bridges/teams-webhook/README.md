# Teams ↔ OpenClaw — retired approach, see msteams plugin

> **This bridge is retired.** It relied on Microsoft Teams' **Incoming Webhook** (an Office 365
> Connector). Microsoft's Office 365 Connectors retirement in Teams had several deadline extensions
> (December 2025 → March 2026 → April 30, 2026) before the final disable rollout of
> **May 18-22, 2026** — see the [Microsoft 365 Developer Blog notice](https://devblogs.microsoft.com/microsoft365dev/retirement-of-office-365-connectors-within-microsoft-teams/)
> and check the [Microsoft 365 Message Center](https://admin.microsoft.com) for your own tenant's
> exact status, since Message Center rollout notices can vary by tenant ring. `TEAMS_INCOMING_WEBHOOK_URL`
> posts to `webhook.office.com` no longer work. Do not deploy this bridge. Kept only as a historical
> record of the earlier design.

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

**This retired bridge already had an inbound path too** — its Outgoing Webhook half was Teams
calling *into* the bridge's `/teams` endpoint on @mention, HMAC-signed. The difference isn't
"outbound-only vs. inbound": it's *narrower, event-triggered* inbound (fires only on @mention, one
HMAC-verified request at a time) vs. the native `msteams` plugin's *standing* inbound requirement —
Teams' cloud must be able to reach **your** `/api/messages` endpoint at any time, authenticated by
Bot Framework rather than a shared HMAC secret. That's a bigger, always-on surface, not a new
category of exposure — and to be clear, **this retired bridge's own inbound path was never resolved
for production either**; it was a reference stub (see its Security notes, preserved below), not a
hardened answer. Don't read "the old bridge was simpler" as "the old bridge had no open questions."
That cuts against openAut's deny-by-default, outbound-only sandbox posture and is a real
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
