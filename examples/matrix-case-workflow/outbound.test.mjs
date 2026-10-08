import test from 'node:test';
import assert from 'node:assert/strict';
import { MatrixTransport } from './transport.mjs';

const policy = { roomId: '!ops:example.test', accountId: 'default', botUserId: '@advisor:example.test',
  homeserver: 'https://matrix.example.test/', equipment: ['ahu-demo'], technicians: ['@technician:example.test'] };
const row = { id: 'F-test', room: policy.roomId, equipment: 'ahu-demo', owner: policy.technicians[0],
  dm: '!dm:example.test', root: '$root' };
const job = { id: 'outbox-test', case_id: row.id, kind: 'alarm', target: row.room, body: 'Synthetic fixture' };
function fixture() {
  const sent = [];
  const cfg = { channels: { matrix: { enabled: true, encryption: true, userId: policy.botUserId, homeserver: policy.homeserver } } };
  const adapter = { async sendText(ctx) { sent.push(ctx); return { channel: 'matrix', messageId: '$receipt', target: { kind: 'room', id: ctx.to } }; } };
  const transport = new MatrixTransport(policy, { loadAdapter: async channel => { assert.equal(channel, 'matrix'); return adapter; },
    getConfig: () => cfg }, 'fixture-only');
  return { transport, cfg, sent, adapter };
}

test('public adapter receives exact account/room/body without Gateway scopes or host queue impersonation', async () => {
  const f = fixture();
  assert.deepEqual(await f.transport.send(job, row), { messageId: '$receipt' });
  assert.deepEqual(Object.keys(f.sent[0]).sort(), ['accountId','cfg','text','to']);
  assert.equal(f.sent[0].to, policy.roomId);
  assert.equal(f.sent[0].text, job.body);
});

test('only confirmed root threads are used for status notices', async () => {
  const f = fixture();
  await f.transport.send({ ...job, kind: 'assigned' }, row);
  assert.equal(f.sent[0].threadId, '$root');
  await assert.rejects(f.transport.send({ ...job, kind: 'closed' }, { ...row, root: null }), /thread/);
  assert.equal(f.sent.length, 1);
});

test('wrong target, equipment, account identity and disabled encryption cause no send', async () => {
  const f = fixture();
  await assert.rejects(f.transport.send({ ...job, target: '!other:example.test' }, row), /scope/);
  await assert.rejects(f.transport.send(job, { ...row, equipment: 'other' }), /scope/);
  f.cfg.channels.matrix.accounts = { default: { userId: '@other:example.test' } };
  await assert.rejects(f.transport.send(job, row), /policy_changed/);
  delete f.cfg.channels.matrix.accounts;
  f.cfg.channels.matrix.encryption = false;
  await assert.rejects(f.transport.send(job, row), /policy_changed/);
  assert.equal(f.sent.length, 0);
});

test('private sends check exact membership before sending', async () => {
  const f = fixture();
  f.transport.verifyPrivateRoom = async (room, owner) => {
    assert.equal(room, row.dm); assert.equal(owner, row.owner); throw Error('membership_changed');
  };
  await assert.rejects(f.transport.send({ ...job, kind: 'dm_intro', target: row.dm }, row), /membership_changed/);
  assert.equal(f.sent.length, 0);
});

test('a bad receipt or transport failure is not automatically retried', async () => {
  const f = fixture();
  let attempts = 0;
  f.adapter.sendText = async () => { attempts++; return { channel: 'matrix', messageId: '$wrong-room', target: { kind: 'room', id: '!other:example.test' } }; };
  await assert.rejects(f.transport.send(job, row), /receipt_unconfirmed/);
  assert.equal(attempts, 1);
  f.adapter.sendText = async () => { attempts++; throw Error('ambiguous_network_failure'); };
  await assert.rejects(f.transport.send(job, row), /ambiguous_network_failure/);
  assert.equal(attempts, 2);
});
