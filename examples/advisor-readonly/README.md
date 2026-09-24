# Advisor read-only diagnostic guidance

Self-contained adaptations of [fdd](../../skills/fdd/SKILL.md) and
[anomaly-correlation](../../skills/anomaly-correlation/SKILL.md) for the constrained `openaut_read`
tool. The general skills carry the research and diagnostic references; these examples include the
runtime instructions in one file per skill because the tool cannot retrieve arbitrary references.

## Contents and evidence

- [FDD guidance](skills/fdd/SKILL.md)
- [Alarm-correlation guidance](skills/anomaly-correlation/SKILL.md)
- [Research and source limitations](../../docs/ADVISOR-DIAGNOSTICS-RESEARCH-20260923.md)
- [Twenty specified evaluation cases](../../docs/ADVISOR-DIAGNOSTICS-EVALUATION.md)
- [Bounded manual demonstration report](../../docs/ADVISOR-DIAGNOSTICS-DEMO-20260923.md)

These are knowledge files, not an installer, calibrated detector or authorization policy.
`permissions` metadata documents intent; the host's policy and restricted tools enforce access.
Neither file adds shell, field writes, alarm acknowledgments, deployment or permission management.

## Integration contract

The existing [public read-tool adapter](../../deploy/advisor-discovery/openclaw/read-tool.mjs) supports
`operation=guidance` with `skill=fdd` or `skill=anomaly-correlation` when the owner provisions
`OPENAUT_GUIDANCE_DIR`. That directory must contain:

```text
<owner-provisioned-guidance-directory>/
  fdd/SKILL.md
  anomaly-correlation/SKILL.md
```

Provision the chosen files read-only to the Advisor service identity. The owner, not Advisor, owns
updates and policy. Use an equipment ID returned by authorized discovery for tool requests; do not
use the evaluation fixture's synthetic IDs against a real reader. General source manuals remain
equipment-scoped and verified separately. Guidance is generic methodology, not equipment evidence.

The examples target Swedish operator dialogue and `Europe/Stockholm` display. When using the public
adapter, the owner must configure `OPENAUT_TIMEZONE=Europe/Stockholm` (its default is UTC) or adapt
the example's time instructions to the chosen deployment. Keep source timestamps and UTC offsets.
History limits are the adapter's 8 metrics / 7 days / 500 rows per request, not a coverage guarantee.

A provisioned host also needs the appropriate skill allow-list, tool policy and guidance-loading
instructions. These examples do not configure those settings. After an approved update, verify
actual guidance content/permissions and host-specific cache/session behavior before a new test session.

## Revision identity

The example files are byte-identical UTF-8/LF copies of the pair associated with the reported lab
demonstration. Compare Git blob content or normalize a CRLF checkout before comparing these hashes:

| File | SHA-256 (UTF-8, LF) | Bytes |
|---|---|---:|
| fdd/SKILL.md | `0a8153493a4bf0a7017bf7e9e83e8c4b2c38b0b2e9f47c732db95219e0421628` | 9362 |
| anomaly-correlation/SKILL.md | `4b1359f20a55e329b1dca4beb40aab5c5fcd41ce8df140490b6abd3a67d1798d` | 8829 |

Two manual synthetic scenarios were assessed from operator-returned replies after lab activation.
The complete 20-case suite was not run, and tool traces proving guidance retrieval during those
dialogues were not supplied. That evidence does not establish model-wide accuracy or transfer the
lab installation's acceptance to another deployment. See the demonstration report for exact limits.
