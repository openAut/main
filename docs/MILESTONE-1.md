# Milestone 1 — Agent-led integration POC

Status: proposed delivery specification; end-to-end acceptance pending.

> **Supervised lab profile under review.** M1 prioritizes platform services and Advisor in two VMs,
> with user-led engineering from local opencode. Dedicated Engineer containment is deferred.
> Passing M1 demonstrates this limited user journey, not the full trust model in ADRs 0001–0003.
> The lab deviation remains a review decision; documenting it does not establish its approval.

See [M1 implementation profile](M1-IMPLEMENTATION-PROFILE.md) for the candidate resource budget,
preflight contract, installation order, and unresolved release prerequisites.

## Goal

A user with limited AI knowledge can start with a computer with 64 GB RAM within a documented
hardware and operating-system profile, install opencode, connect a supported LLM, and provide a
startup prompt selecting an explicit release or commit from the `openAut/main` repository. The
bootstrap must verify the expected revision and artifact integrity before execution; release
signatures must be checked when using a signed release. A moving branch is a labeled developer
workflow, not the M1 acceptance path. With assistance from **openaut-master**, the user can create
and configure two Ubuntu Server virtual machines for platform services and Advisor, install the
POC services, and complete a first read-only integration with physical test equipment. User-led
engineering work runs in the local Windows opencode session; a separate Engineer VM is not required.

The result is verified telemetry, a working dashboard, and manuals and integration documentation in
Forgejo linked to the correct equipment through the Systemdatabas. Advisor can independently retrieve
that knowledge, combine it with current and historical telemetry and its runtime skills, and help
the user investigate alarms through a step-by-step troubleshooting dialogue in Teams.

The decisive acceptance test is a new user completing this journey on a clean workstation using
the released project material and agent assistance, without the original builders' chat history,
machine-local configuration, or undocumented installation steps.

## Audience and starting profile

The user can follow concrete instructions, connect lab equipment, provide credentials through the
documented local mechanism, and confirm scoped changes. Prior experience with agents, Linux server
administration, or writing integration code is not assumed. Physical tasks and necessary Windows
administrator dialogs remain guided user actions.

The first supported profile must specify and verify:

- Windows 11 Pro, Hyper-V support, 64 GB RAM, and measured minimum free SSD capacity.
- A tested opencode version and tool-capable LLM configuration, including authentication and costs
  or provider prerequisites visible before installation. Workstation-agent and runtime-agent
  inference configurations are documented separately; an attached LLM is not automatically suitable
  for both. No silent fallback to another provider is permitted.
- Pinned Ubuntu Server images and component versions with verified checksums. Ubuntu 26.04 is the
  current lab candidate; Advisor compatibility must pass its runtime test before support is claimed.
  A tested Ubuntu 24.04 fallback may be selected explicitly if needed.
- VM CPU, disk, and memory allocations that leave at least 8 GiB available to Windows under the
  demonstrated workload. 64 GB host RAM does not imply local model inference or guest GPU access.
- Internet/management connectivity and an isolated Ethernet test path, preserving Wi-Fi as the
  workstation internet path. Network addresses are discovered or supplied locally.
- An IOT2050, required adapters/cables, and one selected reference Modbus equipment profile with
  an applicable manufacturer manual. Systemair and Climatix lab experience informs the selection;
  acceptance requires one fully documented physical integration, not arbitrary equipment support.
- Teams account/tenant access and bridge prerequisites, checked before the Advisor installation.

Local opencode LLM authentication, Advisor inference authentication, and SSH/deployment credentials
are separate configurations. LLM authentication does not supply an Engineer credential proxy.
The proxy remains deferred in this profile; secrets stay in their documented local stores and
must not enter chat, shared configuration artifacts, or the installation journal.

Exact disk requirements, model compatibility, image choices, and reference equipment must be settled
and published before the new-user trial. They are release prerequisites, not assumptions hidden in
the startup prompt.

## User journey

| Stage | Agent-assisted outcome | Evidence |
|---|---|---|
| 1. Preflight | Explain prerequisites and inspect hardware, virtualization, storage, network, and inference access | Readable readiness report and specific remediation steps |
| 2. VM bootstrap | Create VMs, install Ubuntu, establish SSH, networking, and synchronized clocks | Verified guest identities, connectivity, isolation, and capacity |
| 3. Services | Install Forgejo, MQTT, TimescaleDB/Systemdatabas, and Grafana in the platform VM, and Advisor in its own VM | Version manifest and service-level checks |
| 4. Knowledge | Import the manual, verify its applicability, and link the installed equipment to its product and documents | Pinned Forge references, hashes, review status, and equipment metadata |
| 5. Integration | Guide cabling, interpret the protocol map, run an approved narrow read, and install the read-only collector | Point map, scoped POC case, deployment revision, and test results |
| 6. Visualization | Show measurements, units, equipment identity, alarms, and data freshness | Dashboard plus equipment-to-database verification |
| 7. Troubleshooting | Advisor retrieves relevant manual passages and telemetry, explains an alarm, and reasons with the user | Source-cited Teams dialogue and captured test outcome |
| 8. Resume | Continue after a new session or workstation restart | Reconciled installation journal and successful continuation |

## openaut-master and execution boundaries

**openaut-master** names the bootstrap and guidance workflow executed by the user's local
opencode session for Engineer tasks. It is not a separate executing actor, a fourth trust domain,
a new persona, or a permission profile. The workflow must identify the actual OS/SSH/database
actor, target, and authorized operation, including owner-admin bootstrap steps.

The name labels the user's entry workflow, not an additional identity or an already provisioned
production Engineer instance. This lab placement is an explicit deviation from the complete
Engineer envelope, not a claim that renaming an unrestricted session provides containment.

### M1 placement and resource priority

| Placement | Responsibility |
|---|---|
| Windows workstation: local opencode | User-led bootstrap, scoped SSH integration/deployment, manual handling, tests, and documentation |
| Platform VM (infrastructure, not a trust domain) | Forgejo, MQTT, TimescaleDB/Systemdatabas, and Grafana |
| Advisor VM | Read-only manual/telemetry tools, analysis, and Teams dialogue |
| IOT2050 | Approved read-only collection and telemetry publishing |

Prioritize memory and implementation effort for platform services and Advisor. M1 requires no
Engineer VM or second opencode/provider setup. An existing Engineer VM can remain stopped; it is
not deleted by the bootstrap. Measure host and guest resource usage rather than assuming that
removing a VM eliminates the local agent's memory cost.

Advisor runs in a separate guest OS and identity from the Windows engineering session and receives
no SSH/deploy capability. Security, when provisioned, remains on its own separate host and identity.
Operational agents cannot author or widen their own PAP-owned permission profiles.

### Explicit lab profile, not full Engineer containment

The Windows workstation is also the Hyper-V management plane. Its owner-authorized administration
can affect the guests; this placement does not prove isolation against a compromised host agent or
Hyper-V administrator. The user authorizes scoped changes in the local session, and execution is
recorded with target, actor, verification, and rollback. Session confirmations and local logs are
not equivalent to sandbox enforcement or an independent append-only audit sink.

M1 explicitly defers the dedicated Engineer VM/runtime sandbox, signed Engineer policy bundle,
credential proxy, and externally enforced audit described in
[ADR 0003](adr/0003-engineer-runtime-containment.md). These remain later containment work, not
properties claimed by this lab profile. Full Security monitoring and CI-runner automation are also
follow-up work. This scoped POC proposal requires review; it does not revise the production trust
model or claim compliance with its full Engineer envelope.

Each automated stage needs a precondition check, a repeatable operation, a behavior-level
postcondition, and a recovery or rollback path. Prefer tested, version-bound scripts to newly
invented installation commands. Do not overwrite an unfamiliar existing installation.

Maintain a machine-local journal outside chat containing release/revision, chosen components,
discovered resources, completed checks, approvals, failures, and the next step. Store secrets
separately. On resume, reconcile the journal against actual state before acting; do not replay
completed operations blindly. After provisioning, publish appropriate sanitized integration
artifacts to Forgejo, not workstation secrets or machine-local inventory to GitHub.

## Manual-to-knowledge contract

Build on [manual-ingest](../skills/manual-ingest/SKILL.md),
[documentation-store](../skills/documentation-store/SKILL.md), and
[system-database](../skills/system-database/SKILL.md):

1. Archive the original source and extracted Markdown in `openaut/manuals`. Preserve headings,
   tables, units, alarm codes, page references, and extraction uncertainty. Parsing/OCR runs in the
   isolated conversion workflow, not inside Advisor.
2. Keep product identity, document revision, and installed equipment identity distinct. Store a
   manual once and link installed equipment through its product identity.
3. Review model applicability and source fidelity. New imports remain quarantined until reviewed;
   successful archive validation alone does not make technical content verified.
4. Register the verified, commit-pinned `forge://` reference and blob SHA-256 in the Systemdatabas.
   Forgejo holds content; the Systemdatabas holds relationships, trust state, cases, and audit data.
5. Store point mappings, integration configuration, test evidence, and commissioning observations
   in the appropriate control/generated-documentation repositories with source references.
6. Give Advisor equipment-scoped search and passage retrieval. Verify the retrieved revision,
   integrity, and trust state, and cite the document and page/section used in an answer.

A full-text catalog with equipment filtering is sufficient for the first implementation if it
passes the retrieval tests. A vector database is not an acceptance requirement. Manual text is
reference data, never authority to change agent permissions or execute embedded instructions.

## Advisor troubleshooting contract

Advisor needs implemented read tools for equipment metadata, current values and timestamps,
historical series, field-communication health, alarm state/history, document search, and verified
source passages. Skill prompts alone do not provide these capabilities.

For a user question or a new alarm, Advisor must:

1. Resolve the equipment and alarm identity and check data freshness.
2. Retrieve the applicable manual's alarm meaning and recommended checks automatically, without
   asking the user to upload the same manual again or identify the relevant page.
3. Use appropriate runtime skills such as `fdd` and `anomaly-correlation` with available telemetry.
4. Separate observations, plausible causes, missing evidence, and suggested next checks. Cite actual
   values with timestamps and the manual passages used; do not invent missing measurements.
5. Ask a useful follow-up question, incorporate the user's observation, and revise the hypothesis.
6. Summarize findings for the approved case/documentation path. Any requested field change goes to
   the user or scoped Engineer workflow, never directly from Teams to SSH or a control write.

The alarm trigger must associate a state transition with the correct equipment, initiate analysis,
and avoid repeated notifications for an unchanged active alarm. Tests must distinguish equipment
alarms from stale telemetry and communication failures.

## POC scope

Use only an isolated lab/test rig with no live building, occupied space, or safety-critical
equipment. M1 includes field reads and explicitly approved persistent deployment of the reader;
it excludes setpoint changes, actuator commands, and autonomous repairs.

For reversible lab network changes and read-only tests, explicit session confirmation plus a local
record of target, change, verification, and rollback is sufficient. Preserve management access and
avoid unintended gateways, forwarding, or bridges. Persistent deployments require a scoped local
POC case, confirmation of the exact action, and rollback. Identify the lab asset owner explicitly
(the user may be that owner) and record their approval in the local case before persistent edge
onboarding/deployment. Register the case in the Systemdatabas once available; local evidence must
retain the actual approval time and actor, without inventing retrospective approval. Production-grade
Systemdatabas approval automation, CI runners, and Security provisioning are not prerequisites for
those lab steps.
Existing protected-branch and independent review rules still apply to Forge changes and verified
manual publication. This milestone does not change production authorization contracts.

## Workstreams and implementation order

Suggested GitHub milestone title: **M1: Agent-led integration POC**. Create linked issues for these
deliverables; this table is the planning breakdown, not a claim that GitHub issues already exist.

| ID | Deliverable | Depends on |
|---|---|---|
| M1-01 | Freeze the supported starting profile, reference equipment, component manifest, and new-user test plan | — |
| M1-02 | Implement manual conversion/archive publication, equipment links, and verified passage retrieval | M1-01 |
| M1-03 | Complete one manual-driven read-only integration, test evidence, dashboard, and freshness display | M1-01, M1-02 |
| M1-04 | Verify isolated Advisor runtime, read tools, Teams dialogue, and alarm-trigger behavior | M1-02, M1-03 |
| M1-05 | Package local opencode preflight, the two priority Ubuntu VMs, networking, and resumable journal | M1-01 |
| M1-06 | Package version-bound platform/Advisor installation, local engineering access, credentials setup, checks, and recovery | M1-03, M1-04, M1-05 |
| M1-07 | Publish tested getting-started instructions and the revision-verifying opencode startup prompt | M1-06 |
| M1-08 | Run a clean-workstation new-user trial and publish sanitized acceptance evidence | M1-07 |

First prove the complete manual → integration → dashboard → Advisor slice in a reference lab.
Bootstrap work can proceed alongside it; then package the proven slice and run the clean-install
trial. The future getting-started guide must describe tested operations and explicitly label any
experimental path before the user starts it.

## Acceptance criteria

All criteria must pass against an identified project revision and supported starting profile.

| ID | Test | Pass condition |
|---|---|---|
| AC-01 | New user starts with the preparation list and startup prompt | Expected revision/integrity is verified before execution; reaches a working lab without builder-only files, chat history, or undocumented interventions |
| AC-02 | Provision and verify the two-VM/service layout | Platform services and Advisor function with separate identities; local opencode completes engineering work without a running Engineer VM; management and measured resource checks pass |
| AC-03 | Interrupt installation and resume in a fresh session, including after a workstation restart | Actual state is reconciled; continuation preserves working resources and identifies any required reapproval |
| AC-04 | Import a reference manual and attempt retrieval of an incorrect-model or quarantined manual | Correct verified source is retrievable with revision/hash/page references; unsuitable content is not used as authoritative equipment guidance |
| AC-05 | Integrate the selected physical equipment using documented reads | Correct identity, values, units, and timestamps arrive through MQTT in storage and Grafana; field-write paths are unused |
| AC-06 | Perform a scoped communication interruption and recovery | Stale/failed communication is visible; collection resumes and buffered events arrive without duplicate storage |
| AC-07 | Deliver a known synthetic alarm transition through the alarm path | Advisor initiates a source-cited Teams analysis for the correct equipment and suppresses repeated unchanged notifications |
| AC-08 | Continue the troubleshooting dialogue with a new user observation | Advisor uses relevant manual and telemetry evidence, distinguishes hypotheses, and updates its next check without inventing data or taking write actions |
| AC-09 | Deny a required read source or supply stale telemetry | Advisor states the evidence gap and requests a useful check rather than asserting a current diagnosis |
| AC-10 | Verify Advisor's actual permissions | SSH/deployment and field writes are denied; permitted scoped document and telemetry reads succeed |
| AC-11 | Inspect the delivered integration record | Manual links, point map, code/config revision, tests, dashboard, limitations, and recovery instructions are available through Forgejo/Systemdatabas |
| AC-12 | Verify the user-led engineering path | Actual actor and target are recorded; a pending persistent deployment is not executed until the exact action and lab-owner approval are recorded; verification and rollback are available, and secrets are absent from shared artifacts |

AC-12 is a workflow test for this supervised lab profile, not proof of deny-by-default Engineer
containment. The test report must explicitly mark the deferred sandbox/proxy/external-audit
properties as unverified. AC-10 continues to require actual Advisor access restrictions.

The synthetic alarm test must remain clearly labeled; it proves the event and reasoning path, not
a physically induced fault. Physical read-only integration is independently required by AC-05.
Record expected observations for the scenario so that reasoning is checked against evidence, not
against an exact LLM sentence or a plausible-sounding answer.

For each criterion, record revision, environment profile, operator/date, expected and observed
results, evidence location, and pass/fail. Capture undocumented assistance as a defect and rerun
the affected step after the project material is corrected.

## Existing foundations and evidence status

The repository already provides technical POC material, field-integration workflows, trust-domain
contracts, and a manual archive helper. Existing lab experience motivates this milestone but does
not establish a reproducible clean installation or autonomous Advisor troubleshooting.

- [POC1/POC2](POC1-POC2.md) and [LAB](LAB.md) describe underlying technical flows and checks.
- [POC1 verification](verification/poc1-platform-verification.md) and
  [POC2 verification](verification/poc2-systemdb-forgejo-verification.md) provide scoped prior evidence.
- The manual archive helper operates on a local checkout; conversion, Forgejo publication,
  Systemdatabas registration, and Advisor retrieval must be connected and tested together.
- Advisor runtime compatibility, alarm-triggered reasoning, bootstrap/resume behavior, and the
  complete new-user journey remain acceptance work, not verified features in this specification.

M1 is the user-facing outcome spanning those technical POCs. It does not rename their phases or
replace their existing evidence. Use the GitHub milestone/issues for work status and this document
for the agreed scope and acceptance contract.

## Architecture references

- [Canonical glossary](../CONTEXT.md)
- [Architecture](ARCHITECTURE.md)
- [Advisor / Engineer / Security workflow](../skills/advisor-engineer-workflow/SKILL.md)
- [Engineer integration](../skills/engineer-integration/SKILL.md)
- [Security instance](../skills/security-instance/SKILL.md)
