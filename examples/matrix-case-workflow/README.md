# Matrix case workflow reference

An opt-in, isolated-lab reference for **shared alarm room → technician assignment → private
investigation → report/lesson draft → human confirmation → searchable experience case**.
Operator-facing commands/notices are Swedish. Matrix is the protocol; Element is one client.

This example extracts the reusable case/state/transport logic from the exercised local POC.
Configuration/entry paths have been made portable; the public package itself has **not** been
deployed as a fresh installation. See [the verification record](../../docs/MATRIX-CASE-POC-VERIFICATION.md)
for the exact evidence and limits. It is not a production service or an installer.

## Files and responsibilities

| File | Responsibility |
|---|---|
| `store.mjs` | SQLite cases/audit/outbox, assignment transactions, immutable hashed drafts, human confirmation and scoped retrieval. |
| `workflow.mjs` | Host-bound identity checks, command handling, case-only tools and delivery worker. |
| `transport.mjs` | Restricted room creation/membership checks and native Matrix outbound adapter. |
| `index.mjs` | Configurable entry, `before_dispatch`, run-scoped LLM/completion hooks, prompt guidance and worker lifecycle. |
| `alarm-transform.mjs` | Factory wrapping an already-authorized alarm transform; synthetic-only by default. |
| `policy.example.json` | Disabled placeholder policy, not provisioned infrastructure. |
| `*.test.mjs` | Offline state/identity/transport/registration tests with provider I/O mocked. |

The implementation targets **OpenClaw 2026.9.4**, official **`@openclaw/matrix@2026.9.4`** and
**Node 24.21.0**. SDK APIs are experimental: do not infer compatibility with newer versions.

```sh
npm test --prefix examples/matrix-case-workflow
```

Tests use temporary databases and fixture identities. They do not call a model, homeserver,
field device, or running Gateway. No npm dependencies are needed for these offline tests.

## Operator-controlled integration

1. Provision a local homeserver and a **non-admin** Advisor account. Start without federation or
   public self-registration. All participants must be explicitly admitted to the operations room.
   Use HTTPS, or HTTP restricted to loopback through an authenticated lab tunnel. Mobile access,
   push delivery, DNS and TLS require their own verified access path.
2. Install the pinned native Matrix package through **OpenClaw's official plugin installation
   command** in the same HOME/state/registry and OS identity used by the service. Copying an npm
   folder is not an installation record. Verify `trusted-official` for **matrix**. A local case
   plugin remains local; do not falsify its trust or expose an operator Gateway token as a tool.
   When HOME is root-owned, use an explicit writable npm cache for the installation process.
3. Place this example's code and a completed policy outside model-writable workspaces, owned by
   the operator/release authority. Give only the service identity access to its state directory.
   Keep the native Matrix token in the service environment as `OPENAUT_MATRIX_ACCESS_TOKEN`;
   do not place it in the example policy, chat, command arguments or source control.
4. Merge a **reviewed candidate** into the existing Gateway configuration. The essential entry is:

   ```json
   {
     "plugins": {
       "entries": {
         "openaut-cases": {
           "enabled": true,
           "hooks": {"allowConversationAccess": true},
           "config": {
             "policyFile": "/etc/openaut/matrix-policy.json",
             "stateDirectory": "/var/lib/openaut/cases"
           }
         }
       }
     }
   }
   ```

   These are example paths. Add the example directory to `plugins.load.paths` and the plugin ID
   to the existing explicit plugin allowlist. Preserve unrelated config. `policyFile` must name
   a completed, enabled policy; `stateDirectory` must be an absolute, service-owned location.

   Add `openaut_case` alongside `openaut_read` to the model tool allowlist. Retain the field/SSH/
   filesystem/deploy/messaging-tool denials. The case tool factory additionally requires the
   authenticated Matrix account, assigned technician and exact bound room; it returns no case
   tool for the operations room, web chat or an unrelated DM.
5. Configure native Matrix with the **same** account ID, user ID, homeserver and token. Enable E2EE;
   use explicit room/user allowlists and `dm.sessionScope: "per-room"`. Disable chat administration,
   exec approvals, bot-to-bot triggers and thread-spawn surfaces for this Advisor. Keep auto-join
   off; join the operations room through an operator-controlled step. Verify device trust separately
   from mere login or a readable message. Do not reset crypto state as routine recovery.
6. Align the workspace instructions: `openaut_read` is the operational-data tool; the host may
   also expose `openaut_case` in an assigned case DM. Remove stale blanket statements such as
   “the only tool is openaut_read” or “all case mutation is unavailable.” Allow context/lessons/draft
   only when actually exposed; keep human confirmation and engineering approval distinct.
7. The owner-managed alarm adapter must validate equipment scope, registered metrics, timestamps
   and event identities **before** case creation. `createCaseTransform(base, store)` demonstrates
   the hook boundary and requires the same configured Store as the registered workflow. It does
   not wire itself into a Gateway. The hook route must have owner-controlled authentication and
   allow only the derived `agent:main:hook:openaut-case-` namespace. Default `syntheticOnly: true`
   preserves the base transform's live behavior. Never enable real alarm routing from fixture data.

The full channel/handoff contract and acceptance sequence are in
[Matrix operations workflow](../../docs/MATRIX-OPERATIONS-WORKFLOW.md).

## State and confirmation

- `workflow.sqlite` stores case metadata, the source-attributed investigation timeline, room/session
  bindings, document pointers/hashes, confirmation metadata and the delivery outbox.
- `documents/<sha256>.json` is immutable. A technician confirms that exact revision in its private
  room using `Bekräfta F-… <sha256>`. A new observation invalidates an outstanding draft.
- The frozen document keeps its original `draft` marker. Retrieval combines it with the separate
  confirmation as `technician_confirmed_case`; this is an experience case, not a verified generic
  manufacturer instruction. The application compares the stored bytes with the document hash.
- `search(equipment, query, synthetic)` only returns confirmed cases in the allowed equipment
  scope. It shares only reviewed report/lesson fields and confirmation provenance. Raw evidence
  records remain accessible through the original owner's case context, never through another
  case's experience search. Queries use the same public projection so hidden notes cannot be
  discovered by guessing search terms. Synthetic cases are excluded from ordinary live retrieval.
- Draft validation, revision/evidence reads and metadata commit share one writer transaction.
  A concurrent confirmation cannot be overwritten using a stale pre-transaction status.
- `exportConfirmed` produces report/lesson Markdown and a hash manifest, without the raw DM
  conversation. The export is `pending-forge-review` / `quarantine`. It is not automatic Forge
  publishing or a migration into `system.cases`.

## Delivery, restart and rollback

Outbox transitions are `queued → sending → sent`; an interrupted or ambiguous attempt becomes
`uncertain`. There is **no automatic retry** of an uncertain row. Native transport may have its own
in-flight receipt; reconcile the exact target, message and receipt before any operator recovery.
Do not reset an old alarm ledger to repeat an acceptance test. DM creation can similarly leave an
orphan room after an ambiguous response; do not create another room blindly.

A queued job whose equipment is no longer authorized becomes `blocked`, with an audit reason.
Other allowed jobs continue. Restoring the equipment scope does not automatically re-arm that
job: it remains an operator reconciliation decision.

Completion correlation requires `llm_input`, `llm_output` and successful `agent_end` facts with
the same host run ID/session. Only a clean final assistant text present in that run's output
collection is accepted; full conversation history is not a fallback. Callback arrival order may
differ. Missing, failed, tool-only or uncorrelated results leave the case pending rather than
publishing old text. The bounded in-memory correlation cache is cleared on restart; it does not
authorize a replay after a missed callback. Validate the pinned harness before live routing.

The case plugin uses `api.runtime.channel.outbound.loadAdapter('matrix').sendText`, not the
Gateway RPC helper restricted to bundled/trusted-official plugins. Its own outbox owns attempt
state; it does not invent an internal `deliveryQueueId` for a queue it does not own.

Stop the Gateway/worker before moving or backing up state. Retain the SQLite database and its
document directory together and use a consistent SQLite backup. Only one active workflow worker
may own this store. Keep old code/config available for rollback; preserve cases, native crypto,
credentials and receipts. Restoring config is not permission to replay an uncertain delivery.
Server/bot/room migration requires explicit state reconciliation, not just a URL or allowlist edit.

## Current limits

The public package is a portable **reference adaptation**, not the byte-identical lab deployment.
No local installers, SSH aliases, infrastructure credentials, historical case IDs or repair scripts
are included. It does not provision the homeserver or reader API. The verified host SDK tests and
manual acceptance are described in the evidence document; CI here uses mocked transports.

The accepted operator path is a **new operations-room message** `Jag tar F-…`, not a native thread
takeover. Thread shorthand, reassignment/reopening, attachments/manual ingestion, mobile push,
Security's encrypted-room observation, actual field actions, automatic Forge/Systemdatabas indexing
and a fresh-install journey are outside this reference's live acceptance. The first lab analysis
needed an operator-approved handoff recovery; a new synthetic case must test the corrected
automatic callback before enabling live Matrix alarm routing.
