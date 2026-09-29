// POC workflow ledger. No field actions, approval grants, shell or Forge credentials.
import { DatabaseSync } from 'node:sqlite';
import { createHash } from 'node:crypto';
import { mkdirSync, writeFileSync, renameSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

export const digest = value => createHash('sha256').update(value).digest('hex');
const json = value => JSON.stringify(value);
const text = (value, max = 12000) => {
  if (typeof value !== 'string' || !value.trim() || value.length > max) throw Error('invalid_text');
  return value.trim();
};
const now = () => new Date().toISOString();
const fields = ['symptom', 'observations', 'checks', 'cause', 'action', 'verification', 'lesson', 'limitations'];

export class Store {
  constructor(directory, policy) {
    if (!/^![^\s:]+:[^\s]+$/.test(policy.roomId) || !Array.isArray(policy.technicians) ||
        !policy.technicians.length || policy.technicians.some(x => !/^@[^\s:]+:[^\s]+$/.test(x)) ||
        !Array.isArray(policy.equipment) || !policy.equipment.length) throw Error('invalid_policy');
    this.policy = policy;
    this.directory = directory;
    mkdirSync(directory, { recursive: true, mode: 0o700 });
    mkdirSync(join(directory, 'documents'), { recursive: true, mode: 0o700 });
    this.db = new DatabaseSync(join(directory, 'workflow.sqlite'));
    this.db.exec(`PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; PRAGMA busy_timeout=5000;
      CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS cases (
        id TEXT PRIMARY KEY, source TEXT NOT NULL UNIQUE, equipment TEXT NOT NULL,
        synthetic INTEGER NOT NULL, alarm TEXT NOT NULL, analysis TEXT,
        status TEXT NOT NULL DEFAULT 'analysing', owner TEXT, room TEXT, root TEXT,
        dm TEXT UNIQUE, session TEXT UNIQUE, revision INTEGER NOT NULL DEFAULT 0,
        document TEXT, document_hash TEXT, confirmed_by TEXT, confirmed_at TEXT,
        created TEXT NOT NULL, updated TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS events (
        seq INTEGER PRIMARY KEY, identity TEXT NOT NULL UNIQUE, case_id TEXT NOT NULL,
        actor TEXT NOT NULL, kind TEXT NOT NULL, body TEXT NOT NULL, ts TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS outbox (
        id TEXT PRIMARY KEY, case_id TEXT NOT NULL, kind TEXT NOT NULL,
        target TEXT NOT NULL, body TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'queued',
        receipt TEXT, created TEXT NOT NULL);
    `);
    // Bind this ledger to its operations room/account. Server or bot migration also
    // requires explicit operator reconciliation; a URL change is not an identity proof.
    const binding = json([policy.roomId, policy.accountId]);
    const old = this.db.prepare("SELECT value FROM settings WHERE key='binding'").get();
    if (old && old.value !== binding) throw Error('policy_binding_changed');
    this.db.prepare("INSERT OR IGNORE INTO settings VALUES ('binding',?)").run(binding);
  }
  close() { this.db.close(); }
  recover() { this.db.exec("UPDATE outbox SET state='uncertain' WHERE state='sending'"); }
  transaction(fn) {
    this.db.exec('BEGIN IMMEDIATE');
    try { const result = fn(); this.db.exec('COMMIT'); return result; }
    catch (error) { this.db.exec('ROLLBACK'); throw error; }
  }
  get(id) {
    const row = this.db.prepare('SELECT * FROM cases WHERE id=?').get(id);
    if (!row || !this.policy.equipment.includes(row.equipment)) throw Error('case_not_available');
    return row;
  }
  authorize(actor) {
    if (!this.policy.technicians.includes(actor)) throw Error('sender_not_authorized');
  }
  privateCase(actor, room, id) {
    this.authorize(actor);
    const row = this.get(id);
    if (row.owner !== actor || !room || row.dm !== room) throw Error('private_case_mismatch');
    return row;
  }
  event(id, identity, actor, kind, body) {
    return this.db.prepare('INSERT OR IGNORE INTO events(identity,case_id,actor,kind,body,ts) VALUES (?,?,?,?,?,?)')
      .run(text(identity, 500), id, actor, kind, text(body, 48000), now()).changes === 1;
  }
  queue(row, kind, target, body, suffix = '') {
    const id = digest(json([row.id, kind, suffix]));
    this.db.prepare('INSERT OR IGNORE INTO outbox(id,case_id,kind,target,body,created) VALUES (?,?,?,?,?,?)')
      .run(id, row.id, kind, target, text(body), now());
    return id;
  }
  openAlarm(event) {
    if (!this.policy.equipment.includes(event.equipment_id) || typeof event.synthetic !== 'boolean' ||
        !/^[a-z0-9-]{1,120}$/.test(event.event_id)) throw Error('alarm_out_of_scope');
    const source = json([event.equipment_id, event.synthetic, event.event_id]);
    const id = 'F-' + digest(source).slice(0, 20);
    const alarm = text(json(event), 48000);
    return this.transaction(() => {
      const old = this.db.prepare('SELECT * FROM cases WHERE id=?').get(id);
      if (old) {
        if (old.alarm !== alarm) throw Error('conflicting_alarm_replay');
        return old;
      }
      this.db.prepare('INSERT INTO cases(id,source,equipment,synthetic,alarm,room,created,updated) VALUES (?,?,?,?,?,?,?,?)')
        .run(id, source, event.equipment_id, Number(event.synthetic), alarm, this.policy.roomId, now(), now());
      this.event(id, 'alarm:' + id, 'alarm-watch', 'alarm', alarm);
      return this.get(id);
    });
  }
  completeAnalysis(id, analysis) {
    text(analysis, 10000);
    return this.transaction(() => {
      const row = this.get(id);
      if (row.status !== 'analysing') return row;
      this.db.prepare("UPDATE cases SET analysis=?,status='open',updated=? WHERE id=?").run(analysis, now(), id);
      this.event(id, 'analysis:' + id, 'advisor', 'analysis', analysis);
      this.queue(row, 'alarm', row.room,
        `${row.synthetic ? 'SYNTETISKT PROV · ' : ''}${id} · ${row.equipment}\n${analysis}\n\nAnsvarig: ingen. Skriv ”Jag tar ${id}” som ett nytt meddelande i driftrummet.`);
      return this.get(id);
    });
  }
  caseForRoot(root) {
    const row = this.db.prepare('SELECT id FROM cases WHERE root=?').get(root);
    return row ? this.get(row.id) : null;
  }
  caseForDm(room) {
    const row = this.db.prepare('SELECT id FROM cases WHERE dm=?').get(room);
    return row ? this.get(row.id) : null;
  }
  claim(id, actor, room, eventId) {
    this.authorize(actor);
    if (room !== this.policy.roomId) throw Error('claim_requires_operations_room');
    return this.transaction(() => {
      const row = this.get(id);
      if (row.owner) return { claimed: row.owner === actor, owner: row.owner, status: row.status };
      if (row.status !== 'open' || !row.root) throw Error('alarm_not_published');
      this.db.prepare("UPDATE cases SET owner=?,status='assigned',updated=? WHERE id=?").run(actor, now(), id);
      this.event(id, eventId, actor, 'assigned', actor);
      this.queue(row, 'create_dm', actor, `${id} · ${row.equipment}`);
      this.queue(row, 'assigned', row.room, `${id}: ${actor} har tagit ärendet. Privat felsökningsrum förbereds.`);
      return { claimed: true, owner: actor, status: 'assigned' };
    });
  }
  note(id, actor, room, eventId, body, session) {
    text(body); text(session, 500);
    return this.transaction(() => {
      const row = this.privateCase(actor, room, id);
      if (!['assigned', 'investigating', 'awaiting_confirmation'].includes(row.status)) throw Error('case_closed');
      if (row.session && row.session !== session) throw Error('session_binding_mismatch');
      if (!this.event(id, eventId, actor, 'observation', body)) return false;
      this.db.prepare("UPDATE cases SET session=?,status='investigating',document=NULL,document_hash=NULL,updated=? WHERE id=?")
        .run(session, now(), id);
      return true;
    });
  }
  recordReply(session, runId, body) {
    const row = this.db.prepare('SELECT id FROM cases WHERE session=?').get(session);
    if (!row) return;
    this.transaction(() => this.event(row.id, 'reply:' + runId, 'advisor', 'advice', text(body)));
  }
  history(row) {
    return this.db.prepare('SELECT seq,actor,kind,body,ts FROM events WHERE case_id=? ORDER BY seq').all(row.id);
  }
  context(id, actor, room) {
    const row = this.privateCase(actor, room, id);
    return { case: row, events: this.history(row), lessons: this.search(row.equipment, '', Boolean(row.synthetic)) };
  }
  draft(id, actor, room, proposal) {
    const row = this.privateCase(actor, room, id);
    if (!['investigating', 'awaiting_confirmation'].includes(row.status)) throw Error('case_not_investigating');
    if (!proposal || Object.keys(proposal).sort().join() !== [...fields, 'cause_status', 'evidence'].sort().join() ||
        !['confirmed', 'probable', 'unknown'].includes(proposal.cause_status) || !Array.isArray(proposal.evidence) ||
        proposal.evidence.length < 1 || proposal.evidence.length > 100) throw Error('invalid_report');
    const clean = Object.fromEntries(fields.map(k => [k, text(proposal[k], 1000)]));
    const observations = this.history(row).filter(x => x.kind === 'observation');
    if (proposal.evidence.some(x => !Number.isSafeInteger(x) || !observations.some(y => y.seq === x))) throw Error('unproven_evidence');
    // Documents are immutable, content-addressed files. Ledger holds metadata/pointers.
    const document = { case_id: id, equipment_id: row.equipment, synthetic: Boolean(row.synthetic),
      ...clean, cause_status: proposal.cause_status, evidence: proposal.evidence,
      evidence_records: observations.filter(x => proposal.evidence.includes(x.seq)),
      revision: row.revision + 1, author: 'advisor', technician: actor,
      trust_level: 'draft', publication: 'local-poc-pending-forge', created_at: now() };
    const bytes = json(document) + '\n';
    const hash = digest(bytes);
    const name = hash + '.json';
    writeFileSync(join(this.directory, 'documents', name), bytes, { flag: 'wx', mode: 0o600 });
    this.transaction(() => {
      this.db.prepare("UPDATE cases SET revision=?,document=?,document_hash=?,status='awaiting_confirmation',updated=? WHERE id=?")
        .run(document.revision, name, hash, now(), id);
      this.event(id, 'draft:' + hash, 'advisor', 'report_draft', hash);
      this.queue(row, 'dm_review', room, `UTKAST ${id} · revision ${document.revision}\nOrsaksstatus: ${document.cause_status}\n\n` +
        fields.map(k => `${k}: ${document[k]}`).join('\n\n') +
        `\n\nKontrollera både rapport och lärdom. Bekräfta exakt denna version med:\nBekräfta ${id} ${hash}\n` +
        'Skriv annars din rättelse. Ny information gör detta utkast inaktuellt.', hash);
    });
    return { hash, document, confirmation: `Bekräfta ${id} ${hash}` };
  }
  document(row) {
    if (!/^[a-f0-9]{64}\.json$/.test(row.document || '')) throw Error('document_unavailable');
    const bytes = readFileSync(join(this.directory, 'documents', row.document));
    if (digest(bytes) !== row.document_hash) throw Error('document_integrity_failed');
    return JSON.parse(bytes);
  }
  confirm(id, actor, room, eventId, hash) {
    return this.transaction(() => {
      const row = this.privateCase(actor, room, id);
      if (row.status === 'closed' && row.document_hash === hash) return { closed: true, hash };
      if (row.status !== 'awaiting_confirmation' || row.document_hash !== hash) throw Error('stale_confirmation');
      const doc = this.document(row);
      this.db.prepare("UPDATE cases SET status='closed',confirmed_by=?,confirmed_at=?,updated=? WHERE id=?")
        .run(actor, now(), now(), id);
      this.event(id, eventId, actor, 'report_confirmed', hash);
      this.queue(row, 'closed', row.room, `${id} avslutat av ${actor}.\nOrsaksstatus: ${doc.cause_status}.\n` +
        `${doc.cause}\nVerifiering: ${doc.verification}\nLärdom: ${doc.lesson}\n` +
        'Teknikerbekräftat erfarenhetsfall, inte en generell regel. Dokumenterat i lokal POC-kunskapsbank.');
      return { closed: true, hash };
    });
  }
  search(equipment, query = '', synthetic = false) {
    if (!this.policy.equipment.includes(equipment)) throw Error('equipment_out_of_scope');
    if (typeof query !== 'string' || query.length > 200) throw Error('invalid_query');
    const rows = this.db.prepare("SELECT * FROM cases WHERE equipment=? AND synthetic=? AND status='closed' ORDER BY confirmed_at DESC")
      .all(equipment, Number(synthetic));
    const results = [];
    for (const row of rows) {
      const doc = this.document(row);
      if (query && !json(doc).toLocaleLowerCase('sv').includes(query.toLocaleLowerCase('sv'))) continue;
      results.push({ ...doc, trust_level: 'technician_confirmed_case', confirmed_by: row.confirmed_by,
        confirmed_at: row.confirmed_at, sha256: row.document_hash,
        caveat: 'Erfarenhetsfall, inte instruktion eller bevis för orsaken i ett nytt fall.' });
      if (results.length === 10) break;
    }
    return results;
  }
  nextDelivery() {
    return this.transaction(() => {
      for (const job of this.db.prepare("SELECT * FROM outbox WHERE state='queued' ORDER BY created,id").all()) {
        const row = this.get(job.case_id);
        if ((job.kind === 'create_dm' || job.kind.startsWith('dm_')) && !this.policy.technicians.includes(row.owner)) continue;
        this.db.prepare("UPDATE outbox SET state='sending' WHERE id=?").run(job.id);
        return job;
      }
      return null;
    });
  }
  delivered(job, receipt) {
    return this.transaction(() => {
      const row = this.get(job.case_id);
      if (job.kind === 'create_dm') {
        if (!/^![^\s:]+:[^\s]+$/.test(receipt.roomId) || receipt.roomId === row.room) throw Error('invalid_dm_receipt');
        this.db.prepare('UPDATE cases SET dm=?,updated=? WHERE id=?').run(receipt.roomId, now(), row.id);
        this.queue(row, 'dm_intro', receipt.roomId, `${row.synthetic ? 'SYNTETISKT PROV\n' : ''}${row.id} · ${row.equipment}\n` +
          `${row.analysis}\n\nDu ansvarar för felsökningen. Beskriv din första observation. ` +
          'Advisor hjälper dig med en kontroll i taget. Skriv ”Sammanfatta” när du vill granska rapport och lessons learned.');
      } else {
        if (typeof receipt.messageId !== 'string' || !receipt.messageId.startsWith('$')) throw Error('invalid_send_receipt');
        if (job.kind === 'alarm') this.db.prepare('UPDATE cases SET root=? WHERE id=?').run(receipt.messageId, row.id);
      }
      this.db.prepare("UPDATE outbox SET state='sent',receipt=? WHERE id=?").run(json(receipt), job.id);
    });
  }
  uncertain(job) { this.db.prepare("UPDATE outbox SET state='uncertain' WHERE id=?").run(job.id); }
  exportConfirmed(id, destination) {
    const row = this.get(id);
    if (row.status !== 'closed') throw Error('unconfirmed_report');
    const doc = this.document(row);
    const report = `# Felsökning ${id}\n\nUtrustning: ${row.equipment}\nSyntetiskt: ${Boolean(row.synthetic)}\n` +
      `Bekräftad av: ${row.confirmed_by}\nTid: ${row.confirmed_at}\nOrsaksstatus: ${doc.cause_status}\n\n` +
      fields.filter(x => x !== 'lesson').map(k => `## ${k}\n\n${doc[k]}\n`).join('\n');
    const lesson = `# Lessons learned ${id}\n\n${doc.lesson}\n\n## Giltighet och begränsningar\n\n${doc.limitations}\n\n` +
      `Erfarenhetsfall på ${row.equipment}; inte en generell regel. Syntetiskt: ${Boolean(row.synthetic)}.\n` +
      `Källa: felsökningsärende ${id}, rapport-SHA256 ${row.document_hash}.\n`;
    mkdirSync(destination, { recursive: true, mode: 0o700 });
    for (const [name, content] of [['report.md', report], ['lesson.md', lesson]]) {
      writeFileSync(join(destination, name + '.tmp'), content, { mode: 0o600 });
      renameSync(join(destination, name + '.tmp'), join(destination, name));
    }
    const manifest = { case_id: id, equipment_id: row.equipment, synthetic: Boolean(row.synthetic),
      confirmed_by: row.confirmed_by, confirmed_at: row.confirmed_at,
      source_sha256: row.document_hash, trust_level: 'quarantine',
      publication: 'pending-forge-review', files: { 'report.md': digest(report), 'lesson.md': digest(lesson) } };
    writeFileSync(join(destination, 'manifest.json'), json(manifest) + '\n', { mode: 0o600 });
    return manifest;
  }
}
