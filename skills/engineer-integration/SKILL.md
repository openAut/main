---
name: engineer-integration
description: Guide openAut Engineer through manual-driven equipment integration — ingest a manufacturer manual, extract protocol/register information, validate against a controlled service-PC context, deploy to an edge node over SSH after approval, verify MQTT/TimescaleDB data flow, and write generated documentation back to the Systemdatabas.
---

# engineer-integration — manual to edge integration

This skill describes the workflow behind the public openAut promise:

> "AI:n har läst manualen."

Engineer helps a technician integrate equipment without making Teams a deployment surface. The
technician uses a controlled service-PC / management plane, uploads a manual there, confirms each
step, and Engineer performs SSH/deploy actions only after approval.

Use with [`advisor-engineer-workflow`](../advisor-engineer-workflow/SKILL.md),
[`system-database`](../system-database/SKILL.md), and the relevant protocol skill (`modbus`,
`bacnet`, `mbus`, `knx`, `dali`, or `lorawan`).

## Inputs

- approved `system.cases` row
- equipment/site metadata
- uploaded manual or register list in `system.documents`
- target edge node and management-network SSH identity
- operator confirmation from service-PC control plane
- safety envelope for writable points

## Workflow

1. **Confirm authority**
   - Read the case and approval.
   - Verify `status = approved`.
   - Verify the request came from the controlled management plane, not Teams.

2. **Read and classify the manual**
   - Identify protocol, electrical interface, addressing, baud rate, parity, object/register layout,
     units, scaling, writable values, and safety-relevant constraints.
   - Mark extracted fields as proposed until verified.

3. **Generate an integration plan**
   - front-panel or DIP switch settings
   - wiring and bus topology checks
   - protocol scan commands
   - point map / register map
   - MQTT topic plan
   - safety envelope for any writable points

4. **Operator-confirm physical steps**
   - The technician performs wiring, addressing, and physical checks.
   - Engineer waits for confirmation before continuing.

5. **Deploy to the edge node**
   - SSH to the edge node.
   - Install dependencies.
   - Copy point map and poller/control script.
   - Install or reload systemd service.
   - Never overwrite an existing service without a rollback plan.

6. **Verify data flow**
   - Subscribe to expected MQTT topics.
   - Check TimescaleDB ingestion.
   - Validate plausibility against physical limits and sibling points.
   - Refuse to mark complete if values are implausible.

7. **Write documentation**
   - I/O list
   - protocol/register map
   - MQTT topic schema
   - FAT/SAT notes
   - edge service and rollback notes
   - generated artifacts linked to the case and equipment

## Output format

Engineer should write a structured execution summary:

```text
Integration: [equipment]
Case: [case_id]
Edge node: [node]
Protocol: [protocol]
Verified points: [count]
Writable points: [count, all safety-limited]
MQTT prefix: openaut/[site]/[node]/[system]/
Evidence:
  - scan result
  - sample MQTT payload
  - latest TimescaleDB row
Generated docs:
  - I/O list
  - register map
  - FAT/SAT checklist
Rollback:
  - service disable command
  - previous config path
```

## Refusal conditions

Stop and mark the case `blocked` if any of these are true:

- no approved case
- manual is missing, untrusted, or ambiguous
- protocol settings cannot be verified
- writable point lacks min/max/safe value
- edge node identity does not match Systemdatabasen
- MQTT/TLS identity or ACL does not match node prefix
- physical behavior differs from expected limits

## Suggested generated artifacts

| Artifact | Purpose |
|---|---|
| `io-list.md` | point names, terminals/registers, units, datatypes, writable flag |
| `mqtt-topics.md` | topic names and payload examples |
| `register-map.json` | machine-readable point map for edge poller/control |
| `fat-sat.md` | commissioning and verification checklist |
| `rollback.md` | commands and files needed to revert deployment |

> **Live behaviour is unverified.** This skill defines the Engineer integration contract. Specific
> drivers and hardware procedures belong in protocol- or POC-specific skills.
