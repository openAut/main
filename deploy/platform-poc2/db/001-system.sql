\connect openaut

CREATE TABLE IF NOT EXISTS system.equipment (
  equipment_id text PRIMARY KEY,
  site text NOT NULL REFERENCES system.sites(site),
  parent_equipment_id text REFERENCES system.equipment(equipment_id),
  name text NOT NULL,
  kind text NOT NULL,
  location text,
  manufacturer text,
  model text,
  metadata jsonb NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS system.points (
  point_id text PRIMARY KEY,
  equipment_id text NOT NULL REFERENCES system.equipment(equipment_id),
  node text REFERENCES system.devices(node),
  system_name text NOT NULL,
  metric text NOT NULL,
  display_name text NOT NULL,
  unit text,
  datatype text NOT NULL CHECK (datatype IN ('number', 'boolean', 'string')),
  writable boolean NOT NULL DEFAULT false,
  min_value double precision,
  max_value double precision,
  mqtt_topic text NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS system.documents (
  document_id text PRIMARY KEY,
  site text NOT NULL REFERENCES system.sites(site),
  equipment_id text REFERENCES system.equipment(equipment_id),
  kind text NOT NULL,
  title text NOT NULL,
  uri text NOT NULL,
  sha256 text CHECK (sha256 IS NULL OR sha256 ~ '^[0-9a-f]{64}$'),
  forge_commit text,
  trust_level text NOT NULL DEFAULT 'quarantine'
    CHECK (trust_level IN ('quarantine', 'untrusted', 'verified')),
  uploaded_by text,
  uploaded_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS system.cases (
  case_id text PRIMARY KEY,
  site text NOT NULL REFERENCES system.sites(site),
  equipment_id text REFERENCES system.equipment(equipment_id),
  created_by text NOT NULL DEFAULT session_user,
  assigned_to text,
  status text NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft', 'awaiting_approval', 'approved', 'in_progress', 'blocked', 'completed', 'rejected')),
  title text NOT NULL,
  summary text NOT NULL,
  recommended_action text,
  risk text,
  confidence double precision CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
  approved_forge_commit text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE system.cases ALTER COLUMN created_by SET DEFAULT session_user;

CREATE TABLE IF NOT EXISTS system.approvals (
  approval_id text PRIMARY KEY,
  case_id text NOT NULL REFERENCES system.cases(case_id),
  requested_by text NOT NULL,
  approved_by text,
  status text NOT NULL CHECK (status IN ('awaiting', 'approved', 'rejected', 'expired')),
  scope jsonb NOT NULL,
  reason text,
  created_at timestamptz NOT NULL DEFAULT now(),
  decided_at timestamptz
);

CREATE TABLE IF NOT EXISTS system.generated_artifacts (
  artifact_id text PRIMARY KEY,
  case_id text REFERENCES system.cases(case_id),
  equipment_id text REFERENCES system.equipment(equipment_id),
  kind text NOT NULL,
  title text NOT NULL,
  content_uri text NOT NULL,
  forge_commit text,
  generated_by text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS system.audit_events (
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

DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'advisor_app') THEN CREATE ROLE advisor_app NOLOGIN; END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'approver_app') THEN CREATE ROLE approver_app NOLOGIN; END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'engineer_app') THEN CREATE ROLE engineer_app NOLOGIN; END IF;
END $$;

DROP FUNCTION IF EXISTS system.approve_case(text, text, text, jsonb, text);
DROP FUNCTION IF EXISTS system.request_case_approval(text, text);
DROP FUNCTION IF EXISTS system.engineer_start_case(text, text);

CREATE OR REPLACE VIEW system.engineer_approved_cases
WITH (security_barrier = true) AS
SELECT c.*, a.approval_id, a.scope AS approval_scope
FROM system.cases c
JOIN LATERAL (
  SELECT approval_id, scope
  FROM system.approvals
  WHERE case_id = c.case_id
    AND status = 'approved'
    AND scope = '{"action": "forge-pr-only", "field_write": false}'::jsonb
  ORDER BY decided_at DESC NULLS LAST
  LIMIT 1
) a ON true
WHERE c.status IN ('approved', 'in_progress', 'blocked', 'completed')
;

CREATE OR REPLACE FUNCTION system.approve_case(
  p_case_id text,
  p_approval_id text,
  p_scope jsonb,
  p_reason text DEFAULT NULL
) RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, system
AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM system.cases
    WHERE case_id = p_case_id AND status = 'awaiting_approval' AND created_by <> session_user
  ) THEN
    RAISE EXCEPTION 'case % is not awaiting approval', p_case_id;
  END IF;
  IF p_scope <> '{"action": "forge-pr-only", "field_write": false}'::jsonb THEN
    RAISE EXCEPTION 'POC2 approval scope must be forge-pr-only with field_write=false';
  END IF;
  INSERT INTO system.approvals(approval_id, case_id, requested_by, approved_by, status, scope, reason, decided_at)
  SELECT p_approval_id, case_id, created_by, session_user, 'approved', p_scope, p_reason, now()
  FROM system.cases WHERE case_id = p_case_id;
  UPDATE system.cases SET status = 'approved', updated_at = now() WHERE case_id = p_case_id;
  INSERT INTO system.audit_events(actor, source, action, target_type, target_id, outcome)
  VALUES (session_user, 'system.approve_case', 'approve', 'case', p_case_id, 'approved');
END;
$$;

CREATE OR REPLACE FUNCTION system.request_case_approval(p_case_id text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, system
AS $$
BEGIN
  UPDATE system.cases SET status = 'awaiting_approval', updated_at = now()
  WHERE case_id = p_case_id AND status = 'draft' AND created_by = session_user;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'case % cannot be submitted by %', p_case_id, session_user;
  END IF;
  INSERT INTO system.audit_events(actor, source, action, target_type, target_id, outcome)
  VALUES (session_user, 'system.request_case_approval', 'request_approval', 'case', p_case_id, 'awaiting_approval');
END;
$$;

CREATE OR REPLACE FUNCTION system.engineer_start_case(p_case_id text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, system
AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM system.engineer_approved_cases
    WHERE case_id = p_case_id AND status = 'approved'
  ) THEN
    RAISE EXCEPTION 'case % is not approved for Engineer', p_case_id;
  END IF;
  UPDATE system.cases SET status = 'in_progress', assigned_to = session_user, updated_at = now()
  WHERE case_id = p_case_id;
  INSERT INTO system.audit_events(actor, source, action, target_type, target_id, outcome)
  VALUES (session_user, 'system.engineer_start_case', 'start', 'case', p_case_id, 'in_progress');
END;
$$;

REVOKE ALL ON ALL TABLES IN SCHEMA system FROM advisor_app, approver_app, engineer_app;
REVOKE ALL ON FUNCTION system.approve_case(text, text, jsonb, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION system.request_case_approval(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION system.engineer_start_case(text) FROM PUBLIC;

GRANT USAGE ON SCHEMA system TO advisor_app, approver_app, engineer_app;
GRANT SELECT ON system.sites, system.equipment, system.points, system.documents TO advisor_app;
GRANT INSERT (case_id, site, equipment_id, title, summary, recommended_action, risk, confidence)
  ON system.cases TO advisor_app;
GRANT EXECUTE ON FUNCTION system.request_case_approval(text) TO advisor_app;
GRANT SELECT ON system.cases TO approver_app;
GRANT EXECUTE ON FUNCTION system.approve_case(text, text, jsonb, text) TO approver_app;
GRANT SELECT ON system.engineer_approved_cases TO engineer_app;
GRANT EXECUTE ON FUNCTION system.engineer_start_case(text) TO engineer_app;

REVOKE UPDATE, DELETE ON system.audit_events FROM advisor_app, approver_app, engineer_app;
