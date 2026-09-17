# M1 implementation profile — prioritize platform services and Advisor

Status: candidate implementation plan for [Milestone 1](MILESTONE-1.md), not a tested installer or
a supported release manifest. Resource numbers below are planning allocations pending measurement.

## First deliverable

Build a **read-only workstation preflight** before implementing VM creation. A beginner should
receive a short readiness summary and specific next steps. The preflight must never enable
Hyper-V, change adapters, start/stop VMs, download software, or modify SSH configuration.

The intended end state is local opencode on Windows plus two Ubuntu guests: platform services and
Advisor. A separate Engineer VM, Security VM, and CI VM are not required to run the M1 journey.
Existing resources must be inventoried and offered for explicit reuse; never delete or stop them
automatically to satisfy a resource budget.

## Candidate workstation and VM budget

| Resource | Candidate allocation | Verification needed |
|---|---|---|
| Workstation | Windows 11 Pro, Hyper-V, 64 GB RAM, SSD | Supported build, firmware virtualization, available capacity |
| Platform VM | 4 vCPU, 6 GiB startup / 8 GiB maximum RAM, 100 GiB dynamic VHDX | All data services healthy during ingestion and document retrieval |
| Advisor VM | 4 vCPU, 4 GiB startup / 6 GiB maximum RAM, 60 GiB dynamic VHDX | Pinned runtime, remote inference, Teams and retrieval load |
| Host reserve | At least 8 GiB available to Windows during the combined trial | Include local opencode, browser, hypervisor and any other workload |
| Initial storage planning envelope | 220 GiB free on the selected VM/artifact volume | 160 GiB guest virtual capacity plus 60 GiB installation/backup headroom; replace with measured release requirement |

The 220 GiB envelope is a conservative planning proposal, not a measured minimum. Dynamic VHDX
allocation is not evidence that future writes will fit. Check guest growth, images, logs, database
retention, rollback copies and backups during acceptance; keep backup copies outside the guest.
Resource placement must be configurable rather than assuming a particular disk or workstation.

64 GB describes the first target profile, not a universal minimum for every lab. The existing
smaller lab may support component tests, but it cannot by itself prove the clean 64 GB user trial.
Inference is remote; no guest GPU assignment or local model memory budget is assumed.

## Read-only preflight contract

Report each check as `pass`, `action_required`, or `unknown`, with evidence and a plain-language
next step. Missing permissions or unavailable APIs are `unknown`, not proof of readiness.

| Check | Required result |
|---|---|
| OS and virtualization | Identify Windows edition/build, Hyper-V feature state, management cmdlets and current elevation; explain any administrator/reboot step |
| Capacity | Report installed/available RAM, CPU and free space on the selected existing volume; distinguish target-profile mismatch from immediate capacity failure |
| Existing VMs | List relevant names, state, memory, disks and adapters; detect naming conflicts without modifying resources |
| Network | Identify internet/default route and candidate isolated Ethernet path; flag ambiguity for user selection rather than inferring lab safety from an IP range |
| Isolation context | Ask the user to confirm a controlled test rig with no live/occupied/safety-critical equipment; record confirmation separately from machine observations |
| Local tools | Check opencode, Git, SSH and their versions; obtain the expected project revision from the chosen release manifest |
| Artifact provenance | Compare checkout/revision and integrity against an owner-approved reference; identify signature verification and trust-key setup still required by the release path |
| Inference and Teams | Report configuration readiness without exposing keys; actual authenticated tests are a separate scoped step |

The planned output is a human summary plus an opt-in machine-local structured report with a schema
version, check IDs, timestamp, observed values, status and remediation. No private keys, tokens,
environment dumps or credential-bearing URLs may be captured. Local host/network observations
must be sanitized before sharing. Do not create a blanket "safe to deploy" decision from preflight.

Tests should use recorded/mocked Windows observations for normal, missing-permission, insufficient
capacity and ambiguous-network cases, plus one read-only Windows run. Validate that checks never
call state-changing operations and that unknown conditions cannot silently become `pass`.

## Installation sequence after preflight

1. **Choose the exact inputs.** Freeze the project revision, Ubuntu image/checksum, component
   versions and model endpoint. Record the selected profile and lab asset owner. Resolve the
   release-authenticity decision below before publishing the acceptance startup prompt.
2. **Prepare the journal.** Track planned/completed/verified/blocked steps and artifact revisions,
   with approvals and rollback references. Credentials remain outside it. Reconcile reality on
   resume; configuration changes invalidate the affected verification rather than earlier history.
3. **Provision platform services.** Guide host prerequisites and create the Platform guest with
   its own SSH identity. Configure management, storage and time, then Forgejo, MQTT, the database
   schemas and Grafana. Verify each service before progressing.
4. **Provision Advisor separately.** Create its own guest and identity, validate the pinned runtime
   and remote inference, then add scoped read tools and Teams. Ubuntu 26.04 compatibility is an
   experimental gate; select a verified 24.04 fallback explicitly if the trial fails.
5. **Verify network boundaries.** Platform may reach the isolated field services it needs. Advisor
   has management/service access only. Test denied field paths: absence of a field adapter is
   insufficient because Hyper-V Default Switch can route through the host. Preserve the host's
   Wi-Fi internet path and use no unintended gateway, bridge or forwarding on the field segment.
6. **Import and verify the manual.** Use the existing manual-ingest archive and review workflow,
   then link the product and installed equipment. Test Advisor retrieval before field deployment.
7. **Complete the reference integration.** The local opencode session guides a narrow read,
   prepares the collector and records explicit owner approval before persistent installation.
   Since the Systemdatabas now exists, use it to record the case before the edge deployment in
   this normal sequence; retain the lightweight local-case exception from M1 for bootstrap or
   isolated diagnostic work. Verify telemetry, dashboard, communication health and rollback.
8. **Exercise Advisor and resume.** Run the known synthetic alarm and dialogue tests, then the
   documented restart/resume and communication-recovery checks. Publish sanitized evidence.

Advisor does not receive general Windows/SSH administration tools. The local engineering session
is a supervised lab workflow and is not claimed to implement the production Engineer sandbox.
Untrusted manual conversion still uses its isolated conversion workflow, not arbitrary execution
of document instructions in the host agent session.

## Open decisions before a supported release

| Decision | Completion evidence |
|---|---|
| Reviewed lab deviation from the full Engineer model | Explicit review of the M1 scope; unresolved reviewer objections remain visible |
| Startup artifact authenticity and trust bootstrap | Chosen release authority, trusted verification key distribution, signed artifact format and failed-signature test; a hash alone does not establish approval |
| Ubuntu / Advisor compatibility | Exact versions, successful isolated runtime test or verified fallback |
| Local opencode and runtime models | Tested tool calling and retrieval/dialogue behavior, endpoint configuration and provider prerequisites |
| Resource requirements | Combined workload measurements and measured disk/backup headroom |
| Reference equipment | One selected model/program version, applicable manual and validated read-only point map |
| Teams path | Tenant/account setup instructions and working send/receive test |

The signed-release path is not provisioned by this document. Until authenticity and the other
release decisions are settled, use explicitly labeled development trials, not claims of completed
M1 acceptance. Keep generic installation material in GitHub and site/manual/integration content
in the user's Forgejo and Systemdatabas.
