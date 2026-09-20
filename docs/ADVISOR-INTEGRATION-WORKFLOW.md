# Integrated delivery to Advisor

Advisor has standing **read access within an owner-authorized area**. It discovers equipment from
Systemdatabasen and resolves verified reference material in Forgejo. Engineer delivers collection,
metadata, documentation and alarm connectivity as parts of the **same approved integration case**.

This preserves the vocabulary in [CONTEXT](../CONTEXT.md): Advisor, Engineer and Security are trust
domains on separate hosts; personas describe human needs. The asset owner or appointed policy
authority owns permission profiles. Engineer cannot expand its own or Advisor's authority.

## Data flow

```text
Owner-authorized sites/repositories
                  ↓
Systemdatabas → scoped read service → Advisor (openaut_read)
     ↑                    ↑
Engineer delivery     telemetry + hash-checked Forge material
     ↓
Alarm contract → deterministic watcher → validated hook → equipment conversation
```

The [reference package](../deploy/advisor-discovery/README.md) contains the schema, reader, watcher,
Engineer registration utility, OpenClaw adapter and tests. It is a portable POC reference, not an
automatic production deployment. Physical integration remains governed by the
[edge integration lifecycle](EDGE-INTEGRATION-LIFECYCLE.md) and the relevant protocol workflow.

## Authorization is different from integration metadata

| Information | Owner / writer |
|---|---|
| Allowed sites and Forge repositories | Asset-owner database administration |
| Equipment/product identity, point maps and document references | Approved integration and manual-ingest paths |
| Alarm metrics, types and publication identity | Engineer through an exactly approved delivery contract |
| Telemetry samples | Existing ingest |
| Watcher cursor, deduplication and outbox | Deterministic read-only observer |

`advisor_policy.allowed_sites` and `advisor_policy.forge_repositories` implement the local owner
boundary. They are not editable by Advisor or Engineer. These DBA-owned tables are POC enforcement,
not a replacement for PAP-authored signed profiles in a managed deployment.

`system.advisor_integrations` is **delivery metadata**, not an equipment access list. Equipment in
an approved area is discoverable even before its alarm contract is complete. New equipment within
that area does not require another per-equipment Advisor permission change. A new site/repository
still requires the owner's authorization.

The dedicated reader login should inherit only the new `advisor_reader` read group. Do not use an
owner/superuser login or the broader legacy `advisor_app` group for this service.

## Engineer delivery checklist

1. Record the stable equipment ID, installed label, product/controller/firmware identity, site,
   node and telemetry system. Follow the existing single-master/shared-bus and bounded-read checks.
2. Register points and protocol mappings through the approved integration path. Use
   [manual-ingest](../skills/manual-ingest/SKILL.md) for product manuals and verified source metadata.
   Product manuals stay linked through product identity; site-specific generated material belongs
   to its equipment/site.
3. Create the alarm contract from observed, verified normalized metrics. Supported types are
   `boolean` (unit `bool`), `integer` (`code`/`count`) and `uint16` (`bitfield`). A raw alarm word
   does not establish the meaning of each bit. Unsupported representations require a reviewed adapter.
4. Bind the exact contract and the reviewed artifact's SHA-256 to an owner-approved case. Register
   it with the scoped Engineer database identity. The function checks case status, assignment,
   equipment/site/node/system, approval expiry and exact approved contract equality.
5. Verify discovery, current health, values, history and document references. Missing manuals or
   physical point maps are explicit evidence gaps; they do not justify invented readings.
6. Run a separate synthetic alarm through the watcher. Verify persistent admission **and a completed
   model reply in the correct synthetic conversation**. Confirm no field or telemetry fixture writes.
7. Close the case with source revisions/hashes, evidence, exclusions, sibling-system regression and
   rollback. Registration or HTTP admission alone is not end-to-end acceptance.

Use the same case ID as the equipment integration. The owner can approve the alarm contract with
the rest of that delivery; a separate Advisor-only case is normally unnecessary.

### Contract and approval

```json
{
  "equipment_id": "ahu-03",
  "node": "edge-a",
  "telemetry_system": "ahu-03",
  "alarm_metrics": {"alarm_active": "boolean", "fault_flags": "uint16"},
  "alarm_watch": true,
  "artifact_sha256": "<SHA-256 of the reviewed artifact: 64 lowercase hex characters>"
}
```

The independent approval's `scope` contains `action="advisor-integration"`, `field_write=false`
and `integration` equal to the entire contract. The approved/in-progress case is assigned to the
database connection's `session_user`. Engineer cannot create this approval using the registration
utility. Existing case/Forge approval functions must be explicitly connected to this contract type;
the package does not silently broaden their accepted actions. A local POC can record the scoped
human approval through owner administration, consistent with the lab's approval rules.

## Runtime behavior

- `list_equipment` returns bounded pages from owner-filtered views; every subsequent data read is
  separately authorized and equipment-filtered.
- Documents require the correct equipment/product/site, an authorized repository, `verified`
  trust, a pinned commit and matching blob SHA-256. Source code is data, never executed.
- The watcher refreshes discovery each cycle. Failed/incomplete discovery permits no cached dispatch.
- Each equipment has its own state and conversation. Paths and session IDs are derived from stable
  IDs, never supplied as filenames or routing commands by metadata.
- The hook rechecks authorization and active contract at admission and validates event types.
  Mapped equipment events cannot override the agent, model or session.
- A persistent shared budget caps automatic attempts at six per hour and one per minute, including
  restarts and equipment removal. A crash around sending becomes `uncertain`, not an automatic retry.
- Initial healthy baseline does not create an analysis for every unchanged alarm. Synthetic tests
  use independent state. COV timestamps are publication times, not new measurement timestamps.
- Scope removal pauses dispatch without deleting evidence. Changed binding/profile requires an
  explicit state migration; the worker must not erase a cursor or outbox to hide incompatibility.

## Acceptance evidence

Keep dated operational evidence locally. Publish a sanitized summary containing implementation
version, tests, limitations and acceptance criteria, without host inventories, credentials, real
equipment/session/run IDs, active ledgers or private conversation content. See the
[reference verification note](ADVISOR-DISCOVERY-VERIFICATION.md).
