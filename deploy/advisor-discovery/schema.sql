-- Fresh, owner-run installation after platform-poc1 storage and platform-poc2/db/001-system.sql.
-- Existing installations require an explicit migration; name collisions deliberately fail.
BEGIN;
SET LOCAL lock_timeout='5s';
CREATE ROLE advisor_reader NOLOGIN;
CREATE SCHEMA advisor_policy;
CREATE SCHEMA advisor_read;
REVOKE ALL ON SCHEMA advisor_policy,advisor_read FROM PUBLIC;
ALTER TABLE system.approvals ADD COLUMN IF NOT EXISTS expires_at timestamptz;
CREATE TABLE advisor_policy.allowed_sites (
 site text PRIMARY KEY REFERENCES system.sites(site),
 approved_by text NOT NULL, approval_reference text NOT NULL,
 approved_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE advisor_policy.forge_repositories (
 site text REFERENCES advisor_policy.allowed_sites(site) ON DELETE CASCADE,
 repository text CHECK (repository ~ '^[a-z0-9][a-z0-9._-]{0,99}$'),
 approval_reference text NOT NULL, PRIMARY KEY(site,repository)
);
REVOKE ALL ON ALL TABLES IN SCHEMA advisor_policy FROM PUBLIC,advisor_reader,advisor_app,engineer_app;
REVOKE ALL ON SCHEMA advisor_policy FROM advisor_reader,advisor_app,engineer_app;
CREATE TABLE system.advisor_integrations (
 equipment_id text PRIMARY KEY REFERENCES system.equipment(equipment_id),
 site text NOT NULL REFERENCES system.sites(site), node text NOT NULL, telemetry_system text NOT NULL,
 alarm_metrics jsonb NOT NULL, alarm_watch boolean NOT NULL,
 case_id text NOT NULL REFERENCES system.cases(case_id),
 artifact_sha256 text NOT NULL CHECK(artifact_sha256 ~ '^[a-f0-9]{64}$'),
 registered_by text NOT NULL, registered_at timestamptz NOT NULL DEFAULT now()
);
REVOKE ALL ON system.advisor_integrations FROM PUBLIC,advisor_reader,advisor_app,engineer_app;

CREATE FUNCTION system.register_advisor_integration(p_case text,p_contract jsonb)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE e system.equipment%ROWTYPE; c system.cases%ROWTYPE; item record;
BEGIN
 IF jsonb_typeof(p_contract) IS DISTINCT FROM 'object'
 OR NOT p_contract ?& ARRAY['equipment_id','node','telemetry_system','alarm_metrics','alarm_watch','artifact_sha256']
 OR p_contract - ARRAY['equipment_id','node','telemetry_system','alarm_metrics','alarm_watch','artifact_sha256'] <> '{}'::jsonb
 OR coalesce(p_contract->>'equipment_id','') !~ '^[a-z0-9][a-z0-9._-]{0,62}$'
 OR coalesce(p_contract->>'node','') !~ '^[a-z0-9][a-z0-9._-]{0,62}$'
 OR coalesce(p_contract->>'telemetry_system','') !~ '^[a-z0-9][a-z0-9._-]{0,62}$'
 OR coalesce(p_contract->>'artifact_sha256','') !~ '^[a-f0-9]{64}$'
 OR jsonb_typeof(p_contract->'alarm_watch') IS DISTINCT FROM 'boolean'
 OR jsonb_typeof(p_contract->'alarm_metrics') IS DISTINCT FROM 'object'
 THEN RAISE EXCEPTION 'invalid integration contract'; END IF;
 IF (SELECT count(*) FROM jsonb_each(p_contract->'alarm_metrics'))>64
 OR ((p_contract->>'alarm_watch')::boolean AND p_contract->'alarm_metrics'='{}'::jsonb)
 THEN RAISE EXCEPTION 'invalid alarm metric count'; END IF;
 FOR item IN SELECT * FROM jsonb_each_text(p_contract->'alarm_metrics') LOOP
  IF item.key !~ '^[a-z][a-z0-9_]{0,79}$' OR item.value IS NULL OR item.value NOT IN ('boolean','integer','uint16')
  THEN RAISE EXCEPTION 'unsupported alarm profile'; END IF;
 END LOOP;
 SELECT * INTO e FROM system.equipment WHERE equipment_id=p_contract->>'equipment_id' FOR SHARE;
 SELECT * INTO c FROM system.cases WHERE case_id=p_case FOR UPDATE;
 IF e.equipment_id IS NULL OR c.case_id IS NULL OR c.status NOT IN ('approved','in_progress')
 OR c.assigned_to IS DISTINCT FROM session_user::text
 OR c.equipment_id IS DISTINCT FROM e.equipment_id OR c.site IS DISTINCT FROM e.site
 OR e.metadata->>'node' IS DISTINCT FROM p_contract->>'node'
 OR e.metadata->>'telemetry_system' IS DISTINCT FROM p_contract->>'telemetry_system'
 OR NOT EXISTS (SELECT FROM system.approvals a WHERE a.case_id=p_case AND a.status='approved'
  AND a.approved_by IS NOT NULL AND a.approved_by<>session_user::text
  AND (a.expires_at IS NULL OR a.expires_at>now())
  AND a.scope=jsonb_build_object('action','advisor-integration','field_write',false,'integration',p_contract))
 THEN RAISE EXCEPTION 'case, actor, binding or approved contract mismatch'; END IF;
 PERFORM 1 FROM advisor_policy.allowed_sites WHERE site=e.site FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'site outside owner-authorized area'; END IF;
 INSERT INTO system.advisor_integrations VALUES (e.equipment_id,e.site,p_contract->>'node',
  p_contract->>'telemetry_system',p_contract->'alarm_metrics',(p_contract->>'alarm_watch')::boolean,
  p_case,p_contract->>'artifact_sha256',session_user,now())
 ON CONFLICT(equipment_id) DO UPDATE SET site=excluded.site,node=excluded.node,
  telemetry_system=excluded.telemetry_system,alarm_metrics=excluded.alarm_metrics,
  alarm_watch=excluded.alarm_watch,case_id=excluded.case_id,artifact_sha256=excluded.artifact_sha256,
  registered_by=excluded.registered_by,registered_at=excluded.registered_at;
 INSERT INTO system.audit_events(actor,source,action,target_type,target_id,outcome,details)
 VALUES(session_user,'system.register_advisor_integration','register-advisor-delivery','equipment',
  e.equipment_id,'registered',jsonb_build_object('case_id',p_case,'contract',p_contract));
END $$;
REVOKE ALL ON FUNCTION system.register_advisor_integration(text,jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION system.register_advisor_integration(text,jsonb) TO engineer_app;

CREATE VIEW advisor_read.equipment WITH(security_barrier=true) AS
SELECT e.equipment_id,e.site,e.name,e.manufacturer,e.model,
 e.metadata->>'node' AS node,e.metadata->>'telemetry_system' AS telemetry_system,
 e.metadata->>'protocol' AS protocol,to_jsonb(e)->>'product_id' AS product_id,
 coalesce(i.alarm_watch,false) AS alarm_watch,coalesce(i.alarm_metrics,'{}'::jsonb) AS alarm_metrics,
 i.artifact_sha256 AS integration_revision
FROM system.equipment e JOIN advisor_policy.allowed_sites s ON s.site=e.site
LEFT JOIN system.advisor_integrations i ON i.equipment_id=e.equipment_id AND i.site=e.site
 AND i.node=e.metadata->>'node' AND i.telemetry_system=e.metadata->>'telemetry_system'
WHERE e.equipment_id ~ '^[a-z0-9][a-z0-9._-]{0,62}$';
CREATE VIEW advisor_read.points WITH(security_barrier=true) AS
SELECT p.point_id,p.equipment_id,p.system_name,p.metric,p.display_name,p.unit,p.datatype,p.writable
FROM system.points p JOIN advisor_read.equipment e USING(equipment_id);
CREATE VIEW advisor_read.readings WITH(security_barrier=true) AS
SELECT r.ts,r.metric,r.value,r.bool_val,r.unit,e.equipment_id
FROM telemetry.readings r JOIN advisor_read.equipment e ON r.site=e.site AND r.node=e.node AND r.system=e.telemetry_system;
-- Optional product_id columns are projected through to_jsonb for compatibility with
-- the base POC schema. Global product manuals are authorized through an in-area installation.
CREATE VIEW advisor_read.documents WITH(security_barrier=true) AS
SELECT d.document_id,e.equipment_id,d.kind,d.title,d.uri,d.sha256,d.forge_commit,d.trust_level,
 r.repository AS authorized_repository
FROM system.documents d JOIN advisor_read.equipment e ON
 (d.equipment_id=e.equipment_id AND d.site=e.site)
 OR (d.equipment_id IS NULL AND to_jsonb(d)->>'product_id'=e.product_id AND (d.site IS NULL OR d.site=e.site))
JOIN advisor_policy.forge_repositories r ON r.site=e.site
 AND d.uri LIKE 'forge://openaut/%' AND split_part(d.uri,'/',4)=r.repository
WHERE d.trust_level='verified';
GRANT USAGE ON SCHEMA advisor_read TO advisor_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA advisor_read TO advisor_reader;
COMMIT;
