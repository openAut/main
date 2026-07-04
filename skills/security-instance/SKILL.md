---
name: security-instance
description: Define and provision the separate openAut Security instance — read-only SSH, listen-only Teams observation, passive MQTT/log monitoring, local Forge watch-only monitoring, prompt/social-engineering detection, OT/MQTT identity-and-policy anomaly detection (orchestrating `fdd`/`anomaly-correlation` findings rather than re-detecting process faults itself), isolated security alerts, and compliance reporting. Use when aligning openAut/main with the public security architecture or watching Forge changes, CI, secrets, and deploy artifacts.
permissions:
  knowledge_only: true
  exec: none
  network: none
  delegated_capabilities: "design/provisioning policy; read-only SSH and passive MQTT/log/Forge monitoring are performed by the operator-provisioned Security instance, not by this skill"
---

# security-instance — separate read-only IT/OT security agent

openAut Security is a separate instance that watches Advisor/Engineer and the OT environment without
being able to act on them.

Its core rule:

> It can see. It cannot steer.

This skill complements [`advisor-engineer-workflow`](../advisor-engineer-workflow/SKILL.md) and the
compliance skills (`ai-act`, `nis2`, `cra`, `iso27001`, `iec62443`). It is the runbook contract for
the public security architecture: separate hardware, separate VLAN, read-only SSH, listen-only Teams,
and isolated alerting.

## Trust boundaries

| Boundary | Requirement |
|---|---|
| Hardware | Security runs on separate physical hardware or a separately controlled host. |
| Network | Security lives in its own VLAN/security zone with explicit ACLs. |
| SSH | Security uses `openaut-sec-ro` or equivalent read-only users; no sudo, no shell expansion paths. |
| Teams | Security is listen-only in operational channels and posts only to `#openaut-security-alerts`. |
| MQTT/logs | passive subscribe/read only; no retained-message writes or control topics. |
| Forge | read-only/watch-only org access; no merge, branch protection, token, or artifact write permission. |
| LLM | generative model explains already-classified findings; it is not the sole gatekeeper. |

## Security as orchestrator, not a fourth detector

`fdd` and `anomaly-correlation` already own rule-based fault/anomaly detection over OT telemetry.
Security does not re-implement that logic as its own "baseline/anomaly rules for OT and MQTT
behavior" — a second, independent OT-detector would be exactly the circularity the architecture
review flagged risk of (nothing verifies Security's own detection logic if Security is also *a*
detector). Security **consumes** `fdd`/`anomaly-correlation` findings and classifies their *security*
relevance by correlating them with audit, identity, permission-profile, Systemdatabas-case,
network-policy, and credential-proxy events — it does not decide whether a process is faulty, only
whether a finding (or its absence) indicates a policy, identity, or access problem.

A residual category stays Security's own: anomalies that are about **who is acting**, not **what
broke** — an unauthorized write, a client polling/writing outside its case scope, a spoofed identity.
Split from #13 (checklist item 4) and resolved here as issue #39; both review bots converged on this
same consume-vs-own split.

## What Security watches

**Consumes detector findings** — read-only, from `fdd`/`anomaly-correlation`'s own output, treated as
untrusted input like any other field data (check source, schema, timestamp, provenance):

- `fdd` findings (rule-based fault diagnoses)
- `anomaly-correlation` findings (alarm correlation, silent-drift detection)
- detector provenance/version/timestamp; missing or stale detector output

**Own security controls** — policy, identity, and audit invariants that are Security's alone to watch:

- prompt injection and social-engineering attempts in Teams/document content
- Advisor responses that leak topology, secrets, or unsafe action instructions
- Engineer actions without approved cases, or outside an active case/permission-profile scope
- Forge pushes, branch protection changes, failed CI on deployable artifacts, suspicious binaries, or secrets
- SSH anomalies: unusual user, time, source, command, or failed attempts
- MQTT/OT identity and policy anomalies: unknown or unexpected client IDs, topic/ACL violations,
  retained messages on sensitive topics, credential-proxy misuse, or a write/poll rate that breaks a
  signed permission profile — malformed protocol patterns or an unfamiliar device are a *security*
  signal when they indicate an unauthorized or spoofed actor; a *process* anomaly on otherwise
  legitimate traffic is `fdd`/`anomaly-correlation`'s finding to make, consumed above instead
- attempts to reach denied networks/endpoints (Advisor, Security, PAP, internet — per ADR 0003)
- PAP/permission-profile modification attempts by operational actors
- compliance timers: NIS2 24h/72h, CRA vulnerability reporting, AI Act logging/transparency checks

## Detection pipeline

1. **Collect**
   - read-only SSH logs from Advisor/Engineer hosts
   - Teams channel content through a listen-only path
   - Forge webhooks/API events, PR metadata, CI status, and protected-branch changes
   - MQTT broker metadata and selected passive telemetry
   - Systemdatabas metadata and audit events

2. **Classify**
   - use deterministic checks for obvious policy violations
   - use non-generating classifiers/guards for prompt/social-engineering content where available
   - consume classified findings from `fdd` and `anomaly-correlation`; classify their *security*
     relevance by correlating them with audit, identity, permission-profile, Systemdatabas-case,
     network-policy, and credential-proxy events — do not re-derive OT/process anomalies here

3. **Explain**
   - use NemoClaw/LLM only to summarize evidence and map it to risks/compliance obligations
   - never let generated text decide whether a blocked action should be allowed

4. **Alert**
   - post structured alert to isolated security channel
   - write append-only audit/security event
   - do not alert through Advisor or Engineer channels when doing so would tip off an attacker

## Minimal alert format

```text
Security alert: [title]
Severity: low | medium | high | critical
Source: Teams | SSH | MQTT | OT | Systemdatabas | Compliance
Affected instance: Advisor | Engineer | Security | Edge | Broker | Database
Evidence:
  - [fact 1]
  - [fact 2]
Likely risk:
Recommended security action:
Compliance clock:
  - NIS2 24h: yes/no
  - NIS2 72h: yes/no
  - CRA/AI Act review: yes/no
```

## Deployment checklist

- Create separate host or isolated VM boundary.
- Place host in security VLAN.
- Create read-only SSH users on Advisor/Engineer hosts.
- Configure ACLs so Security cannot route into OT/management except approved read-only endpoints.
- Register listen-only Teams observation and isolated security alert webhook.
- Configure read-only MQTT/API credentials.
- Configure read-only Forge credentials and webhooks for PR, push, branch-protection, release, and CI events.
- Verify Security cannot:
  - open an interactive shell with write privileges
  - call Engineer deploy endpoints
  - write to operational Teams channels
  - publish to control topics
  - merge PRs, push branches, issue Forge tokens, or alter branch protection

## Verification

Use lab events:

- simulated prompt injection in Advisor channel
- manual upload in the wrong channel
- Engineer SSH attempt without approved case
- direct push attempt to a protected Forge branch
- manual moved from quarantine to verified without review evidence
- unknown MQTT client ID
- malformed Modbus/BACnet traffic sample
- NIS2 reporting clock exercise

For each, Security should produce an isolated alert with evidence and no operational side effects.

> **Live behaviour is unverified.** This is a security architecture contract and runbook for future
> implementation, not a substitute for a qualified security assessment.
