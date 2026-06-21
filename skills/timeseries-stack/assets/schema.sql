-- openAut storage tier: TimescaleDB telemetry + relational system schema + least-privilege roles.
-- Run as the postgres superuser:  sudo -u postgres psql -v ON_ERROR_STOP=1 -f schema.sql
-- Set role passwords out-of-band (ALTER ROLE ... PASSWORD) — never store them here.

-- NOTE: psql does not expand shell env vars. These identifiers match config.env defaults
-- (openaut / telemetry / ingest / agent_ro). Adjust here if you changed them in config.env.

CREATE DATABASE openaut;
\connect openaut

CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE SCHEMA IF NOT EXISTS telemetry;
CREATE SCHEMA IF NOT EXISTS system;

-- ---- Relational system data ----
CREATE TABLE IF NOT EXISTS system.sites (
  site        text PRIMARY KEY,
  name        text,
  address     text
);

CREATE TABLE IF NOT EXISTS system.devices (
  node        text PRIMARY KEY,         -- = MQTT client id / cert CN
  site        text REFERENCES system.sites(site),
  kind        text,                     -- e.g. 'iot2050', 'meter'
  protocol    text,                     -- 'bacnet','modbus','mbus',...
  added_at    timestamptz DEFAULT now()
);

-- ---- Time-series telemetry ----
CREATE TABLE IF NOT EXISTS telemetry.readings (
  ts        timestamptz       NOT NULL,
  site      text              NOT NULL,
  node      text              NOT NULL,
  system    text              NOT NULL,
  metric    text              NOT NULL,
  value     double precision,
  bool_val  boolean,
  unit      text
);
SELECT create_hypertable('telemetry.readings', 'ts',
                         partitioning_column => 'node', number_partitions => 4,
                         if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS readings_node_metric_ts
  ON telemetry.readings (node, metric, ts DESC);

CREATE TABLE IF NOT EXISTS telemetry.node_status (
  ts        timestamptz       NOT NULL,
  site      text              NOT NULL,
  node      text              NOT NULL,
  online    boolean           NOT NULL
);
SELECT create_hypertable('telemetry.node_status', 'ts', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS node_status_node_ts
  ON telemetry.node_status (node, ts DESC);

-- 90-day raw retention
SELECT add_retention_policy('telemetry.readings', INTERVAL '90 days', if_not_exists => TRUE);

-- Hourly continuous aggregate the energy agent reads
CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry.readings_hourly
  WITH (timescaledb.continuous) AS
  SELECT time_bucket('1 hour', ts) AS bucket, site, node, system, metric,
         avg(value) AS avg_v, min(value) AS min_v, max(value) AS max_v
  FROM telemetry.readings
  GROUP BY 1,2,3,4,5
  WITH NO DATA;
SELECT add_continuous_aggregate_policy('telemetry.readings_hourly',
  start_offset => INTERVAL '3 days', end_offset => INTERVAL '1 hour',
  schedule_interval => INTERVAL '1 hour', if_not_exists => TRUE);

-- ---- Least-privilege roles ----
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='ingest') THEN CREATE ROLE ingest LOGIN; END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='agent_ro') THEN CREATE ROLE agent_ro LOGIN; END IF;
END $$;

GRANT USAGE ON SCHEMA telemetry TO ingest, agent_ro;
GRANT INSERT ON telemetry.readings, telemetry.node_status TO ingest;            -- write: ingest only
GRANT SELECT ON telemetry.readings, telemetry.readings_hourly, telemetry.node_status TO agent_ro;  -- read: agents only
GRANT USAGE ON SCHEMA system TO agent_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA system TO agent_ro;

-- agents must never write
REVOKE INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA telemetry FROM agent_ro;
