# ADR 0004 — Edge control writes: SSH for code, MQTT for setpoints, Hold Last Value on partition

- **Status:** Proposed (design draft — for review, nothing wired yet)
- **Date:** 2026-07-01
- **Builds on:** [`0001-delivery-and-trust-model`](0001-delivery-and-trust-model.md) (§4 Engineer envelope, §7 controlled ingress / deny-by-default egress), [`0003-engineer-runtime-containment`](0003-engineer-runtime-containment.md) (§2 Engineer's edge-VLAN-in-case-scope reachability and narrow policy-owned egress endpoints — amended by this ADR from three to four), [`skills/forge-governance`](../../skills/forge-governance/SKILL.md), [`skills/system-database`](../../skills/system-database/SKILL.md) (case → Forge → CI-approved-revision pipeline), [`skills/edge-iot2050`](../../skills/edge-iot2050/SKILL.md), [`skills/mqtt-tls-broker`](../../skills/mqtt-tls-broker/SKILL.md), [`CONTEXT.md`](../../CONTEXT.md) (*reglercentral*, *Hold Last Value*), issue #13

## Context

Issue #13 flagged two unresolved items together: **"Writable edge control as a signed, CI-approved
artifact the node *pulls*"**, plus an explicit conflict it named — a node built to keep running
during a network partition cannot, by the same design, be centrally revoked exactly when that
matters most — and, separately, **"Physical / PLC interlocks for every writable point."**

Today there is **no writable path to an edge node at all**. `edge-iot2050`'s `edge_agent.py` only
publishes; it has no `subscribe`/`on_message` and no control loop. `mqtt-tls-broker`'s ACL is
strictly one-way: a node may only **publish** under its own prefix (`openaut/<site>/<node>/#`), and
the AI-tier consumer may only **subscribe**, read-only, to `openaut/#`. Nothing today flows from the
AI tier back down to a node. This ADR designs that path from scratch rather than patching an
existing one.

## Decision

**1. Two separate write channels, not one — different artifacts, different friction, different transport.**

   - **Program / communication-config changes** (rare, heavy): the Python control-loop code itself,
     or its protocol/network configuration. These cross through the **existing** case → Forge →
     CI-gated → approved-revision pipeline (`forge-governance`, `system-database` — signed commits,
     green pipeline, review, hash-pinned artifact, `approved` row before Engineer will act). Engineer
     deploys over **SSH**, inside its own case scope, using the envelope already defined in ADR 0001
     §4 (dedicated OS account, SSH forced-commands, signed/allowlisted deploy-wrapper scripts) and
     reachable per ADR 0003 §2 (edge VLAN in active case scope). **No new pull mechanism, no MQTT
     topic, for code.** This closes the "signed, CI-approved artifact" half of the checklist item
     using infrastructure that already exists — it only needed to be pointed at edge nodes.
   - **Setpoint / operational-parameter updates** to an *already-deployed* control loop (frequent,
     light): travel over **MQTT**, not SSH. This requires a genuinely new capability: today's ACL has
     no inbound topic at all. Command traffic gets a **sibling top-level namespace**,
     `cmd/<site>/<node>/#` — **not** nested under `openaut/<site>/<node>/#` — for two reasons at once:
     - Today's AI-tier consumers (`ingest`, `agent_ro`) already hold a broad, deliberately unscoped
       `openaut/#` read subscription (`skills/mqtt-tls-broker/assets/acl.conf`). If commands lived
       under `openaut/.../cmd/#` they'd leak straight into that existing wildcard with no ACL change
       at all — functional separation of the command namespace from the telemetry namespace is what
       keeps read-only Advisor/ingest consumers from ever seeing command traffic, by construction,
       the same "separate command topics from data topics" pattern used in Sparkplug B and other
       MQTT command-and-control designs.
     - A node's existing publish grant is `{allow, all, publish, ["openaut/+/${clientid}/#"]}` — a
       wildcard on its *own* prefix. If `cmd/#` were nested inside that prefix, this rule would
       already grant the node publish rights to its own command topic, and excluding it would need a
       `deny` rule ordered *before* the wildcard `allow` (fragile, order-dependent). A sibling
       namespace needs no such carve-out: the existing rule simply doesn't match `cmd/...` at all.
     - Two new, purely additive ACL rules follow the broker's existing allow-list-then-deny-all
       shape — no negative/exclusion rules anywhere:
       - `{allow, all, subscribe, ["cmd/${cert_site}/${clientid}/#"]}` — bound to **both** fields of
         the cert, not a `+` wildcard on site. This is deliberately *not* a copy of the existing
         telemetry rule (`openaut/+/${clientid}/#`), which wildcards site: least-privilege on a
         *read* topic tolerates that gap (worst case is a stale/ambiguous reading), but a *write*
         channel cannot inherit it without also inheriting a way for a reused node-id to read another
         site's commands. A node's client cert must therefore carry a **site claim** (e.g. a SAN/OU
         field set at issuance, not just the existing CN-as-node-id) before it is issued `cmd/#`
         subscribe rights.
       - **Precondition, not a follow-up:** the command channel is not activated for a node until its
         cert carries that site claim. Nodes whose certs predate this ADR need reissuing (a
         `mqtt-tls-broker` provisioning change, scoped narrowly to *this* claim) before they can use
         `cmd/#` — this is required for decision 1 to ship, not deferred to Open questions. The
         pre-existing telemetry-side gap (`openaut/+/${clientid}/#` itself still wildcards site) is a
         separate, lower-severity, read-only legacy issue and can still be fixed on its own schedule.
       - Publish to `cmd/#` is granted **per request, not as a standing account** — see write
         identity below; there is no static `{allow, {user, ...}, publish, ["cmd/#"]}` rule.
   - **Write identity: Engineer, via a fourth mediated endpoint — not a new actor.**
     `CONTEXT.md`'s trust-domain model is explicit and non-negotiable: openAut has **three** trust
     domains, and "only the Driftstekniker has a writing path, and it never goes chat→SSH directly —
     it passes through **Engineer** via an approved case in the Systemdatabas." A standalone write
     service that Engineer never touches would be a **fourth write-capable actor outside that model** —
     this ADR's previous draft got that wrong. The corrected design: **Engineer remains the sole
     operational write trust domain — the only one that may initiate a setpoint write, via an
     approved case** — exactly as for SSH deploys. The **mediated MQTT write endpoint** it calls is
     policy-owned mediation infrastructure (a policy enforcement point), not a fourth agent, persona,
     or trust domain — it never initiates anything on its own, only executes what Engineer's approved
     case already authorized. It is a fourth narrow, policy-owned, case-bound infrastructure endpoint
     added alongside the credential proxy and mediated inference endpoint already named in ADR 0003
     §2. Like those two, Engineer hands its case/scope to the endpoint and gets back a result — it
     never holds
     a raw broker socket or a standing credential itself. Concretely, the endpoint:
     1. checks the request is within Engineer's active case scope and that the Systemdatabas case is
        `approved` for that specific `<site>/<node>`;
     2. **requests**, rather than mints itself, a **short-lived, case-scoped** publish credential
        limited to exactly `cmd/<site>/<node>/#` for that one case, from the **same credential proxy**
        ADR 0003 §3 already defines for Engineer's SSH secrets — issuance is authorized against
        PAP-authored signed permission profiles (PAP owns the *policy*, not operational minting; the
        proxy is the mechanism that enforces it, for this credential exactly as for Engineer's own).
        The endpoint holds no standing broker credential and no broad minting secret of its own; it is
        a requester, like Engineer is;
     3. publishes the setpoint, and writes the action to the append-only audit sink.

     Two different blast radii, not one claim: a **leaked per-request credential** is node-scoped by
     construction (point 2) — it is only ever valid for the one `<site>/<node>` it was minted for. A
     **compromised endpoint itself** is a different, larger problem: even holding no credential of its
     own, a compromised endpoint could still *request* proxy-issued tokens for cases it has no business
     touching unless the proxy's own authorization checks the endpoint's identity and active-case claim
     independently — that check is the proxy's job, not the endpoint re-implementing it, exactly as
     Engineer's SSH-secret requests are already authorized by the proxy today. What's still genuinely
     open is the endpoint's *own* containment shape — its sandbox, and its network ACL scoped to just
     Systemdatabas + credential proxy + audit sink + broker — tracked in Open questions, the same way
     ADR 0003 left Engineer's enforcement substrate open while still deciding it *would* be sandboxed.

     **ADR 0003 §2 is amended by this decision**, not silently widened: its three named endpoints are
     now four (see the corresponding edit to `0003-engineer-runtime-containment.md` §2, made alongside
     this ADR). It does *not* reopen §1's containment model (dedicated OS account, sandbox profile) or
     widen Engineer's *direct* network reachability — the broker itself is still never in Engineer's
     reachable set, exactly as decision 4 states, because Engineer talks to the endpoint, not the
     broker.
   - **Case-approval for the MQTT setpoint channel: confirmed, same gate as SSH deploy.**
     `CONTEXT.md`'s persona table already treats a live "bacnet priority-8 override" identically to
     `deploy` — both are `Human-reviewed (write/deploy) → Systemdatabas case` for the Driftstekniker
     persona. A live MQTT setpoint write is the same class of act (a runtime change to an
     already-deployed control loop), so it reuses that existing rule rather than inventing a lighter,
     ungated path. This is no longer an open question, and step 1 of the mediated endpoint above is
     exactly where it's enforced — before anything is ever published.
   - **Legacy limitation, deliberately not inherited:** the existing telemetry ACL's identity model —
     client cert CN is the node id alone (`skills/mqtt-tls-broker`), site-scoping via a `+` wildcard —
     is not carried over to `cmd/#`; the site-claim precondition above is exactly what stops that. The
     telemetry side keeps its existing gap for now (a separate, read-only, lower-severity issue,
     tracked in Open questions for its own fix), but a node id being reused across two sites can no
     longer let it *read commands* meant for another site, because the command subscribe rule checks
     the cert's site claim, not just its node id.

**2. Hold Last Value (HLV), not fail-safe-to-default, is the failure mode on loss of upstream
   communication.** Where the physical field device has its own onboard control (a BACnet priority
   array or a Modbus holding register on a DDC controller / VFD / PLC), HLV **can** be a native
   property of that hardware — verified per writable point against the equipment profile's documented
   comm-loss/restart behaviour, not assumed generically. In all cases the edge node must never
   self-reset or reinitialize a previously-deployed value on its own (e.g. on a service restart).
   Where the edge node itself is the **reglercentral** — it runs the control algorithm in software
   because the field device has no onboard logic — that loop must read from a **locally persisted,
   last validated setpoint**, never a live inbound message. "Validated" means the incoming MQTT
   payload passed schema/type checking, per-point range/clamp limits, and freshness/replay protection
   (sequence number and timestamp checked against previously-seen values) before it is allowed to
   overwrite the held value. The **entire** command envelope is signed and
   verified as one canonical unit — `site`, `node`, writable-point id, value, unit/profile, the
   case/profile-id it was approved under, sequence number, and timestamp — not just the two
   freshness fields; a signature that covered only sequence/timestamp would leave the value and the
   site/node binding open to tampering even while looking "fresh". A message that fails any check
   (signature, schema, range, or freshness) is discarded and the previous known-good value keeps
   being held. Two things must persist
   *together*, across restarts, not just in memory: the held setpoint **and** the anti-replay state
   (last-accepted sequence number/timestamp) — otherwise a node restart resets the replay window and
   a captured old command becomes acceptable again. `retain=false` alone isn't sufficient — MQTT can
   still redeliver a queued QoS 1/2 message from a persistent session or offline queue on reconnect,
   with no retained message involved at all. `cmd/#` subscriptions therefore also require: no
   persistent session (clean start / session expiry 0, no offline queueing), and a `message expiry
   interval` at or below decision 2's own freshness window as a second, broker-side backstop — the
   node's own signature/freshness check (above) is still the primary defense and must not be relied
   on alone, but the broker configuration needs to be exactly as explicit as the retained-message
   prohibition, not merely implied by it. A late-joining or reconnecting subscriber must never receive
   a stale command from *any* broker-side store — retained, queued, or otherwise — instead of relying
   purely on the node's own validated local state. This keeps the loop regulating unaffected by an
   outage anywhere above it in the chain, and this is the same discipline as the existing
   store-and-forward spool, applied to the inbound side.

**3. Central revocation of an already-applied setpoint during a partition is accepted as impossible
   by design**, not solved by a protocol. It is a direct consequence of decisions 1–2: there is no
   push path into a node that isn't reachable, by the same deny-by-default, edge-initiated model that
   already governs everything else in this architecture. The backstop against an unsafe held value is
   a **physical/PLC interlock independent of the software that issued the command** — never a network
   mechanism. **This is the same decision as the "Physical/PLC interlocks" checklist item in #13, not
   a second one** — HLV without an independent interlock is not an acceptable end state for any
   safety-relevant writable point.

**4. Engineer's edge-VLAN/node reachability does not grow; its non-edge infrastructure allowlist
   grows by one mediated endpoint (ADR 0003 §2, amended: three named endpoints become four). The
   broker itself remains unreachable directly from Engineer.** Continuity of control requires zero
   new external connectivity — decision 2 is achieved entirely through traffic that was already
   intended to exist inside the perimeter (field-device-local control, or a new but still-internal,
   still-scoped MQTT namespace). The air-gap / deny-by-default-egress boundary at the perimeter (ADR
   0001 §7) is unchanged and gains no new public egress. What *does* change, honestly stated rather
   than glossed over: Engineer's off-VLAN allowlist is a real, if narrow, new attack surface — one
   more mediated endpoint, the same shape as the two that already exist, that a threat model must
   treat as such rather than assume away because "nothing changed".

## Consequences

- `edge-iot2050` needs a new writable-point mode: subscribe to its own `cmd/<site>/<node>/#` prefix,
  validate each incoming setpoint (schema/range/freshness/replay per decision 2) before persisting it
  locally alongside its anti-replay state, and — only when acting as a reglercentral — run the control
  loop as a process decoupled from the MQTT client's connection state.
- `mqtt-tls-broker`'s topic schema and ACL need the new sibling `cmd/#` namespace, its
  site-and-node-bound subscribe rule, `retain=false`/no server-side retention, and no persistent
  session / offline queueing on `cmd/#` — see decision 1/2. Existing rules (`openaut/#` reads,
  per-node telemetry publish) are untouched by construction; this is still the **first** departure
  from a strictly one-way broker and deserves its own abuse/injection review even though the blast
  radius stays node-scoped (identical containment logic to today's
  publish scoping). It also needs a **cert-issuance change**: nodes need a site claim added before
  they can be granted `cmd/#` subscribe rights (decision 1) — existing certs predate this and need
  reissuing as part of rollout, not after.
- **ADR 0003 §2 is amended alongside this ADR** (done, not deferred): its three named endpoints become
  four, with the mediated MQTT write endpoint described in the same short-lived/case-bound credential
  language already used for the credential proxy. The endpoint itself is still new infrastructure to
  build — it doesn't exist today — but it is Engineer's endpoint to call, not a new trust domain or a
  capability living outside CONTEXT.md's three-trust-domain model. Its own containment (network ACL,
  sandbox, and relying on the credential proxy's own authorization rather than re-implementing it) is
  separate work, tracked in Open questions.
- This ADR does not invent the interlock mechanism itself — that stays a per-equipment engineering
  task — it only establishes that HLV *requires* one wherever the held value could be unsafe.
- Decision 1's case-gate is now confirmed (same gate as `deploy`); implementation must not ship the
  ACL change until the mediator's case-check is actually wired end to end, or it would create an
  ungated write path despite the gate being decided on paper.

## Alternatives considered

- **A single MQTT-pull channel for both code and setpoints** (the literal reading of #13's "artifact
  the node *pulls*"). Rejected: duplicates the case/Forge/CI pipeline already built and reviewed for
  code, for no corresponding gain, and conflates a rare/heavy change with a frequent/light one.
- **Fail-safe-to-default as the universal failure mode.** Rejected: for continuous HVAC/process
  regulation, reverting to a default on every transient comms blip harms comfort/process stability
  more than holding the last approved value — an explicit control-engineering requirement, not a
  security shortcut. Fail-safe remains available where a physical/PLC interlock independently demands
  it.
- **Everything over SSH (no MQTT command channel).** Rejected: makes every routine setpoint nudge as
  heavy as a code deploy, which doesn't match real operational cadence for HVAC tuning.
- **A standalone write service that Engineer never touches** (an earlier revision of this ADR).
  Rejected on review: `CONTEXT.md` is explicit that openAut has three trust domains and that the
  Driftstekniker's only writing path passes through Engineer — a write-capable actor Engineer never
  calls would sit outside that model as an unnamed fourth actor. Replaced with decision 1's mediated
  endpoint, which keeps Engineer as the sole operational write trust domain and adds policy-owned
  mediation infrastructure *Engineer calls*, the same shape as the existing credential proxy and
  mediated inference endpoint.

## Compliance alignment (IEC 62443 / NIS2)

*Working aid, not legal advice; verify against the source texts before binding decisions.*

- **IEC 62443:** HLV as the default failure mode supports **availability** of the regulated process
  (a core SR/FR concern for OT, distinct from IT's confidentiality-first ordering); the new `cmd/#`
  namespace is scoped per **site and node** for subscribe (not just node, unlike the legacy telemetry
  identity model) and reachable for publish only via a short-lived, case-scoped credential requested
  per operation (SR 2.1 authorization enforcement, least privilege, no standing broad-scope write
  credential), and is functionally separated from the existing telemetry namespace rather than
  carved out of it — zone segmentation by construction, not by exception.
- **NIS2 (Dir (EU) 2022/2555):** Art. 21.2 risk-management measures can support the case for favouring
  continuity of the regulated physical process during a network incident — the article does not
  itself prescribe HLV over fail-safe. The failure mode for each safety-relevant point must still be
  risk-assessed per installation; openAut itself is not a NIS2 entity, but the building operator
  deploying it plausibly is.

## Open questions

- **Exact canonical command envelope and signing scheme** for `cmd/<site>/<node>/#` (field order/
  encoding for site/node/point/value/case-id/sequence/timestamp per decision 2), and whether
  acks/reglercentral health status need a topic distinct from `cmd`.
- **The mediated MQTT write endpoint's own containment** — where it runs, how it requests and
  verifies the short-lived per-case broker credential from the credential proxy, and how tightly its
  case-check couples to `system-database` — needs a short design note before implementation, the
  same way ADR 0003 §1–§5 did for Engineer's own sandbox.
- **Exact site-claim mechanism** for the cert reissue decision 1 requires (SAN field vs. OU vs. a
  new extension) and the reissuance rollout plan for nodes provisioned before this ADR.
- **`mqtt-tls-broker`'s telemetry-side site wildcard** (`openaut/+/${clientid}/#`) is untouched by
  this ADR (decision 1's "legacy limitation" note) — still worth fixing broker-wide since it's the
  same underlying gap, just lower severity on a read-only path; tracked as its own follow-up, not
  blocking this ADR.
- **The interlock mechanism itself** (hardware limit switches, PLC-level clamps, etc.) is
  per-equipment and out of scope here — this ADR only establishes that HLV depends on one existing.
