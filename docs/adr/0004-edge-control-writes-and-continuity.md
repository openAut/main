# ADR 0004 — Edge control writes: SSH for code, MQTT for setpoints, Hold Last Value on partition

- **Status:** Proposed (design draft — for review, nothing wired yet)
- **Date:** 2026-07-01
- **Builds on:** [`0001-delivery-and-trust-model`](0001-delivery-and-trust-model.md) (§4 Engineer envelope, §7 controlled ingress / deny-by-default egress), [`0003-engineer-runtime-containment`](0003-engineer-runtime-containment.md) (§2 Engineer's edge-VLAN-in-case-scope reachability), `skills/forge-governance`, `skills/system-database` (case → Forge → CI-approved-revision pipeline), `skills/edge-iot2050`, `skills/mqtt-tls-broker`, `CONTEXT.md` (*reglercentral*, *Hold Last Value*), issue #13

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
     no inbound topic at all. Add a node-scoped command topic (e.g.
     `openaut/<site>/<node>/cmd/#`) with **two separate ACL rules, not one**:
     - The node **subscribes only to its own** command prefix — the same least-privilege pattern
       already used for publish scoping, just mirrored for the inbound direction. A stolen node cert
       still cannot see or affect any other node's commands.
     - The node's **own publish grant is explicitly scoped to exclude `cmd/#`** — it keeps publishing
       telemetry under its own prefix, but may never publish to its own or any other node's command
       topic. **Publishing to `cmd/#` is restricted to a single, case-bound write identity** (a scoped
       Engineer profile or a mediated write service, with its own certificate and carrying the
       case-id for audit) — mirroring how Sparkplug B restricts NCMD/DCMD publish rights to
       authorized Host Applications rather than letting any broker client send commands. Without this
       second rule, the node's existing telemetry-publish grant could technically extend to `cmd/#`,
       which would make the case-gate below unenforceable at the transport layer.
   - **Case-approval for the MQTT setpoint channel: confirmed, same gate as SSH deploy.**
     `CONTEXT.md`'s persona table already treats a live "bacnet priority-8 override" identically to
     `deploy` — both are `Human-reviewed (write/deploy) → Systemdatabas case` for the Driftstekniker
     persona. A live MQTT setpoint write is the same class of act (a runtime change to an
     already-deployed control loop), so it reuses that existing rule rather than inventing a lighter,
     ungated path. This is no longer an open question.

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
   any check is discarded and the previous known-good value keeps being held. This keeps the loop
   regulating unaffected by an outage anywhere above it in the chain, and this is the same discipline
   as the existing store-and-forward spool, applied to the inbound side.

**3. Central revocation of an already-applied setpoint during a partition is accepted as impossible
   by design**, not solved by a protocol. It is a direct consequence of decisions 1–2: there is no
   push path into a node that isn't reachable, by the same deny-by-default, edge-initiated model that
   already governs everything else in this architecture. The backstop against an unsafe held value is
   a **physical/PLC interlock independent of the software that issued the command** — never a network
   mechanism. **This is the same decision as the "Physical/PLC interlocks" checklist item in #13, not
   a second one** — HLV without an independent interlock is not an acceptable end state for any
   safety-relevant writable point.

**4. No change to the air-gap / deny-by-default-egress boundary (ADR 0001 §7).** Continuity of
   control requires zero new external connectivity — decision 2 is achieved entirely through traffic
   that was already intended to exist inside the perimeter (field-device-local control, or a new but
   still-internal, still-scoped MQTT topic). Nothing here reaches further outward than before.

## Consequences

- `edge-iot2050` needs a new writable-point mode: subscribe to its own `cmd` topic, validate each
  incoming setpoint (schema/range/freshness per decision 2) before persisting it locally, and — only
  when acting as a reglercentral — run the control loop as a process decoupled from the MQTT client's
  connection state.
- `mqtt-tls-broker`'s topic schema and ACL need **two** new rules — node-scoped subscribe on `cmd/#`,
  and a separate publish grant restricted to the case-bound write identity (decision 1) — not just the
  subscribe side. This is the **first** departure from a strictly one-way broker and deserves its own
  abuse/injection review even though the blast radius stays node-scoped (identical containment logic
  to today's publish scoping).
- This ADR does not invent the interlock mechanism itself — that stays a per-equipment engineering
  task — it only establishes that HLV *requires* one wherever the held value could be unsafe.
- Decision 1's case-gate is now confirmed (same gate as `deploy`); implementation must not ship the
  ACL change until the write identity is actually case-bound end to end, or it would create an
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

## Compliance alignment (IEC 62443 / NIS2)

*Working aid, not legal advice; verify against the source texts before binding decisions.*

- **IEC 62443:** HLV as the default failure mode supports **availability** of the regulated process
  (a core SR/FR concern for OT, distinct from IT's confidentiality-first ordering); the new inbound
  topic is scoped per-node in both directions (SR 2.1 authorization enforcement, least privilege) —
  subscribe mirrors the existing publish ACL, and publish to `cmd/#` is further restricted to the
  case-bound write identity.
- **NIS2 (Dir (EU) 2022/2555):** Art. 21.2 risk-management measures can support the case for favouring
  continuity of the regulated physical process during a network incident — the article does not
  itself prescribe HLV over fail-safe. The failure mode for each safety-relevant point must still be
  risk-assessed per installation; openAut itself is not a NIS2 entity, but the building operator
  deploying it plausibly is.

## Open questions

- **Exact topic/schema** for the new inbound command channel, and whether acks/reglercentral health
  status need a topic distinct from `cmd`.
- **The interlock mechanism itself** (hardware limit switches, PLC-level clamps, etc.) is
  per-equipment and out of scope here — this ADR only establishes that HLV depends on one existing.
