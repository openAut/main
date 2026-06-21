---
name: system-database
description: Define the openAut Systemdatabas contract — relational PostgreSQL tables for sites, equipment, points, documents, cases, approvals, generated documentation, and audit events alongside TimescaleDB telemetry. Use when aligning openAut/main with the public architecture, designing database migrations, or giving agents a shared case and metadata model.
---

# system-database — metadata, cases, approvals, and audit

The public openAut vision depends on a shared **Systemdatabas**: not just telemetry, but the
operational model that Advisor, Engineer, Security, dashboards, and Power BI read from.

TimescaleDB stores time-series readings. The Systemdatabas stores the things that give those
readings meaning:

- sites, systems, equipment, and points
- protocol/register/BACnet object mappings
- documents and manuals
- cases, approval requests, and execution status
- generated I/O lists, MQTT topic schemas, FAT/SAT notes, and diagrams
- audit events and security-relevant history

This skill defines the contract that future migrations should implement. It complements
[`timeseries-stack`](../timeseries-stack/SKILL.md), whose current `system.sites` and
`system.devices` tables are only the minimum seed.

## Core entities

| Entity | Purpose |
|---|---|
| `system.sites` | Site/building identity and ownership context. |
| `system.equipment` | AHUs, pumps, heat exchangers, chillers, shunt groups, meters, etc. |
| `system.points` | Named physical/logical points with unit, datatype, writable flag, safety limits. |
| `system.protocol_mappings` | Modbus registers, BACnet objects, KNX group addresses, DALI addresses, etc. |
| `system.documents` | Manuals, DU documents, wiring diagrams, uploaded evidence, generated docs. |
| `system.cases` | Advisor/Engineer handoff: proposed action, approval status, execution status. |
| `system.approvals` | Human approvals for deploy/write/regulation actions. |
| `system.generated_artifacts` | I/O lists, MQTT topic schemas, FAT/SAT notes, register maps, network diagrams. |
| `system.audit_events` | Append-only operational and security audit trail. |

## Minimum schema shape

Use proper migrations in a product repo. This is the reference shape agents should preserve when
generating database code:

```sql
CREATE SCHEMA IF NOT EXISTS system;

CREATE TABLE system.equipment (
  equipment_id text PRIMARY KEY,
  site text NOT NULL REFERENCES system.sites(site),
  parent_equipment_id text REFERENCES system.equipment(equipment_id),
  name text NOT NULL,
  kind text NOT NULL,
  location text,
  manufacturer text,
  model text,
  installed_at date,
  metadata jsonb NOT NULL DEFAULT '{}'
);

CREATE TABLE system.points (
  point_id text PRIMARY KEY,
  equipment_id text NOT NULL REFERENCES system.equipment(equipment_id),
  node text REFERENCES system.devices(node),
  system_name text NOT NULL,
  metric text NOT NULL,
  display_name text NOT NULL,
  unit text,
  datatype text NOT NULL CHECK (datatype IN ('number','boolean','string')),
  writable boolean NOT NULL DEFAULT false,
  min_value double precision,
  max_value double precision,
  safe_value text,
  mqtt_topic text NOT NULL UNIQUE
);

CREATE TABLE system.protocol_mappings (
  mapping_id text PRIMARY KEY,
  point_id text NOT NULL REFERENCES system.points(point_id),
  protocol text NOT NULL,
  address jsonb NOT NULL,
  scaling jsonb NOT NULL DEFAULT '{}',
  source_document_id text,
  verified boolean NOT NULL DEFAULT false
);

CREATE TABLE system.documents (
  document_id text PRIMARY KEY,
  site text NOT NULL REFERENCES system.sites(site),
  equipment_id text REFERENCES system.equipment(equipment_id),
  kind text NOT NULL,
  title text NOT NULL,
  uri text NOT NULL,
  sha256 text,
  trust_level text NOT NULL DEFAULT 'untrusted',
  uploaded_by text,
  uploaded_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE system.cases (
  case_id text PRIMARY KEY,
  site text NOT NULL REFERENCES system.sites(site),
  equipment_id text REFERENCES system.equipment(equipment_id),
  created_by text NOT NULL,
  assigned_to text,
  status text NOT NULL,
  title text NOT NULL,
  summary text NOT NULL,
  recommended_action text,
  risk text,
  confidence double precision,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE system.approvals (
  approval_id text PRIMARY KEY,
  case_id text NOT NULL REFERENCES system.cases(case_id),
  requested_by text NOT NULL,
  approved_by text,
  status text NOT NULL,
  scope jsonb NOT NULL,
  reason text,
  created_at timestamptz NOT NULL DEFAULT now(),
  decided_at timestamptz
);

CREATE TABLE system.generated_artifacts (
  artifact_id text PRIMARY KEY,
  case_id text REFERENCES system.cases(case_id),
  equipment_id text REFERENCES system.equipment(equipment_id),
  kind text NOT NULL,
  title text NOT NULL,
  content_uri text NOT NULL,
  generated_by text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE system.audit_events (
  audit_id bigserial PRIMARY KEY,
  ts timestamptz NOT NULL DEFAULT now(),
  actor text NOT NULL,
  source text NOT NULL,
  action text NOT NULL,
  target_type text,
  target_id text,
  outcome text NOT NULL,
  details jsonb NOT NULL DEFAULT '{}'
);
```

## Semantic model guidance

The database should be compatible with a lightweight Haystack/Brick-style view, even if openAut
does not adopt either wholesale at the start:

- stable equipment IDs
- explicit parent/child relationships
- point tags/metadata for analytics
- machine-readable units and datatypes
- protocol mappings separated from point meaning

This lets FDD and energy analysis reason about "supply temperature" or "heating valve" without
knowing whether the value came from Modbus, BACnet, M-Bus, KNX, or another source.

## Agent access

| Actor | Access |
|---|---|
| Ingest | write telemetry only; no case/document writes. |
| Advisor | read system metadata; create/update cases; cannot approve its own actions. |
| Engineer | read approved cases and docs; write execution status, mappings, generated artifacts. |
| Security | read-only metadata/logs plus append security alerts to its own audit/log sink. |
| Power BI / dashboards | read-only reporting views. |

## Verification

- A read-only agent role cannot write `system.points`, `system.protocol_mappings`, or field action state.
- Advisor can create a case but cannot mark it approved.
- Engineer refuses to execute a case without an `approved` approval row.
- Audit events are append-only from normal application roles.

> **Live behaviour is unverified.** Treat this as the canonical schema contract for agents until a
> migration-managed product repository owns the implementation.
