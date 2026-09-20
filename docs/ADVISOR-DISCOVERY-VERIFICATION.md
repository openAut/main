# Advisor discovery — sanitized verification note

## Evidence boundary

The area-scoped design was exercised in an isolated POC with two installed systems: scoped metadata,
telemetry/history and verified Forge retrieval; automatic discovery of registered alarm contracts;
separate synthetic analyses; persistent state; a shared delivery budget; and worker restart.
Existing ambiguous delivery evidence was retained for operator review rather than erased/replayed.

The public package is a **portability adaptation**, not a byte-identical copy of that deployed lab.
It removes lab identifiers, dated directories, one-off rollout code and host-specific module paths.
Connections/credentials/timezone are owner configuration. It uses hashed namespaces for every
equipment and adds optional product-manual projection compatible with the repository's manual-ingest
model. Those changes require a deployment-specific acceptance test before replacing an installation.

## Reproducible checks for this package

Reference checks are rerun after review fixes. The latest results are recorded in the PR's
verification comment; the
disposable PostgreSQL 16-compatible schema/authorization suite passed; Node adapter tests and the
OpenClaw 2026.9.4 hook/discovery/tool-policy tests passed on Node 24. Documentation links and skill
permission schemas were checked. Publication review found no matches for the configured lab-ID,
private-network/workstation-path, runtime-ID or common credential-material patterns in the new payload.

- Python tests cover request limits, per-operation authorization, discovery pagination, real HTTP
  authentication/write rejection, document identity/hash checks and source-code-as-data handling.
- Detector/worker tests cover short transitions, overlaps, late observations, malformed input,
  restart ambiguity, binding/profile changes, revocation, discovery failure and persistent global budget.
- Dense-history regressions put more than 500 samples entirely before the cursor and prove that
  later alarms remain discoverable. Bounded scans resume across restarts and failed requests;
  unpartitionable same-instant density preserves the cursor and reports a quality failure.
- Further full-review regressions cover conflicting old observations within/across polls, complete
  unresolved-outbox capacity, persistent fair dispatch including ambiguous delivery, and denied
  history reads through the HTTP boundary. Real loopback HTTP tests exercise shared document-search
  deadlines and a trickling response; transport tests reject non-loopback cleartext access.
- Engineer tests bind the offline proposal to exact artifact bytes, reject the removed direct
  registration command and forbid identity/connection claims in the proposal envelope.
- Disposable PostgreSQL tests cover fresh implicit-deny, owner area/repository boundaries, constrained
  registration, expiry, artifact approval, denied policy/site edits, automatic discovery and revocation.
  Engineer has no registration EXECUTE privilege; the external owner registrar is separately bound
  to trusted Engineer context, cannot edit policy/approvals, and audits both producer and executor.
  Product-manual tests distinguish shared verified manuals from other products/private site material.
- Node tests cover bounded read requests, equipment-response binding, timezone conversion, synthetic
  routing, current authorization and rejection of caller-controlled agent/session/model fields.
- The optional OpenClaw 2026.9.4 SDK test exercises real plugin discovery, exact read-tool policy and
  hook/session resolution. It does not make a model call or claim browser acceptance.

Run commands are in the [package README](../deploy/advisor-discovery/README.md). Operational evidence
such as host inventories, run/session IDs, case reports, credentials and active SQLite state remains
machine-local. A passing source test is not evidence of connectivity, TLS provisioning, model
completion, physical point-map correctness or production suitability on another installation.
