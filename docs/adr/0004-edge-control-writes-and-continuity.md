# ADR 0004 — Edge control writes: SSH for code, MQTT for setpoints, Hold Last Value on partition

- **Status:** Proposed (design draft — for review, nothing wired yet)
- **Date:** 2026-07-01
- **Builds on:** [`0001-delivery-and-trust-model`](0001-delivery-and-trust-model.md) (§4 Engineer envelope, §7 controlled ingress / deny-by-default egress), [`0003-engineer-runtime-containment`](0003-engineer-runtime-containment.md) (§2 Engineer's edge-VLAN-in-case-scope reachability, three narrow policy-owned egress endpoints), [`skills/forge-governance`](../../skills/forge-governance/SKILL.md), [`skills/system-database`](../../skills/system-database/SKILL.md) (case → Forge → CI-approved-revision pipeline), [`skills/edge-iot2050`](../../skills/edge-iot2050/SKILL.md), [`skills/mqtt-tls-broker`](../../skills/mqtt-tls-broker/SKILL.md), `CONTEXT.md` (*reglercentral*, *Hold Last Value*), issue #13

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
       - `{allow, all, subscribe, ["cmd/+/${clientid}/#"]}` — a node subscribes only to its own
         command prefix. A stolen node cert still cannot see or affect any other node's commands,
         inheriting the same node-id-as-CN identity model as the existing telemetry ACL (see
         "inherited limitation" note below).
       - Publish to `cmd/#` is granted **per request, not as a standing account** — see write
         identity below; there is no static `{allow, {user, ...}, publish, ["cmd/#"]}` rule.
   - **Write identity: Engineer, via a fourth mediated endpoint — not a new actor.**
     `CONTEXT.md`'s trust-domain model is explicit and non-negotiable: openAut has **three** trust
     domains, and "only the Driftstekniker has a writing path, and it never goes chat→SSH directly —
     it passes through **Engineer** via an approved case in the Systemdatabas." A standalone write
     service that Engineer never touches would be a **fourth write-capable actor outside that model** —
     this ADR's previous draft got that wrong. The corrected design: **Engineer remains the sole write
     actor**, exactly as for SSH deploys, and it reaches the broker only through a new **mediated MQTT
     write endpoint** — a fourth narrow, policy-owned, case-bound infrastructure endpoint added
     alongside the credential proxy and mediated inference endpoint already named in ADR 0003 §2. Like
     those two, Engineer hands its case/scope to the endpoint and gets back a result — it never holds
     a raw broker socket or a standing credential itself. Concretely, the endpoint:
     1. checks the request is within Engineer's active case scope and that the Systemdatabas case is
        `approved` for that specific `<site>/<node>`;
     2. mints or uses a **short-lived, case-scoped** publish credential limited to exactly
        `cmd/<site>/<node>/#` for that one case — never a blanket `cmd/#` grant — so a compromised
        endpoint or leaked credential can affect only the single node named in the active case, not
        every site;
     3. publishes the setpoint, and writes the action to the append-only audit sink.
     **This is a deliberate, explicit amendment to ADR 0003 §2**, not a silent widening: that section's
     three named endpoints become four. It does *not* reopen §1's containment model (dedicated OS
     account, sandbox profile) or widen Engineer's *direct* network reachability — the broker itself
     is still never in Engineer's reachable set, exactly as decision 4 states, because Engineer talks
     to the endpoint, not the broker.
   - **Case-approval for the MQTT setpoint channel: confirmed, same gate as SSH deploy.**
     `CONTEXT.md`'s persona table already treats a live "bacnet priority-8 override" identically to
     `deploy` — both are `Human-reviewed (write/deploy) → Systemdatabas case` for the Driftstekniker
     persona. A live MQTT setpoint write is the same class of act (a runtime change to an
     already-deployed control loop), so it reuses that existing rule rather than inventing a lighter,
     ungated path. This is no longer an open question, and step 1 of the mediated endpoint above is
     exactly where it's enforced — before anything is ever published.
   - **Inherited limitation, not solved here:** the node subscribe rule reuses the existing telemetry
     ACL's identity model, where the client cert CN is the node id alone (`skills/mqtt-tls-broker`) and
     site-scoping in the topic pattern relies on a `+` wildcard, not a bound site claim. If a node id
     were ever reused across two sites, that pre-existing ambiguity would now extend to *reading*
     commands, not just telemetry. Fixing it (e.g. binding site into the cert subject) is a
     `mqtt-tls-broker`-wide change out of scope for this ADR; flagged under Open questions. The
     mediated endpoint's own per-case credential (step 2 above) is scoped to the exact site/node pair
     regardless, which limits the practical exposure on the *write* side even before that's fixed.

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
   (a signed sequence number and timestamp, both covered by the signature, checked against
   previously-seen values) before it is allowed to overwrite the held value — a message that fails
   any check is discarded and the previous known-good value keeps being held. Two things must persist
   *together*, across restarts, not just in memory: the held setpoint **and** the anti-replay state
   (last-accepted sequence number/timestamp) — otherwise a node restart resets the replay window and
   a captured old command becomes acceptable again. Command messages are published with `retain=false`
   and the broker must not retain `cmd/#`; a late-joining or reconnecting subscriber must never receive
   a stale command from the broker's own retained-message store instead of from the node's own
   validated local state. This keeps the loop regulating unaffected by an outage anywhere above it in
   the chain, and this is the same discipline as the existing store-and-forward spool, applied to the
   inbound side.

**3. Central revocation of an already-applied setpoint during a partition is accepted as impossible
   by design**, not solved by a protocol. It is a direct consequence of decisions 1–2: there is no
   push path into a node that isn't reachable, by the same deny-by-default, edge-initiated model that
   already governs everything else in this architecture. The backstop against an unsafe held value is
   a **physical/PLC interlock independent of the software that issued the command** — never a network
   mechanism. **This is the same decision as the "Physical/PLC interlocks" checklist item in #13, not
   a second one** — HLV without an independent interlock is not an acceptable end state for any
   safety-relevant writable point.

**4. No change to the air-gap / deny-by-default-egress boundary (ADR 0001 §7). ADR 0003 §2's egress
   allowlist gains one deliberate fourth entry, the mediated MQTT write endpoint — everything else is
   unchanged.** Continuity of control requires zero new external connectivity — decision 2 is achieved
   entirely through traffic that was already intended to exist inside the perimeter (field-device-local
   control, or a new but still-internal, still-scoped MQTT namespace). Engineer's *direct* reachable
   set (edge VLAN in case scope) does not grow, and the broker is still never in it — only the named
   endpoint is, exactly as for the two existing endpoints. Nothing here reaches further outward than
   before.

## Consequences

- `edge-iot2050` needs a new writable-point mode: subscribe to its own `cmd/<site>/<node>/#` prefix,
  validate each incoming setpoint (schema/range/freshness/replay per decision 2) before persisting it
  locally alongside its anti-replay state, and — only when acting as a reglercentral — run the control
  loop as a process decoupled from the MQTT client's connection state.
- `mqtt-tls-broker`'s topic schema and ACL need the new sibling `cmd/#` namespace, its node-subscribe
  rule, and `retain=false`/no server-side retention on `cmd/#` — see decision 1/2. Existing rules
  (`openaut/#` reads, per-node telemetry publish) are untouched by construction; this is still the
  **first** departure from a strictly one-way broker and deserves its own abuse/injection review even
  though the blast radius stays node-scoped (identical containment logic to today's publish scoping).
  The node-id-as-CN identity model it inherits (not site+node) is a pre-existing gap, now relevant to
  writes too — see decision 1's "inherited limitation" note and Open questions.
- **ADR 0003 needs a short follow-up edit**, not a new document: §2's three named endpoints become
  four (add the mediated MQTT write endpoint), with the same short-lived/case-bound credential
  language already used for the credential proxy. The endpoint itself is new infrastructure to build —
  it doesn't exist today — but it is Engineer's endpoint to call, not a new trust domain or a capability
  living outside CONTEXT.md's three-trust-domain model.
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
  endpoint, which keeps Engineer as the sole write actor and adds infrastructure *Engineer calls*,
  the same shape as the existing credential proxy and mediated inference endpoint.

## Compliance alignment (IEC 62443 / NIS2)

*Working aid, not legal advice; verify against the source texts before binding decisions.*

- **IEC 62443:** HLV as the default failure mode supports **availability** of the regulated process
  (a core SR/FR concern for OT, distinct from IT's confidentiality-first ordering); the new `cmd/#`
  namespace is scoped per-node for subscribe and reachable for publish only via a short-lived,
  case-scoped credential minted per request (SR 2.1 authorization enforcement, least privilege, no
  standing broad-scope write credential), and is functionally separated from the existing telemetry
  namespace rather than carved out of it — zone segmentation by construction, not by exception.
- **NIS2 (Dir (EU) 2022/2555):** Art. 21.2 risk-management measures can support the case for favouring
  continuity of the regulated physical process during a network incident — the article does not
  itself prescribe HLV over fail-safe. The failure mode for each safety-relevant point must still be
  risk-assessed per installation; openAut itself is not a NIS2 entity, but the building operator
  deploying it plausibly is.

## Open questions

- **Exact payload schema** for `cmd/<site>/<node>/#` (sequence number / signed timestamp fields per
  decision 2), and whether acks/reglercentral health status need a topic distinct from `cmd`.
- **The mediated MQTT write endpoint's own containment** — where it runs, how it mints/verifies the
  short-lived per-case broker credential, and how tightly its case-check couples to
  `system-database` — needs a short design note before implementation, the same way ADR 0003 §1–§5
  did for Engineer's own sandbox.
- **`mqtt-tls-broker`'s node-id-as-CN identity model** doesn't bind site into the client identity
  (decision 1's "inherited limitation" note); worth fixing broker-wide now that the gap affects
  command delivery, not just telemetry — tracked as a follow-up to `mqtt-tls-broker`, not blocking
  this ADR.
- **The interlock mechanism itself** (hardware limit switches, PLC-level clamps, etc.) is
  per-equipment and out of scope here — this ADR only establishes that HLV depends on one existing.
