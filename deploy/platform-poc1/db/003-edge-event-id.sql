\connect openaut

ALTER TABLE telemetry.readings ADD COLUMN IF NOT EXISTS event_id text;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'telemetry.readings'::regclass AND conname = 'readings_event_id_format'
  ) THEN
    ALTER TABLE telemetry.readings ADD CONSTRAINT readings_event_id_format
      CHECK (event_id IS NULL OR event_id ~ '^[0-9a-f]{32}$');
  END IF;
END $$;

-- TimescaleDB unique indexes must include the time and space partition dimensions.
CREATE UNIQUE INDEX IF NOT EXISTS readings_event_id
  ON telemetry.readings (ts, node, event_id);

-- ON CONFLICT index inference requires read access to the conflict-key columns.
GRANT SELECT (ts, node, event_id) ON telemetry.readings TO ingest;
