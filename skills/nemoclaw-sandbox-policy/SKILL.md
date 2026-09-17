---
name: nemoclaw-sandbox-policy
description: Harden a NemoClaw sandbox after creation — deny-by-default network egress allow-listed to the remote Nemotron inference host, local Forgejo, and Microsoft's Bot Framework/Teams services for the native msteams plugin, TLS in front of vLLM, and a hardening review mapped to IEC 62443 / NIS2 / CRA. Use when locking down an openAut agent's network access, reviewing sandbox security, setting up TLS for remote inference, allowing local Forge access, or managing the four sandbox layers (filesystem, process, network, inference).
metadata:
  openaut-permissions: '{"knowledge_only":true,"tools":"none","network":"none","exec":"none"}'
---

# nemoclaw-sandbox-policy — lock down the openAut sandbox

NemoClaw sandboxes enforce four layers: **filesystem** and **process** are locked at creation;
**network** and **inference** are hot-reloadable. This skill tightens the two hot-reloadable layers
to the openAut defaults — **deny-by-default egress** that allows only the remote Nemotron host, the
local Forge, and Microsoft's Bot Framework services for the native `msteams` channel plugin — and
stands up the **TLS** the inference link depends on.

Run this **after** [`nemoclaw-provision`](../nemoclaw-provision/SKILL.md) and **before** exposing the
agent to users. Assumes `config.env` is sourced.

## The target egress allow-list

By default the sandbox should reach **nothing** except:

| Destination | Why | Source of value |
|---|---|---|
| `$NEMOTRON_HOST:$NEMOTRON_TLS_PORT` | remote Nemotron 3 Super inference over TLS | `config.env` |
| local Forgejo host:port | versioned docs/code/artifacts from openAut Forge | `$FORGE_HOST:$FORGE_PORT` |
| `msteams` outbound (Bot Framework auth + Connector service) | native Teams plugin sends replies via Microsoft's Bot Connector, authenticated via Entra | consult the msteams plugin's `serviceUrl`/cloud config for exact hosts — do not guess |

**Inbound is a separate, unresolved question.** The native `msteams` plugin also needs Teams' cloud
to reach `$MSTEAMS_WEBHOOK_PORT` on this host — that's inbound, not egress, and this skill does not
cover it. See [`nemoclaw-provision`](../nemoclaw-provision/SKILL.md) Step 5 and
[`bridges/teams-webhook`](../../bridges/teams-webhook/README.md) for why it's deliberately left open
(direct exposure vs. a DMZ relay). Do not open an inbound port on `$SANDBOX_HOST` as a shortcut —
resolve the relay design first.

Everything else — package mirrors, model hubs, arbitrary outbound — stays denied. This is the
control that turns "an agent with shell access" into "an agent that can only talk to its model, its
local source-of-record, and its channel", and it is what satisfies the openAut NIS2 / IEC 62443
posture.

## Step 1 — Inspect current policy

```bash
openshell sandbox connect "$SANDBOX_NAME"
# or, from the gateway host:
openshell policy get "$SANDBOX_NAME" --full > current-policy.yaml
```

Note the active network presets. The NemoClaw baseline for an OpenClaw sandbox
(`nemoclaw-blueprint/policies/openclaw-sandbox.yaml`) ships with these presets **enabled by
default** — none of them are openAut destinations:

| Preset | Endpoints | Why it's there by default |
|---|---|---|
| `nvidia` | `integrate.api.nvidia.com:443`, `inference-api.nvidia.com:443` | NVIDIA-hosted cloud inference (not your local Nemotron host) |
| `clawhub` | `clawhub.ai:443` | community skill registry |
| `openclaw_api` | `openclaw.ai:443` | OpenClaw account/API services |
| `openclaw_docs` | `docs.openclaw.ai:443` | in-agent docs fetch |

**If openAut requires local-only inference — and the architecture's "stays on-prem" claim depends on
it — these defaults must be actively removed, not just left alongside the local additions below.**
Leaving `nvidia` enabled means the sandbox can reach NVIDIA's cloud inference in parallel with the
local Nemotron host, which silently breaks data locality.

## Step 2 — Remove the default cloud/registry presets

Policies are declarative YAML, not imperative flags. Edit the snapshot from Step 1 and delete the
`nvidia`, `clawhub`, `openclaw_api`, and `openclaw_docs` entries under `network_policies` (keep
`openclaw_docs` only if operators need in-sandbox doc lookups — otherwise remove it too), then push
the trimmed policy back:

```bash
openshell policy set "$SANDBOX_NAME" --policy current-policy.yaml --wait
```

`--wait` blocks until the sandbox confirms the new policy is loaded; no rebuild required — network
policy is hot-reloadable.

## Step 3 — Add the openAut egress allow-list

Add each openAut destination as its own **preset file** under
`nemoclaw-blueprint/policies/presets/`, then merge it into the live policy. This is the same
structured-merge pattern NemoClaw uses for any custom endpoint — it does not overwrite the rest of
the policy the way a full `policy set` would.

```yaml
# nemoclaw-blueprint/policies/presets/local-nemotron.yaml
preset:
  name: local-nemotron
  description: "Local Nemotron 3 Super inference over TLS"
network_policies:
  local-nemotron:
    name: local-nemotron
    endpoints:
      - host: "$NEMOTRON_HOST"
        port: "$NEMOTRON_TLS_PORT"
        protocol: rest
        tls: terminate
        enforcement: enforce
    binaries:
      - { path: /usr/local/bin/openclaw }
```

```yaml
# nemoclaw-blueprint/policies/presets/local-forge.yaml
preset:
  name: local-forge
  description: "Local Forgejo — versioned docs/code/artifacts"
network_policies:
  local-forge:
    name: local-forge
    endpoints:
      - host: "$FORGE_HOST"
        port: "$FORGE_PORT"
        protocol: rest
        enforcement: enforce
    binaries:
      - { path: /usr/local/bin/openclaw }
```

```yaml
# nemoclaw-blueprint/policies/presets/msteams-outbound.yaml
# TODO: fill in the exact hosts once confirmed against the msteams plugin's active `serviceUrl`/
# cloud config (Public/GCC/GCC High/DoD each use different Bot Connector hosts — do not guess).
# Likely candidates to verify: Entra ID token endpoint (login.microsoftonline.com) and the Bot
# Framework Connector service host for your configured cloud.
preset:
  name: msteams-outbound
  description: "Native msteams plugin — Bot Framework auth + Connector service (egress only)"
network_policies:
  msteams-outbound:
    name: msteams-outbound
    endpoints:
      - host: "REPLACE_ME_login_microsoftonline_com"
        port: 443
        protocol: rest
        enforcement: enforce
      - host: "REPLACE_ME_bot_connector_service_host"
        port: 443
        protocol: rest
        enforcement: enforce
    binaries:
      - { path: /usr/local/bin/openclaw }
```

**This preset is a placeholder, not a verified policy — do not apply it as-is.** Confirm the exact
hostnames against a live `msteams` deployment (`openshell logs` will show what it actually tries to
reach and gets denied) before enforcing egress here; applying a guessed allow-list is worse than
leaving it open during initial testing, because it fails silently instead of loudly.

Apply each preset:

```bash
nemoclaw "$SANDBOX_NAME" policy-add --from-file nemoclaw-blueprint/policies/presets/local-nemotron.yaml
nemoclaw "$SANDBOX_NAME" policy-add --from-file nemoclaw-blueprint/policies/presets/local-forge.yaml
# msteams-outbound is NOT applied here yet -- fill in the placeholder above with verified
# hosts first (see the warning above), then add it the same way as the other two presets.
```

`nemoclaw <sandbox> policy-add --from-file` reads the live policy via `openshell policy get --full`,
structurally merges the preset's `network_policies` into it, and writes the merged result back. Preset
files under `presets/` also persist across sandbox recreations — commit them to the openAut Forge.

Confirm the result:

```bash
openshell policy get "$SANDBOX_NAME" --full
```

Expect to see exactly `local-nemotron` and `local-forge` under `network_policies` for now —
**no** `nvidia`, `clawhub`, `openclaw_api`, or `openclaw_docs` entries. The acceptance test: from
inside the sandbox, a request to any host other than these two destinations must fail, including
`integrate.api.nvidia.com`.

## Step 4 — TLS in front of vLLM (on the Nemotron host)

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

## Step 5 — Confirm the locked layers

Filesystem and process layers are fixed at creation; just confirm they are sane:

```bash
openshell sandbox connect "$SANDBOX_NAME" -- nemoclaw status
```

Expect the sandbox line to report `Landlock + seccomp + netns`. The filesystem layer should expose
only the agent's working directory, not host paths with credentials. If it is wrong, the layer can
only be changed by recreating the sandbox (`nemoclaw onboard --fresh --gpu --name $SANDBOX_NAME` —
**destructive**), so get it right at provision time.

## Hardening review checklist (map to the openAut frameworks)

| Control | Check | Framework |
|---|---|---|
| Deny-by-default egress | `openshell policy get "$SANDBOX_NAME" --full` shows only `local-nemotron`/`local-forge` (+ `msteams-outbound` once hosts are verified) | NIS2 Art. 21, IEC 62443 SR 5.1 (zone/conduit) |
| No cloud-inference leakage | default `nvidia`, `clawhub`, `openclaw_api`, `openclaw_docs` presets removed, not just left alongside the local additions | AI Act (provider control), CRA, data locality |
| Encrypted inference link | TLS verified with CA cert; no `-k`/insecure anywhere | IEC 62443 SR 4.1, CRA Annex I |
| No host credential exposure | filesystem layer scoped to working dir only | NIS2, ISO 27001 A.8 |
| Least-privilege channel/source access | only verified Bot Framework hosts and local Forge reachable; no other chat/Git egress | IEC 62443 SR 7.x |
| Inbound path for msteams reviewed | direct exposure vs. DMZ relay decided and documented before production | IEC 62443 SR 5.1, NIS2 Art. 21 |
| Auditable lifecycle | `nemoclaw logs` retained; recover path tested | NIS2 Art. 23 (incident handling) |

For the broader managed-workspace design rationale (access broker, credential proxy, deny-by-default
egress as a pattern), pair this with a secure-agent-workspace review.

> **Live behaviour is unverified until a NemoClaw host is available.** The policy mechanism itself
> (declarative YAML, `openshell policy set/get`, `nemoclaw <sandbox> policy-add --from-file` for
> structured preset merges) is confirmed against NVIDIA's OpenShell/NemoClaw documentation as of this
> writing — exact preset field names may still shift across releases. The principle to preserve:
> remove the default `nvidia`/`clawhub`/`openclaw_api`/`openclaw_docs` presets, allow exactly
> `local-nemotron` and `local-forge` (msteams egress once verified), deny the rest, TLS-verify the
> inference link, and resolve the msteams **inbound** path before any live deployment.
