# Teams ↔ OpenClaw webhook bridge

NemoClaw/OpenClaw ships Telegram, Discord, and Slack channels — but **not Microsoft Teams**.
openAut defaults to Teams, so this minimal bridge maps the two directions using Teams' built-in
webhook surfaces — no Azure Bot registration, no app manifest.

```
 Teams channel  --(Outgoing Webhook, HMAC-signed)-->  bridge /teams  --> OpenClaw gateway
 OpenClaw gateway --(local POST)--> bridge /to-teams --(Incoming Webhook)--> Teams channel
```

Two Teams features do the work:

- **Incoming Webhook** (gateway → Teams): a per-channel URL you POST a JSON card to. Goes in
  `TEAMS_INCOMING_WEBHOOK_URL`.
- **Outgoing Webhook** (Teams → gateway): Teams POSTs to your endpoint when the bot is @mentioned,
  signed with an HMAC shared secret. Goes in `TEAMS_OUTGOING_SECRET`, endpoint
  `http://$TEAMS_BRIDGE_HOST:$TEAMS_BRIDGE_PORT/teams`.

> Outgoing Webhooks only fire on @mention and only reply within that channel. That fits the openAut
> personas (alarm threads, weekly summaries, decision pings). If you later need proactive 1:1
> messages or adaptive cards at scale, graduate to Azure Bot Service — the bridge contract
> (gateway ↔ HTTP) stays the same, only this process is replaced.

## Setup

1. **Incoming Webhook** — in the target Teams channel: *Connectors → Incoming Webhook → Create*,
   copy the URL into `TEAMS_INCOMING_WEBHOOK_URL` in `config.env`.
2. **Outgoing Webhook** — *Team → Manage → Outgoing Webhooks → Create*; callback URL =
   `http://<bridge-host>:<port>/teams`; copy the generated HMAC secret into `TEAMS_OUTGOING_SECRET`.
3. **Run the bridge** co-located with the gateway (simplest: on the sandbox host, loopback):

   ```bash
   set -a; . ./config.env; set +a
   python3 bridges/teams-webhook/teams_bridge.py
   ```

4. **Bind the gateway** to the bridge: point the gateway's generic webhook/webchat surface at
   `http://$TEAMS_BRIDGE_HOST:$TEAMS_BRIDGE_PORT/from-gateway`, or have your agents POST replies
   there. (Exact gateway webhook config depends on your OpenClaw version.)
5. **Egress** — ensure `nemoclaw-sandbox-policy` allow-lists the bridge host and the Teams webhook
   domain; everything else stays denied.

## Security notes

- The bridge **verifies the HMAC signature** on every inbound Teams request and rejects unsigned or
  mismatched ones — without this, anyone who learns the URL could inject messages to your agent.
- It binds to `$TEAMS_BRIDGE_HOST` (loopback by default). Do not expose it on a public interface;
  if Teams' cloud must reach it, front it with a tunnel/reverse proxy that terminates TLS.
- Treat all Teams text as untrusted input to the agent (prompt-injection surface) — the sandbox
  policy is the backstop.

> This is a reference stub: it shows the contract and the security checks, not a production service.
> Live behaviour is unverified until wired to a real Teams channel and gateway.
