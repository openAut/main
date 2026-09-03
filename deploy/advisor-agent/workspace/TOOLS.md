# TOOLS.md — notes on how Advisor should use its tools

- **Telemetry queries** — prefer `timeseries-stack`'s `telemetry.readings_hourly` continuous
  aggregate over scanning raw readings; only drop to raw resolution when the hourly aggregate
  doesn't resolve the question (e.g. a fast transient).
- **Systemdatabas reads** — resolve equipment → points → recent cases in that order; don't query
  cases before you have the equipment context, or you'll miss why a case was opened.
- **Forge document reads** — always resolve through the Systemdatabas `documents` row first (for
  `trust_level` and `sha256`), never fetch a Forge blob directly by guessing a path.
- **Case creation** — one case per root cause, not one per symptom. If `anomaly-correlation`
  suppressed several alarms under one parent, the case is about the parent.
- **Teams replies** — this workspace is bound to the `msteams` channel plugin (see
  `../openclaw.json`). Keep replies to the response shape in `AGENTS.md`; don't pad with
  pleasantries — people are reading this mid-incident.
