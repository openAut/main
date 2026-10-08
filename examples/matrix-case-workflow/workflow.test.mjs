import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { Store, digest } from './store.mjs';
import { Workflow } from './workflow.mjs';
import { MatrixTransport } from './transport.mjs';

const policy = { roomId: '!ops:example.test', accountId: 'default',
  technicians: ['@anna:example.test','@bo:example.test'], equipment: ['ta04','ta07'] };
const anna = policy.technicians[0];
const bo = policy.technicians[1];
const event = (id = 'alarm-1', synthetic = false) => ({ event_id: id, synthetic, equipment_id: 'ta04', changes: [{ metric: 'alarm', current: true }] });
function fixture(t) {
  const directory = mkdtempSync(join(tmpdir(), 'openaut-matrix-test-'));
  const store = new Store(directory, structuredClone(policy));
  const sent = [];
  const transport = {
    async verifyPrivateRoom() {},
    async createPrivateRoom(row) { return { roomId: '!dm-' + row.id + ':example.test' }; },
    async send(job) { sent.push(job); return { messageId: '$' + job.id }; },
  };
  t.after(() => { store.close(); rmSync(directory, { recursive: true, force: true }); });
  const flow = new Workflow(store, transport);
  return { store, directory, transport, sent, flow };
}
async function opened(f, id, synthetic = false) {
  const row = f.store.openAlarm(event(id, synthetic));
  f.store.completeAnalysis(row.id, 'Preliminär analys. Kontrollera mätvärdet.');
  await f.flow.flush();
  return f.store.get(row.id);
}
async function assigned(f, id, actor = anna, synthetic = false) {
  const row = await opened(f, id, synthetic);
  f.store.claim(row.id, actor, policy.roomId, '$claim-' + row.id);
  await f.flow.flush();
  return f.store.get(row.id);
}
function report(store, row) {
  const observation = store.history(row).find(x => x.kind === 'observation');
  return { symptom: 'Larm', observations: 'Mätning saknas', checks: 'Kontrollerad källa',
    cause: 'Orsak ej fastställd', cause_status: 'unknown', action: 'Ingen fältändring',
    verification: 'Kan inte verifieras', lesson: 'Kontrollera mätvärde innan slutsats',
    limitations: 'Ett fall; modell/version okänd', evidence: [observation.seq] };
}
function inbound(row, body, actor = anna, room = row.dm, id = '$message') {
  const ctx = { channelId: 'matrix', accountId: 'default', conversationId: room,
    senderId: actor, messageId: id, sessionKey: 'agent:main:matrix:' + room };
  return [{ content: body, senderId: actor, conversationId: room }, ctx];
}

test('full alarm → group → claim → DM → confirmed report → reusable experience', async t => {
  const f = fixture(t);
  const row = await opened(f, 'full');
  const request = inbound(row, 'Jag tar den', anna, policy.roomId, '$take');
  request[0].threadId = row.root;
  assert.equal((await f.flow.inbound(...request)).handled, true);
  await f.flow.flush();
  const claimed = f.store.get(row.id);
  assert.equal(claimed.owner, anna);
  assert.ok(claimed.dm);
  assert.ok(f.sent.some(x => x.kind === 'dm_intro'));
  assert.equal(await f.flow.inbound(...inbound(claimed, 'Jag har kontrollerat givaren.')), undefined);
  const draft = f.store.draft(row.id, anna, claimed.dm, report(f.store, row));
  assert.equal(f.store.search('ta04').length, 0);
  const response = await f.flow.inbound(...inbound(claimed, draft.confirmation, anna, claimed.dm, '$confirm'));
  assert.equal(response.handled, true);
  await f.flow.flush();
  const found = f.store.search('ta04', 'mätvärde');
  assert.equal(found.length, 1);
  assert.equal(found[0].cause_status, 'unknown');
  assert.equal(found[0].trust_level, 'technician_confirmed_case');
  assert.ok(f.sent.some(x => x.kind === 'closed' && x.target === policy.roomId));
  const output = join(f.directory, 'export');
  const manifest = f.store.exportConfirmed(row.id, output);
  assert.equal(manifest.files['report.md'], digest(readFileSync(join(output, 'report.md'))));
  assert.equal(manifest.trust_level, 'quarantine');
  assert.ok(!readFileSync(join(output, 'report.md'), 'utf8').includes('Jag har kontrollerat givaren.'));
});

test('replayed alarms are idempotent but conflicting payloads are refused', async t => {
  const f = fixture(t);
  const a = await opened(f, 'replay');
  assert.equal(f.store.openAlarm(event('replay')).id, a.id);
  f.store.completeAnalysis(a.id, 'En annan analys');
  await f.flow.flush();
  assert.equal(f.sent.filter(x => x.kind === 'alarm').length, 1);
  assert.throws(() => f.store.openAlarm({ ...event('replay'), changes: [] }), /conflicting/);
});

test('two independent SQLite connections cannot both claim an alarm', async t => {
  const f = fixture(t); const row = await opened(f, 'race');
  const other = new Store(f.directory, policy);
  try {
    assert.equal(f.store.claim(row.id, anna, policy.roomId, '$a').claimed, true);
    assert.equal(other.claim(row.id, bo, policy.roomId, '$b').claimed, false);
    assert.equal(other.get(row.id).owner, anna);
    assert.equal(other.db.prepare("SELECT count(*) AS n FROM outbox WHERE kind='create_dm'").get().n, 1);
  } finally { other.close(); }
});

test('unauthorized users, wrong rooms and forged tool actor arguments are denied', async t => {
  const f = fixture(t); const row = await assigned(f, 'access');
  assert.throws(() => f.store.claim(row.id, '@eve:example.test', policy.roomId, '$e'), /authorized/);
  assert.throws(() => f.store.claim(row.id, bo, '!wrong:example.test', '$b'), /operations_room/);
  assert.throws(() => f.store.context(row.id, bo, row.dm), /mismatch/);
  const tool = f.flow.tool({ messageChannel: 'matrix', agentAccountId: 'default',
    nativeChannelId: row.dm, requesterSenderId: anna, sessionKey: 'test' });
  f.store.note(row.id, anna, row.dm, '$n', 'observation', 'test');
  assert.equal((await tool.execute('c', { operation: 'context', actor: bo })).isError, true);
  assert.equal((await tool.execute('c', { operation: 'confirm' })).isError, true);
  assert.equal(f.flow.tool({ messageChannel: 'webchat', requesterSenderId: anna }), null);
  assert.equal(f.flow.tool({ messageChannel: 'matrix', agentAccountId: 'default', nativeChannelId: row.dm, requesterSenderId: bo }), null);
});

test('two cases belonging to one technician get different DM rooms and isolated evidence', async t => {
  const f = fixture(t); const a = await assigned(f, 'a'); const b = await assigned(f, 'b');
  assert.notEqual(a.dm, b.dm);
  f.store.note(a.id, anna, a.dm, '$a', 'secret A', 'session-a');
  f.store.note(b.id, anna, b.dm, '$b', 'secret B', 'session-b');
  assert.throws(() => f.store.note(a.id, anna, b.dm, '$bad', 'text', 'session-b'), /mismatch/);
  assert.ok(!JSON.stringify(f.store.context(b.id, anna, b.dm)).includes('secret A'));
});

test('only actual observation IDs can support drafts; stale confirmation never closes', async t => {
  const f = fixture(t); const row = await assigned(f, 'stale');
  f.store.note(row.id, anna, row.dm, '$a', 'First check', 'session');
  assert.throws(() => f.store.draft(row.id, anna, row.dm, { ...report(f.store, row), evidence: [9999] }), /unproven/);
  const draft = f.store.draft(row.id, anna, row.dm, report(f.store, row));
  f.store.note(row.id, anna, row.dm, '$b', 'Correction', 'session');
  assert.throws(() => f.store.confirm(row.id, anna, row.dm, '$c', draft.hash), /stale/);
  assert.throws(() => f.store.exportConfirmed(row.id, join(f.directory, 'export')), /unconfirmed/);
});

test('synthetic lessons never contaminate live searches; altered files are detected', async t => {
  const f = fixture(t); const row = await assigned(f, 'synthetic', anna, true);
  f.store.note(row.id, anna, row.dm, '$n', 'Synthetic evidence', 'session');
  const draft = f.store.draft(row.id, anna, row.dm, report(f.store, row));
  f.store.confirm(row.id, anna, row.dm, '$c', draft.hash);
  assert.equal(f.store.search('ta04').length, 0);
  assert.equal(f.store.search('ta04', '', true).length, 1);
  writeFileSync(join(f.directory, 'documents', f.store.get(row.id).document), 'changed');
  assert.throws(() => f.store.search('ta04', '', true), /integrity/);
});

test('ambiguous delivery remains uncertain across restart; no blind resend', async t => {
  const f = fixture(t);
  const row = f.store.openAlarm(event('uncertain'));
  f.store.completeAnalysis(row.id, 'Analysis');
  const job = f.store.nextDelivery();
  assert.equal(job.kind, 'alarm');
  const second = new Store(f.directory, policy);
  try {
    second.recover();
    assert.equal(second.nextDelivery(), null);
    assert.equal(second.db.prepare('SELECT state FROM outbox WHERE id=?').get(job.id).state, 'uncertain');
  } finally { second.close(); }
  await f.flow.flush();
  assert.equal(f.sent.length, 0);
});

test('private room membership failure blocks model and case tool', async t => {
  const f = fixture(t); const row = await assigned(f, 'membership');
  f.transport.verifyPrivateRoom = async () => { throw Error('private_room_boundary_failed'); };
  assert.equal((await f.flow.inbound(...inbound(row, 'test'))).handled, true);
  assert.equal(f.store.history(row).filter(x => x.kind === 'observation').length, 0);
  const tool = f.flow.tool({ messageChannel: 'matrix', agentAccountId: 'default', nativeChannelId: row.dm, requesterSenderId: anna });
  assert.equal((await tool.execute('id', { operation: 'context' })).isError, true);
});

test('real Matrix adapter requires exactly bot and owner plus encryption and invite-only rules', async () => {
  const bot = '@advisor:example.test';
  const state = [
    { type: 'm.room.member', state_key: bot, content: { membership: 'join' } },
    { type: 'm.room.member', state_key: anna, content: { membership: 'invite' } },
    { type: 'm.room.encryption', state_key: '', content: { algorithm: 'm.megolm.v1.aes-sha2' } },
    { type: 'm.room.join_rules', state_key: '', content: { join_rule: 'invite' } },
    { type: 'm.room.power_levels', state_key: '', content: { users: { [bot]: 100 }, invite: 100 } },
  ];
  const transport = new MatrixTransport({ ...policy, botUserId: bot, homeserver: 'http://127.0.0.1:18008/' }, {}, 'test-fixture',
    async () => new Response(JSON.stringify(state), { status: 200 }));
  await transport.verifyPrivateRoom('!dm:example.test', anna);
  state.push({ type: 'm.room.member', state_key: bo, content: { membership: 'join' } });
  await assert.rejects(transport.verifyPrivateRoom('!dm:example.test', anna), /boundary/);
  assert.throws(() => new MatrixTransport({ botUserId: bot, homeserver: 'http://matrix.example.test/' }, {}, 'test'), /secure/);
});

test('revoked technicians cannot read, claim, confirm or receive queued private documents', async t => {
  const f = fixture(t); const row = await assigned(f, 'revoke');
  f.store.note(row.id, anna, row.dm, '$n', 'evidence', 'session');
  const draft = f.store.draft(row.id, anna, row.dm, report(f.store, row));
  f.store.policy.technicians = [bo];
  assert.throws(() => f.store.confirm(row.id, anna, row.dm, '$c', draft.hash), /authorized/);
  assert.throws(() => f.store.context(row.id, anna, row.dm), /authorized/);
  await f.flow.flush();
  assert.equal(f.sent.filter(x => x.kind === 'dm_review').length, 0);
});

test('before_dispatch claims from canonical content, not the model envelope, and returns flat text', async t => {
  const f = fixture(t); const row = await opened(f, 'dispatch');
  const [event, ctx] = inbound(row, `Jag tar ${row.id}`, anna, policy.roomId, '$dispatch');
  event.body = '[Transport metadata]\n' + event.content;
  const result = await f.flow.beforeDispatch(event, ctx);
  assert.equal(result.handled, true);
  assert.ok(result.text.includes(row.id));
  assert.equal(result.reply, undefined);
  assert.equal(f.store.get(row.id).owner, anna);
  await f.flow.beforeDispatch(event, ctx);
  assert.equal(f.store.db.prepare("SELECT count(*) AS n FROM outbox WHERE kind='create_dm'").get().n, 1);
});

test('an embedded command in an envelope cannot assign; normal questions and unrelated DMs continue normally', async t => {
  const f = fixture(t); const row = await opened(f, 'envelope');
  const [event, ctx] = inbound(row, 'Vilka system finns?', anna, policy.roomId, '$question');
  event.body = `Jag tar ${row.id}`;
  assert.equal(await f.flow.beforeDispatch(event, ctx), undefined);
  assert.equal(f.store.get(row.id).owner, null);
  const direct = inbound(row, 'Hej', anna, '!unbound:example.test', '$unbound');
  assert.equal(await f.flow.beforeDispatch(...direct), undefined);
});

test('before_dispatch preserves sender authority and never exposes the private case tool in the group', async t => {
  const f = fixture(t); const row = await opened(f, 'dispatch-authority');
  const [event, ctx] = inbound(row, `Jag tar ${row.id}`, anna, policy.roomId, '$spoof');
  ctx.senderId = bo;
  assert.equal((await f.flow.beforeDispatch(event, ctx)).handled, true);
  assert.equal(f.store.get(row.id).owner, null);
  assert.equal(f.flow.tool({ messageChannel: 'matrix', agentAccountId: 'default',
    nativeChannelId: policy.roomId, requesterSenderId: anna }), null);
});

test('closed experience sharing exposes reviewed fields, never another technician raw evidence or hidden search matches', async t => {
  const f = fixture(t); const a = await assigned(f, 'private-source');
  const marker = 'PRIVATE_UNREVIEWED_OBSERVATION';
  f.store.note(a.id, anna, a.dm, '$private', marker, 'private-source-session');
  const draft = f.store.draft(a.id, anna, a.dm, report(f.store, a));
  const preview = f.store.db.prepare("SELECT body FROM outbox WHERE case_id=? AND kind='dm_review'").get(a.id).body;
  assert.equal(preview.includes(marker), false);
  f.store.confirm(a.id, anna, a.dm, '$confirmed', draft.hash);
  const b = await assigned(f, 'other-owner', bo);
  const shared = f.store.context(b.id, bo, b.dm).lessons;
  assert.equal(shared.length, 1);
  assert.equal(shared[0].sha256, draft.hash);
  assert.equal(shared[0].trust_level, 'technician_confirmed_case');
  assert.equal(Object.hasOwn(shared[0], 'evidence_records'), false);
  assert.equal(JSON.stringify(shared).includes(marker), false);
  assert.equal(f.store.search('ta04', marker).length, 0);
  assert.ok(f.store.context(a.id, anna, a.dm).events.some(item => item.body === marker));
  assert.ok(f.store.document(f.store.get(a.id)).evidence_records.some(item => item.body === marker));
});

test('a confirmation on another connection before draft transaction cannot be overwritten', async t => {
  const f = fixture(t); const row = await assigned(f, 'confirmation-race');
  f.store.note(row.id, anna, row.dm, '$first-note', 'Observed', 'race-session');
  const first = f.store.draft(row.id, anna, row.dm, report(f.store, row));
  const other = new Store(f.directory, policy);
  const transaction = f.store.transaction.bind(f.store);
  f.store.transaction = fn => {
    other.confirm(row.id, anna, row.dm, '$race-confirmation', first.hash);
    return transaction(fn);
  };
  try {
    assert.throws(() => f.store.draft(row.id, anna, row.dm, report(f.store, row)), /case_not_investigating/);
    const after = other.get(row.id);
    assert.equal(after.status, 'closed');
    assert.equal(after.document_hash, first.hash);
    assert.equal(after.revision, 1);
    assert.equal(after.confirmed_by, anna);
  } finally { other.close(); }
});

test('draft holds its writer lock during evidence validation; a later observation invalidates the draft', async t => {
  const f = fixture(t); const row = await assigned(f, 'observation-race');
  f.store.note(row.id, anna, row.dm, '$initial-observation', 'Observed', 'race-session');
  const proposal = report(f.store, row);
  const other = new Store(f.directory, policy);
  other.db.exec('PRAGMA busy_timeout=0');
  const history = f.store.history.bind(f.store);
  f.store.history = target => {
    assert.throws(() => other.note(row.id, anna, row.dm, '$concurrent', 'New information', 'race-session'), /locked/);
    return history(target);
  };
  try {
    const draft = f.store.draft(row.id, anna, row.dm, proposal);
    other.note(row.id, anna, row.dm, '$after-commit', 'New information', 'race-session');
    assert.equal(other.get(row.id).status, 'investigating');
    assert.equal(other.get(row.id).document_hash, null);
    assert.throws(() => other.confirm(row.id, anna, row.dm, '$stale', draft.hash), /stale_confirmation/);
  } finally { other.close(); }
});

test('revoked equipment is parked with audit while later authorized deliveries continue', async t => {
  const f = fixture(t);
  const retired = f.store.openAlarm({ ...event('retired'), equipment_id: 'ta04' });
  f.store.completeAnalysis(retired.id, 'Retired equipment fixture');
  const allowed = f.store.openAlarm({ ...event('allowed'), equipment_id: 'ta07' });
  f.store.completeAnalysis(allowed.id, 'Allowed equipment fixture');
  f.store.db.prepare("UPDATE outbox SET created='2000-01-01T00:00:00Z' WHERE case_id=?").run(retired.id);
  f.store.policy.equipment = ['ta07'];
  await f.flow.flush();
  assert.equal(f.store.db.prepare('SELECT state FROM outbox WHERE case_id=?').get(retired.id).state, 'blocked');
  assert.equal(f.store.db.prepare('SELECT state FROM outbox WHERE case_id=?').get(allowed.id).state, 'sent');
  assert.equal(f.sent.length, 1);
  assert.equal(f.store.db.prepare("SELECT body FROM events WHERE case_id=? AND kind='delivery_blocked'").get(retired.id).body, 'equipment_scope_revoked');
  f.store.policy.equipment = ['ta04', 'ta07'];
  await f.flow.flush();
  assert.equal(f.sent.length, 1); // Reauthorization is not permission to replay a parked job.
});
