SELECT count(*) FROM telemetry.readings
WHERE site=:'edge_site' AND node=:'edge_node' AND metric='supply_temp'
  AND ts=to_timestamp(:'event_ts'::double precision);
SELECT count(*) FROM telemetry.node_status
WHERE site=:'edge_site' AND node=:'edge_node'
  AND ts=to_timestamp(:'event_ts'::double precision);
