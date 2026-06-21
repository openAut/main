#!/usr/bin/env bash
# Verify the openAut storage tier: hypertable exists, continuous aggregate present,
# and the read-only agent role cannot INSERT. Sources ../../../config.env.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
# shellcheck disable=SC1091
set -a; . "$ROOT/config.env"; set +a

PSQL="ssh ${TSDB_SSH_USER}@${TSDB_HOST} sudo -u postgres psql -d ${TSDB_DB} -tAc"

echo "== telemetry hypertables present? =="
$PSQL "SELECT hypertable_name FROM timescaledb_information.hypertables WHERE hypertable_name IN ('readings','node_status') ORDER BY 1;"

echo "== continuous aggregate present? =="
$PSQL "SELECT view_name FROM timescaledb_information.continuous_aggregates;"

echo "== read-only role refused INSERT (expect ERROR) =="
if ssh "${TSDB_SSH_USER}@${TSDB_HOST}" \
     "sudo -u postgres psql -d ${TSDB_DB} -c \
      \"SET ROLE ${TSDB_AGENT_RO_USER}; INSERT INTO telemetry.readings(ts,site,node,system,metric) \
        VALUES (now(),'x','x','x','x');\"" 2>/dev/null; then
  echo "FAIL — ${TSDB_AGENT_RO_USER} was able to INSERT; revoke write." >&2
  exit 1
else
  echo "OK — ${TSDB_AGENT_RO_USER} is read-only."
fi
