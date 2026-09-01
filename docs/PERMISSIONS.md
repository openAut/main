# Skill `permissions:` schema

> ⚠️ **Learning project — not for production.** See the [README](../README.md) for the full
> disclaimer.

Every `SKILL.md` declares its openAut permissions in its YAML frontmatter. New skills use the
Agent Skills-compatible `metadata.openaut-permissions` JSON string. Existing skills may retain the
legacy top-level `permissions:` mapping until they are migrated. The declaration documents, in one
place, what the skill is allowed to do, so intent is explicit, reviewable, and machine-checkable
(`scripts/validate_skills.py`, run in CI).

The namespaced metadata form matters because the Agent Skills specification permits custom string
metadata but does not define a top-level `permissions` field.

This is **declared intent / metadata**. It does not itself grant or enforce capabilities at runtime;
the sandbox policy, exec allow-lists, and the Advisor/Engineer trust split are the enforcement. A
clear, consistent contract here is what lets the validator and future loader logic reason about a
skill without reading its whole body.

## Required frontmatter keys

| Key | Type | Notes |
|---|---|---|
| `name` | string | non-empty; matches the skill directory |
| `description` | string | non-empty |
| `metadata.openaut-permissions` | JSON string | preferred standards-compatible form containing the keys below |
| `permissions` | mapping | legacy openAut form containing the same keys |

## `permissions` keys

All keys are optional **except `knowledge_only`**, which is required. Unknown keys are rejected by the
validator (catches typos and silent drift).

| Key | Type | Meaning |
|---|---|---|
| `knowledge_only` | bool | **required.** `true` = the skill only supplies knowledge/process; it does not itself act. |
| `tools` | string | tool access, or `none`. |
| `exec` | string | command execution this skill performs, or `none`. Name the wrapper/scripts if any. |
| `network` | string | network the skill reaches, or `none`. |
| `files` | string | filesystem access, e.g. `read-only`, or `none`. |
| `credentials` | string | how the skill handles secrets/keys/tokens. |
| `control_writes` | string | for skills that can change field/OT state: `none`, or a string containing **`owner-confirmed`** (never autonomous). |
| `delegated_capabilities` | string | for governing/workflow skills: states that the real SSH/deploy/provisioning is performed by an approved runtime/role, **not** by this skill. |
| `data_access` | string | data the skill reads, e.g. `read-only (telemetry store)`. |
| `data_sensitivity` | string | sensitivity/handling of the data, e.g. `network topology - owner DM only`. |
| `serial` | string | serial-port access (e.g. LoRa), or `none`. |
| `external_services` | string | external services reached, e.g. via an operator wrapper. |

## Rules the validator enforces

1. **No UTF-8 BOM** before `---` (a loader that checks `startswith('---')` must recognise the
   frontmatter).
2. Frontmatter parses as YAML and contains `name`, `description`, `permissions`.
3. `permissions.knowledge_only` is present and boolean.
4. Every key in `permissions` is from the table above.
5. **If `knowledge_only: true`:** either `exec`/`network`/`tools` are all `none`/absent, **or**
   `delegated_capabilities` is present (the skill guides action that an approved role performs).
6. **If `knowledge_only: false`:** at least one of `exec`/`network`/`files` is declared and not
   `none` (an acting skill must say what it acts on).
7. **If `control_writes` is present:** its value is `none` or contains `owner-confirmed`.

## Examples by skill class

**Acting skill, standards-compatible form** (preferred for new skills):
```yaml
metadata:
  openaut-permissions: '{"knowledge_only":false,"exec":"python scripts/tool.py","network":"none","files":"read-write","control_writes":"none"}'
```

**Knowledge / standards, legacy form** (e.g. `ai-act`, `iec62443`):
```yaml
permissions:
  knowledge_only: true
  tools: none
  network: none
  exec: none
```

**Analytics over the telemetry store** (e.g. `fdd`):
```yaml
permissions:
  knowledge_only: true
  exec: none
  network: none
  data_access: "read-only (openAut telemetry store)"
```

**Governing / workflow** (e.g. `advisor-engineer-workflow`):
```yaml
permissions:
  knowledge_only: true
  exec: none
  network: none
  delegated_capabilities: "Engineer (not this skill) performs Forge writes/PRs, deploy runbooks and edge SSH, owner-approved via the Systemdatabas"
```

**Fieldbus protocol with control** (e.g. `knx`):
```yaml
permissions:
  knowledge_only: false
  network: "KNXnet/IP tunnelling/routing (LAN) + MQTT bridge"
  exec: "operator-provisioned bus tooling, allowlisted"
  files: "read-only"
  control_writes: "owner-confirmed (Driftstekniker path), never autonomous"
```

**Infrastructure / provisioning** (e.g. `mqtt-tls-broker`):
```yaml
permissions:
  knowledge_only: false
  exec: "allowlisted scripts (gen-certs.sh, verify-tls.sh)"
  network: "MQTT/TLS broker (EMQX) on the node"
  files: "read-write (PKI dir; private keys chmod 600)"
  credentials: "generates/handles TLS CA + broker/client certs (node-local)"
```
