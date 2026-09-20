"""Discovery worker. Only owner-configured loopback endpoints are accepted by this reference."""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from engine import Store, canonical, poll, iso

ID = re.compile(r'[a-z0-9][a-z0-9._-]{0,62}\Z')


def key_for(equipment):
    if not isinstance(equipment, str) or not ID.fullmatch(equipment):
        raise ValueError('invalid_equipment')
    return hashlib.sha256(equipment.encode()).hexdigest()[:32]


def state_name(equipment):
    return 'eq-' + key_for(equipment) + '-live.sqlite'


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('redirect_refused')


class Client:
    def __init__(self, config, equipment=None):
        self.equipment = equipment
        self.api, self.hook = config['read_api'].rstrip('/') + '/', config['hook_url'].rstrip('/')
        for url in (self.api, self.hook):
            target = urlsplit(url)
            if target.scheme != 'http' or target.hostname not in ('127.0.0.1', '::1') or target.username or target.password or target.query or target.fragment:
                raise ValueError('owner_loopback_endpoint_required')
        self.reader_token = Path(config['reader_token_file']).read_text().strip()
        self.hook_token = Path(config['hook_token_file']).read_text().strip()
        if not self.reader_token or not self.hook_token:
            raise ValueError('unprovisioned_identity')
        self.http = build_opener(ProxyHandler({}), NoRedirect())

    def get(self, operation, args):
        req = Request(self.api + operation + '?' + urlencode(args), headers={'Authorization': 'Bearer ' + self.reader_token})
        with self.http.open(req, timeout=10) as response:
            raw = response.read(256 * 1024 + 1)
        if len(raw) > 256 * 1024:
            raise ValueError('response_too_large')
        return json.loads(raw)

    def read(self, operation, args):
        return self.get(operation, {**args, 'equipment_id': self.equipment})

    def discover(self):
        rows, seen, after = [], set(), ''
        while True:
            value = self.get('list_equipment', {'limit': '20', **({'after': after} if after else {})})
            page = value['equipment']
            if not isinstance(page, list) or len(page) > 20:
                raise ValueError('invalid_page')
            previous = after
            for row in page:
                equipment = row.get('equipment_id')
                key_for(equipment)
                if equipment in seen or equipment <= previous:
                    raise ValueError('invalid_order')
                seen.add(equipment)
                rows.append(row)
                previous = equipment
            if len(rows) > 1000:
                raise ValueError('capacity_exceeded')
            cursor = value.get('next_after')
            if cursor is None:
                return rows
            if not page or cursor != previous or cursor <= after:
                raise ValueError('invalid_cursor')
            after = cursor

    def ready(self):
        origin = urlsplit(self.hook)
        try:
            with self.http.open(f'{origin.scheme}://{origin.netloc}/', timeout=3) as response:
                return response.status == 200
        except OSError:
            return False

    def send(self, batch, synthetic):
        request = Request(self.hook + ('-test' if synthetic else ''), method='POST', data=batch['payload'].encode(),
                          headers={'Authorization': 'Bearer ' + self.hook_token, 'Content-Type': 'application/json', 'Idempotency-Key': batch['id']})
        with self.http.open(request, timeout=25) as response:
            result = json.loads(response.read(10000))
            if response.status != 200 or result.get('ok') is not True or not re.fullmatch(r'[a-f0-9-]{36}', result.get('runId', '')):
                raise ValueError('admission_unconfirmed')
        return result['runId']


class Budget:
    def __init__(self, directory):
        # Refuse legacy databases rather than silently starting new baselines alongside them.
        for path in directory.glob('*.sqlite'):
            if path.name != 'discovery-budget.sqlite' and not re.fullmatch(r'eq-[a-f0-9]{32}-(live|synthetic)\.sqlite', path.name):
                raise ValueError('unrecognized_state_requires_migration')
        self.db = sqlite3.connect(directory / 'discovery-budget.sqlite')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS attempts(equipment TEXT,batch TEXT,ts REAL,PRIMARY KEY(equipment,batch))')
        for path in directory.glob('eq-*-live.sqlite'):
            with contextlib.closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as old:
                row = old.execute("SELECT value FROM meta WHERE key='equipment_id'").fetchone()
                if not row:
                    raise ValueError('unidentified_ledger')
                equipment = json.loads(row[0])
                key_for(equipment)
                mode = old.execute("SELECT value FROM meta WHERE key='synthetic'").fetchone()
                if state_name(equipment) != path.name or not mode or json.loads(mode[0]) is not False:
                    self.db.close()
                    raise ValueError('ledger_namespace_mismatch')
                with self.db:
                    self.db.executemany('INSERT OR IGNORE INTO attempts VALUES (?,?,?)', [(equipment, b, t) for b, t in old.execute('SELECT id,attempt FROM batches WHERE attempt>?', (time.time() - 3600,))])

    def reconcile(self, store):
        with store.db:
            for batch, ts in self.db.execute('SELECT batch,ts FROM attempts WHERE equipment=?', (store.equipment_id,)):
                store.db.execute("UPDATE batches SET state='uncertain',attempt=? WHERE id=? AND state='queued'", (ts, batch))

    def reserve(self, equipment, batch, now):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            count, last = self.db.execute('SELECT count(*),max(ts) FROM attempts WHERE ts>?', (now - 3600,)).fetchone()
            if count >= 6 or (last is not None and now - last < 60):
                self.db.rollback()
                return False
            changed = self.db.execute('INSERT OR IGNORE INTO attempts VALUES (?,?,?)', (equipment, batch, now)).rowcount
            self.db.commit()
            return changed == 1
        except Exception:
            self.db.rollback()
            raise

    def close(self):
        self.db.close()


def dispatch(store, client, now, budget=None):
    batch = store.next_batch(now)
    if not batch or not client.ready():
        return
    if budget is not None and not budget.reserve(store.equipment_id, batch['id'], now):
        return
    store.sending(batch['id'], now)
    try:
        receipt = client.send(batch, store.synthetic)
    except HTTPError as exc:
        store.finish(batch['id'], 'failed' if exc.code in (400, 401, 403, 404, 405, 413, 429) else 'uncertain')
        return
    except Exception:
        store.finish(batch['id'], 'uncertain')
        return
    store.finish(batch['id'], 'admitted', receipt)


def descriptor(row):
    for field in ('equipment_id', 'site', 'node', 'telemetry_system'):
        key_for(row.get(field))
    if not isinstance(row.get('name'), str) or not 1 <= len(row['name']) <= 200:
        raise ValueError('invalid_name')
    return {k: row[k] for k in ('equipment_id', 'site', 'node', 'telemetry_system', 'name', 'alarm_metrics')}


def open_store(path, row, synthetic=False):
    desc = descriptor(row)
    return Store(path, equipment_id=desc['equipment_id'], display_name=desc['name'], alarm_metrics=desc['alarm_metrics'],
                 binding=canonical({k: desc[k] for k in ('site', 'node', 'telemetry_system')}), synthetic=synthetic)


class Worker:
    def __init__(self, directory, client_factory):
        self.directory, self.factory = directory, client_factory
        self.catalog = client_factory(None)
        self.stores = {}
        self.budget = Budget(directory)

    def cycle(self):
        rows = self.catalog.discover()  # Fail closed: no cached dispatch after a discovery error.
        active = set()
        status = {'checked_at': time.time(), 'discovery': 'ok', 'equipment': {}}
        for row in rows:
            if row.get('alarm_watch') is not True:
                continue
            equipment = row['equipment_id']
            try:
                signature = canonical(descriptor(row))
                current = self.stores.get(equipment)
                if current and current[0] != signature:
                    self.stores.pop(equipment)[1].close()
                    current = None
                if current is None:
                    current = (signature, open_store(self.directory / state_name(equipment), row), self.factory(equipment))
                    self.stores[equipment] = current
                active.add(equipment)
                _, store, client = current
                self.budget.reconcile(store)
                poll(client.read, store, time.time())
                dispatch(store, client, time.time(), self.budget)
                status['equipment'][equipment] = store.summary()
            except Exception:
                status['equipment'][equipment] = {'health': 'integration_requires_review'}
        for equipment in set(self.stores) - active:
            self.stores.pop(equipment)[1].close()
        return status

    def close(self):
        for _, store, _ in self.stores.values():
            store.close()
        self.budget.close()


def synthetic(directory, client, equipment):
    rows = [r for r in client.discover() if r['equipment_id'] == equipment and r.get('alarm_watch') is True]
    if len(rows) != 1:
        raise ValueError('scope_not_registered')
    store = open_store(directory / ('eq-' + key_for(equipment) + '-synthetic.sqlite'), rows[0], True)
    try:
        fixture = store.get('fixture_time')
        if fixture is None:
            fixture = time.time()
            with store.db:
                store.set('fixture_time', fixture)
        if store.get('fixture_created') is None:
            baseline = [{'metric': m, 'ts': iso(fixture - 3), 'unit': {'boolean': 'bool', 'integer': 'code', 'uint16': 'bitfield'}[kind],
                         'value': None if kind == 'boolean' else 0, 'bool_val': False if kind == 'boolean' else None} for m, kind in sorted(store.profile.items())]
            if store.get('cursor') is None:
                store.seed(baseline, fixture - 2)
            change = dict(baseline[0], ts=iso(fixture - 1))
            change['bool_val' if change['unit'] == 'bool' else 'value'] = True if change['unit'] == 'bool' else 1
            store.apply([change], fixture, time.time())
            with store.db:
                store.set('fixture_created', fixture)
        dispatch(store, client, time.time())
        print(json.dumps(store.summary()))
        print('Admission is not model completion. Verify the synthetic conversation before closing the case.')
    finally:
        store.close()


def main():
    import fcntl
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--synthetic', metavar='EQUIPMENT_ID')
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8'))
    directory = Path(config['state_dir']).resolve(strict=True)
    os.umask(0o077)
    factory = lambda equipment: Client(config, equipment)
    with (directory / ('synthetic.lock' if args.synthetic else 'live.lock')).open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.synthetic:
            synthetic(directory, factory(args.synthetic), args.synthetic)
            return
        worker = Worker(directory, factory)
        try:
            while True:
                try:
                    status = worker.cycle()
                except Exception:
                    status = {'checked_at': time.time(), 'discovery': 'unavailable_no_dispatch', 'equipment': {}}
                temp = directory / 'status.tmp'
                temp.write_text(json.dumps(status, indent=2) + '\n')
                temp.chmod(0o640)
                os.replace(temp, directory / 'discovery-status.json')
                time.sleep(30)
        finally:
            worker.close()


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('WATCHER_STOPPED: inspect sanitized status; raw credentials withheld.') from None
