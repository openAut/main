---
name: security-instance
description: Define and provision the separate openAut Security instance — read-only SSH, listen-only Teams observation, passive MQTT/log monitoring, prompt/social-engineering detection, OT anomaly detection, isolated security alerts, and compliance reporting. Use when aligning openAut/main with the public security architecture.
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
| LLM | generative model explains already-classified findings; it is not the sole gatekeeper. |

## What Security watches

- prompt injection and social-engineering attempts in Teams/document content
- Advisor responses that leak topology, secrets, or unsafe action instructions
- Engineer actions without approved cases
- SSH anomalies: unusual user, time, source, command, or failed attempts
- MQTT anomalies: unknown client IDs, topic violations, retained messages on sensitive topics
- OT protocol anomalies: malformed Modbus/BACnet patterns, rogue devices, abnormal polling/write rates
- compliance timers: NIS2 24h/72h, CRA vulnerability reporting, AI Act logging/transparency checks

## Detection pipeline

1. **Collect**
   - read-only SSH logs from Advisor/Engineer hosts
   - Teams channel content through a listen-only path
   - MQTT broker metadata and selected passive telemetry
   - Systemdatabas metadata and audit events

2. **Classify**
   - use deterministic checks for obvious policy violations
   - use non-generating classifiers/guards for prompt/social-engineering content where available
   - use baseline/anomaly rules for OT and MQTT behavior

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
- Verify Security cannot:
  - open an interactive shell with write privileges
  - call Engineer deploy endpoints
  - write to operational Teams channels
  - publish to control topics

## Verification

Use lab events:

- simulated prompt injection in Advisor channel
- manual upload in the wrong channel
- Engineer SSH attempt without approved case
- unknown MQTT client ID
- malformed Modbus/BACnet traffic sample
- NIS2 reporting clock exercise

For each, Security should produce an isolated alert with evidence and no operational side effects.

> **Live behaviour is unverified.** This is a security architecture contract and runbook for future
> implementation, not a substitute for a qualified security assessment.
