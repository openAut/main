---
name: iec62443
description: IEC 62443 industrial automation & control system (IACS/OT) security — the series structure (parts 2-1/3-2/3-3/4-1/4-2), zones and conduits, security levels SL 0–4, the seven foundational requirements, and the secure development lifecycle. Use for OT/ICS security questions in building automation, segmenting a control network, choosing target security levels, or showing how openAut's edge/broker design meets 62443.
permissions:
  knowledge_only: true
  tools: none
  network: none
  exec: none
---

# iec62443 — IACS / OT security

Knowledge support for **IEC 62443**, the security series for **Industrial Automation & Control
Systems (IACS)** — the OT counterpart to ISO 27001's IT focus. openAut's field/edge tier is exactly
an IACS, so 62443 governs how its networks, components and processes are secured. This skill answers
structure, zones/conduits, security-level and requirement questions and maps them onto openAut.

## Series structure

Four groups; the ones you cite most in building automation:

| Part | Audience | Content |
|---|---|---|
| **62443-2-1** | asset owner | IACS security **management programme** (policies, processes) |
| **62443-2-4** | service providers | requirements for integrators/maintainers |
| **62443-3-2** | system integrator | **risk assessment**, partitioning into **zones & conduits**, assign target SLs |
| **62443-3-3** | system integrator | **system security requirements** (SRs) per SL |
| **62443-4-1** | product supplier | **secure product development lifecycle** (SDL) |
| **62443-4-2** | product supplier | **component requirements** (CRs) per SL |

Roles matter: **asset owner**, **system integrator**, **product supplier** carry different parts.

## Zones and conduits (the core idea)

Segment the system into **zones** (groups of assets with shared security needs) connected only by
defined **conduits** (controlled communication paths). Each zone/conduit gets a **target security
level**. This is defence-in-depth: a compromise in one zone is contained.

For openAut: the field bus + edge node is one zone; the AI tier (broker/DB/agent) another; the
conduit between them is the **mutual-TLS MQTT** link — single, authenticated, encrypted. The agent's
deny-by-default egress is a conduit restriction (FR5, restricted data flow).

## Security levels (SL 0–4)

SLs express resistance to escalating threat:

| SL | Threat resisted |
|---|---|
| **SL 0** | no specific requirement |
| **SL 1** | casual/coincidental violation |
| **SL 2** | intentional, **simple** means, low resources/skill |
| **SL 3** | intentional, **sophisticated** means, moderate resources, IACS-specific skill |
| **SL 4** | intentional, sophisticated means, **extended** resources |

Three flavours: **SL-T** (target, from risk assessment), **SL-C** (capability of a component/system),
**SL-A** (achieved as deployed). The job: ensure **SL-A ≥ SL-T** for each zone/conduit.

## The seven foundational requirements (FR)

All SRs/CRs roll up to seven FRs:

| FR | Name | Intent |
|---|---|---|
| **FR1** | Identification & authentication control (IAC) | know who/what is acting |
| **FR2** | Use control (UC) | enforce privileges/authorisation |
| **FR3** | System integrity (SI) | prevent unauthorised change |
| **FR4** | Data confidentiality (DC) | protect data at rest/in transit |
| **FR5** | Restricted data flow (RDF) | zones/conduits, segmentation |
| **FR6** | Timely response to events (TRE) | detect, log, respond |
| **FR7** | Resource availability (RA) | resist DoS, ensure availability |

## How openAut maps to the FRs (illustrative)

| openAut control | FR |
|---|---|
| Per-node client certificate, cert-CN identity | FR1 (IAC) |
| CN-bound MQTT ACL, least-privilege DB roles, owner-confirmed writes | FR2 (UC) |
| Sandbox (Landlock/seccomp), signed/pinned install | FR3 (SI) |
| Mutual-TLS MQTT, TLS inference link, on-prem data | FR4 (DC) |
| Zones (field/edge vs AI tier), deny-by-default egress, single conduit | FR5 (RDF) |
| Audit logs, lifecycle/recover, incident routing to Teams | FR6 (TRE) |
| Edge store-and-forward buffering, Restart=always, LWT status | FR7 (RA) |

## Secure development (4-1)

If you build components/agents, **62443-4-1** defines the SDL: security requirements, secure design,
secure implementation, verification/testing, defect/patch management, and a defined security update
process — the lifecycle expectation behind the CRA as well. See [`cra`](../cra/SKILL.md).

## Use this skill to

- Partition a building-automation network into zones/conduits and assign SL-Ts.
- Check a product's SL-C against your SL-T (procurement).
- Explain an FR/SR/CR or the role split (owner/integrator/supplier).
- Show how an openAut deployment evidences a foundational requirement.

> Complementary to [`iso27001`](../iso27001/SKILL.md) (IT management system) and
> [`nis2`](../nis2/SKILL.md) (legal obligation). Guidance, not a certification or a substitute for a
> 62443 assessment.
