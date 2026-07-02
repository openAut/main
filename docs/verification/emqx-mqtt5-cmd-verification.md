# EMQX cert-derived identity + MQTT5 verification (issue #24)

- **Date:** 2026-07-02
- **Broker under test:** EMQX 5.8.9 Community Edition, official `.deb` release (`emqx-5.8.9-ubuntu24.04-amd64.deb`), fresh install on an isolated lab VM (`oa-lab`) — not the shared production broker.
- **Method:** a new, isolated TLS listener (`ssl:cmdtest`, port 8884, `verify_peer` + `fail_if_no_peer_cert = true`) bound to a throwaway test CA, with ACL rules scoped to a `cmd-test/` namespace — zero contact with any existing broker configuration. Client tests via `mosquitto_pub`/`mosquitto_sub` 2.0.22 (MQTT5).

## Headline finding: SAN-based site/node extraction requires EMQX Enterprise Edition

ADR 0004's decision 1 left "exact site-claim field (SAN vs OU vs a new extension)" open, following both reviewers' preference for a URI SAN. **That mechanism does not exist in EMQX Community Edition.** EMQX's `client_attrs_init` variform functions for extracting individual SAN fields (`cert_san.uri`, `cert_san.dns`, etc.) into separate named attributes were merged 2026-06-18 ([PR #17603](https://github.com/emqx/emqx/pull/17603)) under `changes/ee/` — confirmed Enterprise-only by the changelog directory convention, and consistent with our instance reporting `"edition":"ce"` on login. This is new information ADR 0004 didn't have.

**What Community Edition actually supports** (confirmed live, not from docs alone): the built-in ACL file format supports a placeholder `${cert_common_name}` — the client certificate's whole Common Name substituted verbatim into a topic pattern. There is no built-in way to extract two separate fields (site, node) from one certificate in CE.

**Working CE mechanism, verified:** set the certificate's CN to the combined `<site>/<node>` path segment itself (e.g. `CN=A/n1`), and the broker can bind ACL scope to it via a single rule:
```
{allow, all, subscribe, ["cmd-test/${cert_common_name}/#"]}.
{deny,  all, all,       ["cmd-test/#"]}.
```
This finding is now reflected directly in [ADR 0004](../adr/0004-edge-control-writes-and-continuity.md) decision 1's precondition 1–2 (updated in the same PR as this document) — **the site-claim field is the certificate CN, not a SAN or OU**, for a Community Edition deployment. This verification report is evidence for that decision, not itself the normative source; the ADR is. (If Enterprise Edition is ever adopted, the SAN-based `client_attrs_init` mechanism would give genuinely separate `${client_attrs.site}`/`${client_attrs.node}` placeholders — worth reconsidering then, but not needed for the CE precondition.)

**Important scope note — the test setup below also grants `publish` on the node's own cert-derived scope, and that part is a lab shortcut, not the production design.** ADR 0004 decision 1 is explicit that subscribe is node-wide by design (a node needs to receive commands for all its own points) but **publish is per-request, mediated, and case-scoped** — issued through the mediated MQTT write endpoint, never a standing grant on a node's own certificate. The tests below use a symmetric `{allow, all, publish, [...]}` rule purely to exercise the `${cert_common_name}` substitution mechanism itself from both directions (does identity-scoping work at all, in either direction) — it is **not** a template for how a real deployment should grant publish rights. Copying this ACL verbatim into a production config would grant every node standing, unmediated publish rights to its own `cmd/#` subtree, bypassing the case-approval and credential-proxy flow decision 1 requires.

## Test 1 — cert-derived identity, positive/negative scope

The lab ACL adds a **test-only** publish rule alongside the subscribe rule shown above, purely to exercise `${cert_common_name}` substitution in both directions -- not a recommendation to grant standing publish on a node's own cert (see the scope note above):
```
{allow, all, publish, ["cmd-test/${cert_common_name}/#"]}.
```

| # | Test | Result |
|---|------|--------|
| 1 | Cert `CN=A/n1` publishes to `cmd-test/A/n1/setpoint` (own scope) | Allowed |
| 2 | Same cert publishes to `cmd-test/B/n2/setpoint` (different site) | Denied (`Not authorized`) |
| 3 | Cert `CN=A/n1`, MQTT ClientID spoofed to `B-n2-spoofed-clientid`, publishes to `cmd-test/B/n2/setpoint` | Denied -- proves ClientID is **not** used for authority |
| 4 | Same spoofed-ClientID connection publishes to its own cert-derived scope (`cmd-test/A/n1/setpoint`) | Allowed -- scope follows the certificate, not the ClientID |
| 5 | Certificate with no CN at all (`O=` only) publishes to any `cmd-test/` topic | Denied |

Confirms ADR 0004's core precondition: identity for `cmd/#` authorization must come from the certificate, never from the client-supplied MQTT ClientID -- verified against a live broker, not assumed.

## Test 2 — identifier validation (issue #25): wildcard injection, proven exploitable

This directly tests issue #25's concern -- that an unvalidated identifier used to build an ACL rule could widen scope. **It does, and it was reproduced end-to-end, including actual data exfiltration:**

- A certificate with `CN=+` was issued (deliberately invalid per issue #25's proposed regex -- `+` is a forbidden character).
- Substituted into the ACL template, the rule becomes `cmd-test/+/#` -- and MQTT's `+` wildcard (any single topic level) is live at that point, **not** treated as a literal string.
- **Proof of exploit:** the `CN=+` client subscribed to `cmd-test/A/n1/setpoint` (a specific victim topic it has no legitimate claim to) -- SUBACK success. A legitimate client (`CN=A/n1`) then published `SECRET_PAYLOAD_FOR_A_N1_ONLY` to that topic. **The `CN=+` client received it.** Full cross-tenant read access via a single malformed certificate field, with the placeholder-substitution ACL mechanism EMQX ships out of the box.
- A parallel test with `CN=#` was **not** exploitable via this same pattern: MQTT requires `#` to be the last character of a topic filter, so the substituted rule (`cmd-test/#/#`, `#` not at the end) is malformed and never matches -- publish attempts were denied (MQTT5 reason code 135). This is incidental protection from MQTT's own grammar, not a mitigation -- a different placeholder position (e.g. `${cert_common_name}` as the *last* segment) would likely make `#` exploitable too, and `+` is already sufficient to prove the vulnerability class.
- A certificate with `CN=A/../B/n2` (path-traversal-shaped) behaved as an inert literal -- MQTT topics have no `..`-segment semantics, so this client just got its own (odd-looking but harmless) scope. Not a vulnerability, but confirms path-traversal isn't a live vector here -- the wildcard characters are the actual risk, not path syntax.

**Conclusion: issue #25's identifier-validation precondition is not a hardening nice-to-have, it is a proven, exploitable gap if skipped.** Any deployment that activates `cmd/#` with `${cert_common_name}`-style ACL templating and does not reject `+`/`#` (and, by the same logic, should reject `$`, control characters, and empty values) in the CN before issuance is vulnerable to this exact cross-tenant read.

**Character rejection alone is not sufficient for this ACL pattern — the CN needs a structural check too.** Rejecting forbidden characters stops the wildcard-injection exploit above, but `${cert_common_name}` substitutes the *entire* CN as one unit, so a CN that's individually "clean" per-character can still be structurally wrong in a way that silently widens scope: a CN of just `A` (missing the node segment) would resolve to `cmd-test/A/#` — every node under site A, not the one node it should be scoped to. The CN must be validated as a **whole two-segment structure**, not just character-filtered:

```
^(?P<site>[a-z0-9](?:[a-z0-9._-]{0,61}[a-z0-9])?)/(?P<node>[a-z0-9](?:[a-z0-9._-]{0,61}[a-z0-9])?)$
```

— exactly one `/` separating two non-empty segments, each independently matching issue #25's proposed per-segment canonical-id pattern. This is enforced at cert-issuance time by the asset-owner/Systemdatabas process (per ADR 0004 decision 1's third precondition) — the CN is never accepted as a free-form string from a certificate signing request.

## Test 3 — MQTT5 message expiry

Broker's `mqtt.message_expiry_interval` set to `5s` (a broker-enforced upper bound -- default is `infinity`, i.e. unset/unbounded, and **must be explicitly configured** for any real deployment; this is itself a rollout precondition, not automatic).

**Config used** (global `mqtt` scope, applies broker-wide — not a per-listener setting in this EMQX version):
```
$ echo 'mqtt.message_expiry_interval = 5s' > /tmp/expiry.conf
$ sudo emqx ctl conf load /tmp/expiry.conf
load mqtt on cluster ok
$ sudo emqx ctl conf show mqtt | grep expiry
  message_expiry_interval = "5s"
```
`emqx ctl conf load` applies immediately, cluster-wide, no restart — verified by the immediate `conf show` readback and by the timing behavior in the test table below.

| # | Test | Result |
|---|------|--------|
| 1 | Persistent session (`clean_start=false`, `session-expiry-interval=300s`) subscribes, disconnects. A message is published with `message-expiry-interval=2s` while offline. Client reconnects after 8s (past both the 2s client value and the 5s broker max). | Message **not delivered** -- expired as required |
| 2 | Same persistent session; a fresh message (no explicit expiry, defaults to the broker's 5s) is published while offline; client reconnects within ~1s. | Message **delivered** -- confirms expiry isn't overly aggressive |

Confirms ADR 0004's decision 2/precondition: a late-reconnecting node must never receive a stale queued command, and the broker's own `message_expiry_interval` is the enforceable backstop, verified as functional in EMQX 5.8.9 CE (default install has this **unset**, i.e. no protection, until deliberately configured).

## Rollout implications for ADR 0004 / issue #24's checklist

- [x] Site-claim field: **resolved and reflected in ADR 0004** -- certificate CN, formatted as the canonical `<site>/<node>` identifier (not SAN/OU as originally proposed; that mechanism is EE-only).
- [x] EMQX cert-to-identity ACL binding: **verified working** in CE via `${cert_common_name}`, positive and negative cases both confirmed.
- [x] MQTT5 message expiry: **verified working**, but confirmed **not the default** -- `mqtt.message_expiry_interval` must be explicitly set as part of rollout, not assumed.
- [ ] Cert-reissuance rollout plan: still a planning task, not a technical verification -- unchanged, tracked in issue #24.
- **New findings for issue #25** (posted there, not re-litigated here): the wildcard-injection test above is a confirmed exploit, not a hypothesis, and the per-character validation it originally proposed needs a companion **structural** check on the combined CN (exactly one `/`, two non-empty valid segments) -- character-filtering alone is not sufficient for the `${cert_common_name}`-as-whole-string ACL pattern this verification confirms is the working CE mechanism.
