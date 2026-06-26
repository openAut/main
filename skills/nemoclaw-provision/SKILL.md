---
name: nemoclaw-provision
description: Provision a NemoClaw agent on a remote server end-to-end — SSH preflight, run the NemoClaw installer, onboard a sandbox pointed at a remote Nemotron 3 Super inference host over TLS, attach a Microsoft Teams channel via webhook bridge, and verify. Use when standing up an openAut agent host, installing or onboarding NemoClaw/OpenClaw on a DGX Spark or RTX box, or wiring an agent to remote inference and Teams.
permissions:
  knowledge_only: false
  exec: "allowlisted scripts (preflight.sh, verify-inference.sh) over SSH"
  network: "SSH to sandbox host; TLS to Nemotron inference endpoint"
  files: "read-only (sources config.env)"
  credentials: "SSH + NEMOTRON_API_KEY/CA from config.env (node-provisioned, not in repo)"
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
- The **Teams webhook bridge** is deployable — see [`bridges/teams-webhook`](../../bridges/teams-webhook/README.md).

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
Run it **non-express** so we can point inference at the remote host instead of accepting local vLLM:

```bash
ssh "$SANDBOX_SSH_USER@$SANDBOX_HOST" \
  "curl -fsSL https://www.nvidia.com/nemoclaw.sh | NEMOCLAW_INSTALL_TAG=$NEMOCLAW_INSTALL_TAG bash"
```

Accept the license (`yes`). When asked **Express vs Custom**, choose **Custom** — express install
hard-codes local vLLM and we want remote Nemotron.

## Step 3 — Onboard the sandbox against remote Nemotron 3 Super

In the wizard:

1. **Inference Backend** → choose **Custom / OpenAI-compatible endpoint** (not "Local vLLM").
2. **Base URL** → `$NEMOTRON_BASE_URL` (e.g. `https://192.168.1.43:8443/v1`).
3. **Model** → `$NEMOTRON_MODEL` (`nemotron-3-super`).
4. **API key** → `$NEMOTRON_API_KEY` (blank if the proxy needs none).
5. **Sandbox name** → `$SANDBOX_NAME`.
6. **Policy tier** → **Balanced** (we tighten egress in the next skill).
7. Skip the Telegram/Discord/Slack channel prompt — Teams is attached separately in Step 5.

If you prefer non-interactive onboarding for a second sandbox:

```bash
ssh "$SANDBOX_SSH_USER@$SANDBOX_HOST" \
  "nemoclaw onboard --gpu --name $SANDBOX_NAME"
# then set the inference backend explicitly (see your NemoClaw version's `inference` subcommand)
```

> **Why custom and not local:** NemoClaw's inference layer is hot-reloadable and routes calls to
> whatever backend you configure. Pointing it at the remote OpenAI-compatible endpoint keeps the
> 120B MoE model off the agent host and on the dedicated GPU box.

## Step 4 — Make the sandbox trust the Nemotron TLS endpoint

The sandbox must verify the proxy's certificate rather than skip verification. Ensure the CA cert is
present and referenced. With a self-signed/internal CA, install it into the sandbox trust store:

```bash
ssh "$SANDBOX_SSH_USER@$SANDBOX_HOST" \
  "test -f $NEMOTRON_CA_CERT && echo 'CA present' || echo 'MISSING CA — fix before continuing'"
```

Never disable TLS verification to "make it work". If verification fails, fix the cert chain — a
disabled check defeats the whole point of the egress-lock + TLS default.

## Step 5 — Attach the Microsoft Teams channel (webhook bridge)

Teams is not a native NemoClaw channel. Deploy the bridge, then point the gateway's generic
webhook/webchat surface at it. Full steps: [`bridges/teams-webhook`](../../bridges/teams-webhook/README.md).

Summary:

1. Create a **Teams Incoming Webhook** in the target channel → put its URL in
   `TEAMS_INCOMING_WEBHOOK_URL` (gateway → Teams).
2. Create a **Teams Outgoing Webhook** pointing at `http://$TEAMS_BRIDGE_HOST:$TEAMS_BRIDGE_PORT/teams`
   with a shared secret → put it in `TEAMS_OUTGOING_SECRET` (Teams → gateway).
3. Run the bridge near the gateway (co-located on the sandbox host is simplest).
4. The egress policy in the next skill must allow the bridge host and the Teams webhook domain.

## Step 6 — Verify end-to-end

```bash
bash skills/nemoclaw-provision/scripts/verify-inference.sh
ssh "$SANDBOX_SSH_USER@$SANDBOX_HOST" "nemoclaw $SANDBOX_NAME status"
```

`verify-inference.sh` curls `$NEMOTRON_BASE_URL/models` **over TLS with the CA cert** and confirms
`$NEMOTRON_MODEL` is listed. The `status` output should show inference healthy and the sandbox
running. Then post a test message from the gateway through the bridge and confirm it lands in Teams.

## Lifecycle reference

```bash
ssh "$SANDBOX_SSH_USER@$SANDBOX_HOST" "nemoclaw list"                       # all sandboxes
ssh "$SANDBOX_SSH_USER@$SANDBOX_HOST" "nemoclaw $SANDBOX_NAME status"       # health + inference
ssh "$SANDBOX_SSH_USER@$SANDBOX_HOST" "nemoclaw $SANDBOX_NAME logs --follow"
ssh "$SANDBOX_SSH_USER@$SANDBOX_HOST" "nemoclaw $SANDBOX_NAME recover"      # restart if stale
```

> **Live behaviour is unverified until a DGX Spark / RTX host is available.** Wizard prompt wording
> and the exact inference subcommand may differ across NemoClaw releases — adapt the labels, the
> flow (preflight → install → remote inference → TLS trust → Teams → verify) holds.

## Troubleshooting

- **Inference timeout** — confirm the vLLM box is up and the TLS proxy forwards to it; watch for
  vLLM "Application startup complete"; check the sandbox can reach `$NEMOTRON_HOST:$NEMOTRON_TLS_PORT`
  (it must be on the egress allow-list — see `nemoclaw-sandbox-policy`).
- **TLS verification fails** — the CA cert is wrong or not trusted; fix the chain, do not skip verify.
- **Teams silent** — check the bridge logs, the outgoing-webhook secret, and that the Teams webhook
  domain is on the egress allow-list.
