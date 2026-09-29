import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import plugin, { registerWorkflow } from './index.mjs';
import { Store } from './store.mjs';
import { alarmSession } from './workflow.mjs';
import { createCaseTransform } from './alarm-transform.mjs';

const policy = { enabled: true, roomId: '!ops:example.test', accountId: 'default',
  equipment: ['ahu-demo'], technicians: ['@technician:example.test'] };
function fixture(t) {
  const root = mkdtempSync(join(tmpdir(), 'openaut-integration-'));
  const store = new Store(root, policy);
  t.after(() => { store.close(); rmSync(root, { recursive: true, force: true }); });
  return { root, store };
}
const envelope = synthetic => ({ payload: { event_json: JSON.stringify({
  equipment_id: 'ahu-demo', synthetic, event_id: 'fixture-event',
}) } });

test('case transform validates first and leaves live routing untouched by default', async t => {
  const {store} = fixture(t);
  const result = { message: 'Validated input', sessionKey: 'original', deliver: false };
  const denied = createCaseTransform(async () => { throw Error('scope_denied'); }, store);
  await assert.rejects(denied(envelope(true)), /scope_denied/);
  assert.equal(store.db.prepare('SELECT count(*) AS n FROM cases').get().n, 0);
  const transform = createCaseTransform(async () => result, store);
  assert.equal(await transform(envelope(false)), result);
  assert.equal(store.db.prepare('SELECT count(*) AS n FROM cases').get().n, 0);
  const transformed = await transform(envelope(true));
  const row = store.db.prepare('SELECT * FROM cases').get();
  assert.equal(transformed.sessionKey, alarmSession(row));
  assert.equal(transformed.deliver, false);
});

test('failed model completion cannot queue an alarm; successful completion is idempotent', async t => {
  const {store} = fixture(t);
  const hooks = {};
  const api = { on(name, fn) { hooks[name] = fn; }, registerTool() {}, registerService() {}, logger: { error() {} } };
  registerWorkflow(api, store, {});
  assert.equal(typeof hooks.before_dispatch, 'function');
  assert.equal(hooks.inbound_claim, undefined);
  const row = store.openAlarm(JSON.parse(envelope(true).payload.event_json));
  const event = { success: false, messages: [{ role: 'assistant', content: [{ type: 'text', text: 'Synthetic fixture' }] }] };
  hooks.agent_end(event, { sessionKey: alarmSession(row) });
  assert.equal(store.nextDelivery(), null);
  event.success = true;
  hooks.agent_end(event, { sessionKey: alarmSession(row) });
  hooks.agent_end(event, { sessionKey: alarmSession(row) });
  assert.equal(store.db.prepare('SELECT count(*) AS n FROM outbox').get().n, 1);
});

test('plugin entry refuses implicit paths and an unprovisioned disabled policy', t => {
  const {root} = fixture(t);
  assert.throws(() => plugin.register({ pluginConfig: {} }), /operator_paths_required/);
  const path = join(root, 'policy.json');
  writeFileSync(path, JSON.stringify({ ...policy, enabled: false }));
  assert.throws(() => plugin.register({ pluginConfig: { policyFile: path, stateDirectory: join(root, 'state') } }), /workflow_not_enabled/);
});
