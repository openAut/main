import datetime as dt
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1] / 'deploy/advisor-discovery'


def load(name):
    spec = importlib.util.spec_from_file_location('discovery_' + name, ROOT / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reader, engine, integration = load('reader'), load('engine'), load('integration')
with patch.dict(sys.modules, {'engine': engine}):
    worker = load('worker')


def equipment(key='ahu-03'):
    return {'equipment_id': key, 'site': 'site-a', 'node': 'edge-a', 'telemetry_system': key,
            'name': 'Fixture AHU', 'alarm_watch': True, 'alarm_metrics': {'fault_flags': 'uint16'}}


def row(ts, value, metric='fault_flags'):
    return {'metric': metric, 'ts': engine.iso(ts), 'value': value, 'bool_val': None, 'unit': 'bitfield'}


@pytest.fixture
def store(tmp_path):
    value = engine.Store(tmp_path / worker.state_name('ahu-03'), equipment_id='ahu-03', alarm_metrics={'fault_flags':'uint16'}, binding='site-a/edge-a/ahu-03')
    value.seed([row(999, 0)], 1000)
    value.health('healthy', 1000)
    yield value
    value.close()


@pytest.mark.parametrize('operation', ['equipment','points','latest','health','alarms','documents','document_passage'])
def test_scope_denied_before_data_or_document_queries(operation):
    class Backend(reader.Reader):
        def query(self, sql, params=()):
            assert 'advisor_read.equipment' in sql
            return []
    args = {'equipment_id':'outside-area'}
    if operation == 'document_passage': args['document_id'] = 'known-doc'
    with pytest.raises(reader.ReadError) as exc:
        Backend({}).execute(operation, args)
    assert exc.value.status == 403


def test_discovery_pagination_and_new_system():
    class Backend(reader.Reader):
        def query(self, sql, params=()):
            if 'COLLATE "C"' in sql:
                return [equipment(k) for k in ['ahu-01','ahu-02','ahu-03'] if k > params[0]][:params[1]]
            return [equipment()] if params == ('ahu-03',) else []
    backend = Backend({})
    first = backend.execute('list_equipment', {'limit':'2'})
    second = backend.execute('list_equipment', {'after':first['next_after']})
    assert first['next_after'] == 'ahu-02' and second['next_after'] is None
    assert second['equipment'][0]['equipment_id'] == 'ahu-03'
    assert backend.execute('equipment', {'equipment_id':'ahu-03'})['equipment'][0]['site'] == 'site-a'


def test_history_limits_and_extra_arguments():
    now = dt.datetime(2030, 1, 8, tzinfo=dt.timezone.utc)
    valid = {'equipment_id':'ahu-03','metrics':'supply_temp','start':'2030-01-01T00:00:00Z','end':'2030-01-08T00:00:00Z','limit':'500'}
    assert reader.validate('history',valid,now)['limit'] == 500
    for change in [{'metrics':'x;SELECT'}, {'limit':'501'}, {'start':'2030-01-01T00:00:00'},
                   {'start':'2029-12-31T00:00:00Z'}, {'sql':'SELECT 1'}]:
        with pytest.raises(reader.ReadError): reader.validate('history',{**valid,**change},now)
    with pytest.raises(reader.ReadError): reader.validate('list_equipment',{'equipment_id':'ahu-03'},now)


def test_forge_document_identity_integrity_and_code_as_data():
    blob = b'raise RuntimeError("reference data, never execute")\n'
    doc = {'equipment_id':'ahu-03','trust_level':'verified','forge_commit':'a'*40,
           'sha256':hashlib.sha256(blob).hexdigest(),'authorized_repository':'manuals',
           'uri':'forge://openaut/manuals/fixture.py?commit='+'a'*40}
    backend = reader.Reader({'forge_origin':'https://forge.example.invalid','forge_token_file':'fixture-token-file'})
    class Opener:
        def open(self, request, timeout):
            assert request.full_url.startswith('https://forge.example.invalid/api/v1/repos/openaut/manuals/raw/')
            return io.BytesIO(blob)
    backend.http = Opener()
    with patch.object(Path, 'read_text', return_value='synthetic-fixture-token'):
        lines, quality = backend.text(doc,'ahu-03')
        assert lines[0].startswith('raise RuntimeError') and quality == 'verified_source_text'
        with pytest.raises(reader.ReadError): backend.text({**doc,'sha256':'b'*64},'ahu-03')
    for change in [{'equipment_id':'other'}, {'trust_level':'quarantine'}, {'authorized_repository':'different'},
                   {'uri':doc['uri'].replace('fixture.py','../fixture.py')}, {'forge_commit':'main'}]:
        with pytest.raises(reader.ReadError): reader.document_target({**doc,**change},'ahu-03')


def test_heartbeat_and_cov_are_distinct():
    now = dt.datetime(2030,1,8,tzinfo=dt.timezone.utc)
    rows = [{'metric':'field_protocol_last_success_unixtime','ts':now,'value':now.timestamp()},
            {'metric':'field_protocol_healthy','ts':now-dt.timedelta(days=3),'bool_val':True}]
    assert reader.health(rows,now)['state'] == 'healthy'
    assert reader.health(rows,now+dt.timedelta(seconds=121))['state'] == 'stale'
    assert reader.health(rows,now-dt.timedelta(seconds=31))['state'] == 'clock_skew'


def test_http_auth_duplicate_scope_and_writes():
    class Backend:
        config = {'api_token_sha256':hashlib.sha256(b'synthetic').hexdigest()}
        def execute(self, action, args):
            reader.validate(action,args,reader.utcnow())
            return {'equipment_id':args['equipment_id']}
    server = reader.Server(('127.0.0.1',0),reader.Handler)
    server.reader = Backend()
    thread = threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        def status(query, token='synthetic', method='GET'):
            request=Request(f'http://127.0.0.1:{server.server_port}/v1/latest?'+query,
                            headers={'Authorization':'Bearer '+token},method=method)
            try:
                with urlopen(request,timeout=3) as response: return response.status
            except HTTPError as exc: return exc.code
        assert status('equipment_id=ahu-03') == 200
        assert status('equipment_id=ahu-03',token='invalid') == 401
        assert status('equipment_id=ahu-03&equipment_id=other') == 400
        for method in ('POST','PUT','PATCH','DELETE'):
            assert status('equipment_id=ahu-03',method=method) == 405
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=3)


def test_repeated_transition_return_and_restart(store):
    store.apply([row(1001,1),row(1002,0)],1003,1004)
    store.apply([row(1001,1),row(1002,0)],1003,1005)
    batch=store.next_batch(1006)
    event=json.loads(json.loads(batch['payload'])['event_json'])
    assert [c['current'] for c in event['changes']] == [1,0]
    store.sending(batch['id'],1006)
    store.finish(batch['id'],'admitted','fixture-receipt')
    assert store.next_batch(5000) is None


@pytest.mark.parametrize('state', ['sending','admitted'])
def test_restart_never_blindly_resends(tmp_path,state):
    path=tmp_path/'state.sqlite'
    args={'equipment_id':'ahu-03','alarm_metrics':{'fault_flags':'uint16'},'binding':'binding'}
    current=engine.Store(path,**args)
    current.seed([row(999,0)],1000); current.apply([row(1001,1)],1002,1003)
    batch=current.next_batch(1004); current.sending(batch['id'],1004)
    if state=='admitted': current.finish(batch['id'],'admitted','fixture')
    current.close()
    current=engine.Store(path,**args)
    try:
        assert current.summary()['batches'] == {('uncertain' if state=='sending' else 'admitted'):1}
        assert current.next_batch(5000) is None
    finally: current.close()


def test_malformed_data_is_atomic_and_late_data_does_not_reverse_state(store):
    with pytest.raises(engine.DataError): store.apply([row(1001,1),row(1002,-1)],1003,1004)
    assert store.get('cursor') == 1000
    store.apply([row(1010,0)],1020,1021)
    store.apply([row(1005,1)],1030,1031)
    assert json.loads(store.db.execute('SELECT value FROM points').fetchone()[0]) == 0
    assert store.summary()['unbatched_events'] == 1


def test_incomplete_history_and_scope_do_not_advance(store):
    def read(operation,args):
        if operation=='alarms':
            return {'equipment_id':'ahu-03','queried_at':engine.iso(1100),'health':{'state':'healthy'},'readings':[row(999,0)]}
        return {'equipment_id':'ahu-03','readings':[],'truncated':True}
    engine.poll(read,store,1100)
    assert store.get('cursor') == 1000 and store.get('health') == 'history_backpressure'


def test_binding_or_profile_change_requires_review(tmp_path):
    path=tmp_path/'state.sqlite'
    args={'equipment_id':'ahu-03','alarm_metrics':{'fault_flags':'uint16'},'binding':'first'}
    engine.Store(path,**args).close()
    for change in [{'binding':'other'}, {'equipment_id':'other'}, {'synthetic':True}, {'alarm_metrics':{'different':'boolean'}}]:
        with pytest.raises(engine.DataError): engine.Store(path,**{**args,**change})


def test_global_budget_survives_removed_equipment_and_reservation_crash(tmp_path,store):
    budget=worker.Budget(tmp_path)
    for i in range(6): assert budget.reserve('retired',str(i),1000+i*61)
    budget.close()
    budget=worker.Budget(tmp_path)
    assert not budget.reserve('new','event',1500)
    store.apply([row(1001,1)],1002,1003)
    batch=store.next_batch(4700)
    assert budget.reserve(store.equipment_id,batch['id'],4700)
    budget.reconcile(store)
    assert store.summary()['batches'] == {'uncertain':1}
    budget.close()


def test_discovery_revocation_and_unavailability_preserve_state(tmp_path):
    now=time.time()
    class Client:
        rows=[equipment()]
        unavailable=False
        def __init__(self,equipment): self.equipment=equipment
        def discover(self):
            if self.unavailable: raise OSError('fixture outage')
            return self.rows
        def read(self,operation,args):
            if operation=='alarms': return {'equipment_id':self.equipment,'queried_at':engine.iso(time.time()),'health':{'state':'healthy'},'readings':[row(now-10,0)]}
            return {'equipment_id':self.equipment,'readings':[],'truncated':False}
        def ready(self): return True
        def send(self,*args): raise AssertionError('no unchanged baseline should be dispatched')
    instance=worker.Worker(tmp_path,Client)
    try:
        assert instance.cycle()['equipment']['ahu-03']['health']=='healthy'
        baseline=instance.stores['ahu-03'][1].get('initial_baseline_at')
        Client.rows=[]
        assert instance.cycle()['equipment']=={} and instance.stores=={}
        Client.rows=[equipment()]; instance.cycle()
        assert instance.stores['ahu-03'][1].get('initial_baseline_at')==baseline
        Client.unavailable=True
        with pytest.raises(OSError): instance.cycle()
    finally: instance.close()


def test_engineer_artifact_and_contract_validation():
    artifact=b'{"synthetic_fixture":true}\n'
    contract={'equipment_id':'ahu-03','node':'edge-a','telemetry_system':'ahu-03','alarm_watch':True,
              'alarm_metrics':{'fault_flags':'uint16'},'artifact_sha256':hashlib.sha256(artifact).hexdigest()}
    assert integration.validate_contract(contract,artifact)==contract
    for patch in [{'artifact_sha256':'0'*64},{'alarm_metrics':{}},{'alarm_metrics':{'fault_flags':None}},{'site':'other'}]:
        with pytest.raises(ValueError): integration.validate_contract({**contract,**patch},artifact)


@pytest.mark.parametrize('kind,unit,value,boolean,accepted', [
    ('boolean','bool',None,False,True), ('boolean','bool',None,1,False),
    ('integer','code',-32768,None,True), ('integer','count',65535,None,True),
    ('integer','count',65536,None,False), ('integer','code',1.5,None,False),
    ('integer','bitfield',1,None,False), ('uint16','bitfield',65535,None,True),
    ('uint16','bitfield',-1,None,False),
])
def test_declared_alarm_type_and_range(kind,unit,value,boolean,accepted):
    reading={'metric':'signal','ts':engine.iso(99),'unit':unit,'value':value,'bool_val':boolean}
    if accepted:
        assert engine.alarm_row(reading,100,{'signal':kind})[0]=='signal'
    else:
        with pytest.raises(engine.DataError): engine.alarm_row(reading,100,{'signal':kind})


def test_legacy_state_is_refused_without_erasing_evidence(tmp_path):
    old=tmp_path/'legacy.sqlite'
    old.write_bytes(b'fixture evidence from a prior namespace')
    with pytest.raises(ValueError,match='requires_migration'):
        worker.Budget(tmp_path)
    assert old.read_bytes()==b'fixture evidence from a prior namespace'


def test_normalized_communication_alarm_is_not_a_transport_outage(tmp_path):
    store=engine.Store(tmp_path/'fixture.sqlite',equipment_id='ahu-03',alarm_metrics={'comm_alarm':'boolean'},binding='fixture')
    try:
        baseline={'metric':'comm_alarm','ts':engine.iso(999),'bool_val':False,'unit':'bool'}
        store.seed([baseline],1000)
        store.apply([{**baseline,'ts':engine.iso(1001),'bool_val':True}],1002,1003)
        value=json.loads(json.loads(store.next_batch(1004)['payload'])['event_json'])
        assert value['changes'][0]['kind']=='equipment_communication_alarm'
    finally: store.close()
