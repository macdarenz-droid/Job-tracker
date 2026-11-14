// One D1 row per manual record: the copy, the kept whole-tracker route, the per-record routes and the Free plan limits.
// Everything runs offline on tests/d1sqlite.js. The records are made up; nothing here comes from the live tracker.
import test from 'node:test';
import assert from 'node:assert/strict';
import api from '../src/index.js';
import {LIMITS} from './d1sqlite.js';
import {CODE, size, file, record, tracker, environment} from './helpers.js';

async function raw(ctx, path, options = {}) {
  const body = options.body === undefined ? undefined : typeof options.body === 'string' ? options.body : JSON.stringify(options.body);
  const headers = {'X-Tracker-Code': CODE, ...(body === undefined ? {} : {'Content-Type': 'application/json', 'Content-Length': String(Buffer.byteLength(body))}), ...options.headers};
  ctx.invocation();
  const response = await api.fetch(new Request('https://tracker.example' + path, {method: options.method || 'GET', headers, body}), ctx.env);
  return {status: response.status, text: await response.text(), headers: response.headers};
}
async function call(ctx, path, options) {
  const {status, text} = await raw(ctx, path, options);
  return {status, bytes: Buffer.byteLength(text), data: text ? JSON.parse(text) : null, queries: ctx.counters.queries, used: {...ctx.counters}};
}
const put = (ctx, version, state) => call(ctx, '/api/state', {method: 'PUT', body: {expected_version: version, state}});
const copy = ctx => call(ctx, '/api/admin/backfill', {method: 'POST'});
async function copied(state, version) {
  const ctx = environment(state, version);
  assert.equal((await copy(ctx)).status, 200);
  return ctx;
}
// Runs `action` once, just before the first D1 batch for which `when` is true: a second writer that gets in between.
function intrude(ctx, when, action) {
  const original = ctx.DB.batch;
  let seen = 0;
  ctx.DB.batch = async list => {
    if (when(list, seen++)) { ctx.DB.batch = original; await action(); }
    return original(list);
  };
}
// Runs `action` once, right after the Worker has read the tracker's version and before its next query.
function afterVersionRead(ctx, action) {
  const prepare = ctx.DB.prepare;
  ctx.DB.prepare = sql => {
    const statement = prepare(sql);
    if (sql !== 'SELECT version, payload, updated_at FROM tracker_state WHERE id = 1') return statement;
    const first = statement.first;
    statement.first = async () => { const value = await first.call(statement); ctx.DB.prepare = prepare; await action(); return value; };
    return statement;
  };
}
const rowOf = (ctx, id) => ctx.db.prepare('SELECT position, version, summary, body FROM records WHERE id = ?').get(id);
const storedMode = ctx => ctx.db.prepare('SELECT substr(payload, 1, 21) AS head FROM tracker_state WHERE id = 1').get().head === '{"storage":"rows-v1",' ? 'rows' : 'document';

test('before the copy the Worker is the single document as before, and the per-record routes say they are not active', async () => {
  const state = tracker(400);
  state.manual_entries.push(record(9000, {notes: 'p'.repeat(1_797_500 - size(state))}));
  const ctx = environment(state);
  const before = await call(ctx, '/api/state');
  assert.equal(before.queries, 2, 'the code lookup and one read, as before');
  assert.ok(before.bytes > 1_780_000 && before.bytes < 1_800_000);
  const next = structuredClone(before.data.state);
  next.manual_entries.push(record(9001));
  const full = await put(ctx, before.data.version, next);
  assert.equal(full.status, 413);
  assert.equal(full.data.error, 'Tracker exceeds the state size limit.');
  assert.deepEqual((await call(ctx, '/api/version')).data, {version: 225, updated_at: state.updated_at, storage: 'document'});
  for (const [path, options] of [['/api/records'], ['/api/records/rec-0001'], ['/api/records', {method: 'POST', body: {records: [record(9002)]}}],
    ['/api/records/rec-0001', {method: 'PATCH', body: {expected_version: 1, patch: {status: 'MANUAL_APPLIED'}}}]]) {
    const reply = await call(ctx, path, options);
    assert.equal(reply.status, 409);
    assert.match(reply.data.error, /not active/);
  }
  assert.equal(ctx.db.prepare('SELECT COUNT(*) AS n FROM records').get().n, 0);
  assert.equal((await call(ctx, '/api/state')).data.version, 225, 'nothing above changed the tracker');
  // A client cannot switch the storage mode by sending the marker itself.
  const forged = await put(ctx, 225, {storage: 'rows-v1', ...before.data.state});
  assert.equal(forged.status, 400);
  assert.equal(forged.data.error, 'Invalid tracker format.');
  assert.equal(storedMode(ctx), 'document');
  assert.equal((await put(ctx, 225, before.data.state)).status, 200, 'the same state without the marker saves as before');
});

test('the copy is lossless, keeps the untouched document, changes no version and is safe to run again', async () => {
  const state = tracker(399);
  // An odd record that the single document would have accepted is copied as it is, not refused.
  state.manual_entries.push({id: 'odd-' + 'y'.repeat(300), company: 'Odd Legacy Pty Ltd', role: 'Drafter', attachments: ['kept as it was'], match_score: 'n/a', advert: 'none', location: {suburb: 'Melton'}});
  const ctx = environment(state);
  const before = await call(ctx, '/api/state');
  const done = await copy(ctx);
  assert.equal(done.status, 200);
  assert.deepEqual({...done.data, remainder_bytes: 0}, {storage: 'rows', already: false, version: 225, records: 403, remainder_bytes: 0});
  assert.ok(done.data.remainder_bytes < 130_000, 'what stays in the single row is the frozen history and the Bin');
  assert.equal(done.queries, 16, 'code lookup, read, backup, 11 batches of 40, read back, switch');
  assert.ok(done.used.largestBatch < 400_000 && done.used.mostParameters === 6);
  const after = await call(ctx, '/api/state');
  assert.equal(after.data.version, before.data.version);
  assert.deepEqual(after.data.state, before.data.state);
  assert.equal(ctx.db.prepare('SELECT payload FROM tracker_state_backup WHERE version = 225').get().payload, JSON.stringify(state), 'the backup is the payload byte for byte');
  assert.equal(rowOf(ctx, 'rec-0398').body, JSON.stringify(state.manual_entries[401]));
  assert.deepEqual(JSON.parse(rowOf(ctx, state.manual_entries[402].id).summary), {id: state.manual_entries[402].id, row_version: 1, company: 'Odd Legacy Pty Ltd', role: 'Drafter', location: '', status: '', route: '', closes_at: '', fit_percent: null, updated_at: '', files: 1});
  assert.equal(rowOf(ctx, 'rec-0002').version, 3, 'a row starts at its record\'s own version');
  const again = await copy(ctx);
  assert.deepEqual(again.data, {storage: 'rows', already: true, version: 225, records: 403});
  assert.equal(again.queries, 3);
  assert.deepEqual((await call(ctx, '/api/state')).data, after.data);
  assert.deepEqual((await call(ctx, '/api/version')).data, {version: 225, updated_at: state.updated_at, storage: 'rows'});
  // The odd record does not stop later whole-tracker saves; a new record with such an id is refused.
  assert.equal((await put(ctx, 225, after.data.state)).status, 200);
  const long = structuredClone(after.data.state);
  long.manual_entries.push(record(9300, {id: 'z'.repeat(201)}));
  assert.equal((await put(ctx, 226, long)).status, 400);
});

test('the copy is guarded: a save that lands in the middle wins, the tracker stays a single document, and a second run finishes', async () => {
  const ctx = environment();
  const before = (await call(ctx, '/api/state')).data;
  const edited = structuredClone(before.state);
  edited.manual_entries[5].status = 'MANUAL_APPLIED';
  edited.manual_entries.push(record(7000));
  intrude(ctx, (list, n) => n === 1, async () => assert.equal((await put(ctx, 225, edited)).status, 200));
  const lost = await copy(ctx);
  assert.equal(lost.status, 409);
  assert.match(lost.data.error, /still uses the single document/);
  assert.equal(storedMode(ctx), 'document');
  const between = (await call(ctx, '/api/state')).data;
  assert.equal(between.version, 226);
  assert.equal(between.state.manual_entries[5].status, 'MANUAL_APPLIED');
  assert.equal(ctx.db.prepare('SELECT COUNT(*) AS n FROM records').get().n, 40, 'only the batch before the save was copied');
  const stale = await call(ctx, '/api/admin/backfill', {method: 'POST', body: {expected_version: 225}});
  assert.equal(stale.status, 409);
  assert.equal(stale.data.current_version, 226);
  assert.equal(storedMode(ctx), 'document');
  const done = await call(ctx, '/api/admin/backfill', {method: 'POST', body: {expected_version: 226}});
  assert.equal(done.status, 200);
  assert.equal(done.data.records, 404);
  const after = (await call(ctx, '/api/state')).data;
  assert.equal(after.version, 226);
  assert.deepEqual(after.state, between.state, 'rows from the interrupted run were brought up to date, not left stale');
});

test('the copy refuses a document it cannot hold exactly, and changes nothing', async () => {
  for (const [spoil, status] of [
    [state => state.manual_entries.push({...state.manual_entries[4]}), 400],
    [state => { state.manual_entries[7].id = 7; }, 400],
    [state => { delete state.updated_at; }, 400],
    [state => { delete state.leads; }, 400],
    [state => { state.manual_entries[9].notes = 'x'.repeat(200_001); state.manual_entries.length = 20; }, 413]]) {
    const state = tracker(40);
    spoil(state);
    const ctx = environment(state), before = (await call(ctx, '/api/state')).data;
    const reply = await copy(ctx);
    assert.equal(reply.status, status);
    assert.match(reply.data.error, /Nothing was changed/);
    assert.equal(storedMode(ctx), 'document');
    assert.equal(ctx.db.prepare('SELECT COUNT(*) AS n FROM records').get().n, 0);
    assert.deepEqual((await call(ctx, '/api/state')).data, before);
  }
});

test('the switch itself refuses unless the saved backup is the document it replaces and the rows are the ones just compared', async () => {
  const ctx = environment(tracker(20));
  ctx.db.prepare("INSERT INTO tracker_state_backup (version, payload, saved_at) VALUES (225, '{}', '2026-01-01T00:00:00Z')").run();
  const wrongBackup = await copy(ctx);
  assert.equal(wrongBackup.status, 409);
  assert.equal(storedMode(ctx), 'document');
  ctx.db.exec('DELETE FROM tracker_state_backup');
  // A row that is not in the document turns up after the read-back and before the switch.
  const prepare = ctx.DB.prepare;
  ctx.DB.prepare = sql => {
    if (sql.startsWith('UPDATE tracker_state SET payload = ?, updated_at')) ctx.db.prepare("INSERT INTO records (id, position, version, summary, body) VALUES ('stray', 999, 1, '{}', '{}')").run();
    return prepare(sql);
  };
  const stray = await copy(ctx);
  ctx.DB.prepare = prepare;
  assert.equal(stray.status, 409);
  assert.equal(storedMode(ctx), 'document');
  assert.equal((await copy(ctx)).status, 409, 'and the read-back refuses it on the next run');
  ctx.db.exec("DELETE FROM records WHERE id = 'stray'");
  assert.equal((await copy(ctx)).status, 200);
  assert.equal(storedMode(ctx), 'rows');
});

test('the single document can be put back while nothing has been saved since the copy, and not afterwards', async () => {
  const state = tracker(60), ctx = environment(state);
  const before = (await call(ctx, '/api/state')).data;
  await copy(ctx);
  assert.equal((await call(ctx, '/api/admin/restore-document', {method: 'POST', body: {expected_version: 224}})).status, 409);
  const back = await call(ctx, '/api/admin/restore-document', {method: 'POST', body: {expected_version: 225}});
  assert.deepEqual(back.data, {storage: 'document', already: false, version: 225});
  assert.equal(back.queries, 3);
  assert.equal(ctx.db.prepare('SELECT payload FROM tracker_state WHERE id = 1').get().payload, JSON.stringify(state));
  assert.deepEqual((await call(ctx, '/api/state')).data, before);
  assert.equal((await call(ctx, '/api/records')).status, 409);
  assert.equal((await call(ctx, '/api/admin/restore-document', {method: 'POST', body: {expected_version: 225}})).data.already, true);
  // The single document still saves as before, and the next copy takes that save with it.
  const edited = structuredClone(before.state);
  edited.manual_entries[2].notes = 'changed while a single document';
  assert.equal((await put(ctx, 225, edited)).status, 200);
  assert.equal((await copy(ctx)).data.version, 226);
  assert.equal((await call(ctx, '/api/records/' + edited.manual_entries[2].id)).data.record.notes, 'changed while a single document');
  const patched = await call(ctx, '/api/records/rec-0001', {method: 'PATCH', body: {expected_version: 2, patch: {status: 'MANUAL_APPLIED'}}});
  assert.equal(patched.status, 200);
  const refused = await call(ctx, '/api/admin/restore-document', {method: 'POST', body: {expected_version: 226}});
  assert.equal(refused.status, 409);
  assert.equal(storedMode(ctx), 'rows');
  assert.equal((await call(ctx, '/api/records/rec-0001')).data.record.status, 'MANUAL_APPLIED');
});

test('after the copy the tracker grows past 2 MB; the limits are per record and for the remainder', async () => {
  const ctx = await copied();
  let current = (await call(ctx, '/api/state')).data;
  const next = structuredClone(current.state);
  for (let n = 500; n < 563; n++) next.manual_entries.push(record(n, {notes: 'n'.repeat(9000)}));
  const saved = await put(ctx, current.version, next);
  assert.equal(saved.status, 200);
  assert.equal(saved.data.version, 226);
  assert.equal(saved.queries, 4);
  assert.equal(saved.used.writes.length, 64, '63 new rows and the version; no existing row and no remainder was written');
  assert.ok(saved.used.writes.at(-1).sql.startsWith('UPDATE tracker_state SET version'));
  assert.ok(saved.used.largestBatch < 700_000);
  assert.equal((await put(ctx, current.version, next)).status, 409, 'the same stale version is refused as before');
  const added = await call(ctx, '/api/records', {method: 'POST', body: {records: Array.from({length: 50}, (_, i) => record(600 + i))}});
  assert.equal(added.status, 201);
  current = (await call(ctx, '/api/state')).data;
  assert.equal(current.version, 227);
  assert.equal(current.state.manual_entries.length, 403 + 63 + 50);
  assert.ok(size(current.state) > 2_400_000, 'larger than one D1 string or row could ever hold');
  assert.deepEqual(current.state.manual_entries.slice(0, 466), next.manual_entries);
  assert.equal(current.state.updated_at, (await call(ctx, '/api/version')).data.updated_at);

  const huge = structuredClone(current.state);
  huge.manual_entries.push(record(9100, {notes: 'é'.repeat(100_001)}));
  const tooBig = await put(ctx, current.version, huge);
  assert.equal(tooBig.status, 413);
  assert.match(tooBig.data.error, /rec-9100 .*larger than 200000 bytes/);
  assert.equal((await call(ctx, '/api/records', {method: 'POST', body: {records: [record(9101, {notes: 'x'.repeat(200_000)})]}})).status, 413);
  const fat = structuredClone(current.state);
  fat.notice = 'x'.repeat(1_700_000);
  const remainder = await put(ctx, current.version, fat);
  assert.equal(remainder.status, 413);
  assert.equal(remainder.data.error, 'Tracker exceeds the state size limit.');
  const many = structuredClone(current.state);
  for (let n = 0; n < 12; n++) many.manual_entries.push(record(9200 + n, {notes: 'x'.repeat(190_000)}));
  const burst = await put(ctx, current.version, many);
  assert.equal(burst.status, 413);
  assert.match(burst.data.error, /too much at once/);
  assert.deepEqual((await call(ctx, '/api/state')).data, current, 'a refused save changes nothing');
});

test('a whole-tracker save that changes one record among hundreds writes that one row', async () => {
  const ctx = await copied();
  const current = (await call(ctx, '/api/state')).data;
  const next = structuredClone(current.state);
  const target = next.manual_entries.find(row => row.id === 'rec-0123');
  Object.assign(target, {status: 'MANUAL_APPLIED', applied_date: '2026-11-13', application_method: 'SEEK', version: target.version + 1});
  const before = rowOf(ctx, 'rec-0123'), neighbour = rowOf(ctx, 'rec-0124'), base = ctx.db.prepare('SELECT payload FROM tracker_state WHERE id = 1').get().payload;
  const saved = await put(ctx, current.version, next);
  assert.equal(saved.status, 200);
  assert.deepEqual(saved.used.writes.map(write => [write.sql.slice(0, 20), write.changes]), [['UPDATE records SET v', 1], ['UPDATE tracker_state', 1]]);
  assert.ok(saved.used.largestBatch < 6_000, 'about one record goes to D1, not the tracker');
  const row = rowOf(ctx, 'rec-0123');
  assert.equal(row.version, before.version + 1);
  assert.equal(row.position, before.position);
  assert.equal(JSON.parse(row.summary).status, 'MANUAL_APPLIED');
  assert.equal(JSON.parse(row.summary).row_version, row.version);
  assert.deepEqual(rowOf(ctx, 'rec-0124'), neighbour);
  assert.equal(ctx.db.prepare('SELECT payload FROM tracker_state WHERE id = 1').get().payload, base);
  const after = (await call(ctx, '/api/state')).data;
  assert.equal(after.version, current.version + 1);
  assert.equal(after.state.updated_at, saved.data.updated_at);
  assert.deepEqual({...after.state, updated_at: ''}, {...next, updated_at: ''});
  // Saving exactly what was read writes no row at all; only the version moves.
  const same = await put(ctx, after.version, after.state);
  assert.equal(same.status, 200);
  assert.equal(same.used.writes.length, 1);
  // Moving one job to the Bin changes the remainder and no record.
  const binned = structuredClone(after.state);
  binned.record_visibility.push({record_key: 'manual:rec-0007', deleted: 1, version: 1});
  const bin = await put(ctx, after.version + 1, binned);
  assert.equal(bin.status, 200);
  assert.deepEqual(bin.used.writes.map(write => write.sql.startsWith('UPDATE tracker_state SET payload = ?,')), [true]);
});

test('the whole-tracker save keeps every old rule: no dropped record, no dropped document, frozen history, Bin history', async () => {
  const ctx = await copied(tracker(60));
  const current = (await call(ctx, '/api/state')).data;
  const attempt = async change => { const next = structuredClone(current.state); change(next); return put(ctx, current.version, next); };
  const dropped = await attempt(next => { next.manual_entries.splice(10, 1); });
  assert.equal(dropped.status, 400);
  assert.equal(dropped.data.error, 'Existing manual records must be preserved. Move them to Bin instead.');
  assert.equal((await attempt(next => { next.manual_entries = []; })).status, 400);
  const files = await attempt(next => { next.manual_entries.find(row => row.attachments.length === 2).attachments.pop(); });
  assert.equal(files.data.error, 'Existing document references must be preserved.');
  assert.equal((await attempt(next => { next.manual_entries[4] = {...next.manual_entries[5]}; })).data.error, 'Invalid or duplicate manual record.');
  assert.equal((await attempt(next => { next.manual_entries.push({id: 5, company: 'X', role: 'Y', attachments: []}); })).data.error, 'Invalid or duplicate manual record.');
  assert.equal((await attempt(next => { next.manual_entries[8].attachments.push({filename: 'a.pdf', data_base64: 'AAAA'}); })).data.error, 'Upload attachment bytes to Cloudflare before saving the record.');
  assert.equal((await attempt(next => { next.applications = []; })).data.error, 'Automatic application history cannot be replaced.');
  assert.equal((await attempt(next => { next.leads[0].role = 'Altered'; })).data.error, 'Existing lead evidence cannot be replaced.');
  assert.equal((await attempt(next => { next.leads.pop(); })).data.error, 'Existing lead history must be preserved.');
  assert.equal((await attempt(next => { next.record_visibility.shift(); })).data.error, 'Existing Bin history must be preserved.');
  assert.equal((await attempt(next => { delete next.manual_entries; })).data.error, 'Invalid tracker format.');
  assert.equal((await call(ctx, '/api/state', {method: 'PUT', body: '{'})).data.error, 'Invalid JSON.');
  assert.equal((await call(ctx, '/api/state', {method: 'PUT', body: {state: current.state}})).data.error, 'A current version is required.');
  assert.deepEqual((await call(ctx, '/api/state')).data, current, 'none of the refused saves changed anything');
  // Still allowed, as before: a new researched lead, a documented closure, an added file, a changed field.
  const ok = await attempt(next => {
    next.leads.push({key: 'example.test|grad-2026-11-13', company: 'Example Civil', role: 'Graduate Civil Engineer', status: 'READY_FOR_JEREMIE', checked_at: '2026-11-13T01:00:00Z', job_url: 'https://example.test/careers/graduate'});
    next.manual_entries[8].attachments.push(file(8, 'confirmation'));
    next.manual_entries[9].notes = 'edited';
  });
  assert.equal(ok.status, 200);
  const after = (await call(ctx, '/api/state')).data.state;
  assert.equal(after.leads.length, current.state.leads.length + 1);
  assert.equal(after.manual_entries[8].attachments.at(-1).id, 'doc-8-confirmation');
  assert.equal(after.manual_entries[9].notes, 'edited');
});

test('a whole-tracker save that loses a race writes nothing, not even its rows', async () => {
  const ctx = await copied(tracker(60));
  const current = (await call(ctx, '/api/state')).data;
  const next = structuredClone(current.state);
  next.manual_entries.find(row => row.id === 'rec-0010').notes = 'from the slow whole-tracker save';
  next.manual_entries.push(record(8000));
  // The record's own version moves from 2 to 3 here, the number the slow save is about to write.
  intrude(ctx, () => true, async () => assert.equal((await call(ctx, '/api/records/rec-0010', {method: 'PATCH', body: {expected_version: 2, patch: {notes: 'from the phone'}}})).status, 200));
  const slow = await put(ctx, current.version, next);
  assert.equal(slow.status, 409);
  assert.equal(JSON.parse(rowOf(ctx, 'rec-0010').body).notes, 'from the phone');
  assert.equal(rowOf(ctx, 'rec-0010').version, 3);
  assert.equal(rowOf(ctx, 'rec-8000'), undefined);
  assert.equal((await call(ctx, '/api/version')).data.version, current.version + 1, 'only the phone\'s save moved the version');
});

test('list, read, add and change single records', async () => {
  const ctx = await copied(tracker(60));
  const list = await call(ctx, '/api/records');
  assert.equal(list.status, 200);
  assert.equal(list.data.version, 225);
  assert.equal(list.data.records.length, 63);
  assert.deepEqual(list.data.records[3 + 7], {id: 'rec-0007', row_version: 2, company: 'Example Civil 7', role: 'Junior Civil Drafter', location: 'Melton VIC', status: 'ASK_OWNER', route: 'EMAIL',
    closes_at: '2026-12-08T12:59:59.999Z', fit_percent: 62, updated_at: '2026-10-08T00:00:00.000Z', key: 'manual:rec-0007', job_url: 'https://jobs.example.test/job/7',
    created_at: '2026-10-01T00:00:00.000Z', created_by: 'test-runner', contributor_name: 'Test', files: 2});
  assert.ok(list.bytes < (await call(ctx, '/api/state')).bytes / 8, 'the list is a fraction of the tracker');
  const one = await call(ctx, '/api/records/rec-0007');
  assert.deepEqual(one.data, {row_version: 2, record: record(7)});
  assert.equal((await call(ctx, '/api/records/nope')).status, 404);
  assert.equal((await call(ctx, '/api/records/%E0%A4%A')).status, 404);

  const queueEntry = {id: 'queue/entry 1', company: 'Queue Co', role: 'Civil Drafter', route: 'SEEK', closes_at: '2026-11-20', status: 'READY_SEEK', attachments: []};
  const added = await call(ctx, '/api/records', {method: 'POST', body: {records: [record(100), queueEntry]}});
  assert.equal(added.status, 201);
  assert.deepEqual(added.data, {added: ['rec-0100', 'queue/entry 1'], version: 226, updated_at: added.data.updated_at});
  assert.equal(added.data.updated_at, (await call(ctx, '/api/version')).data.updated_at);
  assert.equal((await call(ctx, '/api/records', {method: 'POST', body: {record: record(101)}})).status, 201);
  const fetched = await call(ctx, '/api/records/' + encodeURIComponent('queue/entry 1'));
  assert.deepEqual(fetched.data, {row_version: 1, record: queueEntry});
  const listed = (await call(ctx, '/api/records')).data;
  assert.equal(listed.version, 227, 'each add moves the tracker version, so the page and whole-tracker clients notice');
  assert.deepEqual(listed.records.slice(-3).map(row => row.id), ['rec-0100', 'queue/entry 1', 'rec-0101']);
  assert.deepEqual(listed.records.at(-2), {id: 'queue/entry 1', row_version: 1, company: 'Queue Co', role: 'Civil Drafter', location: '', status: 'READY_SEEK', route: 'SEEK', closes_at: '2026-11-20', fit_percent: null, updated_at: '', files: 0});
  assert.deepEqual((await call(ctx, '/api/state')).data.state.manual_entries.slice(-3).map(row => row.id), ['rec-0100', 'queue/entry 1', 'rec-0101']);

  // An id that exists is refused and nothing in the request is added.
  const repeat = await call(ctx, '/api/records', {method: 'POST', body: {records: [record(102), record(100), record(7)]}});
  assert.equal(repeat.status, 409);
  assert.deepEqual(repeat.data.existing_ids.sort(), ['rec-0007', 'rec-0100']);
  assert.equal(rowOf(ctx, 'rec-0102'), undefined);
  assert.equal((await call(ctx, '/api/records', {method: 'POST', body: {records: [record(103), record(103)]}})).status, 400);
  assert.equal((await call(ctx, '/api/records', {method: 'POST', body: {records: []}})).status, 400);
  assert.equal((await call(ctx, '/api/records', {method: 'POST', body: {records: Array.from({length: 51}, (_, i) => record(2000 + i))}})).status, 400);
  assert.equal((await call(ctx, '/api/records', {method: 'POST', body: {records: [{id: 'bad', company: 'X', role: 'Y', attachments: [{data_base64: 'AAAA'}]}]}})).status, 400);
  assert.equal((await call(ctx, '/api/records', {method: 'POST', body: {records: [{id: 'bad', company: 'X'}]}})).status, 400);
  assert.equal((await call(ctx, '/api/records', {method: 'POST', body: {records: [record(104, {id: 'x'.repeat(201)})]}})).status, 400);
  assert.equal((await call(ctx, '/api/records', {method: 'POST', body: {records: [record(104, {attachments: [null]})]}})).status, 400);
  assert.equal((await call(ctx, '/api/records', {method: 'POST', body: 'not json'})).status, 400);
  assert.equal((await call(ctx, '/api/version')).data.version, 227, 'refused adds do not move the version');

  // One record is changed under its own version; the request is a few hundred bytes.
  const patch = {expected_version: 2, patch: {status: 'MANUAL_APPLIED', applied_date: '2026-11-13', application_method: 'SEEK', id: 'other', key: 'other', created_by: 'someone'}};
  assert.ok(size(patch) < 200);
  const saved = await call(ctx, '/api/records/rec-0007', {method: 'PATCH', body: patch});
  assert.equal(saved.status, 200);
  assert.deepEqual([saved.data.row_version, saved.data.version, saved.data.updated_at], [3, 228, saved.data.record.updated_at], 'the record\'s new guard, and the whole tracker\'s version and time after this change');
  assert.deepEqual(saved.data.record, {...record(7), status: 'MANUAL_APPLIED', applied_date: '2026-11-13', application_method: 'SEEK', updated_at: saved.data.record.updated_at, version: 3});
  assert.notEqual(saved.data.record.updated_at, record(7).updated_at);
  const stale = await call(ctx, '/api/records/rec-0007', {method: 'PATCH', body: patch});
  assert.equal(stale.status, 409);
  assert.equal(stale.data.current_row_version, 3);
  assert.equal((await call(ctx, '/api/records/rec-0007', {method: 'PATCH', body: {expected_version: 3, patch: {attachments: []}}})).data.error, 'Existing document references must be preserved.');
  assert.equal((await call(ctx, '/api/records/rec-0007', {method: 'PATCH', body: {expected_version: 3, patch: {company: 7}}})).status, 400);
  assert.equal((await call(ctx, '/api/records/rec-0007', {method: 'PATCH', body: {expected_version: 3, patch: {notes: 'x'.repeat(200_000)}}})).status, 413);
  assert.equal((await call(ctx, '/api/records/rec-0007', {method: 'PATCH', body: {expected_version: 3}})).status, 400);
  assert.equal((await call(ctx, '/api/records/nope', {method: 'PATCH', body: {expected_version: 1, patch: {notes: 'x'}}})).status, 404);
  const state = (await call(ctx, '/api/state')).data;
  assert.equal(state.version, 228, 'only the one accepted change moved the version');
  assert.deepEqual(state.state.manual_entries.find(row => row.id === 'rec-0007'), saved.data.record);
  assert.equal((await call(ctx, '/api/records')).data.records.find(row => row.id === 'rec-0007').status, 'MANUAL_APPLIED');
  // The other record's own version did not move, so its holder can still save it.
  assert.equal((await call(ctx, '/api/records/rec-0008', {method: 'PATCH', body: {expected_version: 3, patch: {notes: 'second editor'}}})).status, 200);
});

test('two changes to one record: the second is refused whole; an add that loses a race for an id adds nothing', async () => {
  const ctx = await copied(tracker(20));
  const body = notes => ({method: 'PATCH', body: {expected_version: 2, patch: {notes}}});
  intrude(ctx, (list, n) => n === 1, async () => assert.equal((await call(ctx, '/api/records/rec-0001', body('first'))).status, 200));
  const second = await call(ctx, '/api/records/rec-0001', body('second'));
  assert.equal(second.status, 409);
  assert.equal(JSON.parse(rowOf(ctx, 'rec-0001').body).notes, 'first');
  assert.equal((await call(ctx, '/api/version')).data.version, 226, 'the refused change did not move the tracker version');

  intrude(ctx, (list, n) => n === 1, async () => assert.equal((await call(ctx, '/api/records', {method: 'POST', body: {records: [record(301, {company: 'Winner'})]}})).status, 201));
  const late = await call(ctx, '/api/records', {method: 'POST', body: {records: [record(300), record(301), record(302)]}});
  assert.equal(late.status, 409);
  assert.deepEqual(late.data.existing_ids, ['rec-0301']);
  assert.equal(JSON.parse(rowOf(ctx, 'rec-0301').body).company, 'Winner');
  assert.equal(rowOf(ctx, 'rec-0300'), undefined);
  assert.equal(rowOf(ctx, 'rec-0302'), undefined);
  assert.equal((await call(ctx, '/api/version')).data.version, 227);
});

test('a whole-tracker save that crosses another writer gets the usual 409, whatever the other writer did', async () => {
  const addsRecord = ctx => call(ctx, '/api/records', {method: 'POST', body: {records: [record(900)]}});
  const addsFile = ctx => call(ctx, '/api/records/rec-0004', {method: 'PATCH', body: {expected_version: 2, patch: {attachments: [file(4, 'confirmation')]}}});
  const changesStatus = ctx => call(ctx, '/api/records/rec-0004', {method: 'PATCH', body: {expected_version: 2, patch: {status: 'SENT'}}});
  // The last case sends more than 1.8 MB, where the Worker reads the version before the body has arrived.
  for (const [other, extra] of [[addsRecord, 0], [addsFile, 0], [changesStatus, 0], [addsRecord, 40]]) {
    const ctx = await copied(extra ? tracker(400) : tracker(30));
    const current = (await call(ctx, '/api/state')).data;
    const next = structuredClone(current.state);
    next.manual_entries.find(row => row.id === 'rec-0002').notes = 'page edit';
    for (let n = 0; n < extra; n++) next.manual_entries.push(record(5000 + n));
    assert.equal(size({expected_version: current.version, state: next}) > 1_800_000, extra > 0);
    let landed;
    afterVersionRead(ctx, async () => { landed = await other(ctx); });
    const slow = await put(ctx, current.version, next);
    assert.ok(landed.status < 300);
    assert.equal(slow.status, 409);
    assert.deepEqual(slow.data, {error: 'A newer cloud version exists. Refresh before saving.', current_version: current.version + 1});
    assert.equal(JSON.parse(rowOf(ctx, 'rec-0002').body).notes, record(2).notes, 'nothing of the refused save was written');
    assert.equal(rowOf(ctx, 'rec-5000'), undefined);
    // Refreshed, the same edit saves, and the other writer's change is still there.
    const fresh = (await call(ctx, '/api/state')).data;
    fresh.state.manual_entries.find(row => row.id === 'rec-0002').notes = 'page edit';
    assert.equal((await put(ctx, fresh.version, fresh.state)).status, 200);
    const after = (await call(ctx, '/api/state')).data.state;
    assert.equal(after.manual_entries.find(row => row.id === 'rec-0002').notes, 'page edit');
    if (other === addsRecord) assert.equal(after.manual_entries.at(-1).id, 'rec-0900');
    if (other === addsFile) assert.equal(after.manual_entries.find(row => row.id === 'rec-0004').attachments.length, 1);
    if (other === changesStatus) assert.equal(after.manual_entries.find(row => row.id === 'rec-0004').status, 'SENT');
  }
});

test('a single-document save that was under way when the copy switched modes gets 409 and cannot undo the switch', async () => {
  const ctx = environment(tracker(30));
  const before = (await call(ctx, '/api/state')).data;
  const edited = structuredClone(before.state);
  edited.manual_entries[3].notes = 'saved by the page during the deploy';
  afterVersionRead(ctx, async () => assert.equal((await copy(ctx)).status, 200));
  const racing = await put(ctx, 225, edited);
  assert.equal(racing.status, 409);
  assert.equal(racing.data.error, 'A newer cloud version exists. Refresh before saving.');
  assert.equal(storedMode(ctx), 'rows');
  const copiedState = (await call(ctx, '/api/state')).data;
  assert.deepEqual([copiedState.version, copiedState.state], [225, before.state], 'the copy stands and the refused save wrote nothing');
  // The client refreshes and saves again: the same save now goes to the one row it changes.
  const again = await put(ctx, 225, edited);
  assert.equal(again.status, 200);
  assert.deepEqual(again.used.writes.map(write => write.sql.slice(0, 20)), ['UPDATE records SET v', 'UPDATE tracker_state']);
  assert.equal(storedMode(ctx), 'rows');
  assert.equal((await call(ctx, '/api/state')).data.state.manual_entries[3].notes, 'saved by the page during the deploy');
});

test('the guard of a record is row_version; the version field inside a record is not the guard and can differ', async () => {
  assert.deepEqual(Object.keys((await call(environment(tracker(3)), '/api/state')).data), ['version', 'state'], 'the single document answers as before');
  const ctx = await copied(tracker(10));
  const state = (await call(ctx, '/api/state')).data;
  assert.deepEqual(Object.keys(state), ['version', 'state', 'row_versions']);
  assert.deepEqual(state.row_versions, state.state.manual_entries.map(row => rowOf(ctx, row.id).version), 'row_versions[i] belongs to manual_entries[i]');
  // The page adds a file with a whole-tracker save and does not touch the record's own version field.
  const at = state.state.manual_entries.findIndex(row => row.id === 'rec-0004');
  state.state.manual_entries[at].attachments.push(file(4, 'confirmation'));
  assert.equal((await put(ctx, state.version, state.state)).status, 200);
  const one = (await call(ctx, '/api/records/rec-0004')).data;
  assert.deepEqual([one.row_version, one.record.version], [3, 2]);
  assert.equal((await call(ctx, '/api/records')).data.records.find(row => row.id === 'rec-0004').row_version, 3);
  assert.equal((await call(ctx, '/api/state')).data.row_versions[at], 3);
  const byBody = await call(ctx, '/api/records/rec-0004', {method: 'PATCH', body: {expected_version: one.record.version, patch: {status: 'MANUAL_APPLIED'}}});
  assert.equal(byBody.status, 409);
  assert.equal(byBody.data.current_row_version, 3);
  const byRow = await call(ctx, '/api/records/rec-0004', {method: 'PATCH', body: {expected_version: one.row_version, patch: {status: 'MANUAL_APPLIED'}}});
  assert.deepEqual([byRow.status, byRow.data.row_version, byRow.data.record.version], [200, 4, 3]);
});

test('an add can carry the version of the list its duplicate check was made on, and is refused if anything was saved since', async () => {
  const ctx = await copied(tracker(5));
  const listed = (await call(ctx, '/api/records')).data;
  assert.equal(listed.version, 225);
  // Two runners find the same advert, see no duplicate in the same list, and add it under different ids.
  const job = {company: 'Acme Civil', role: 'Civil Drafter', status: 'READY_SEEK', job_url: 'https://www.seek.com.au/job/12345678', seek_id: '12345678', attachments: []};
  const first = await call(ctx, '/api/records', {method: 'POST', body: {expected_version: listed.version, records: [{...job, id: 'runner-a'}]}});
  assert.deepEqual([first.status, first.data.version], [201, 226]);
  const second = await call(ctx, '/api/records', {method: 'POST', body: {expected_version: listed.version, records: [{...job, id: 'runner-b'}]}});
  assert.equal(second.status, 409);
  assert.deepEqual(second.data, {error: 'A newer cloud version exists. Refresh before saving.', current_version: 226});
  assert.equal(second.queries, 2, 'refused at the check, before any write');
  assert.equal((await call(ctx, '/api/records')).data.records.filter(row => row.seek_id === '12345678').length, 1);
  // The other save lands after the check and before the write: the guarded statements add nothing.
  intrude(ctx, (list, n) => n === 1, async () => assert.equal((await call(ctx, '/api/records', {method: 'POST', body: {records: [record(70)]}})).status, 201));
  const late = await call(ctx, '/api/records', {method: 'POST', body: {expected_version: 226, records: [{...job, id: 'runner-c'}, record(71)]}});
  assert.equal(late.status, 409);
  assert.equal(rowOf(ctx, 'runner-c'), undefined);
  assert.equal(rowOf(ctx, 'rec-0071'), undefined);
  assert.equal((await call(ctx, '/api/version')).data.version, 227, 'only the other save moved the version');
  for (const bad of [0, '226', 1.5, null]) assert.equal((await call(ctx, '/api/records', {method: 'POST', body: {expected_version: bad, records: [record(72)]}})).status, 400);
  assert.equal((await call(ctx, '/api/records', {method: 'POST', body: {expected_version: 227, records: [record(72)]}})).status, 201);
  assert.equal((await call(ctx, '/api/records', {method: 'POST', body: {records: [record(73)]}})).status, 201, 'without a version an add still never collides');
});

test('moving one job to the Bin and back writes the remainder only, never a record', async () => {
  const ctx = await copied();
  const before = (await call(ctx, '/api/state')).data;
  const base = ctx.db.prepare('SELECT payload FROM tracker_state WHERE id = 1').get().payload;
  const parse = JSON.parse;
  let parsed = 0;
  JSON.parse = (value, ...rest) => { parsed += String(value).length; return parse(value, ...rest); };
  let bin;
  try { bin = await call(ctx, '/api/visibility', {method: 'POST', body: {record_key: 'manual:rec-0007', deleted: true}}); } finally { JSON.parse = parse; }
  assert.equal(bin.status, 200);
  assert.deepEqual(bin.data, {version: 226, updated_at: bin.data.updated_at, entry: {record_key: 'manual:rec-0007', deleted: 1, version: 1, updated_at: bin.data.updated_at}});
  assert.equal(bin.queries, 3);
  assert.deepEqual(bin.used.writes.map(write => write.sql.startsWith('UPDATE tracker_state SET payload = ?,')), [true]);
  assert.ok(parsed < base.length + bin.bytes + 300, 'the Worker opened the remainder (about 120 KB) and no record');
  const binned = (await call(ctx, '/api/state')).data;
  assert.equal(binned.version, 226);
  assert.deepEqual(binned.state, {...before.state, updated_at: bin.data.updated_at, record_visibility: [...before.state.record_visibility, bin.data.entry]});
  // Back out of the Bin: the entry stays and counts up, as the page has always done.
  const back = await call(ctx, '/api/visibility', {method: 'POST', body: {record_key: 'manual:rec-0007', deleted: false}});
  assert.deepEqual(back.data.entry, {record_key: 'manual:rec-0007', deleted: 0, version: 2, updated_at: back.data.updated_at});
  // An entry from the old tracker keeps its other fields.
  const old = before.state.record_visibility[0];
  const toggled = await call(ctx, '/api/visibility', {method: 'POST', body: {record_key: old.record_key, deleted: !old.deleted}});
  assert.deepEqual(toggled.data.entry, {...old, deleted: old.deleted ? 0 : 1, version: old.version + 1, updated_at: toggled.data.updated_at});
  const after = (await call(ctx, '/api/state')).data;
  assert.equal(after.version, 228);
  assert.equal(after.state.record_visibility.length, before.state.record_visibility.length + 1, 'no Bin entry is ever removed');
  for (const body of [{deleted: true}, {record_key: '', deleted: true}, {record_key: 'manual:rec-0001', deleted: 1}, {record_key: 'k'.repeat(401), deleted: true}, 'not json'])
    assert.equal((await call(ctx, '/api/visibility', {method: 'POST', body})).status, 400);
  // A save that lands between this route's read and its write: the guarded statement changes nothing.
  const prepare = ctx.DB.prepare;
  ctx.DB.prepare = sql => {
    const statement = prepare(sql);
    if (!sql.startsWith('SELECT version, payload FROM tracker_state WHERE id = 1 AND')) return statement;
    const first = statement.first;
    statement.first = async () => { const value = await first.call(statement); ctx.DB.prepare = prepare; await call(ctx, '/api/records', {method: 'POST', body: {records: [record(950)]}}); return value; };
    return statement;
  };
  const lost = await call(ctx, '/api/visibility', {method: 'POST', body: {record_key: 'manual:rec-0008', deleted: true}});
  assert.equal(lost.status, 409);
  assert.deepEqual({...(await call(ctx, '/api/state')).data.state, updated_at: '', manual_entries: []}, {...after.state, updated_at: '', manual_entries: []});
  // Before the copy the route is not active and changes nothing.
  const single = environment(tracker(5));
  const refused = await call(single, '/api/visibility', {method: 'POST', body: {record_key: 'manual:rec-0001', deleted: true}});
  assert.equal(refused.status, 409);
  assert.match(refused.data.error, /not active/);
  assert.equal((await call(single, '/api/version')).data.version, 225);
});

test('every request path stays inside the Workers Free plan limits on a tracker of 400 records', async () => {
  const ctx = environment();
  const seen = [];
  const measure = async (name, expected, path, options) => {
    const reply = await call(ctx, path, options);
    assert.ok(reply.status < 300, `${name}: ${reply.status} ${JSON.stringify(reply.data).slice(0, 120)}`);
    assert.equal(reply.queries, expected, name + ' D1 queries');
    assert.ok(reply.queries <= LIMITS.queries && reply.used.largestStatement <= LIMITS.statementBytes && reply.used.mostParameters <= LIMITS.parameters && reply.used.largestValue <= LIMITS.valueBytes, name);
    seen.push({request: name, d1_queries: reply.queries, statements: reply.used.statements, longest_sql_bytes: reply.used.largestStatement, most_parameters: reply.used.mostParameters,
      largest_statement_values: reply.used.largestValue, largest_batch_bytes: reply.used.largestBatch, response_bytes: reply.bytes});
    return reply.data;
  };
  const doc = await measure('GET /api/state (single document)', 2, '/api/state');
  await measure('PUT /api/state (single document)', 3, '/api/state', {method: 'PUT', body: {expected_version: doc.version, state: doc.state}});
  await measure('GET /api/version', 2, '/api/version');
  await measure('POST /api/admin/backfill (403 records)', 16, '/api/admin/backfill', {method: 'POST', body: {expected_version: doc.version + 1}});
  await measure('POST /api/admin/backfill (already done)', 3, '/api/admin/backfill', {method: 'POST'});
  const rows = await measure('GET /api/state (rows)', 3, '/api/state');
  const changed = structuredClone(rows.state);
  changed.manual_entries[200].notes = 'one changed record';
  await measure('PUT /api/state (rows, one record changed)', 4, '/api/state', {method: 'PUT', body: {expected_version: rows.version, state: changed}});
  await measure('GET /api/records', 2, '/api/records');
  await measure('GET /api/records/<id>', 2, '/api/records/rec-0200');
  await measure('POST /api/records (50 records)', 3, '/api/records', {method: 'POST', body: {records: Array.from({length: 50}, (_, i) => record(1000 + i))}});
  await measure('PATCH /api/records/<id>', 3, '/api/records/rec-0300', {method: 'PATCH', body: {expected_version: 1, patch: {status: 'MANUAL_APPLIED'}}});
  await measure('POST /api/visibility', 3, '/api/visibility', {method: 'POST', body: {record_key: 'manual:rec-0300', deleted: true}});
  const wrong = await call(ctx, '/api/records', {headers: {'X-Tracker-Code': '000000'}});
  assert.equal(wrong.status, 401);
  assert.equal(wrong.queries, 2);
  seen.push({request: 'any route, wrong code', d1_queries: wrong.queries, statements: wrong.used.statements, longest_sql_bytes: wrong.used.largestStatement, most_parameters: wrong.used.mostParameters,
    largest_statement_values: wrong.used.largestValue, largest_batch_bytes: 0, response_bytes: wrong.bytes});
  console.table(seen);
});

test('reading the tracker, the list or one record parses and re-serialises nothing; a change opens one record', async () => {
  const ctx = await copied();
  const watched = async (path, options) => {
    const parse = JSON.parse, stringify = JSON.stringify;
    let parsed = 0, written = 0;
    JSON.parse = (value, ...rest) => { parsed += String(value).length; return parse(value, ...rest); };
    JSON.stringify = (...args) => { const out = stringify(...args); written += out?.length || 0; return out; };
    try { return {...await raw(ctx, path, options), parsed, written}; } finally { JSON.parse = parse; JSON.stringify = stringify; }
  };
  const state = await watched('/api/state');
  assert.equal(state.status, 200);
  assert.ok(state.text.length > 1_700_000);
  assert.deepEqual([state.parsed, state.written < 100], [0, true]);
  const list = await watched('/api/records');
  assert.deepEqual([list.status, list.parsed, list.written < 100], [200, 0, true]);
  const one = await watched('/api/records/rec-0050');
  assert.deepEqual([one.status, one.parsed, one.written], [200, 0, 0]);
  const poll = await watched('/api/version');
  assert.deepEqual([poll.status, poll.parsed, poll.written < 120], [200, 0, true]);
  const body = JSON.stringify({expected_version: 3, patch: {status: 'MANUAL_APPLIED'}});
  const patch = await watched('/api/records/rec-0050', {method: 'PATCH', body});
  assert.equal(patch.status, 200);
  assert.ok(patch.parsed < 6_000 && patch.written < 12_000, 'one record of about 4 KB, not the 1.7 MB tracker');
});

test('every new route needs the code, the wrong-code throttle is unchanged, and PATCH is allowed from the site only', async () => {
  const routes = [['/api/version', 'GET'], ['/api/records', 'GET'], ['/api/records', 'POST'], ['/api/records/rec-0001', 'GET'], ['/api/records/rec-0001', 'PATCH'],
    ['/api/visibility', 'POST'], ['/api/admin/backfill', 'POST'], ['/api/admin/restore-document', 'POST']];
  for (const mode of ['document', 'rows']) {
    const ctx = mode === 'rows' ? await copied(tracker(5)) : environment(tracker(5));
    const before = (await call(ctx, '/api/state')).data;
    for (const [path, method] of routes) {
      const body = method === 'GET' ? undefined : {expected_version: 225, patch: {status: 'MANUAL_APPLIED'}, records: [record(50)], record_key: 'manual:rec-0001', deleted: true};
      for (const code of ['000000', '', '65432', '6543210']) {
        ctx.db.exec('DELETE FROM auth_attempts');
        assert.equal((await call(ctx, path, {method, body, headers: {'X-Tracker-Code': code}})).status, 401, `${mode} ${method} ${path}`);
      }
    }
    assert.deepEqual((await call(ctx, '/api/state')).data, before, 'requests without the code changed nothing');
    assert.equal(storedMode(ctx), mode);
    ctx.db.exec('DELETE FROM auth_attempts');
    for (let i = 0; i < 5; i++) assert.equal((await call(ctx, routes[i][0], {method: 'GET', headers: {'X-Tracker-Code': '000000'}})).status, 401);
    const throttled = await call(ctx, '/api/records', {headers: {'X-Tracker-Code': '000000'}});
    assert.equal(throttled.status, 429);
    assert.equal((await call(ctx, '/api/records')).status, 429, 'even the right code waits out the window, as before');
  }
  const ctx = await copied(tracker(5));
  const preflight = await api.fetch(new Request('https://tracker.example/api/records/rec-0001', {method: 'OPTIONS', headers: {Origin: 'https://macdarenz-droid.github.io'}}), ctx.env);
  assert.equal(preflight.status, 204);
  assert.match(preflight.headers.get('Access-Control-Allow-Methods'), /PATCH/);
  assert.equal(preflight.headers.get('Access-Control-Allow-Origin'), 'https://macdarenz-droid.github.io');
  assert.equal((await raw(ctx, '/api/records', {headers: {Origin: 'https://other.example'}})).status, 403);
  const allowed = await raw(ctx, '/api/records', {headers: {Origin: 'https://macdarenz-droid.github.io'}});
  assert.equal(allowed.headers.get('Cache-Control'), 'no-store');
  assert.equal(allowed.headers.get('X-Content-Type-Options'), 'nosniff');
});

test('a failure is logged without the code and without any record content', async () => {
  const ctx = await copied(tracker(5));
  const marker = 'PRIVATE-NOTE-IN-A-RECORD';
  ctx.db.prepare('UPDATE records SET body = ? WHERE id = ?').run(`{"id":"rec-0001","notes":"${marker}" broken`, 'rec-0001');
  const original = {error: console.error, log: console.log, warn: console.warn}, lines = [];
  for (const level of Object.keys(original)) console[level] = (...args) => lines.push(args.map(String).join(' '));
  let broken, refused, unavailable;
  try {
    broken = await call(ctx, '/api/records/rec-0001', {method: 'PATCH', body: {expected_version: 2, patch: {notes: marker + ' again'}}});
    refused = await call(ctx, '/api/records', {method: 'POST', body: {records: [record(3, {notes: marker})]}});
    ctx.DB.batch = async () => { throw Error(`D1_ERROR: near "${marker}": syntax error`); };
    unavailable = await call(ctx, '/api/records/rec-0002', {method: 'PATCH', body: {expected_version: 3, patch: {notes: marker}}});
  } finally { Object.assign(console, original); }
  assert.equal(broken.status, 503);
  assert.equal(refused.status, 409);
  assert.equal(unavailable.status, 503);
  assert.deepEqual(lines, ['Tracker API failure PATCH /api/records SyntaxError ', 'Tracker API failure PATCH /api/records Error D1_ERROR']);
  for (const reply of [broken, unavailable]) assert.deepEqual(reply.data, {error: 'Cloud save is temporarily unavailable. Nothing was saved by this request.'});
});
