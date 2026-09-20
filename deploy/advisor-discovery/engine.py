"""Durable, deterministic detector. Equipment authorization belongs to the read service."""
import datetime as dt
import hashlib
import json
import math
import re
import sqlite3

MAX_HISTORY_REQUESTS = 32


class DataError(Exception):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def iso(value):
    return dt.datetime.fromtimestamp(value, dt.timezone.utc).isoformat()


def timestamp(value):
    try:
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError()
        return parsed.timestamp()
    except (ValueError, TypeError, AttributeError, OverflowError):
        raise DataError('invalid_timestamp') from None


def alarm_row(row, now, profile):
    metric = row.get('metric')
    if not isinstance(metric, str) or metric not in profile:
        raise DataError('unknown_alarm_metric')
    ts = timestamp(row.get('ts'))
    if ts > now + 30:
        raise DataError('future_alarm_timestamp')
    kind = profile[metric]
    if kind == 'boolean':
        value = row.get('bool_val')
        if type(value) is not bool or row.get('unit') != 'bool':
            raise DataError('invalid_boolean')
    else:
        value = row.get('value')
        if type(value) not in (int, float) or not math.isfinite(value) or int(value) != value:
            raise DataError('invalid_integer')
        allowed_units = ('bitfield',) if kind == 'uint16' else ('code', 'count')
        if row.get('unit') not in allowed_units or not (0 if kind == 'uint16' else -32768) <= value <= 65535:
            raise DataError('invalid_unit_or_range')
        value = int(value)
    return metric, ts, value


class Store:
    def __init__(self, path, *, equipment_id, alarm_metrics, binding, display_name=None, synthetic=False):
        if not isinstance(equipment_id, str) or not re.fullmatch(r'[a-z0-9][a-z0-9._-]{0,62}', equipment_id):
            raise DataError('invalid_equipment')
        if not isinstance(alarm_metrics, dict) or not 1 <= len(alarm_metrics) <= 64 or any(
                not re.fullmatch(r'[a-z][a-z0-9_]{0,79}', k) or v not in ('boolean', 'integer', 'uint16') for k, v in alarm_metrics.items()):
            raise DataError('invalid_profile')
        self.equipment_id, self.profile = equipment_id, alarm_metrics
        self.display_name, self.synthetic = display_name or equipment_id, synthetic
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS points(metric TEXT PRIMARY KEY,ts REAL NOT NULL,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS observations(id TEXT PRIMARY KEY,metric TEXT NOT NULL,ts REAL NOT NULL,value TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS observations_order ON observations(metric,ts);
CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,observed REAL NOT NULL,kind TEXT NOT NULL,
 metric TEXT NOT NULL,ts REAL NOT NULL,old TEXT NOT NULL,new TEXT NOT NULL,batch TEXT);
CREATE TABLE IF NOT EXISTS batches(id TEXT PRIMARY KEY,created REAL NOT NULL,payload TEXT NOT NULL,
 state TEXT NOT NULL,attempt REAL,run_id TEXT);
''')
        expected = {'equipment_id': equipment_id, 'synthetic': synthetic, 'alarm_metrics': alarm_metrics, 'binding': binding}
        existing = {r[0]: json.loads(r[1]) for r in self.db.execute('SELECT key,value FROM meta')}
        if existing and any(k not in existing or existing[k] != v for k, v in expected.items()):
            self.db.close()
            raise DataError('state_contract_mismatch_requires_review')
        with self.db:
            for k, v in expected.items():
                self.set(k, v)
            self.db.execute("UPDATE batches SET state='uncertain' WHERE state='sending'")

    def close(self):
        self.db.close()

    def get(self, key, default=None):
        row = self.db.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, key, value):
        self.db.execute('INSERT INTO meta VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, canonical(value)))

    def remember(self, metric, ts, value):
        key = hashlib.sha256(canonical([metric, ts, value]).encode()).hexdigest()
        return self.db.execute('INSERT OR IGNORE INTO observations VALUES (?,?,?,?)', (key, metric, ts, canonical(value))).rowcount == 1

    def seed(self, rows, end):
        parsed = [alarm_row(row, end, self.profile) for row in rows]
        if len(parsed) != len(self.profile) or {p[0] for p in parsed} != set(self.profile):
            raise DataError('incomplete_snapshot')
        with self.db:
            self.db.execute('DELETE FROM points')
            self.db.executemany('INSERT INTO points VALUES (?,?,?)', [(m, t, canonical(v)) for m, t, v in parsed])
            for m, t, v in parsed:
                self.remember(m, t, v)
            self.set('metrics', sorted(self.profile))
            self.set('cursor', end)
            self.set('initial_baseline_at', end)
            self.set('history_scan', {})

    def event(self, kind, metric, ts, before, after, now):
        key = hashlib.sha256(canonical([self.equipment_id, self.synthetic, kind, metric, ts, before, after]).encode()).hexdigest()
        self.db.execute('INSERT OR IGNORE INTO events VALUES (?,?,?,?,?,?,?,NULL)', (key, now, kind, metric, ts, canonical(before), canonical(after)))

    def health(self, state, now):
        if state not in {'healthy', 'stale', 'clock_skew', 'communication_fault', 'unknown', 'source_unavailable', 'history_backpressure', 'history_gap', 'data_quality'}:
            raise DataError('invalid_health_state')
        with self.db:
            old = self.get('health')
            if old != state and not (old is None and state == 'healthy'):
                self.event('field_communication' if state == 'communication_fault' else 'data_health', 'read_health', now, old, state, now)
            self.set('health', state)
            self.set('checked_at', now)

    def apply(self, rows, end, now, *, advance_cursor=True, history_scan=None):
        cursor = self.get('cursor')
        if cursor is None or end < cursor or end > now + 30:
            raise DataError('invalid_cursor')
        parsed = sorted([alarm_row(row, now, self.profile) for row in rows], key=lambda p: (p[1], p[0]))
        if any(ts >= end for _, ts, _ in parsed):
            raise DataError('history_end_mismatch')
        with self.db:
            if self.db.execute('SELECT count(*) FROM events WHERE batch IS NULL').fetchone()[0] + len(parsed) > 10000:
                raise DataError('pending_capacity')
            for metric, ts, value in parsed:
                point = self.db.execute('SELECT ts,value FROM points WHERE metric=?', (metric,)).fetchone()
                if not self.remember(metric, ts, value):
                    continue
                if ts < point['ts']:
                    old = self.db.execute('SELECT value FROM observations WHERE metric=? AND ts<? ORDER BY ts DESC LIMIT 1', (metric, ts)).fetchone()
                    before = json.loads(old[0]) if old else json.loads(point['value'])
                    if before != value:
                        self.event('late_published_alarm_observation', metric, ts, before, value, now)
                    continue
                before = json.loads(point['value'])
                if ts == point['ts']:
                    if before != value:
                        raise DataError('conflicting_timestamp')
                    continue
                if before != value:
                    kind = 'equipment_communication_alarm' if metric.startswith(('comm_', 'comm_error')) else 'process_alarm_change'
                    self.event(kind, metric, ts, before, value, now)
                self.db.execute('UPDATE points SET ts=?,value=? WHERE metric=?', (ts, canonical(value), metric))
            if advance_cursor:
                self.set('cursor', end)
            if history_scan is not None:
                # The page's observations/events and its checkpoint commit together.
                self.set('history_scan', history_scan)
            self.db.execute('DELETE FROM observations WHERE ts<?', (end - 7 * 86400,))

    def next_batch(self, now):
        with self.db:
            ready = self.db.execute("SELECT * FROM batches WHERE state='queued' ORDER BY created LIMIT 1").fetchone()
            if ready:
                return dict(ready)
            rows = self.db.execute('SELECT * FROM events WHERE batch IS NULL ORDER BY observed,ts,metric LIMIT 40').fetchall()
            if not rows:
                return None
            key = 'event-' + hashlib.sha256(canonical([r['id'] for r in rows]).encode()).hexdigest()
            event = {'equipment_id': self.equipment_id, 'display_name': self.display_name, 'synthetic': self.synthetic,
                     'event_id': key, 'observed_at': iso(now),
                     'changes': [{'kind': r['kind'], 'metric': r['metric'], 'source_ts': iso(r['ts']),
                                  'previous': json.loads(r['old']), 'current': json.loads(r['new'])} for r in rows]}
            self.db.execute("INSERT INTO batches VALUES (?,?,?,'queued',NULL,NULL)", (key, now, canonical({'event_json': canonical(event)})))
            self.db.executemany('UPDATE events SET batch=? WHERE id=?', [(key, r['id']) for r in rows])
            return dict(self.db.execute('SELECT * FROM batches WHERE id=?', (key,)).fetchone())

    def sending(self, key, now):
        with self.db:
            if self.db.execute("UPDATE batches SET state='sending',attempt=? WHERE id=? AND state='queued'", (now, key)).rowcount != 1:
                raise DataError('batch_not_queued')

    def finish(self, key, state, run_id=None):
        if state not in ('admitted', 'failed', 'uncertain'):
            raise DataError('invalid_delivery_state')
        with self.db:
            self.db.execute("UPDATE batches SET state=?,run_id=? WHERE id=? AND state='sending'", (state, run_id, key))

    def summary(self):
        return {'equipment_id': self.equipment_id, 'synthetic': self.synthetic,
                'health': self.get('health'), 'cursor': self.get('cursor'), 'checked_at': self.get('checked_at'),
                'history_pending_ranges': len(self.get('history_scan', {}).get('pending', [])),
                'unbatched_events': self.db.execute('SELECT count(*) FROM events WHERE batch IS NULL').fetchone()[0],
                'batches': dict(self.db.execute('SELECT state,count(*) FROM batches GROUP BY state')),
                'delivery_note': 'admitted is not model completion; uncertain is never automatically resent'}


def scan_history(reader, store, now, end_now):
    """Split BOTH the overlap and forward range; resume bounded work across polls/restarts.

    A complete page is applied without advancing the global cursor. Truncated prefixes are
    never applied. The global cursor moves only after every metric/window in this scan has
    been covered. Partial pages and the remaining work queue share one SQLite transaction.
    """
    cursor = store.get('cursor')
    plan = store.get('history_scan', {})
    if not plan:
        # Round-trip through the wire timestamp precision before splitting/validating bounds.
        start = timestamp(iso(max(store.get('initial_baseline_at'), cursor - 120)))
        end = timestamp(iso(min(end_now, cursor + 3600)))
        if end <= cursor:
            return
        metrics = store.get('metrics')
        plan = {'cursor': cursor, 'end': end,
                'pending': [{'start': start, 'end': end, 'metrics': metrics[i:i + 8]}
                            for i in range(0, len(metrics), 8)]}
        with store.db:
            store.set('history_scan', plan)
    if plan.get('cursor') != cursor or not isinstance(plan.get('pending'), list) or not cursor < plan.get('end', 0) <= now + 30:
        raise DataError('invalid_history_checkpoint')
    for _ in range(MAX_HISTORY_REQUESTS):
        if not plan['pending']:
            break
        part, *remaining = plan['pending']
        start, end, metrics = part['start'], part['end'], part['metrics']
        if not start < end <= plan['end'] or not 1 <= len(metrics) <= 8 or any(m not in store.profile for m in metrics):
            raise DataError('invalid_history_partition')
        value = reader('history', {'metrics': ','.join(metrics), 'start': iso(start), 'end': iso(end), 'limit': '500'})
        rows = value.get('readings')
        if value.get('equipment_id') != store.equipment_id or not isinstance(rows, list) or len(rows) > 500 or type(value.get('truncated')) is not bool:
            raise DataError('invalid_history')
        if value['truncated']:
            if len(metrics) > 1:
                half = len(metrics) // 2
                children = [{**part, 'metrics': metrics[:half]}, {**part, 'metrics': metrics[half:]}]
            else:
                middle = timestamp(iso((start + end) / 2))
                if not start < middle < end:
                    # No time partition can recover >500 rows for one metric/instant.
                    # Keep the cursor/checkpoint and report an explicit data-quality gap.
                    raise DataError('unpageable_timestamp_density')
                children = [{**part, 'end': middle}, {**part, 'start': middle}]
            plan = {**plan, 'pending': children + remaining}
            with store.db:
                store.set('history_scan', plan)
            continue
        if any(r.get('metric') not in metrics or not start <= timestamp(r.get('ts')) < end for r in rows):
            raise DataError('history_partition_mismatch')
        plan = {**plan, 'pending': remaining}
        store.apply(rows, max(cursor, end), now, advance_cursor=False, history_scan=plan)
    if plan['pending']:
        store.health('history_backpressure', now)
        return
    store.apply([], plan['end'], now, history_scan={})
    store.health('healthy', now)


def poll(reader, store, now):
    try:
        current = reader('alarms', {})
        if current.get('equipment_id') != store.equipment_id:
            raise DataError('scope_mismatch')
        state = current.get('health', {}).get('state', 'unknown')
        if state != 'healthy':
            store.health(state, now)
            return
        if abs(timestamp(current['queried_at']) - now) > 60:
            store.health('clock_skew', now)
            return
        end_now = min(timestamp(current['queried_at']) - 2, now - 2)
        cursor = store.get('cursor')
        if cursor is None:
            store.seed(current['readings'], now)
            store.health('healthy', now)
            return
        if end_now - cursor > 7 * 86400 - 120:
            store.health('history_gap', now)
            store.seed(current['readings'], now)
            return
        if end_now < cursor:
            return
        metrics = store.get('metrics')
        if sorted(r['metric'] for r in current['readings']) != metrics:
            store.health('data_quality', now)
            return
        scan_history(reader, store, now, end_now)
    except DataError:
        store.health('data_quality', now)
    except Exception:
        store.health('source_unavailable', now)
