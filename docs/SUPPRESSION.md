# SkillSpector suppression policy (`.skillspector-baseline.yaml`)

> ⚠️ **Learning project — not for production.** See the [README](../README.md) for the full
> disclaimer.

Some skills ship reference scripts that [SkillSpector](https://github.com/NVIDIA/SkillSpector) flags
as high-risk even though the code is legitimate (e.g. TLS/PKI generation, SSH provisioning). Those
findings are suppressed per skill in a `.skillspector-baseline.yaml` file so re-scans stay green —
**without hiding anything**, because every suppression is recorded with a reason and reviewed.

This file is the policy CI and reviewers hold baselines to.

## Rules

1. **False positives only.** A baseline may suppress a *reviewed* false positive. It must **never**
   be used to silence a genuine finding. If a finding is real, fix the code.
2. **Concrete reason required.** Every entry's `reason` must name the control that makes the finding
   safe (e.g. `chmod 600 key`, `curl --cacert, no --insecure`, `node-local config.env, never
   transmitted`, hardened systemd unit). Generic placeholders such as
   `Accepted finding (auto-generated baseline)` are **not allowed**.
3. **No broad glob `rules`.** Prefer per-finding `fingerprints`. If a glob `rule` is unavoidable, it
   needs its own justification and must be narrowly scoped.
4. **Reviewed as security-relevant code.** A baseline change is reviewed like any security change: a
   human who is not the author signs off (mirrors the forge two-person rule).
5. **Regenerate on code change.** When a suppressed script changes, regenerate the affected
   fingerprints and re-justify each reason — a stale hash silently stops suppressing, or worse,
   suppresses something new.

## Good vs. bad suppression

**Good** — names the specific control that makes it safe:
```yaml
- hash: sha256:da432afa66e512dd
  rule_id: PE3
  file: scripts/gen-certs.sh
  reason: "FP, not exfiltration: reads/writes node-local PKI material to GENERATE certs; nothing is transmitted off-host."
```

**Bad** — generic, unreviewable, would be rejected:
```yaml
- hash: sha256:da432afa66e512dd
  rule_id: PE3
  file: scripts/gen-certs.sh
  reason: "Accepted finding (auto-generated baseline)"
```

## Regenerating a baseline

```bash
# Re-scan a skill and write a fresh baseline (then hand-edit every reason per the rules above):
skillspector baseline skills/<name> --no-llm -o skills/<name>/.skillspector-baseline.yaml
```

After regenerating, replace each auto-generated reason with a concrete justification and remove any
duplicate `hash` entries before committing.
