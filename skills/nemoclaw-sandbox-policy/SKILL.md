---
name: nemoclaw-sandbox-policy
description: Harden a NemoClaw sandbox after creation — deny-by-default network egress allow-listed to the remote Nemotron inference host, local Forgejo, and the Teams webhook bridge, TLS in front of vLLM, and a hardening review mapped to IEC 62443 / NIS2 / CRA. Use when locking down an openAut agent's network access, reviewing sandbox security, setting up TLS for remote inference, allowing local Forge access, or managing the four sandbox layers (filesystem, process, network, inference).
---

# nemoclaw-sandbox-policy — lock down the openAut sandbox

NemoClaw sandboxes enforce four layers: **filesystem** and **process** are locked at creation;
**network** and **inference** are hot-reloadable. This skill tightens the two hot-reloadable layers
to the openAut defaults — **deny-by-default egress** that allows only the remote Nemotron host, the
local Forge, and the Teams bridge — and stands up the **TLS** the inference link depends on.

Run this **after** [`nemoclaw-provision`](../nemoclaw-provision/SKILL.md) and **before** exposing the
agent to users. Assumes `config.env` is sourced.

## The target egress allow-list

By default the sandbox should reach **nothing** except:

| Destination | Why | Source of value |
|---|---|---|
| `$NEMOTRON_HOST:$NEMOTRON_TLS_PORT` | remote Nemotron 3 Super inference over TLS | `config.env` |
| local Forgejo host:port | versioned docs/code/artifacts from openAut Forge | `$FORGE_HOST:$FORGE_PORT` |
| Teams webhook bridge host:port | gateway → bridge → Teams | `$TEAMS_BRIDGE_HOST:$TEAMS_BRIDGE_PORT` |
| Teams Incoming Webhook domain | bridge → Teams channel (`*.webhook.office.com`) | from `TEAMS_INCOMING_WEBHOOK_URL` |

Everything else — package mirrors, model hubs, arbitrary outbound — stays denied. This is the
control that turns "an agent with shell access" into "an agent that can only talk to its model, its
local source-of-record, and its channel", and it is what satisfies the openAut NIS2 / IEC 62443
posture.

## Step 1 — Inspect current policy

```bash
ssh "$SANDBOX_SSH_USER@$SANDBOX_HOST" "nemoclaw $SANDBOX_NAME policy-list"
```

Note the active network presets. The "Balanced" tier set during onboarding is broader than we want.

## Step 2 — Apply the deny-by-default egress allow-list

Network policy is hot-reloadable, so this takes effect without rebuilding the sandbox. Add only the
required destinations (exact subcommand/flags vary by NemoClaw version — adapt to your `policy-add`):

```bash
# Remote inference host (TLS port only)
ssh "$SANDBOX_SSH_USER@$SANDBOX_HOST" \
  "nemoclaw $SANDBOX_NAME policy-add egress --host $NEMOTRON_HOST --port $NEMOTRON_TLS_PORT --proto tcp"

# Teams webhook bridge (if not co-located on loopback)
ssh "$SANDBOX_SSH_USER@$SANDBOX_HOST" \
  "nemoclaw $SANDBOX_NAME policy-add egress --host $TEAMS_BRIDGE_HOST --port $TEAMS_BRIDGE_PORT --proto tcp"

# Local Forgejo host
ssh "$SANDBOX_SSH_USER@$SANDBOX_HOST" \
  "nemoclaw $SANDBOX_NAME policy-add egress --host $FORGE_HOST --port $FORGE_PORT --proto tcp"

# Teams Incoming Webhook domain (Microsoft), if the bridge sends from inside the sandbox
ssh "$SANDBOX_SSH_USER@$SANDBOX_HOST" \
  "nemoclaw $SANDBOX_NAME policy-add egress --host outlook.office.com --port 443 --proto tcp"
```

Then confirm the default is **deny**, not allow:

```bash
ssh "$SANDBOX_SSH_USER@$SANDBOX_HOST" "nemoclaw $SANDBOX_NAME policy-list"
```

If the tier defaults to allow-all-outbound, switch it to a deny-by-default preset and re-add the
destinations above. The acceptance test: from inside the sandbox, a request to any host other than
the allow-listed destinations must fail.

## Step 3 — TLS in front of vLLM (on the Nemotron host)

vLLM serves plaintext HTTP (commonly `:11434`). Do **not** expose that on the network. Put a TLS
reverse proxy on the Nemotron host and only allow-list the TLS port. Example with Caddy:

```
# /etc/caddy/Caddyfile on the Nemotron host
{$NEMOTRON_TLS_HOST}:8443 {
    tls /etc/caddy/nemotron.crt /etc/caddy/nemotron.key
    reverse_proxy 127.0.0.1:11434
}
```

- Generate the cert from your internal CA (or a private mkcert CA). Export that CA's public cert to
  the sandbox host as `$NEMOTRON_CA_CERT` so the sandbox can verify the proxy — see
  [`nemoclaw-provision`](../nemoclaw-provision/SKILL.md) Step 4.
- Bind vLLM to `127.0.0.1` only; the proxy is the sole public listener.
- Optionally require a bearer token at the proxy and set `NEMOTRON_API_KEY` to it (mTLS is stronger
  if both ends are under your control).

Verify the TLS path with the provision skill's `verify-inference.sh` (it uses `--cacert`, never `-k`).

## Step 4 — Confirm the locked layers

Filesystem and process layers are fixed at creation; just confirm they are sane:

```bash
ssh "$SANDBOX_SSH_USER@$SANDBOX_HOST" "nemoclaw $SANDBOX_NAME status"
```

Expect the sandbox line to report `Landlock + seccomp + netns`. The filesystem layer should expose
only the agent's working directory, not host paths with credentials. If it is wrong, the layer can
only be changed by recreating the sandbox (`nemoclaw onboard --fresh --gpu --name $SANDBOX_NAME` —
**destructive**), so get it right at provision time.

## Hardening review checklist (map to the openAut frameworks)

| Control | Check | Framework |
|---|---|---|
| Deny-by-default egress | `policy-list` shows only the allow-listed destinations | NIS2 Art. 21, IEC 62443 SR 5.1 (zone/conduit) |
| Encrypted inference link | TLS verified with CA cert; no `-k`/insecure anywhere | IEC 62443 SR 4.1, CRA Annex I |
| No host credential exposure | filesystem layer scoped to working dir only | NIS2, ISO 27001 A.8 |
| Least-privilege channel/source access | only Teams bridge and local Forge reachable; no other chat/Git egress | IEC 62443 SR 7.x |
| Inference goes to the trusted model only | base URL pinned to `$NEMOTRON_HOST`, no fallback to public APIs | AI Act (provider control), CRA |
| Auditable lifecycle | `nemoclaw logs` retained; recover path tested | NIS2 Art. 23 (incident handling) |

For the broader managed-workspace design rationale (access broker, credential proxy, deny-by-default
egress as a pattern), pair this with a secure-agent-workspace review.

> **Live behaviour is unverified until a NemoClaw host is available.** `policy-add` flag names differ
> across releases — the principle (allow exactly three destinations, deny the rest, TLS-verify the
> inference link, local Forge, and Teams bridge) is what to preserve.
