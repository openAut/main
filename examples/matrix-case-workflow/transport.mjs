// The Matrix plugin owns messaging/E2EE. This adapter only creates restricted rooms
// and verifies membership through the Client-Server API, with the same bot identity.
export class MatrixTransport {
  constructor(policy, outbound, token, fetcher = fetch) {
    if (!token || !policy.botUserId?.startsWith('@')) throw Error('matrix_credentials_missing');
    const url = new URL(policy.homeserver);
    const localTunnel = url.protocol === 'http:' && url.hostname === '127.0.0.1';
    if ((!localTunnel && url.protocol !== 'https:') || url.username || url.password || url.pathname !== '/') throw Error('secure_homeserver_required');
    this.policy = policy; this.outbound = outbound; this.token = token; this.fetcher = fetcher;
  }
  async request(method, path, body) {
    const response = await this.fetcher(new URL('/_matrix/client/v3/' + path, this.policy.homeserver), {
      method, redirect: 'error', signal: AbortSignal.timeout(15000),
      headers: { Authorization: 'Bearer ' + this.token, 'Content-Type': 'application/json' },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    if (!response.ok) throw Error('matrix_request_failed');
    const buffer = await response.arrayBuffer();
    if (buffer.byteLength > 512 * 1024) throw Error('matrix_response_too_large');
    return JSON.parse(new TextDecoder().decode(buffer));
  }
  async createPrivateRoom(row) {
    const result = await this.request('POST', 'createRoom', {
      visibility: 'private', preset: 'private_chat', is_direct: true,
      name: `${row.id} · ${row.equipment}`, invite: [row.owner],
      creation_content: { 'm.federate': false },
      power_level_content_override: { users: { [this.policy.botUserId]: 100 }, users_default: 0,
        events_default: 0, state_default: 100, invite: 100, kick: 100, ban: 100, redact: 100 },
      initial_state: [
        { type: 'm.room.encryption', state_key: '', content: { algorithm: 'm.megolm.v1.aes-sha2' } },
        { type: 'm.room.history_visibility', state_key: '', content: { history_visibility: 'joined' } },
      ],
    });
    await this.verifyPrivateRoom(result.room_id, row.owner);
    // Explicit direct-room discovery; preserve the account's other direct rooms.
    const path = `user/${encodeURIComponent(this.policy.botUserId)}/account_data/m.direct`;
    let direct;
    // Missing initial m.direct is normal. Other failures must remain visible.
    const response = await this.fetcher(new URL('/_matrix/client/v3/' + path, this.policy.homeserver), {
      headers: { Authorization: 'Bearer ' + this.token }, redirect: 'error', signal: AbortSignal.timeout(15000),
    });
    if (response.status === 404) direct = {};
    else if (response.ok) direct = await response.json();
    else throw Error('direct_room_registry_unavailable');
    direct[row.owner] = [...new Set([...(direct[row.owner] ?? []), result.room_id])];
    await this.request('PUT', path, direct);
    return { roomId: result.room_id };
  }
  async verifyPrivateRoom(room, owner) {
    if (!/^![^\s:]+:[^\s]+$/.test(room || '')) throw Error('invalid_room');
    const state = await this.request('GET', `rooms/${encodeURIComponent(room)}/state`);
    const members = state.filter(x => x.type === 'm.room.member' && ['join','invite'].includes(x.content?.membership));
    const allowed = [this.policy.botUserId, owner];
    const encryption = state.find(x => x.type === 'm.room.encryption' && x.state_key === '');
    const joinRule = state.find(x => x.type === 'm.room.join_rules' && x.state_key === '');
    const levels = state.find(x => x.type === 'm.room.power_levels' && x.state_key === '')?.content;
    if (members.length !== 2 || members.some(x => !allowed.includes(x.state_key)) ||
        !allowed.every(x => members.some(y => y.state_key === x)) ||
        encryption?.content?.algorithm !== 'm.megolm.v1.aes-sha2' || joinRule?.content?.join_rule !== 'invite' ||
        !levels || levels.invite !== 100 || (levels.users?.[owner] ?? levels.users_default ?? 0) !== 0 ||
        levels.users?.[this.policy.botUserId] !== 100) throw Error('private_room_boundary_failed');
  }
  async send(job, row) {
    const group = ['alarm', 'assigned', 'closed'].includes(job.kind);
    const direct = ['dm_intro', 'dm_review'].includes(job.kind);
    if (job.case_id !== row.id || row.room !== this.policy.roomId ||
        !this.policy.equipment.includes(row.equipment) || (!group && !direct) ||
        (group ? job.target !== this.policy.roomId : !row.dm || job.target !== row.dm ||
          !this.policy.technicians.includes(row.owner))) throw Error('outbound_target_out_of_scope');
    if (typeof job.body !== 'string' || !job.body.trim() || job.body.length > 12000) throw Error('invalid_outbound_text');
    if (['assigned', 'closed'].includes(job.kind) && !row.root?.startsWith('$')) throw Error('alarm_thread_not_confirmed');
    const adapter = await this.outbound.loadAdapter('matrix');
    if (typeof adapter?.sendText !== 'function') throw Error('matrix_outbound_adapter_unavailable');
    const cfg = this.outbound.getConfig();
    const base = cfg?.channels?.matrix;
    const account = { ...base, ...base?.accounts?.[this.policy.accountId] };
    if (base?.enabled !== true || account.enabled !== true || account.encryption !== true ||
        account.userId !== this.policy.botUserId || account.homeserver !== this.policy.homeserver) {
      throw Error('matrix_account_policy_changed');
    }
    if (direct) await this.verifyPrivateRoom(job.target, row.owner);
    // This is the public channel send primitive, not an operator Gateway RPC. Our SQLite
    // outbox owns retries; do not invent a core deliveryQueueId or grant operator scopes.
    const result = await adapter.sendText({
      cfg, accountId: this.policy.accountId, to: job.target, text: job.body,
      ...(['assigned', 'closed'].includes(job.kind) ? { threadId: row.root } : {}),
    });
    const messageId = result?.primaryMessageId ?? result?.receipt?.primaryPlatformMessageId ?? result?.messageId;
    if (result?.channel !== 'matrix' || result?.target?.kind !== 'room' || result.target.id !== job.target ||
        typeof messageId !== 'string' || !/^\$[^\s]{1,254}$/.test(messageId)) throw Error('matrix_outbound_receipt_unconfirmed');
    return { messageId };
  }
}
