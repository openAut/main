-- Entirely synthetic data; run only in the disposable test container.
INSERT INTO system.sites(site) VALUES('site-a'),('site-b');
INSERT INTO system.equipment(equipment_id,site,name,kind,metadata) VALUES
 ('ahu-03','site-a','Fixture AHU','ahu','{"node":"edge-a","telemetry_system":"ahu-03"}'),
 ('ahu-99','site-b','Other site fixture','ahu','{"node":"edge-b","telemetry_system":"ahu-99"}');
INSERT INTO telemetry.readings(ts,site,node,system,metric,value,unit) VALUES
 (now(),'site-a','edge-a','ahu-03','supply_temp',19.5,'degC'),
 (now(),'site-b','edge-b','ahu-99','supply_temp',99.5,'degC');
INSERT INTO system.documents(document_id,site,equipment_id,kind,title,uri,trust_level) VALUES
 ('own-doc','site-a','ahu-03','manual','Fixture manual','forge://openaut/manuals/fixture.md','verified'),
 ('wrong-site','site-b','ahu-03','manual','Wrong site','forge://openaut/manuals/other.md','verified'),
 ('wrong-repo','site-a','ahu-03','manual','Wrong repo','forge://openaut/private/other.md','verified'),
 ('unverified','site-a','ahu-03','manual','Quarantine','forge://openaut/manuals/new.md','quarantine');
DO $$ BEGIN
 IF EXISTS(SELECT FROM advisor_read.equipment) THEN RAISE EXCEPTION 'implicit access'; END IF;
END $$;
INSERT INTO advisor_policy.allowed_sites VALUES('site-a','fixture-owner','fixture-approval',now());
INSERT INTO advisor_policy.forge_repositories VALUES('site-a','manuals','fixture-approval');
CREATE ROLE fixture_engineer NOLOGIN;
GRANT engineer_app TO fixture_engineer;
INSERT INTO system.cases(case_id,site,equipment_id,assigned_to,status,title,summary) VALUES
 ('delivery','site-a','ahu-03','fixture_engineer','approved','Fixture delivery','Synthetic case'),
 ('outside','site-b','ahu-99','fixture_engineer','approved','Outside','Synthetic case');
INSERT INTO system.approvals(approval_id,case_id,requested_by,approved_by,status,scope) VALUES
 ('approved','delivery','fixture_engineer','fixture-owner','approved',jsonb_build_object('action','advisor-integration','field_write',false,
 'integration',jsonb_build_object('equipment_id','ahu-03','node','edge-a','telemetry_system','ahu-03','alarm_metrics','{"fault_flags":"uint16"}'::jsonb,'alarm_watch',true,'artifact_sha256',repeat('a',64)))),
 ('outside-approval','outside','fixture_engineer','fixture-owner','approved',jsonb_build_object('action','advisor-integration','field_write',false,
 'integration',jsonb_build_object('equipment_id','ahu-99','node','edge-b','telemetry_system','ahu-99','alarm_metrics','{"fault_flags":"uint16"}'::jsonb,'alarm_watch',true,'artifact_sha256',repeat('a',64))));

SET SESSION AUTHORIZATION fixture_engineer;
SELECT system.register_advisor_integration('delivery',jsonb_build_object('equipment_id','ahu-03','node','edge-a',
 'telemetry_system','ahu-03','alarm_metrics','{"fault_flags":"uint16"}'::jsonb,'alarm_watch',true,'artifact_sha256',repeat('a',64)));
DO $$ DECLARE denied boolean; BEGIN
 denied=false;
 BEGIN INSERT INTO advisor_policy.allowed_sites VALUES('site-b','self','self',now());
 EXCEPTION WHEN insufficient_privilege THEN denied=true; END;
 IF NOT denied THEN RAISE EXCEPTION 'Engineer changed policy'; END IF;
 denied=false;
 BEGIN UPDATE system.equipment SET site='site-a' WHERE equipment_id='ahu-99';
 EXCEPTION WHEN insufficient_privilege THEN denied=true; END;
 IF NOT denied THEN RAISE EXCEPTION 'Engineer relabeled site'; END IF;
 denied=false;
 BEGIN UPDATE system.approvals SET approved_by=session_user WHERE case_id='delivery';
 EXCEPTION WHEN insufficient_privilege THEN denied=true; END;
 IF NOT denied THEN RAISE EXCEPTION 'Engineer can edit approvals'; END IF;
 denied=false;
 BEGIN PERFORM system.register_advisor_integration('outside',jsonb_build_object('equipment_id','ahu-99','node','edge-b',
 'telemetry_system','ahu-99','alarm_metrics','{"fault_flags":"uint16"}'::jsonb,'alarm_watch',true,'artifact_sha256',repeat('a',64)));
 EXCEPTION WHEN raise_exception THEN denied=true; END;
 IF NOT denied THEN RAISE EXCEPTION 'outside registration succeeded'; END IF;
 denied=false;
 BEGIN PERFORM system.register_advisor_integration('delivery',jsonb_build_object('equipment_id','ahu-03','node','edge-a',
 'telemetry_system','ahu-03','alarm_metrics','{"fault_flags":"uint16"}'::jsonb,'alarm_watch',true,'artifact_sha256',repeat('b',64)));
 EXCEPTION WHEN raise_exception THEN denied=true; END;
 IF NOT denied THEN RAISE EXCEPTION 'artifact approval bypass'; END IF;
END $$;
RESET SESSION AUTHORIZATION;
UPDATE system.approvals SET expires_at=now()-interval '1 second' WHERE approval_id='approved';
SET SESSION AUTHORIZATION fixture_engineer;
DO $$ DECLARE denied boolean=false; BEGIN
 BEGIN PERFORM system.register_advisor_integration('delivery',jsonb_build_object('equipment_id','ahu-03','node','edge-a',
 'telemetry_system','ahu-03','alarm_metrics','{"fault_flags":"uint16"}'::jsonb,'alarm_watch',true,'artifact_sha256',repeat('a',64)));
 EXCEPTION WHEN raise_exception THEN denied=true; END;
 IF NOT denied THEN RAISE EXCEPTION 'expired approval accepted'; END IF;
END $$;
RESET SESSION AUTHORIZATION;

-- Self approvals are independently rejected even when an owner fixture creates one.
UPDATE system.approvals SET expires_at=NULL,approved_by='fixture_engineer' WHERE approval_id='approved';
SET SESSION AUTHORIZATION fixture_engineer;
DO $$ DECLARE denied boolean=false; BEGIN
 BEGIN PERFORM system.register_advisor_integration('delivery',jsonb_build_object('equipment_id','ahu-03','node','edge-a',
 'telemetry_system','ahu-03','alarm_metrics','{"fault_flags":"uint16"}'::jsonb,'alarm_watch',true,'artifact_sha256',repeat('a',64)));
 EXCEPTION WHEN raise_exception THEN denied=true; END;
 IF NOT denied THEN RAISE EXCEPTION 'self approval accepted'; END IF;
END $$;
RESET SESSION AUTHORIZATION;
SET SESSION AUTHORIZATION advisor_reader;
DO $$ DECLARE denied boolean=false; BEGIN
 IF (SELECT array_agg(equipment_id) FROM advisor_read.equipment)<>ARRAY['ahu-03']::text[] THEN RAISE EXCEPTION 'wrong equipment scope'; END IF;
 IF NOT(SELECT alarm_watch FROM advisor_read.equipment WHERE equipment_id='ahu-03') THEN RAISE EXCEPTION 'missing contract'; END IF;
 IF (SELECT array_agg(value::numeric) FROM advisor_read.readings)<>ARRAY[19.5]::numeric[] THEN RAISE EXCEPTION 'cross-site telemetry'; END IF;
 IF (SELECT array_agg(document_id) FROM advisor_read.documents)<>ARRAY['own-doc']::text[] THEN RAISE EXCEPTION 'document boundary'; END IF;
 IF has_table_privilege(current_user,'advisor_read.equipment','UPDATE,INSERT,DELETE') THEN RAISE EXCEPTION 'reader can write'; END IF;
 BEGIN PERFORM * FROM system.equipment;
 EXCEPTION WHEN insufficient_privilege THEN denied=true; END;
 IF NOT denied THEN RAISE EXCEPTION 'reader can bypass views'; END IF;
END $$;
RESET SESSION AUTHORIZATION;
INSERT INTO system.equipment(equipment_id,site,name,kind) VALUES('ahu-04','site-a','New fixture','ahu');
DO $$ BEGIN
 IF (SELECT count(*) FROM advisor_read.equipment)<>2 THEN RAISE EXCEPTION 'automatic discovery failed'; END IF;
 IF (SELECT alarm_watch FROM advisor_read.equipment WHERE equipment_id='ahu-04') THEN RAISE EXCEPTION 'unregistered watch'; END IF;
END $$;

-- Model the optional product-catalog columns without changing the base schema migration.
ALTER TABLE system.equipment ADD COLUMN product_id text;
ALTER TABLE system.documents ADD COLUMN product_id text;
ALTER TABLE system.documents ALTER COLUMN site DROP NOT NULL;
UPDATE system.equipment SET product_id='product-a' WHERE equipment_id='ahu-03';
INSERT INTO system.documents(document_id,site,product_id,kind,title,uri,trust_level) VALUES
 ('product-doc',NULL,'product-a','manual','Shared product manual','forge://openaut/manuals/product.md','verified'),
 ('other-product',NULL,'product-b','manual','Different product','forge://openaut/manuals/other-product.md','verified'),
 ('private-product','site-b','product-a','manual','Private site material','forge://openaut/manuals/private-product.md','verified');
SET SESSION AUTHORIZATION advisor_reader;
DO $$ BEGIN
 IF (SELECT array_agg(document_id ORDER BY document_id) FROM advisor_read.documents WHERE equipment_id='ahu-03')<>ARRAY['own-doc','product-doc']::text[] THEN
  RAISE EXCEPTION 'product manual scope failed'; END IF;
 IF EXISTS(SELECT FROM advisor_read.documents WHERE equipment_id='ahu-04') THEN RAISE EXCEPTION 'manual attached to wrong product'; END IF;
END $$;
RESET SESSION AUTHORIZATION;
DELETE FROM advisor_policy.allowed_sites WHERE site='site-a';
DO $$ BEGIN
 IF EXISTS(SELECT FROM advisor_read.equipment) OR EXISTS(SELECT FROM advisor_read.readings) OR EXISTS(SELECT FROM advisor_read.documents) THEN
  RAISE EXCEPTION 'owner revocation failed'; END IF;
END $$;
SELECT 'PORTABLE_DISCOVERY_DATABASE_TESTS_PASS';
