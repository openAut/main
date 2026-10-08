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
  const ctx = { sessionKey: alarmSession(row), runId: 'fixture-run' };
  const assistant = { role: 'assistant', stopReason: 'stop', content: [{ type: 'text', text: 'Synthetic fixture' }] };
  const event = { success: false, runId: ctx.runId, messages: [assistant] };
  hooks.llm_input({ runId: ctx.runId }, ctx);
  hooks.llm_output({ runId: ctx.runId, lastAssistant: assistant, assistantTexts: ['Synthetic fixture'] }, ctx);
  hooks.agent_end(event, ctx);
  assert.equal(store.nextDelivery(), null);
  event.success = true;
  hooks.llm_input({ runId: ctx.runId }, ctx);
  hooks.llm_output({ runId: ctx.runId, lastAssistant: assistant, assistantTexts: ['Synthetic fixture'] }, ctx);
  hooks.agent_end(event, ctx);
  hooks.agent_end(event, ctx);
  assert.equal(store.db.prepare('SELECT count(*) AS n FROM outbox').get().n, 1);
});

test('historical assistant text and a current tool-only turn never become a new alarm', async t => {
  const {store} = fixture(t); const hooks = {};
  registerWorkflow({ on: (name, fn) => { hooks[name] = fn; }, registerTool() {}, registerService() {}, logger: { error() {} } }, store, {});
  const row = store.openAlarm(JSON.parse(envelope(true).payload.event_json));
  const ctx = { sessionKey: alarmSession(row), runId: 'new-turn' };
  const old = { role: 'assistant', stopReason: 'stop', content: 'Historical answer' };
  const current = { role: 'assistant', stopReason: 'toolUse', content: [{ type: 'toolCall', id: 'call', name: 'openaut_read' }] };
  hooks.llm_input({ runId: ctx.runId }, ctx);
  hooks.llm_output({ runId: ctx.runId, lastAssistant: current, assistantTexts: [] }, ctx);
  hooks.agent_end({ success: true, runId: ctx.runId, messages: [old, { role: 'user', content: 'New question' }, current] }, ctx);
  assert.equal(store.get(row.id).status, 'analysing');
  assert.equal(store.nextDelivery(), null);
  // A callback without current-run output also cannot infer an answer from history.
  hooks.agent_end({ success: true, runId: 'no-output', messages: [old] }, { ...ctx, runId: 'no-output' });
  assert.equal(store.nextDelivery(), null);
});

test('completion/output order can reverse, but the session and run must match', async t => {
  const {store} = fixture(t); const hooks = {};
  registerWorkflow({ on: (name, fn) => { hooks[name] = fn; }, registerTool() {}, registerService() {}, logger: { error() {} } }, store, {});
  const row = store.openAlarm(JSON.parse(envelope(true).payload.event_json));
  const ctx = { sessionKey: alarmSession(row), runId: 'ordered' };
  const output = { runId: ctx.runId, assistantTexts: ['Current answer'],
    lastAssistant: { role: 'assistant', stopReason: 'stop', content: 'Current answer' } };
  hooks.llm_input({ runId: ctx.runId }, ctx);
  hooks.agent_end({ success: true, runId: ctx.runId, messages: [] }, ctx);
  hooks.llm_output(output, { ...ctx, sessionKey: 'another-session' });
  hooks.llm_output({ ...output, runId: 'another-run' }, ctx);
  assert.equal(store.nextDelivery(), null);
  hooks.llm_output(output, ctx);
  assert.equal(store.get(row.id).analysis, 'Current answer');
  assert.equal(store.db.prepare('SELECT count(*) AS n FROM outbox').get().n, 1);
});

test('a retry with no text clears prior attempt output and does not log old DM advice', async t => {
  const {store} = fixture(t); const hooks = {};
  registerWorkflow({ on: (name, fn) => { hooks[name] = fn; }, registerTool() {}, registerService() {}, logger: { error() {} } }, store, {});
  const row = store.openAlarm(JSON.parse(envelope(true).payload.event_json));
  // Fixture binding; this test isolates correlation from the independently tested claim path.
  store.db.prepare('UPDATE cases SET session=? WHERE id=?').run('case-dm', row.id);
  const ctx = { sessionKey: 'case-dm', channel: 'matrix', accountId: 'default', runId: 'retry' };
  hooks.llm_input({ runId: ctx.runId }, ctx);
  hooks.llm_output({ runId: ctx.runId, assistantTexts: ['Old attempt'],
    lastAssistant: { role: 'assistant', stopReason: 'stop', content: 'Old attempt' } }, ctx);
  hooks.llm_input({ runId: ctx.runId }, ctx); // New harness attempt, same run identity.
  hooks.agent_end({ runId: ctx.runId, success: true, messages: [{ role: 'assistant', content: 'Old attempt' }] }, ctx);
  hooks.llm_output({ runId: ctx.runId, assistantTexts: [], lastAssistant: { role: 'assistant', stopReason: 'toolUse' } }, ctx);
  assert.equal(store.db.prepare("SELECT count(*) AS n FROM events WHERE kind='advice'").get().n, 0);
});

test('plugin entry refuses implicit paths and an unprovisioned disabled policy', t => {
  const {root} = fixture(t);
  assert.throws(() => plugin.register({ pluginConfig: {} }), /operator_paths_required/);
  const path = join(root, 'policy.json');
  writeFileSync(path, JSON.stringify({ ...policy, enabled: false }));
  assert.throws(() => plugin.register({ pluginConfig: { policyFile: path, stateDirectory: join(root, 'state') } }), /workflow_not_enabled/);
});
