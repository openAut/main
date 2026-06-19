---
name: timeseries-stack
description: Provision the openAut storage tier — PostgreSQL with the TimescaleDB extension for telemetry hypertables plus a relational system schema for devices and config, an MQTT-to-database ingest path, retention and continuous aggregates, and least-privilege roles (ingest write, agent read-only). Use when setting up TimescaleDB/PostgreSQL, storing building timeseries, ingesting MQTT into a database, or granting agents read access to historical data.
---

# timeseries-stack — TimescaleDB + PostgreSQL

The openAut AI tier stores telemetry in **TimescaleDB** (time-series) and system/config data in plain
**PostgreSQL** tables, on-premise. This skill installs the database, creates the schema, wires an
**MQTT → database** ingest path from the EMQX broker, sets **retention + continuous aggregates**, and
creates **least-privilege roles** so the energy/manager agents get read-only access and nothing more.

Depends on [`mqtt-tls-broker`](../mqtt-tls-broker/SKILL.md) (the data source). Assumes `config.env`
is sourced.

## Step 1 — Install PostgreSQL + TimescaleDB

```bash
ssh "$TSDB_SSH_USER@$TSDB_HOST" \
  "sudo apt-get update && sudo apt-get install -y postgresql && \
   echo 'add the TimescaleDB apt repo per docs, then:' && \
   sudo apt-get install -y timescaledb-2-postgresql-16 && \
   sudo timescaledb-tune --yes && sudo systemctl restart postgresql"
```

(Use TimescaleDB's current documented repo setup for your PostgreSQL major version.)

## Step 2 — Create the database, schema, roles

Apply `assets/schema.sql`. It creates the `$TSDB_DB` database, the `$TSDB_TS_SCHEMA` telemetry
hypertable, a relational `system` schema (devices, sites), and two roles:

- **`$TSDB_INGEST_USER`** — INSERT on telemetry only (used by the ingest consumer).
- **`$TSDB_AGENT_RO_USER`** — SELECT only (granted to the Energisamordnare / Förvaltare agents).

```bash
scp skills/timeseries-stack/assets/schema.sql "$TSDB_SSH_USER@$TSDB_HOST:/tmp/"
ssh "$TSDB_SSH_USER@$TSDB_HOST" "sudo -u postgres psql -v ON_ERROR_STOP=1 -f /tmp/schema.sql"
```

Set role passwords out-of-band (do not hard-code them in the repo); store them in the host's secret
store or PostgreSQL `.pgpass`.

## Step 3 — Telemetry data model

The hypertable matches the MQTT topic schema from the broker skill:

```
telemetry.readings(
  ts        timestamptz   not null,   -- from payload "ts" (unix epoch -> timestamptz)
  site      text          not null,   -- openaut/<site>/...
  node      text          not null,   -- .../<node>/...
  system    text          not null,   -- .../<system>/...
  metric    text          not null,   -- .../<metric>
  value     double precision,
  bool_val  boolean,                  -- for binary points
  unit      text
)  -- hypertable on ts, space-partitioned by node
```

## Step 4 — MQTT → database ingest

Two supported paths (pick one):

- **Telegraf** (`assets/telegraf-mqtt-to-pg.conf`): `mqtt_consumer` input subscribing to `openaut/#`
  over TLS (CA + the `ingest` client cert) → `outputs.postgresql`. Lowest-code.
- **Python consumer** (`scripts/ingest.py`): paho-mqtt over TLS → `psycopg`. Use when you need custom
  topic→column parsing or store-and-forward.

Either connects to EMQX as the **`ingest`** identity (cert CN), subscribes read-only to `openaut/#`,
parses `openaut/<site>/<node>/<system>/<metric>` into columns, and inserts into `telemetry.readings`.
Run it as a systemd service on the AI-tier host.

## Step 5 — Retention & continuous aggregates

```sql
-- keep raw telemetry 90 days
SELECT add_retention_policy('telemetry.readings', INTERVAL '90 days');
-- hourly rollups the energy agent reads instead of scanning raw data
CREATE MATERIALIZED VIEW telemetry.readings_hourly
  WITH (timescaledb.continuous) AS
  SELECT time_bucket('1 hour', ts) AS bucket, site, node, system, metric,
         avg(value) avg_v, min(value) min_v, max(value) max_v
  FROM telemetry.readings GROUP BY 1,2,3,4,5;
SELECT add_continuous_aggregate_policy('telemetry.readings_hourly',
  start_offset => INTERVAL '3 days', end_offset => INTERVAL '1 hour',
  schedule_interval => INTERVAL '1 hour');
```

(Also in `assets/schema.sql`.)

## Step 6 — Grant agents read-only

The `nemoclaw-agent-workflow` personas connect as **`$TSDB_AGENT_RO_USER`** with SELECT on
`telemetry.*`. They can never write. Verify:

```bash
bash skills/timeseries-stack/scripts/verify-db.sh
```

It checks the hypertable exists, the continuous aggregate is populated, and the read-only role is
refused an INSERT.

## Security review (openAut frameworks)

| Control | Check | Framework |
|---|---|---|
| Least privilege | ingest = INSERT only; agents = SELECT only | IEC 62443 SR 2.1, NIS2 Art. 21 |
| Encrypted ingest | consumer connects to EMQX over TLS w/ client cert | IEC 62443 SR 4.1, CRA |
| Data minimisation/retention | 90-day raw retention, aggregates for the rest | ISO 27001 A.8, GDPR-adjacent |
| On-prem only | DB bound to the AI-tier host, no cloud egress | NIS2, openAut air-gap goal |

> **Live behaviour is unverified until a database host is available.** TimescaleDB package names and
> the continuous-aggregate API vary by version — the data model, roles, and ingest contract are the
> durable part.
