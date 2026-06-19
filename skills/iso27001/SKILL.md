---
name: iso27001
description: ISO/IEC 27001:2022 information security management — ISMS scope and clauses 4–10, the Annex A 93 controls (four themes), risk assessment and treatment, Statement of Applicability, and the certification/audit cycle. Use for questions about building or auditing an ISMS, mapping controls, preparing for certification, or how openAut's design satisfies 27001 expectations.
---

# iso27001 — ISO/IEC 27001:2022 (ISMS)

Knowledge support for **ISO/IEC 27001:2022**, the standard for an **Information Security Management
System (ISMS)** — a risk-based management framework, not a checklist. openAut lists ISO 27001 among
its built-in security expectations; this skill answers scope, controls, risk, and certification
questions and maps them onto the openAut design.

## The ISMS — management clauses 4–10

Certification is against clauses **4–10** (Annex A is the control catalogue, applied via risk):

| Clause | Theme | Core requirement |
|---|---|---|
| 4 | Context | scope of the ISMS, interested parties, boundaries |
| 5 | Leadership | top-management commitment, policy, roles |
| 6 | Planning | **risk assessment & treatment**, security objectives, SoA |
| 7 | Support | resources, competence, awareness, documented information |
| 8 | Operation | run the risk treatment; operational controls |
| 9 | Performance evaluation | monitoring, **internal audit**, management review |
| 10 | Improvement | nonconformity, corrective action, continual improvement |

The engine is **Plan-Do-Check-Act**: assess risk → treat it with controls → measure → improve.

## Annex A 2022 — 93 controls, four themes

The 2022 revision restructured controls from 114 (14 domains) to **93 controls in 4 themes**:

| Theme | Count | Examples |
|---|---|---|
| **A.5 Organizational** | 37 | policies, supplier security, threat intel, incident management |
| **A.6 People** | 8 | screening, awareness, responsibilities, remote working |
| **A.7 Physical** | 14 | secure areas, equipment, cabling, media |
| **A.8 Technological** | 34 | access control, crypto, logging, secure development, network security |

2022 added **11 new controls**, incl. threat intelligence, ICT readiness for business continuity,
information security for cloud use, data leakage prevention, monitoring, secure coding, and web
filtering. Controls also carry attributes (control type, security property, operational capability).

## Risk assessment, treatment, and the SoA

- **Risk assessment** (clause 6.1.2): identify risks to confidentiality/integrity/availability,
  assign owners, analyse likelihood × impact.
- **Risk treatment** (6.1.3): choose to modify (apply controls), retain, avoid, or share each risk;
  select controls (Annex A is the reference set, but you may add others).
- **Statement of Applicability (SoA):** the central document — every Annex A control listed with
  *applicable or not*, justification, and implementation status. Auditors live in the SoA.

## Certification cycle

- **Stage 1 audit** — documentation/readiness review.
- **Stage 2 audit** — implementation effectiveness; leads to certification.
- **Surveillance audits** — annually; **recertification** every **3 years**.
- Nonconformities (major/minor) must be addressed with corrective action.

## How openAut maps to 27001 (illustrative)

| openAut control | Annex A area |
|---|---|
| Deny-by-default sandbox egress, network namespaces | A.8 network security, access control |
| Mutual-TLS MQTT, TLS inference link | A.8 cryptography, secure transfer |
| Least-privilege DB roles, per-node cert identity | A.8 access control / identity |
| On-prem / air-gap-capable, data never leaves site | A.5 / A.8 data handling, supplier independence |
| Audit logs, lifecycle/recover, incident handling | A.5 incident management, A.8 logging |
| Key custody (`pki/` 600, gitignored) | A.8 key management |

This is **complementary** to NIS2 (legal obligation) and IEC 62443 (OT-specific): 27001 is the
management system that organises the rest. See [`nis2`](../nis2/SKILL.md) and
[`iec62443`](../iec62443/SKILL.md).

## Use this skill to

- Explain a clause/control or the 2014→2022 mapping.
- Draft SoA entries and risk-treatment rationale.
- Prepare for / interpret an audit finding.
- Show how an openAut deployment evidences a given control.

> Guidance, not a certification. A real ISMS needs organisation-specific scope, risk work, and an
> accredited auditor.
