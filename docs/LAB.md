# Local lab path

This repo is primarily a runbook pack. Use this lab path to verify the durable contracts without
connecting to a real building, a Teams tenant, or a NemoClaw host.

## 1. Python checks

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
python -m unittest discover -s tests
```

The tests cover the MQTT topic contract, payload mapping into Timescale rows, node status messages,
and the bounded edge spool.

## 2. Minimal MQTT -> DB rehearsal

Bring up an EMQX + TimescaleDB stack with your own Compose file or lab host, then apply:

```bash
sudo -u postgres psql -v ON_ERROR_STOP=1 -f skills/timeseries-stack/assets/schema.sql
```

For a first dry run, publish payloads matching the contract:

```bash
mosquitto_pub -h "$EMQX_HOST" -p "$EMQX_TLS_PORT" \
  --cafile "$MQTT_CA_CERT" --cert "$PKI_DIR/clients/$EDGE_NODE_ID.crt" \
  --key "$PKI_DIR/clients/$EDGE_NODE_ID.key" \
  -t "openaut/$EDGE_SITE/$EDGE_NODE_ID/ahu/supply_temp" \
  -m '{"value":21.5,"ts":1700000000,"unit":"degC"}'

mosquitto_pub -h "$EMQX_HOST" -p "$EMQX_TLS_PORT" \
  --cafile "$MQTT_CA_CERT" --cert "$PKI_DIR/clients/$EDGE_NODE_ID.crt" \
  --key "$PKI_DIR/clients/$EDGE_NODE_ID.key" \
  -t "openaut/$EDGE_SITE/$EDGE_NODE_ID/$status" \
  -m '{"value":true,"ts":1700000000}'
```

Telemetry rows should land in `telemetry.readings`; node online/offline events should land in
`telemetry.node_status`.

## Maturity checklist

| Area | Current level | Before real use |
|---|---|---|
| Runbooks | Concept complete | Rehearse on isolated lab hosts |
| Python stubs | Unit-tested contracts | Add hardware-specific drivers and integration tests |
| MQTT/TLS | Reference config | Verify against the exact EMQX version in use |
| Timescale schema | Lab-oriented | Add migrations, backups, retention review |
| Teams bridge | Authenticated reference stub | Put behind TLS/reverse proxy and add observability |
| Field writes | Human-confirmed only | Site risk assessment and qualified controls engineer approval |
