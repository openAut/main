import { digest } from './store.mjs';

const casePattern = 'F-[a-f0-9]{20}';
const denied = text => ({ handled: true, reply: { text } });

// Channel facts are host-supplied; no actor/room/approval identity is accepted from tools.
export function identity(event, ctx, policy) {
  if (ctx.channelId !== 'matrix' || ctx.accountId !== policy.accountId ||
      !ctx.senderId || event.senderId !== ctx.senderId || !ctx.conversationId ||
      (event.conversationId && event.conversationId !== ctx.conversationId)) throw Error('untrusted_matrix_context');
  return { actor: ctx.senderId, room: ctx.conversationId, session: ctx.sessionKey,
    eventId: ctx.messageId || event.messageId };
}

export class Workflow {
  constructor(store, transport) { this.store = store; this.transport = transport; this.busy = false; }
  async beforeDispatch(event, ctx) {
    if (ctx.channelId !== 'matrix' || ctx.accountId !== this.store.policy.accountId) return;
    // Only this workflow's operations room and bound case DMs are owned here.
    // Keep unrelated allowed Advisor DMs on their normal read-only route.
    try {
      if (ctx.conversationId !== this.store.policy.roomId && !this.store.caseForDm(ctx.conversationId)) return;
    } catch {
      return { handled: true, text: 'Ärendet är inte tillgängligt i denna dialog.' };
    }
    if (typeof event.content !== 'string') return { handled: true, text: 'Meddelandets ursprungliga text saknas. Skicka ett nytt textmeddelande.' };
    // before_dispatch.content is BodyForCommands/RawBody; body may contain the model envelope.
    const result = await this.inbound({ ...event, body: event.content }, ctx);
    if (result?.handled) return { handled: true, ...(result.reply?.text ? { text: result.reply.text } : {}) };
  }
  async inbound(event, ctx) {
    if (ctx.channelId !== 'matrix' || ctx.accountId !== this.store.policy.accountId) return;
    try {
      const who = identity(event, ctx, this.store.policy);
      this.store.authorize(who.actor);
      if (!who.eventId) throw Error('missing_event_identity');
      const body = (event.body ?? event.content ?? '').trim();
      if (!body || body.length > 12000) return denied('Skicka en textobservation på högst 12 000 tecken.');
      if (event.providerUpdate?.editedTimestamp || event.metadata?.isEdit) return denied('Skicka rättelsen som ett nytt meddelande för spårbarhet.');
      if (who.room === this.store.policy.roomId) {
        const match = body.match(new RegExp(`^jag tar (den|${casePattern})[.!]?$`, 'i'));
        if (!match) return; // Ordinary group questions still reach read-only Advisor.
        const root = event.threadId || ctx.replyToIdFull || ctx.replyToId || event.replyToId;
        const id = match[1].toLowerCase() === 'den' ? this.store.caseForRoot(root)?.id
          : 'F-' + match[1].slice(2).toLowerCase();
        if (!id) return denied('Svara i rätt larmtråd, eller skriv ”Jag tar F-…” med hela ärende-ID:t.');
        const result = this.store.claim(id, who.actor, who.room, who.eventId);
        return denied(result.claimed ? `${id} är tilldelat dig. Advisor förbereder en egen DM för ärendet.`
          : `${id} har redan tagits av ${result.owner}.`);
      }
      const row = this.store.caseForDm(who.room);
      if (!row) return denied('Denna POC använder ärendets privata felsökningsrum. Ta ett larm i driftrummet först.');
      this.store.privateCase(who.actor, who.room, row.id);
      // Recheck members on every incoming turn, not only when creating the room.
      await this.transport.verifyPrivateRoom(who.room, who.actor);
      const confirmation = body.match(new RegExp(`^Bekräfta (${casePattern}) ([a-f0-9]{64})$`, 'i'));
      if (confirmation) {
        if (confirmation[1] !== row.id) throw Error('confirmation_case_mismatch');
        this.store.confirm(row.id, who.actor, who.room, who.eventId, confirmation[2]);
        return denied(`${row.id} avslutat. Rapport och lessons learned är teknik­erbekräftade i den lokala POC-kunskapsbanken.`);
      }
      if (row.status === 'closed') return denied('Ärendet är avslutat. Nya larm får ett nytt ärende.');
      if (!this.store.note(row.id, who.actor, who.room, who.eventId, body, who.session)) return { handled: true };
      return; // Advisor responds using only its read tools and the bounded case tool.
    } catch (error) {
      return denied(`Ärendeåtgärden kunde inte genomföras (${error.message}). Ingen behörighet eller fältåtgärd har godkänts.`);
    }
  }
  async flush() {
    if (this.busy) return;
    this.busy = true;
    try {
      // Bound one cycle; never replay unknown side effects after a restart.
      for (let i = 0; i < 8; i++) {
        const job = this.store.nextDelivery();
        if (!job) break;
        try {
          const row = this.store.get(job.case_id);
          const receipt = job.kind === 'create_dm'
            ? await this.transport.createPrivateRoom(row)
            : await this.transport.send(job, row);
          this.store.delivered(job, receipt);
        } catch {
          this.store.uncertain(job);
        }
      }
    } finally { this.busy = false; }
  }
  tool(ctx) {
    const policy = this.store.policy;
    if (ctx.messageChannel !== 'matrix' || ctx.agentAccountId !== policy.accountId ||
        !ctx.nativeChannelId || !ctx.requesterSenderId) return null;
    const room = ctx.nativeChannelId;
    const row = this.store.caseForDm(room);
    if (!row) return null;
    try { this.store.privateCase(ctx.requesterSenderId, room, row.id); } catch { return null; }
    return {
      name: 'openaut_case', label: 'openAut felsökningsärende',
      description: 'Läs ärendets evidens och tidigare erfarenhetsfall eller skapa rapportutkast. Kan aldrig bekräfta, godkänna eller utföra fältåtgärder. Identitet och ärende binds av värden.',
      parameters: { type: 'object', additionalProperties: false, required: ['operation'], properties: {
        operation: { type: 'string', enum: ['context', 'draft', 'lessons'] },
        query: { type: 'string', maxLength: 200 },
        report: { type: 'object', additionalProperties: false,
          required: ['symptom','observations','checks','cause','action','verification','lesson','limitations','cause_status','evidence'],
          properties: { ...Object.fromEntries(['symptom','observations','checks','cause','action','verification','lesson','limitations']
            .map(k => [k, { type: 'string', minLength: 1, maxLength: 1000 }])),
          cause_status: { type: 'string', enum: ['confirmed','probable','unknown'] },
          evidence: { type: 'array', minItems: 1, maxItems: 100, items: { type: 'integer' } } } },
      } },
      execute: async (_callId, args) => {
        try {
          await this.transport.verifyPrivateRoom(room, ctx.requesterSenderId);
          const current = this.store.privateCase(ctx.requesterSenderId, room, row.id);
          if (current.session !== ctx.sessionKey) throw Error('session_binding_mismatch');
          if (!args || Object.keys(args).some(k => !['operation','query','report'].includes(k))) throw Error('invalid_arguments');
          let details;
          if (args.operation === 'context') details = this.store.context(row.id, ctx.requesterSenderId, room);
          else if (args.operation === 'draft') details = this.store.draft(row.id, ctx.requesterSenderId, room, args.report);
          else if (args.operation === 'lessons') details = this.store.search(row.equipment, args.query ?? '', Boolean(row.synthetic));
          else throw Error('operation_not_allowed');
          return { content: [{ type: 'text', text: JSON.stringify(details) }], details };
        } catch (error) { return { isError: true, content: [{ type: 'text', text: error.message }] }; }
      },
    };
  }
}

export const alarmSession = row => `agent:main:hook:openaut-case-${digest(row.source)}`;
