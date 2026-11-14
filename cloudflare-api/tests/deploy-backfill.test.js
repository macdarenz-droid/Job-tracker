// The deploy workflow's own migration checks, run against the Worker on this machine and a stand-in for wrangler.
import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import {mkdtempSync, mkdirSync, writeFileSync, readFileSync, chmodSync, cpSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {spawn, spawnSync} from 'node:child_process';
import api from '../src/index.js';
import {CODE, tracker, environment} from './helpers.js';

const checks = resolve('scripts/deploy-checks.mjs');
const mode = ctx => ctx.db.prepare('SELECT substr(payload, 1, 21) AS head FROM tracker_state WHERE id = 1').get().head === '{"storage":"rows-v1",' ? 'rows' : 'document';

// Serves the Worker on 127.0.0.1. `tamper` may replace a response body, to play a Worker that reads back wrongly,
// or act as another client before the response goes out.
async function serve(ctx, tamper = () => null) {
  const server = http.createServer(async (req, res) => {
    const chunks = [];
    for await (const chunk of req) chunks.push(chunk);
    const headers = Object.fromEntries(['x-tracker-code', 'content-type', 'content-length'].filter(name => req.headers[name]).map(name => [name, req.headers[name]]));
    ctx.invocation();
    const response = await api.fetch(new Request('http://127.0.0.1' + req.url, {method: req.method, headers, body: chunks.length ? Buffer.concat(chunks) : undefined}), ctx.env);
    const text = await response.text();
    res.writeHead(response.status, {'Content-Type': 'application/json'});
    res.end(await tamper(req, text) ?? text);
  });
  await new Promise(done => server.listen(0, '127.0.0.1', done));
  return server;
}
function run(step, server, extra = {}) {
  const env = {...process.env, CLOUDFLARE_ACCOUNT_ID: 'test-account', CLOUDFLARE_API_TOKEN: 'fixture-token', TRACKER_ACCESS_CODE: CODE,
    TRACKER_API_TEST_URL: 'http://127.0.0.1:' + server.address().port, ...extra};
  return new Promise(done => {
    const child = spawn(process.execPath, [checks, step], {env});
    let stdout = '', stderr = '';
    child.stdout.on('data', data => { stdout += data; });
    child.stderr.on('data', data => { stderr += data; });
    child.on('close', status => done({status, stdout, stderr}));
  });
}
const quiet = output => { assert.doesNotMatch(output, /Example Civil|rec-0|654321|Melton/, 'the public log has counts only'); return output; };

test('the deploy step copies the tracker, proves it reads back the same, prints counts only, and is harmless to run again', async () => {
  const ctx = environment(tracker(120)), server = await serve(ctx);
  const dir = mkdtempSync(join(tmpdir(), 'tracker-verify-'));
  writeFileSync(join(dir, 'job-tracker-deploy-preflight.json'), JSON.stringify({jobs: 0, files: 0}));
  try {
    const early = await run('verify', server, {RUNNER_TEMP: dir});
    assert.equal(early.status, 0, early.stderr);
    assert.match(quiet(early.stdout), /Storage: single document\./);
    const first = await run('backfill', server);
    assert.equal(first.status, 0, first.stderr);
    assert.match(quiet(first.stdout), /^Copied 123 manual entries to one row each\. Version 226 before and after; content deep-equal before and after: 14 applications, 46 leads, 123 manual entries, 11 Bin entries\. The single row now holds \d+ bytes\.\n$/);
    assert.equal(mode(ctx), 'rows');
    const second = await run('backfill', server);
    assert.equal(second.status, 0, second.stderr);
    assert.match(quiet(second.stdout), /^Records already have their own rows: nothing to copy\. Version 226: 14 applications, 46 leads, 123 manual entries, 11 Bin entries, 123 listed records\.\n$/);
    const live = await run('verify', server, {RUNNER_TEMP: dir});
    assert.equal(live.status, 0, live.stderr);
    assert.match(quiet(live.stdout), /Storage: one row per record\.\nLive verification passed: 14 applications, 46 leads, 123 manual entries, 11 Bin entries; .* shared D1 version 227\./);
  } finally { server.close(); rmSync(dir, {recursive: true, force: true}); }
});

test('when the Worker refuses the copy the step fails and the tracker is still the single document', async () => {
  const state = tracker(30);
  state.manual_entries.push({...state.manual_entries[10]});
  const ctx = environment(state), server = await serve(ctx);
  try {
    const before = ctx.db.prepare('SELECT version, payload FROM tracker_state WHERE id = 1').get();
    const result = await run('backfill', server);
    assert.equal(result.status, 1);
    assert.match(quiet(result.stderr), /answered HTTP 400: a record in the document cannot be copied as it is.*\. The copy did not happen: the tracker is still the single document and serves as before/);
    assert.equal(result.stdout, '');
    assert.deepEqual(ctx.db.prepare('SELECT version, payload FROM tracker_state WHERE id = 1').get(), before);
    const wrongCode = await run('backfill', server, {TRACKER_ACCESS_CODE: '111111'});
    assert.equal(wrongCode.status, 1);
    assert.match(wrongCode.stderr, /returned 401\. Nothing was changed\./);
  } finally { server.close(); }
});

test('when the copy switched but its reply was lost, the step says so from a fresh read and does not claim the single document', async () => {
  const ctx = environment(tracker(30));
  let once = true;
  // The Worker switches modes, then the answer is cut off on the way back: the runner sees a 200 with no readable body.
  const server = await serve(ctx, req => { if (req.url === '/api/admin/backfill' && once) { once = false; return '{"stor'; } return null; });
  try {
    const result = await run('backfill', server);
    assert.equal(result.status, 1);
    assert.equal(mode(ctx), 'rows');
    assert.match(quiet(result.stderr), /answered HTTP 200: unexpected answer\. But the tracker now reports one row per record, so the switch did happen\. Run the workflow again to finish the checks; do not revert the Worker\./);
    assert.doesNotMatch(result.stderr, /still the single document/);
    const again = await run('backfill', server);
    assert.equal(again.status, 0, again.stderr);
    assert.match(quiet(again.stdout), /^Records already have their own rows: nothing to copy\./);
  } finally { server.close(); }
});

test('when the tracker does not read back the same after the copy, the step puts the single document back and fails', async () => {
  const ctx = environment(tracker(30));
  const original = ctx.db.prepare('SELECT version, payload FROM tracker_state WHERE id = 1').get();
  let copiedYet = false;
  const server = await serve(ctx, (req, text) => {
    if (req.url === '/api/admin/backfill') copiedYet = true;
    if (!copiedYet || req.url !== '/api/state' || req.method !== 'GET') return null;
    const body = JSON.parse(text);
    body.state.manual_entries[4].notes = 'not what was stored';
    return JSON.stringify(body);
  });
  try {
    const result = await run('backfill', server);
    assert.equal(result.status, 1);
    assert.match(quiet(result.stderr), /did not read back the same .*The single document was put back and the Worker serves it as before\./);
    assert.equal(mode(ctx), 'document');
    assert.deepEqual(ctx.db.prepare('SELECT version, payload FROM tracker_state WHERE id = 1').get(), original);
  } finally { server.close(); }
});

test('when someone saves between the copy and the comparison, the step fails and names the storage mode it finds', async () => {
  const send = (ctx, path, method, body) => { ctx.invocation(); return api.fetch(new Request('http://127.0.0.1' + path, {method, headers: {'X-Tracker-Code': CODE, 'Content-Type': 'application/json'}, body: JSON.stringify(body)}), ctx.env); };
  // A runner changes one record right after the copy: rows stay, and a second run finishes the checks.
  const ctx = environment(tracker(30));
  let once = true;
  const server = await serve(ctx, async req => {
    if (req.url === '/api/admin/backfill' && once) { once = false; assert.equal((await send(ctx, '/api/records/rec-0001', 'PATCH', {expected_version: 2, patch: {notes: 'a runner'}})).status, 200); }
    return null;
  });
  try {
    const result = await run('backfill', server);
    assert.equal(result.status, 1);
    assert.match(quiet(result.stderr), /saved again \(version 225 then 226\) before this job could compare it\. Records now have their own rows\. Run the workflow again/);
    assert.equal(mode(ctx), 'rows');
    const again = await run('backfill', server);
    assert.equal(again.status, 0, again.stderr);
    assert.match(quiet(again.stdout), /^Records already have their own rows: nothing to copy\. Version 226:/);
  } finally { server.close(); }
  // Someone puts the single document back and saves it: the message must not claim rows.
  const undone = environment(tracker(30));
  let first = true;
  const second = await serve(undone, async req => {
    if (req.url !== '/api/admin/backfill' || !first) return null;
    first = false;
    assert.equal((await send(undone, '/api/admin/restore-document', 'POST', {expected_version: 225})).status, 200);
    const current = await (await send(undone, '/api/state', 'GET')).json();
    assert.equal((await send(undone, '/api/state', 'PUT', {expected_version: 225, state: current.state})).status, 200);
    return null;
  });
  try {
    const result = await run('backfill', second);
    assert.equal(result.status, 1);
    assert.match(quiet(result.stderr), /saved again \(version 225 then 226\) .*The tracker is a single document at this moment\. Run the workflow again/);
    assert.equal(mode(undone), 'document');
    assert.equal((await run('backfill', second)).status, 0, 'the next run copies again');
    assert.equal(mode(undone), 'rows');
  } finally { second.close(); }
});

test('the live checks only ever talk to the real Worker or to this machine', () => {
  const target = url => spawnSync(process.execPath, [checks, 'target'], {env: {...process.env, TRACKER_API_TEST_URL: url}, encoding: 'utf8'}).stdout.trim();
  assert.equal(target('http://127.0.0.1:8123'), 'http://127.0.0.1:8123');
  for (const url of ['', 'https://evil.example', 'http://127.0.0.1:8123.evil.example', 'http://127.0.0.1:8123/x', 'http://localhost:8123'])
    assert.equal(target(url), 'https://job-tracker-api.mmarcdarenz.workers.dev');
});

// A stand-in for wrangler that answers the D1 queries of prepare and after-migration from a small description.
function wranglerFixture(db) {
  const dir = mkdtempSync(join(tmpdir(), 'tracker-migrate-'));
  mkdirSync(join(dir, 'node_modules/.bin'), {recursive: true});
  cpSync('migrations', join(dir, 'migrations'), {recursive: true});
  writeFileSync(join(dir, 'wrangler.jsonc'), readFileSync('wrangler.jsonc', 'utf8'));
  writeFileSync(join(dir, 'db.json'), JSON.stringify(db));
  const cli = `#!/usr/bin/env node
const fs=require('node:fs');
const db=JSON.parse(fs.readFileSync('db.json','utf8'));
const args=process.argv.slice(2),sql=args[args.indexOf('--command')+1]||'',out=rows=>console.log(JSON.stringify([{results:rows}]));
if(args.join(' ').startsWith('d1 list')) console.log(JSON.stringify([{name:'job-tracker-db',uuid:'12345678-1234-1234-1234-123456789abc',version:'production'}]));
else if(args.join(' ').startsWith('d1 time-travel info')) console.log('Current recovery bookmark: 00000085-0000024c');
else if(sql.includes('sqlite_master')) out(Object.keys(db.tables).filter(name=>sql.includes("'"+name+"'")).map(name=>({name})));
else if(sql.includes('LEFT JOIN')) out([{count:0}]);
else if(sql.includes('COUNT(*)')) out([{count:db.tables[sql.split(' FROM ')[1]]}]);
else if(sql.includes('AS rows_mode')) out([{rows_mode:db.rows_mode}]);
else if(sql.startsWith('SELECT id FROM records')) out(db.record_ids.map(id=>({id})));
else if(sql.startsWith('SELECT id FROM jobs')) out([{id:7}]);
else if(sql.startsWith('SELECT payload')) out([{payload:JSON.stringify({manual_entries:db.document_ids.map(id=>({id}))})}]);
else throw Error('Unrecognised fixture query: '+sql);
`;
  writeFileSync(join(dir, 'node_modules/.bin/wrangler'), cli);
  chmodSync(join(dir, 'node_modules/.bin/wrangler'), 0o755);
  const env = {...process.env, RUNNER_TEMP: dir, CLOUDFLARE_ACCOUNT_ID: 'test-account', CLOUDFLARE_API_TOKEN: 'fixture-token', TRACKER_ACCESS_CODE: CODE};
  return {dir, set: next => writeFileSync(join(dir, 'db.json'), JSON.stringify(next)), run: step => spawnSync(process.execPath, [checks, step], {cwd: dir, env, encoding: 'utf8'})};
}
const old = {jobs: 1, files: 1, tracker_state: 1, document_index: 26, auth_attempts: 0};

test('after the migration the new tables must exist and no old row may be gone', () => {
  const start = {tables: old, rows_mode: 0, record_ids: [], document_ids: ['cloudflare-legacy-job:7']};
  const {dir, set, run} = wranglerFixture(start);
  try {
    const before = run('prepare');
    assert.equal(before.status, 0, before.stderr);
    assert.match(before.stdout, /1 jobs, 1 files, 1 tracker state rows, 26 stored documents, 0 record rows\./);
    const notApplied = run('after-migration');
    assert.equal(notApplied.status, 1);
    assert.match(notApplied.stderr, /missing tables: records, tracker_state_backup; fewer rows: none/);
    set({...start, tables: {...old, records: 0, tracker_state_backup: 0, document_index: 25}});
    const lost = run('after-migration');
    assert.equal(lost.status, 1);
    assert.match(lost.stderr, /missing tables: none; fewer rows: documents/);
    set({...start, tables: {...old, records: 0, tracker_state_backup: 0}});
    const good = run('after-migration');
    assert.equal(good.status, 0, good.stderr);
    assert.match(good.stdout, /1 tracker state rows, 26 stored documents and 0 record rows retained; tables present: tracker_state, document_index, auth_attempts, records, tracker_state_backup\./);
  } finally { rmSync(dir, {recursive: true, force: true}); }
});

test('a later deployment finds the imported old jobs among the record rows', () => {
  const rows = {tables: {...old, records: 230, tracker_state_backup: 1}, rows_mode: 1, record_ids: ['cloudflare-legacy-job:7'], document_ids: []};
  const {dir, set, run} = wranglerFixture(rows);
  try {
    const found = run('prepare');
    assert.equal(found.status, 0, found.stderr);
    assert.match(found.stdout, /230 record rows\./);
    assert.equal(run('after-migration').status, 0);
    set({...rows, record_ids: []});
    const gone = run('prepare');
    assert.equal(gone.status, 1);
    assert.match(gone.stderr, /does not include all old jobs/);
    // An interrupted copy leaves rows behind while the tracker is still the single document: the document is what counts.
    set({...rows, rows_mode: 0, record_ids: [], document_ids: ['cloudflare-legacy-job:7']});
    assert.equal(run('prepare').status, 0);
  } finally { rmSync(dir, {recursive: true, force: true}); }
});
