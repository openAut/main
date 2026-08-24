# POC2 Systemdatabas and Forgejo verification

- **Date:** 2026-08-20
- **Scope:** isolated workstation lab; no field write or deployment
- **Result:** database and Forge governance foundations passed; full POC2 remains incomplete

## Systemdatabas evidence

Migration `deploy/platform-poc2/db/001-system.sql` added equipment, points, documents, cases,
approvals, generated artifacts, and append-only audit data alongside the existing telemetry schema.
It also added separate `advisor_app`, `approver_app`, and `engineer_app` group roles.

The verification script proved:

1. Advisor could create a draft and request approval only through the constrained function.
2. Engineer was refused when attempting to start an unapproved draft.
3. Advisor could not supply a forged `created_by` identity.
4. An identity holding both Advisor and Approver memberships could not approve its own case.
5. The approver could not add any permission beyond the exact POC2 forge-PR-only scope.
6. The approver function moved a forge-PR-only case to approved and recorded an audit event.
7. Engineer could start the approved case through a constrained function and read its scope.
8. Request, approval, and Engineer start used three distinct session identities and produced three
   audit records.

```text
POC2_DB_OK unapproved_case=denied invalid_scope=denied self_approval=denied spoofed_actor=denied approved_case=in_progress:3:3
```

## Forgejo evidence

Forgejo 16.0.2 ran rootless against its own PostgreSQL database and was bound to Platform loopback.
A human completed the forced administrator password change. Bootstrap automation then created:

- private organization `openaut`
- five private repositories
- restricted `openaut-engineer` service identity
- write-scoped Engineer team membership
- protected `main` on all five repositories
- one required review, with direct push/merge limited to the human administrator

```text
FORGEJO_BOOTSTRAP_OK org=openaut repos=5 engineer_team=2 protected_main=5
POC2_FORGE_ENGINEER_OK identity=openaut-engineer restricted=true admin=false private_repos=5 repo_access=5
```

## Lessons

- The richer Systemdatabas model previously existed only as a Markdown reference; the telemetry
  schema contained only `sites` and `devices`.
- Column grants alone are insufficient for state transitions. Security-definer functions provide a
  small enforcement point for request, approval, and Engineer start transitions.
- Forgejo should use a separate database role/database even when colocated with TimescaleDB.
- Bootstrap administrator tokens and Engineer tokens must be files outside version control, scoped,
  short-lived or revocable, and never written to command output.
- Loopback plus an SSH tunnel provides an encrypted bootstrap path but does not satisfy the target
  TLS endpoint requirement.

## Remaining acceptance work

- Add the managed TLS endpoint and CA trust path.
- Deliver the scoped Forge token to Engineer without exposing it to prompts or logs.
- Prove branch creation, PR, human review, protected merge, and case-linked audit evidence.
- Add CI status enforcement and deterministic migration tests before claiming POC2 complete.
