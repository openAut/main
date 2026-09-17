---
name: nemoclaw-provision
description: Provision a NemoClaw agent on a remote server end-to-end — SSH preflight, run the NemoClaw installer, onboard a sandbox pointed at a remote Nemotron 3 Super inference host over TLS, attach a Microsoft Teams channel via OpenClaw's native msteams plugin, and verify. Use when standing up an openAut agent host, installing or onboarding NemoClaw/OpenClaw on a DGX Spark or RTX box, or wiring an agent to remote inference and Teams.
metadata:
  openaut-permissions: '{"knowledge_only":false,"exec":"allowlisted scripts (preflight.sh, verify-inference.sh) over SSH","network":"SSH to sandbox host; TLS to Nemotron inference endpoint","files":"read-only (sources config.env)","credentials":"SSH + NEMOTRON_API_KEY/CA from config.env (node-provisioned, not in repo)"}'
---

# nemoclaw-provision — install an openAut NemoClaw agent

Drives NVIDIA's documented NemoClaw install flow over SSH and wires it to the two openAut defaults:
**Microsoft Teams** as the channel and a **remote Nemotron 3 Super** inference host reached over
**TLS with locked egress**.

This skill installs the platform and creates the sandbox. It does **not** define the role agents —
that is [`nemoclaw-agent-workflow`](../nemoclaw-agent-workflow/SKILL.md) — nor the egress hardening
detail — that is [`nemoclaw-sandbox-policy`](../nemoclaw-sandbox-policy/SKILL.md). Run those two
after this one.

## Prerequisites

- `config.env` filled in (copy from `config.env.example` at the repo root). All commands below
  assume it is sourced: `set -a; . ./config.env; set +a`.
- SSH access to `$SANDBOX_HOST` as `$SANDBOX_SSH_USER` (key-based, no passphrase prompts).
- The **Nemotron host already serves vLLM behind a TLS reverse proxy** on `$NEMOTRON_TLS_PORT`,
  and `$NEMOTRON_CA_CERT` exists on the sandbox host. If not, set that up first — see
  [`nemoclaw-sandbox-policy`](../nemoclaw-sandbox-policy/SKILL.md) §"TLS in front of vLLM".
- **Microsoft Teams** channel access: ability to create an Azure Bot / Entra ID app registration
  (via `teams app create` or the Azure portal) in the target tenant — see
  [`bridges/teams-webhook`](../../bridges/teams-webhook/README.md) for why the old webhook approach
  is retired and what replaced it.

> All SSH from this skill runs as: `ssh "$SANDBOX_SSH_USER@$SANDBOX_HOST" '<remote command>'`.
> On Windows hosts run the SSH from PowerShell so the ssh-agent key is available.

## Step 1 — Preflight the target host

NemoClaw requires Ubuntu 24.04, an NVIDIA GPU, and Docker 28+. Verify before touching anything:

```bash
bash skills/nemoclaw-provision/scripts/preflight.sh
```

The script SSHes in and checks `/etc/os-release`, `nvidia-smi`, and `docker info`. Abort if any
check fails — a half-met prerequisite makes the installer fail deep into the wizard.

## Step 2 — Run the NemoClaw installer

The installer adds Node, the OpenShell runtime, the pinned NemoClaw CLI, then launches onboarding.

```bash
ssh "$SANDBOX_SSH_USER@$SANDBOX_HOST" \
  "curl -fsSL https://www.nvidia.com/nemoclaw.sh | NEMOCLAW_INSTALL_TAG=$NEMOCLAW_INSTALL_TAG bash"
```

Accept the license (`yes`). This launches the `nemoclaw onboard` wizard.

## Step 3 — Onboard the sandbox against remote Nemotron 3 Super

The wizard presents a numbered list of inference providers. Select **Other OpenAI-compatible
endpoint** — not "NVIDIA Endpoints" (that routes to NVIDIA's cloud) and not any "Local" option (that
means a model running on the sandbox host itself, not our remote GPU box):

1. **Provider** → **Other OpenAI-compatible endpoint**.
2. **Endpoint URL** → `$NEMOTRON_BASE_URL` (e.g. `https://192.168.1.43:8443/v1`).
3. **Model** → `$NEMOTRON_MODEL` (`nemotron-3-super`).
4. **API key** → `$NEMOTRON_API_KEY` (a non-empty placeholder if the proxy needs none — the wizard
   requires a value even for unauthenticated endpoints).
5. **Sandbox name** → `$SANDBOX_NAME`.
6. Skip the Telegram/Discord/Slack channel prompt — Teams is attached separately in Step 5.

The network policy applied at this point is NemoClaw's default baseline (`nvidia`/`clawhub`/
`openclaw_api`/`openclaw_docs` presets) — leave it as-is here; [`nemoclaw-sandbox-policy`](../nemoclaw-sandbox-policy/SKILL.md)
removes the unwanted defaults and adds the openAut-specific presets afterward. Do not try to lock
egress from inside this wizard.

For a second sandbox, or scripted deployment, use the documented non-interactive form:

```bash
ssh "$SANDBOX_SSH_USER@$SANDBOX_HOST" \
  "NEMOCLAW_PROVIDER=custom \
   NEMOCLAW_ENDPOINT_URL='$NEMOTRON_BASE_URL' \
   NEMOCLAW_MODEL='$NEMOTRON_MODEL' \
   COMPATIBLE_API_KEY='$NEMOTRON_API_KEY' \
   nemoclaw onboard --non-interactive --name $SANDBOX_NAME"
```

> **Why "Other OpenAI-compatible endpoint" and not a local option:** the agent inside the sandbox
> always talks to `inference.local`; OpenShell intercepts that traffic on the host and forwards it to
> whichever provider you configured. Selecting the compatible-endpoint provider with our remote
> `$NEMOTRON_BASE_URL` keeps the 120B MoE model off the agent host and on the dedicated GPU box,
> without the model ever being reachable directly by the sandboxed agent.

## Step 4 — Make the sandbox trust the Nemotron TLS endpoint

The sandbox must verify the proxy's certificate rather than skip verification. Ensure the CA cert is
present and referenced. With a self-signed/internal CA, install it into the sandbox trust store:

```bash
ssh "$SANDBOX_SSH_USER@$SANDBOX_HOST" \
  "test -f $NEMOTRON_CA_CERT && echo 'CA present' || echo 'MISSING CA — fix before continuing'"
```

Never disable TLS verification to "make it work". If verification fails, fix the cert chain — a
disabled check defeats the whole point of the egress-lock + TLS default.

## Step 5 — Attach the Microsoft Teams channel (native msteams plugin)

Teams is a **native, bundled OpenClaw channel plugin** (`msteams`, Bot Framework / Azure Bot based)
— it does not need a custom bridge. The earlier `bridges/teams-webhook` approach is retired: it
relied on Teams Incoming Webhooks (Office 365 Connectors), which Microsoft discontinued in a
rollout completed 2026-05-22.

1. Provision the bot — simplest path, no manual Azure portal steps:
   ```bash
   ssh "$SANDBOX_SSH_USER@$SANDBOX_HOST" \
     "teams app create --name 'openAut Advisor' --endpoint 'https://<endpoint>/api/messages'"
   ```
   This registers an Entra ID app + bot and prints `CLIENT_ID`/`CLIENT_SECRET`/`TENANT_ID` — save
   them into `MSTEAMS_APP_ID`/`MSTEAMS_APP_PASSWORD`/`MSTEAMS_TENANT_ID` in `config.env`.
2. Configure OpenClaw:
   ```json5
   {
     channels: {
       msteams: {
         enabled: true,
         appId: "$MSTEAMS_APP_ID",
         appPassword: "$MSTEAMS_APP_PASSWORD",
         tenantId: "$MSTEAMS_TENANT_ID",
         webhook: { port: 3978, path: "/api/messages" },
       },
     },
   }
   ```
3. Install the resulting Teams app package into the target team (or personal scope for DMs).

> **Open design question — not resolved here:** `msteams` requires Teams' cloud to reach your
> `/api/messages` endpoint, i.e. an **inbound** path, unlike everything else this skill sets up
> (which is outbound-only). For a dev/lab setup, a tunnel (`devtunnel`/`tailscale funnel`) is enough
> — see the Microsoft Teams plugin docs. Whether production exposes an endpoint directly or routes
> through a DMZ relay that re-terminates into the sandbox is **explicitly deferred** — see
> [`nemoclaw-sandbox-policy`](../nemoclaw-sandbox-policy/SKILL.md). Do not expose `$SANDBOX_HOST`
> directly to the internet as a shortcut.

## Step 6 — Verify end-to-end

```bash
bash skills/nemoclaw-provision/scripts/verify-inference.sh
ssh "$SANDBOX_SSH_USER@$SANDBOX_HOST" "nemoclaw $SANDBOX_NAME status"
```

`verify-inference.sh` curls `$NEMOTRON_BASE_URL/models` **over TLS with the CA cert** and confirms
`$NEMOTRON_MODEL` is listed. The `status` output should show inference healthy and the sandbox
running. Then send a test message to the Teams app and confirm the agent replies in Teams.

## Lifecycle reference

```bash
ssh "$SANDBOX_SSH_USER@$SANDBOX_HOST" "nemoclaw list"                       # all sandboxes
ssh "$SANDBOX_SSH_USER@$SANDBOX_HOST" "nemoclaw $SANDBOX_NAME status"       # health + inference
ssh "$SANDBOX_SSH_USER@$SANDBOX_HOST" "nemoclaw $SANDBOX_NAME logs --follow"
ssh "$SANDBOX_SSH_USER@$SANDBOX_HOST" "nemoclaw $SANDBOX_NAME recover"      # restart if stale
```

> **Live behaviour is unverified until a DGX Spark / RTX host is available.** The onboarding shape
> (provider list including "Other OpenAI-compatible endpoint", `NEMOCLAW_PROVIDER`/`NEMOCLAW_ENDPOINT_URL`/
> `NEMOCLAW_MODEL`/`COMPATIBLE_API_KEY` for non-interactive setup, `nemoclaw status`) is confirmed
> against NVIDIA's NemoClaw documentation as of this writing. What's still unverified end-to-end: the
> exact `nemoclaw onboard --non-interactive --name` flag combination, and whether `$SANDBOX_NAME` is
> required or optional per sandbox-lifecycle command on your installed version — check
> `nemoclaw onboard --help` against a live host before scripting this unattended.

## Troubleshooting

- **Inference timeout** — confirm the vLLM box is up and the TLS proxy forwards to it; watch for
  vLLM "Application startup complete"; check the sandbox can reach `$NEMOTRON_HOST:$NEMOTRON_TLS_PORT`
  (it must be on the egress allow-list — see `nemoclaw-sandbox-policy`).
- **TLS verification fails** — the CA cert is wrong or not trusted; fix the chain, do not skip verify.
- **Teams silent** — check the msteams plugin logs, that `appId`/`appPassword`/`tenantId` are
  correct, that the inbound endpoint (tunnel or relay) is actually reachable from Teams' cloud, and
  that the app package is installed in the target team.
