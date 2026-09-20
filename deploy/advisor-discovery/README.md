# Area-scoped Advisor reference

Portable POC implementation of the [integrated delivery workflow](../../docs/ADVISOR-INTEGRATION-WORKFLOW.md).
Python 3.12 on Linux for services; use the Node version supported by the selected OpenClaw runtime
(this adapter was tested with Node 24 and OpenClaw 2026.9.4). Dependencies are provided by
the repository's `requirements.txt` / `requirements-dev.txt`. There are no imports from dated lab
directories, host-specific equipment allowlists, embedded credentials or one-off deployment scripts.

Use this handoff only when the owner enables the extension and includes it in the approved case.
Otherwise record **not applicable** in the ordinary edge-integration acceptance record.

## Components

| File | Purpose |
|---|---|
| [`schema.sql`](schema.sql) | Fresh owner-controlled read boundary and mediated registration |
| `reader.py` | Bounded authenticated metadata/telemetry/Forge API |
| `engine.py` | Persistent observation, overlap, deduplication and outbox |
| `worker.py` | Discovery, shared durable budget, dispatch and synthetic fixtures |
| `integration.py` | Engineer-side offline validation and proposal preparation |
| `control_plane.py` | Owner-operated registrar outside Engineer; retains SQL credentials |
| `openclaw/` | Standalone plugin and authenticated-hook transform |
| `*.example.json` | Unprovisioned configuration examples, not operational credentials |

## Owner installation

1. Apply the existing storage setup and `deploy/platform-poc2/db/001-system.sql`. As the owner,
   back up applicable schema definitions/ACLs, then apply [`schema.sql`](schema.sql) in the intended database.
   It creates **NOLOGIN** `advisor_reader` and `advisor_delivery_registrar` groups and empty site/repository policy. Name collisions
   intentionally fail; this is not an in-place installer for an existing lab.
2. Record owner-authorized sites and repositories in `advisor_policy.allowed_sites` and
   `advisor_policy.forge_repositories`. Operational identities cannot write these tables.
   Provision a dedicated least-privilege login inheriting only `advisor_reader`, with CONNECT and
   an owner-managed libpq service definition (for example, selected through `PGSERVICEFILE` and
   a protected password file). Do not reuse a superuser or broader `advisor_app` login.
3. Provision a high-entropy read token, its SHA-256 in the reader configuration, and a Forge read
   identity limited to approved repositories. Keep tokens/passwords in protected credential files,
   never in source control, model arguments or diagnostic output. Example placeholders must be replaced.
4. Start `python reader.py --config /owner/provisioned/reader.json` under a non-login read identity.
   The reader enforces a loopback listener; remote Forge origins must use HTTPS. Remote clients
   require an explicitly owner-provisioned TLS-terminating proxy or authenticated tunnel to that
   loopback listener. For remote databases/Forge, use owner-approved conduits/TLS;
   the Forge origin is configured by the owner, never by a model request. Refuse redirects.
5. Install the complete `openclaw/` directory as a root-owned plugin under the gateway's
   `hooks/transforms/openaut-read/`. Add that directory to the plugin load paths, enable plugin
   `openaut-read`, and keep the effective model tool allowlist exactly `openaut_read`. Merge
   `hooks.example.json` into the owner-controlled gateway configuration. Select the model in the
   agent's own configuration; alarm payloads cannot override it.
6. Configure the adapter with owner-managed environment variables:
   `OPENAUT_READ_API`, `OPENAUT_READER_TOKEN_FILE`, optional `OPENAUT_GUIDANCE_DIR` (containing the
   granted `fdd/SKILL.md` and `anomaly-correlation/SKILL.md`) and `OPENAUT_TIMEZONE` (default UTC).
   Configure `OPENAUT_ALARM_HOOK_TOKEN` on the gateway to match the worker's separate protected
   hook-token file. These variables are not model-controlled configuration operations.
7. Provision a separate non-login watcher identity, its protected state directory and a hardened
   service running `python worker.py --config /owner/provisioned/worker.json`. Limit egress to
   loopback; use `NoNewPrivileges`, no capabilities, read-only system/home, and only the state
   directory writable. The reader has its own narrow DB/Forge conduit, not field-network access.
8. Validate actual identity/file permissions, TLS/loopback binding, denied operations, effective
   tool policy and synthetic model completion before recording acceptance. Keep Advisor, Engineer
   and Security on separate hosts as required by the trust model.

This package supplies components, not an automatic credential/proxy/service provisioning system.
Existing installation state requires a reviewed migration. This public variant uses hashed file/
session names for all equipment and strict stored profile/binding checks; it does not contain lab
identity aliases, and the worker refuses unrecognized SQLite namespaces. Do not point it at legacy ledgers without a migration preserving cursors,
observations, outboxes, budget and conversation continuity.

## Data contracts

Metadata comes from `system.equipment`, `system.points`, `system.documents` and
`system.advisor_integrations`; samples come from `telemetry.readings`. Field health uses normalized
`field_protocol_healthy`, `field_protocol_last_success_unixtime` and
`field_protocol_consecutive_errors`. Heartbeat freshness is 120 seconds; COV sample age is separate.

Alarm profiles accept booleans, `integer` codes/counts in **-32768..65535**, and unsigned
16-bit `uint16` bitfields in **0..65535**. Wider counters, floating-point alarm representations or
different units need an explicitly reviewed normalization adapter/profile extension.

Document views support equipment/site-specific sources and optional product-level manuals through
`equipment.product_id` / `documents.product_id` when a product catalog is installed. Product columns
and catalog lifecycle are owned by the existing manual-ingest workflow, not created by this schema.
Global product manuals must have no equipment/site restriction and be in an authorized repository;
private material from another site is excluded even when the product matches.

Generated artifacts must also be cataloged as verified documents with a blob SHA-256 to be served
by this API; a `generated_artifacts` pointer alone does not establish that retrieval trust state.

Forge URIs use the canonical `forge://openaut/<repo>/<path>?commit=<40-hex>` form. Each returned
source must be verified, commit-pinned and match its independent SHA-256. UTF-8 text, Markdown,
JSON/YAML/CSV/Python/SQL are reference data. XLSX requires an owner-produced, read-only extraction
cache named `<source-sha256>.json`, containing `source_sha256`, `text`, and `text_sha256`. Its text is
marked not independently reviewed. PDF/images require a separate ingest/conversion step. Missing
evidence never becomes an invented physical point map or alarm-bit definition.

## Engineer delivery

```text
python integration.py validate --contract delivery.json --artifact reviewed-point-map.json
python integration.py prepare --contract delivery.json --artifact reviewed-point-map.json --case approved-case --output delivery-request.json
```

These commands read/write only the permitted Engineer work directory and approved artifact inputs.
The proposal contains case and contract data, never SQL connection settings or an asserted actor.
It is not an approval. **Engineer receives no SQL route, credentials or registration EXECUTE grant.**

An owner-controlled release/job wrapper collects the proposal through the existing artifact handoff,
validates release/case evidence and supplies the authenticated Engineer principal from its trusted
execution context. Production delivery uses the reviewed signed Main release and existing release
pipeline, per ADR 0001; this utility does not implement or replace release attestation. The owner
may use a scoped, explicitly approved local handoff in the isolated POC. A bare work-directory file
must not be watched and auto-approved as though it were a signed release.

On that owner-controlled management host, **outside the Engineer sandbox**, the registrar runs:

```text
python control_plane.py --request accepted-request.json --artifact approved-release-artifact.json --engineer authenticated-engineer-principal --service registrar_service
```

The owner provisions this service identity with only `advisor_delivery_registrar`, not Engineer,
approver or policy-administration privileges. The trusted job context supplies `--engineer`; copying
an actor string from an untrusted proposal is not authentication. The DB function checks this principal
against the owner-recorded case assignment, and independently checks the exact unexpired approval,
artifact and publication binding. Both the Engineer principal and actual registrar `session_user`
are audited. Neither the producer nor the registrar may approve its own delivery or edit area policy.

This introduces no additional Engineer network exception: the four infrastructure endpoints in
[ADR 0003 §2](../../docs/adr/0003-engineer-runtime-containment.md) remain the only off-VLAN destinations.
The registrar has its own owner-managed DB conduit. Engineer does not call a new registration URL or
connect to Systemdatabasen/Forge directly. Equipment/point/document registration and the existing
case/Forge approval verbs continue through their separately approved integration/ingest paths.

The watcher discovers active contracts without per-equipment code/config changes. It waits 30 seconds
between cycles, caps discovery at 1,000 equipment, reads 20 per page, and maintains separate state.
Limits: 64 alarm metrics per contract, eight metrics/500 samples per history call, seven-day history
window, 120-second overlap, bounded pending events. No promise of unbounded late-data recovery or
distributed exactly-once delivery. Automatic attempts share a durable six/hour and one/minute cap;
eligible equipment rotate after the last durable attempt, including failures, across restarts.
Collection runs for all active scopes before dispatch selection; one persistently busy early ID
cannot consume every available budget slot. This is round-robin fairness, not severity prioritization.
History scans split metric groups and time intervals, including the overlap before the cursor.
At most 32 requests are made per equipment/poll. Complete pages and the remaining scan queue are
checkpointed together; the global cursor advances only once the fixed scan target is fully covered.
An interrupted scan resumes after restart rather than refetching a permanently oversized prefix.
`history_backpressure` can mean bounded work remains, not discarded data. More than 500 rows for
one metric at one indivisible timestamp cannot be time-partitioned: this is an explicit `data_quality`
failure with the cursor/checkpoint retained, requiring corrected source identity/timestamp resolution.
All unresolved events count toward the 10,000-event outbox cap, including queued, sending, failed
and uncertain batches. At capacity, ingestion pauses with `outbox_backpressure` in status without
discarding evidence or resending uncertain batches. Already admitted audit history has separate
retention semantics and does not occupy this unresolved-event allowance.
The read API also limits latest snapshots to 256 metrics, document lists to 20 sources per equipment,
Forge blobs to 2 MiB and JSON responses to 256 KiB. Oversized results fail explicitly rather than
silently presenting incomplete evidence. Point-registry truncation is reported in the response.
Read requests share a seven-second monotonic work budget inside the tool's ten-second timeout.
Database statement timeouts and document fetches use the remaining budget; a socket watchdog also
limits slow/trickling Forge responses. Document search returns `incomplete`, `budget_exhausted`
and explicit `unavailable` entries instead of continuing through 20 individual fetch timeouts.
Only fully fetched/hash-verified passages are returned. TLS/DNS and database conduits still require
owner-provisioned infrastructure and deployment-specific acceptance.

For an approved synthetic acceptance test, run under the watcher's identity/configuration:

```text
python worker.py --config /owner/provisioned/worker.json --synthetic ahu-03
```

This uses separate state and never writes field equipment or telemetry. Re-running does not blindly
resend admitted/uncertain batches. Explicit synthetic tests are outside the automatic delivery budget.
Inspect the persistent receipt and completed model reply in the derived synthetic conversation;
admission is not completion. Missing documentation/point mapping must appear in the delivery evidence.

## Rollback and operation

Pause the worker before schema/policy/code transitions. Back up views including owner/ACLs and
snapshot SQLite using its backup API under the ledger owner; a lone copy of a live WAL database is
not sufficient. Restore saved code/configuration and reader views in dependency order. Preserve all
active ledgers (including in-progress history scan checkpoints), synthetic receipts and `discovery-budget.sqlite`; never overwrite new events with an
old backup. Scope revocation stops new dispatch but intentionally retains audit evidence. A changed
binding/profile is `integration_requires_review`, not a reason to delete state and rebaseline silently.

`discovery-status.json` contains current discovery and per-equipment status. Check timestamp, health,
queued/failed/uncertain delivery counts separately from service liveness. Existing `uncertain` events
require operator reconciliation against the conversation/logs before any approved retry.

## Tests

From the repository root, with Python 3.12 and `requirements-dev.txt`:

```text
python -m pytest tests/test_advisor_discovery.py -q
node deploy/advisor-discovery/test-openclaw.mjs
```

For a disposable PostgreSQL 16-compatible database test, supply an already-local image:

```text
python deploy/advisor-discovery/verify_database.py --image <local-postgresql-image>
```

Optional `--ssh-host <test-host-alias>` runs Docker remotely while the Python 3.12 driver stays local.
The container has no network/host ports, a memory limit and tmpfs data, uses only synthetic fixtures,
never connects to the application database and is removed afterward. Image pulling is disabled.

The optional `test-openclaw-sdk.mjs` requires `OPENCLAW_HOOKS_MODULE` pointing to the installed hook
module from **OpenClaw 2026.9.4**. It checks real plugin discovery, effective tool policy and
hook/session processing without model/network calls. Compiled export bindings are version-specific;
revalidate against the selected runtime before deployment. See the
[verification note](../../docs/ADVISOR-DISCOVERY-VERIFICATION.md) for the evidence boundary.
