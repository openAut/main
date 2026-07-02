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
     `cmd/<site>/<node>/#`, with individual writable points as sub-topics (`cmd/<site>/<node>/<point>`)
     — **not** nested under `openaut/<site>/<node>/#` — for two reasons at once. (The node's own
     *subscribe* grant below is node-wide by design — a node needs to receive commands for all its own
     points; it is the *publish* side, scoped per point to what a case actually approved, where
     least-privilege matters — see the write-identity bullet.)
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
       - `{allow, all, subscribe, ["cmd/${cert_common_name}/#"]}` — bound to the **cert-derived**
         Common Name, which *is* the combined `<site>/<node>` claim on Community Edition (verified;
         see the precondition below) — not MQTT ClientID and not a `+` wildcard on site.
         `mqtt-tls-broker`'s
         own SKILL.md documents "CN = client id" only as a **provisioning convention** and flags that
         "live behaviour is unverified until an EMQX host is available" — meaning nothing today
         actually stops a connecting client from presenting a valid cert but choosing a different,
         self-supplied MQTT ClientID at connect time. Tolerable, if sloppy, for a *read* topic
         (worst case is a stale/ambiguous reading); **not** tolerable for a channel that grants
         subscribe rights to commands, where it would let a node read another node's setpoints by
         simply connecting with that node's ClientID.
       - **Precondition, not a follow-up:** before `cmd/#` is activated for *any* node, three things
         must all be true, not just documented as intent:
         1. **Site-claim field, verified against a live EMQX 5.8.9 Community Edition instance**
            ([`docs/verification/emqx-mqtt5-cmd-verification.md`](../verification/emqx-mqtt5-cmd-verification.md)):
            the node's cert carries a **site
            claim as part of the Common Name (CN)** — the CN is the combined, canonical
            `<site>/<node>` identifier itself (e.g. `CN=A/n1`), not a separate SAN or OU field.
            SAN-based extraction of `site` and `node` as two independent claims was the original
            intent, but EMQX's `client_attrs_init` + `cert_san.*` mechanism that would provide it is
            **EMQX Enterprise Edition only** (confirmed against the deployed Community Edition — that
            capability doesn't exist there). Community Edition's only built-in cert-derived ACL
            placeholder is `${cert_common_name}`, one whole-CN string — the design uses that
            constraint rather than assuming a two-field mechanism this project isn't running. If
            Enterprise Edition is ever adopted, the SAN-based two-field mechanism remains a strictly
            better option and should be revisited then; it is not required for Community Edition.
         2. the broker is configured so the identity used in ACL evaluation (`${cert_common_name}`)
            is **read from the certificate itself** at the TLS layer, via EMQX's built-in
            `verify_peer` + `fail_if_no_peer_cert = true` TLS options — **verified working** against
            EMQX 5.8.9 CE, never trusted from a client-supplied MQTT ClientID (confirmed: a spoofed
            ClientID does not grant access to another node's scope, and does not lose access to its
            own cert-derived scope), and
         3. `site` and `node` are **canonical, asset-owner/Systemdatabas-owned identifiers, referenced
            (not minted) by PAP-authored permission profiles** — PAP owns role/policy definitions and
            signed permission profiles ([`CONTEXT.md`](../../CONTEXT.md),
            [`0002-access-control-and-roles`](0002-access-control-and-roles.md)), not equipment naming;
            a profile may scope a case to `site=A`/`node=B`/`point=C`, but the topology identifiers
            themselves come from the same asset-owner/Systemdatabas case-and-approval flow that already
            governs node onboarding, exactly as decision 1's case-approval bullet requires for every
            other writable-point action. Letting a profile mint its own identifier would let an
            operational actor indirectly widen its own scope through local naming — the same failure
            mode ADR 0002 already forecloses for policy itself. These identifiers must also be
            **stable canonical IDs, not free-text display names**: a display name can change without
            notice, and a permission profile's scope must not follow it implicitly. `site`, `node`, and
            `point` are each validated *individually* against a **canonical-id allow-pattern**, applied
            with a full-string match (e.g. Python `re.fullmatch(..., flags=re.ASCII)`, not `search`) so
            partial matches can't slip through, and never silently normalized (`Site-01` is rejected,
            not rewritten to `site-01` — silent rewriting would make Systemdatabas and topology diverge
            from what was actually requested):
            ```
            ^(?=.{1,63}$)[a-z0-9]+(?:[._-][a-z0-9]+)*$
            ```
            1–63 characters, lowercase ASCII letters/digits only, with `.`/`_`/`-` allowed strictly
            *one at a time, between* two alphanumerics — never leading, trailing, or consecutive
            (`a..b`, `a-_b`, and `a.-b` are all rejected, not just `-a` or `a-`) — which by construction
            forbids an MQTT wildcard (`+`, `#`), a topic separator (`/`), NUL/control characters,
            whitespace, a broker-reserved leading `$`, and Unicode/homoglyph confusables. **Validated at two
            enforcement points, defense in depth, neither trusting the other:** (1) Systemdatabas at
            equipment-profile write time — stops bad data at the source and keeps topology consistent
            — and (2) the mediated MQTT write endpoint at request time, as the last fail-closed check
            before a topic string, ACL scope, or signed command envelope is built from these segments;
            the endpoint may not assume every upstream writer already validated. Cert-issuance time is
            a *third*, already-decided instance of the same check — not a new checkpoint — since CN
            construction is exactly precondition 1's `<site>/<node>` build step, formalized in
            [`docs/operations/cert-reissuance-plan.md`](../operations/cert-reissuance-plan.md) step 2.
            `site`/`node`/`point` are security-bearing segments, never UI text — a BACnet object name,
            vendor point name, or any other display label belongs in a separate `display_name`-style
            field that this pattern does not govern and permission-profile scope must never follow
            implicitly. Because Community Edition's
            `${cert_common_name}` carries `site` and `node` together as one CN string (precondition 1),
            per-character validation of each segment is not sufficient on its own — the CN also needs
            a **structural** check that *replaces* what would otherwise have been two independent
            per-field checks under a SAN-based, Enterprise-only mechanism:
            ```
            ^(?=[a-z0-9._-]{1,63}/)(?P<site>[a-z0-9]+(?:[._-][a-z0-9]+)*)/(?=[a-z0-9._-]{1,63}$)(?P<node>[a-z0-9]+(?:[._-][a-z0-9]+)*)$
            ```
            (two length lookaheads, one per segment, since a single trailing `$`-anchored lookahead
            can't bound both halves of a compound value independently — each named group still uses
            the same no-consecutive-separator segment pattern as the per-field regex above). **This
            regex must be applied with the same full-string match discipline as the per-field pattern
            above (`fullmatch`, not `match`/`search`)** — with `match`/`search`, `$` can match just
            before a trailing newline rather than true end-of-string, silently accepting a CN of
            `site/node\n`; verified empirically that `fullmatch` correctly rejects this while
            `match`/`search` do not. This applies to both segment length lookaheads, not only the
            final `$`.
            One literal `/` separating two non-empty segments that each independently match the
            per-segment pattern above, constructed at cert-issuance time by the asset-owner/Systemdatabas
            process, never accepted as a free-form string from a certificate request. `/` is forbidden
            *inside* `site`, `node`, or `point` individually — it exists only as the fixed separator in
            this one compound field. **This is a verified, not theoretical,
            requirement** ([`docs/verification/emqx-mqtt5-cmd-verification.md`](../verification/emqx-mqtt5-cmd-verification.md)):
            a CN of a single unvalidated character (`+`) reproducibly granted cross-tenant read access
            to another node's topic by being live-interpreted as an MQTT wildcard once substituted into
            `cmd/${cert_common_name}/#`, and a CN missing the node segment entirely (e.g. just `A`)
            would silently widen a grant from node-scope to site-scope — both are precisely the
            failure modes this precondition exists to close, not edge cases to defer. Without this,
            a value taken unvalidated from an equipment profile could widen a subscribe/publish grant
            beyond the single point it was meant to scope, or forge a different node's topic. This
            applies uniformly to the cert-derived CN's `site`/`node` segments and to the `point`
            segment, which has no certificate to anchor it and so depends entirely on this check.
         Nodes whose certs predate this ADR need reissuing as part of rollout. The pre-existing
         telemetry-side gap (`openaut/+/${clientid}/#`, which wildcards site *and* still trusts
         client-supplied ClientID) is a separate, lower-severity, read-only legacy issue, tracked on
         its own schedule — but its existence means precondition 1–2 should really be verified once,
         for the broker as a whole, not re-litigated per topic.
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
     a raw broker socket or a standing credential itself. Concretely — and **scoped to the specific
     writable point, not the whole node**, since a case approves one or more named points, never
     blanket access to everything under a node, the same granularity decision 2's per-point
     range/clamp checks and HLV already assume — the endpoint:
     1. checks the request is within Engineer's active case scope and that the Systemdatabas case is
        `approved` for that specific `<site>/<node>/<point>`;
     2. **requests**, rather than mints itself, a **short-lived, case-scoped** publish credential
        limited to exactly `cmd/<site>/<node>/<point>` — the one point the case approved, never the
        node-wide `cmd/<site>/<node>/#` — from the **same credential proxy** ADR 0003 §3 already
        defines for Engineer's SSH secrets (that proxy issues any short-lived, scoped credential
        Engineer or this endpoint needs, not only SSH ones) — issuance is authorized against
        PAP-authored signed
        permission profiles (PAP owns the *policy*, not operational minting; the proxy is the
        mechanism that enforces it, for this credential exactly as for Engineer's own). A case that
        legitimately covers multiple points gets multiple point-scoped credentials, not one
        node-wide grant. The endpoint holds no standing broker credential and no broad minting
        secret of its own; it is a requester, like Engineer is;
     3. publishes the setpoint.

     **Every attempt is audited, not just successful ones — and the write fails closed if the audit
     sink is unreachable before the endpoint acts.** Before step 1 is evaluated, the endpoint writes a
     synchronous **intent** entry (command digest, case/profile-id, site/node/point) to the append-only
     audit sink, as structured, individually-encoded fields — never concatenated into one free-text
     string — so a request carrying a not-yet-canonicalized identifier (decision 1's third precondition
     above) can't corrupt the audit record itself even before that validation has run against it; if the
     write fails, the endpoint stops there — it never proceeds to step 1, 2, or 3 — the same fail-closed
     posture as decision 2's "discard on failed validation", not a silent write-without-a-trail. Once the intent entry is confirmed written, step 1 rejections (out-of-scope
     case, not `approved`), step 2 failures (proxy declines to issue), step 3 failures (broker publish
     error), and step 3 success each write a matching **outcome** entry to the same sink, referencing the
     intent entry. An endpoint that only logged what it *did* would leave Security blind to probing or a
     compromise attempt that never got past step 1 or 2. This intent/outcome split exists because the
     sink can still become unreachable *after* the intent write succeeds — mid credential-request or
     mid-publish — at which point the write may have already happened with no outcome entry to show for
     it; claiming that case can still be "prevented" would overstate what a post-hoc log write can
     guarantee. Instead, an intent entry with no matching outcome within a bounded window is a distinct,
     explicitly-defined audit state — **unresolved intent** — that Security must be able to query and
     alert on, rather than a silently-dropped gap.

     Two different blast radii, not one claim: a **leaked per-request credential** is scoped to a
     single writable point by construction (point 2) — it is only ever valid for the one
     `<site>/<node>/<point>` it was minted for, not the whole node. A
     **compromised endpoint itself** is a different, larger problem: even holding no credential of its
     own, a compromised endpoint could still *request* proxy-issued tokens for cases it has no business
     touching unless the proxy's own authorization checks the endpoint's identity and active-case claim
     independently — that check is the proxy's job, not the endpoint re-implementing it, exactly as
     Engineer's SSH-secret requests are already authorized by the proxy today.

     **Minimum containment, decided here, not deferred whole:** the endpoint runs under its own
     dedicated service account and sandbox (not Engineer's, not shared with any other endpoint),
     owner-/PAP-governed lifecycle (create/kill/upgrade — the same "no self-granted authority" rule
     ADR 0003 §5 puts on Engineer applies here too), and **deny-by-default egress to exactly four
     destinations**: Systemdatabas (case-approval checks), the credential/signing proxy, the MQTT
     broker, and the append-only audit sink — no reachability to Advisor, Security, the PAP network,
     or the public internet, mirroring ADR 0003 §2's shape for Engineer. What's still genuinely open
     is the **enforcement substrate** for that sandbox (namespaces+LSM vs. microVM) — tracked in Open
     questions, the same way ADR 0003 §Open-questions left that same choice open for Engineer while
     still deciding Engineer *would* be sandboxed.

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
     site-scoping via a `+` wildcard, and node identity via `${clientid}` rather than a verified
     cert-derived claim (`skills/mqtt-tls-broker`) — is not carried over to `cmd/#`; the precondition
     above (cert-derived site *and* node, enforced at the TLS layer, not the client's self-reported
     ClientID) is exactly what stops both failure modes at once. The telemetry side keeps its existing
     gap for now (a separate, read-only, lower-severity issue, tracked in Open questions for its own
     fix), but neither a reused node id nor a spoofed ClientID can let a node *read commands* meant for
     another node or site, because the command subscribe rule is evaluated against the certificate
     itself, not anything the connecting client asserts.

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
   overwrite the held value. The **freshness window** itself is not left implicit: it is a per-point
   attribute of the same equipment/permission profile that already carries that point's range/clamp
   limits, with a **default maximum of 60 seconds** unless a profile explicitly sets a
   tighter one — and the same value is what both the node's local check *and* the broker's
   `message expiry interval` (below) are configured from, a single source of truth rather than two
   independently-set numbers that could silently drift apart. The **entire** command envelope is signed and
   verified as one canonical unit — `site`, `node`, writable-point id, value, unit/profile, the
   case/profile-id it was approved under, sequence number, and timestamp — not just the two
   freshness fields; a signature that covered only sequence/timestamp would leave the value and the
   site/node binding open to tampering even while looking "fresh".

   **Signing identity and key custody — a minimum decision, not fully deferred:** the **mediated MQTT
   write endpoint** (decision 1), not Engineer, holds the signing capability, and it does so the same
   way it holds its publish credential — by requesting use of it per-request from the **same
   credential/signing proxy already counted among the endpoint's four allowed egress destinations in
   decision 1** (it is one service performing two related functions — issuing short-lived publish
   credentials and signing command envelopes — not two separate destinations; "PAP-governed" describes
   who authors that service's policy, not a second network endpoint), never holding the private key as
   a standing secret of its own. Engineer never has access to the raw signing key, consistent with ADR
   0003's "never raw credentials in opencode's context". The edge node verifies against a trust anchor
   distributed through the **same signed-artifact pipeline** already used for code deploys (ADR 0001) —
   this is not a second, separately-invented PKI. Exact key rotation cadence and the canonical field
   encoding are left to Open questions, but *who* signs and *where trust is anchored* are decided
   here.

   A message that fails any check
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
   prohibition, not merely implied by it. `message expiry interval` is MQTT 5 semantics: **cmd/#
   requires MQTT 5 on both publisher and broker configuration**, with the broker enforcing a maximum
   expiry rather than trusting a publisher-set value — this is a fourth precondition, alongside the
   cert-claim and identifier-canonicalization ones above, to verify against the deployed EMQX version
   before `cmd/#` is activated for any node; if the deployed fleet cannot be moved off MQTT 3.1.1, the
   node's own signature/freshness check becomes the *only* defense against a queued stale command and
   this decision must be revisited before rollout, not assumed away. A late-joining or reconnecting
   subscriber must never receive a stale command from *any* broker-side store — retained, queued, or
   otherwise — instead of relying purely on the node's own validated local state. This keeps the loop
   regulating unaffected by an outage anywhere above it in the chain, and this is the same discipline
   as the existing store-and-forward spool, applied to the inbound side.

**3. Central revocation of an already-applied setpoint during a partition is accepted as impossible
   by design**, not solved by a protocol. It is a direct consequence of decisions 1–2: there is no
   push path into a node that isn't reachable, by the same deny-by-default, edge-initiated model that
   already governs everything else in this architecture. The backstop against an unsafe held value is
   a **physical/PLC interlock independent of the software that issued the command** — never a network
   mechanism. **This addresses the "Physical/PLC interlocks" checklist item in #13, but narrower than
   its literal "every writable point" wording**: HLV without an independent interlock is not an
   acceptable end state for any **safety-relevant** writable point — not every writable point needs
   one (a comfort-tuning setpoint with no safety consequence doesn't). #13 stays open for whichever is
   broader in practice; this ADR decides the *safety-relevant* subset, it does not close the checklist
   item outright.

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
  reissuing as part of rollout, not after; the procedure is decided in
  [`docs/operations/cert-reissuance-plan.md`](../operations/cert-reissuance-plan.md). It also needs
  **MQTT 5 support** (decision 2's `message expiry interval` requirement) confirmed on both broker
  and publisher/node clients before `cmd/#` is activated for any node, not assumed from the ACL
  config alone — verified against a live broker
  ([`docs/verification/emqx-mqtt5-cmd-verification.md`](../verification/emqx-mqtt5-cmd-verification.md)).
- **ADR 0003 §2 is amended alongside this ADR** (done, not deferred): its three named endpoints become
  four, with the mediated MQTT write endpoint described in the same short-lived/case-bound credential
  language already used for the credential proxy. The endpoint itself is still new infrastructure to
  build — it doesn't exist today — but it is Engineer's endpoint to call, not a new trust domain or a
  capability living outside CONTEXT.md's three-trust-domain model. Its minimum containment shape
  (dedicated sandbox/service account, owner-/PAP-governed lifecycle, deny-by-default egress to exactly
  Systemdatabas + credential proxy + broker + audit sink, full audit of denied/failed attempts too)
  is decided by decision 1; only the enforcement substrate is separate work, tracked in Open questions.
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
  identity model) and reachable for publish only via a short-lived, **point-scoped** credential
  requested per operation (SR 2.1 authorization enforcement, least privilege — narrower than the node
  itself, no standing broad-scope write credential), and is functionally separated from the existing
  telemetry namespace rather than carved out of it — this supports logical separation and
  least-privilege/conduit-style policy
  enforcement; it is a topic/ACL-level control, not a claim that MQTT namespacing by itself
  constitutes IEC 62443 zone/conduit segmentation, which is a broader network-architecture concept.
- **NIS2 (Dir (EU) 2022/2555):** Art. 21.2 risk-management measures can support the case for favouring
  continuity of the regulated physical process during a network incident — the article does not
  itself prescribe HLV over fail-safe. The failure mode for each safety-relevant point must still be
  risk-assessed per installation; openAut itself is not a NIS2 entity, but the building operator
  deploying it plausibly is.

## Open questions

Each item below is decided *that* it must happen and, where applicable, its shape or preconditions;
none are blocking for this ADR's Proposed status. Tracked as separate issues rather than left as
open-ended prose, so each gets its own owner and can close independently of this document:

- **Exact canonical field encoding** for the signed command envelope, key-rotation cadence, and
  whether acks/reglercentral health status need a topic distinct from `cmd` — *who* signs and the
  trust-anchor pipeline are decided in decision 2. Tracked as issue #27.
- **The "unresolved intent" audit reconciliation window** — decision 1 decides the intent/outcome
  audit split and that Security must be able to query unmatched intents; the exact bounded window
  before an unmatched intent is surfaced is left open. Tracked as issue #26.
- **The mediated MQTT write endpoint's enforcement substrate** — namespaces+LSM vs. a microVM, the
  same choice ADR 0003's Open questions left open for Engineer; the containment *shape* itself
  (sandbox, egress allowlist, audited denials) is decided in decision 1, not open. Tracked as
  issue #28.
- **Site-claim field, EMQX directive, and MQTT5/broker max-expiry: verified** against a live EMQX
  5.8.9 Community Edition instance
  ([`docs/verification/emqx-mqtt5-cmd-verification.md`](../verification/emqx-mqtt5-cmd-verification.md))
  — decision
  1's precondition 1–2 text above now reflects the result (CN via `${cert_common_name}`, not a
  separate SAN/OU claim, which needs Enterprise Edition). The cert-reissuance rollout plan for nodes
  provisioned before this ADR is decided in
  [`docs/operations/cert-reissuance-plan.md`](../operations/cert-reissuance-plan.md) — a procedure,
  not a claim that any real fleet has been migrated; there is no deployed fleet yet. Building the
  inventory/issuance tooling the plan describes, and re-verifying against the actual target EMQX
  edition/version if it ever differs from the CE instance tested, are both real follow-on work, but
  neither blocks closing issue #24 — that issue asked for the plan, not the fleet or the tooling.
- **`mqtt-tls-broker`'s telemetry-side gap** (`openaut/+/${clientid}/#`, which wildcards site *and*
  still trusts client-supplied ClientID) is untouched by this ADR (decision 1's "legacy limitation"
  note) — still worth fixing broker-wide, ideally by applying the *same* cert-derived-identity
  mechanism decision 1 introduces once issue #24 lands. Tracked as issue #29.
- **The interlock mechanism itself** (hardware limit switches, PLC-level clamps, etc.) is
  per-equipment and out of scope here — this ADR only establishes that HLV depends on one existing.
  Already tracked in issue #13.
