import {existsSync, readdirSync, readFileSync, writeFileSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {join} from 'node:path';
import {isDeepStrictEqual} from 'node:util';

const mode = process.argv[2];
const dbName = 'job-tracker-db';
// The tests point the live checks at a Worker on this machine. No other address is accepted, so the access code
// can never be sent anywhere but the real Worker. "target" prints the address in use.
const workerUrl = /^http:\/\/127\.0\.0\.1:\d+$/.test(process.env.TRACKER_API_TEST_URL || '') ? process.env.TRACKER_API_TEST_URL : 'https://job-tracker-api.mmarcdarenz.workers.dev';
const checkpoint = join(process.env.RUNNER_TEMP || '/tmp', 'job-tracker-deploy-preflight.json');
const baseTables = ['jobs', 'files', 'tracker_state', 'document_index', 'auth_attempts'];
const rowsMode = `substr(payload, 1, 21) = '{"storage":"rows-v1",'`; // the marker src/index.js writes when records have their own rows

function requireEnvironment() {
  if (!process.env.CLOUDFLARE_ACCOUNT_ID || !process.env.CLOUDFLARE_API_TOKEN)
    throw Error('Cloudflare account ID and API token must be configured in the workflow.');
  if (!/^\d{6}$/.test(process.env.TRACKER_ACCESS_CODE || ''))
    throw Error('TRACKER_ACCESS_CODE must be a six-digit GitHub Actions secret.');
}

function wrangler(...args) {
  const result = spawnSync('./node_modules/.bin/wrangler', args, {encoding:'utf8', maxBuffer: 4 * 1024 * 1024});
  if (result.status !== 0) throw Error(`Wrangler ${args.slice(0, 2).join(' ')} failed: ${(result.stderr || result.stdout || '').slice(-1200)}`);
  return result.stdout.trim();
}

function parseJson(text, label) {
  try { return JSON.parse(text); } catch { throw Error(`${label} did not return parseable JSON. No database change was attempted.`); }
}

function databaseList(value) {
  if (Array.isArray(value)) return value;
  if (Array.isArray(value?.result)) return value.result;
  if (Array.isArray(value?.databases)) return value.databases;
  throw Error('Unrecognised D1 list result. No database change was attempted.');
}

function queryRows(sql) {
  const value = parseJson(wrangler('d1', 'execute', 'DB', '--remote', '--command', sql, '--json'), 'D1 query');
  const batch = Array.isArray(value) ? value[0] : value;
  const rows = batch?.results || batch?.result?.results;
  if (!Array.isArray(rows)) throw Error('Unrecognised D1 query result; stopping before deployment.');
  return rows;
}

// Every table a migration in this folder creates, so a new migration is checked without editing this script.
function migrationTables() {
  if (!existsSync('migrations')) return [];
  return readdirSync('migrations').filter(name => name.endsWith('.sql')).sort()
    .flatMap(name => [...readFileSync(join('migrations', name), 'utf8').matchAll(/CREATE TABLE IF NOT EXISTS (\w+)/g)].map(match => match[1]));
}

function tableCounts() {
  const wanted = [...new Set([...baseTables, ...migrationTables()])];
  const tables = new Set(queryRows(`SELECT name FROM sqlite_master WHERE type='table' AND name IN (${wanted.map(name => `'${name}'`).join(',')})`).map(row => row.name));
  const count = table => tables.has(table) ? Number(queryRows(`SELECT COUNT(*) AS count FROM ${table}`)[0]?.count) : 0;
  const jobs = count('jobs'), files = count('files'), states = count('tracker_state');
  const documents = count('document_index'), records = count('records'), backups = count('tracker_state_backup');
  if (![jobs, files, states, documents, records, backups].every(Number.isSafeInteger)) throw Error('Could not verify D1 row counts.');
  if (files && !jobs) throw Error('Old file rows exist without a jobs table; manual reconciliation is required.');
  if (files && Number(queryRows('SELECT COUNT(*) AS count FROM files f LEFT JOIN jobs j ON j.id=f.job_id WHERE j.id IS NULL')[0]?.count))
    throw Error('Orphaned old file references need manual reconciliation before deployment.');
  return {jobs, files, states, documents, records, backups, tables:[...tables]};
}

function assertExistingStateReconciled(counts) {
  if (!counts.states || !counts.jobs) return;
  let existing;
  if (counts.records && Number(queryRows(`SELECT ${rowsMode} AS rows_mode FROM tracker_state WHERE id=1`)[0]?.rows_mode)) {
    // Records have their own rows: the imported jobs are rows too, and the single row no longer lists them.
    existing = new Set(queryRows("SELECT id FROM records WHERE id LIKE 'cloudflare-legacy-job:%'").map(row => row.id));
  } else {
    const saved = queryRows('SELECT payload FROM tracker_state WHERE id=1')[0];
    if (!saved?.payload) throw Error('Existing tracker state cannot be inspected.');
    const state = parseJson(saved.payload, 'Existing tracker state');
    existing = new Set((state.manual_entries || []).map(row => row.id));
  }
  const legacyIds = queryRows('SELECT id FROM jobs');
  if (legacyIds.some(row => !existing.has(`cloudflare-legacy-job:${row.id}`)))
    throw Error('A tracker state already exists but does not include all old jobs. Stop for a guarded merge.');
}

async function prepare() {
  requireEnvironment();
  const list = databaseList(parseJson(wrangler('d1', 'list', '--json'), 'D1 list'));
  const matches = list.filter(db => db.name === dbName);
  if (matches.length !== 1) throw Error('Expected exactly one existing job-tracker-db database. No new database will be created.');
  const id = matches[0].uuid || matches[0].id;
  if (!/^[0-9a-f]{8}-[0-9a-f-]{27,}$/i.test(id || '')) throw Error('Existing D1 ID is missing or invalid.');
  const config = JSON.parse(readFileSync('wrangler.jsonc', 'utf8'));
  if (config.name !== 'job-tracker-api' || config.d1_databases?.[0]?.database_name !== dbName || config.r2_buckets?.[0]?.bucket_name !== 'job-tracker-files')
    throw Error('Worker name or existing D1/R2 resource names do not match the reviewed configuration.');
  config.d1_databases[0].database_id = id;
  writeFileSync('wrangler.jsonc', JSON.stringify(config, null, 2) + '\n');

  if (matches[0].version !== 'production')
    throw Error('D1 Time Travel could not be confirmed for this database. Obtain a separate backup before deployment.');
  const counts = tableCounts();
  assertExistingStateReconciled(counts);
  console.log(`Existing D1 verified: ${counts.jobs} jobs, ${counts.files} files, ${counts.states} tracker state rows, ${counts.documents} stored documents, ${counts.records} record rows.`);
  console.log('Recovery bookmark before migration:');
  console.log(wrangler('d1', 'time-travel', 'info', dbName));
  writeFileSync(checkpoint, JSON.stringify(counts));
}

async function afterMigration() {
  const before = parseJson(readFileSync(checkpoint, 'utf8'), 'Preflight checkpoint');
  const after = tableCounts();
  const required = [...new Set(['tracker_state', 'document_index', 'auth_attempts', ...migrationTables()])];
  const missing = required.filter(name => !after.tables.includes(name));
  const fewer = ['jobs', 'files', 'states', 'documents', 'records', 'backups'].filter(name => after[name] < (before[name] || 0));
  if (missing.length || fewer.length)
    throw Error(`Existing rows decreased or new tables are missing after migration (missing tables: ${missing.join(', ') || 'none'}; fewer rows: ${fewer.join(', ') || 'none'}). Deployment stopped.`);
  console.log(`Additive migration verified: ${after.jobs} old jobs and ${after.files} old files retained; ${after.states} tracker state rows, ${after.documents} stored documents and ${after.records} record rows retained; tables present: ${required.join(', ')}.`);
  writeFileSync(checkpoint, JSON.stringify({...after,previous:before}));
}

async function api(path, body) {
  const response = await fetch(workerUrl + path, {method:body ? 'POST' : 'GET', cache:'no-store', body:body && JSON.stringify(body),
    headers:{'X-Tracker-Code':process.env.TRACKER_ACCESS_CODE, ...(body ? {'Content-Type':'application/json'} : {})}});
  let data = null;
  try { data = await response.json(); } catch {}
  return {status:response.status, data};
}

// The Actions log is public: counts and version numbers only, never a record or a message from the Worker.
const tally = state => `${state.applications.length} applications, ${state.leads.length} leads, ${state.manual_entries.length} manual entries, ${state.record_visibility.length} Bin entries`;
const refusal = {400:'a record in the document cannot be copied as it is (an id is missing, not text, or used twice)', 409:'the tracker kept changing during the copy',
  413:'one record is larger than a row may hold', 404:'the deployed Worker does not have the copy route', 503:'the Worker failed; see its log in Cloudflare'};

// Moves the tracker from one JSON document to one D1 row per record, once, and proves from outside that nothing
// a client reads has changed. Until the Worker's last statement the tracker stays the single document, so every
// failure before that leaves the old mode serving. A mismatch found here after that statement is undone below.
async function backfill() {
  requireEnvironment();
  for (let attempt = 1; ; attempt++) {
    const before = await api('/api/state');
    if (before.status !== 200 || !Number.isSafeInteger(before.data?.version) || !Array.isArray(before.data.state?.manual_entries))
      throw Error(`Reading the tracker before the copy returned ${before.status}. Nothing was changed.`);
    const version = before.data.version, entries = before.data.state.manual_entries;
    const copy = await api('/api/admin/backfill', {expected_version:version});
    if (copy.status === 409 && attempt < 3) { console.log('The tracker was saved by someone else during the copy. Reading it again.'); continue; }
    if (copy.status !== 200 || copy.data?.storage !== 'rows') {
      // A reply lost after the Worker's last statement hides a switch that did happen, so the mode comes from a fresh
      // read, never from the failed answer. Reverting the Worker while records have their own rows hides every record.
      const storage = (await api('/api/version')).data?.storage;
      const where = storage === 'document' ? 'The copy did not happen: the tracker is still the single document and serves as before.'
        : storage === 'rows' ? 'But the tracker now reports one row per record, so the switch did happen. Run the workflow again to finish the checks; do not revert the Worker.'
        : 'Its storage mode could not be read. Check GET /api/version before anything else, and do not revert the Worker until it says "document".';
      throw Error(`The copy step answered HTTP ${copy.status}: ${refusal[copy.status] || 'unexpected answer'}. ${where}`);
    }
    const after = await api('/api/state'), list = await api('/api/records');
    const listed = list.status === 200 && after.status === 200 && Array.isArray(list.data?.records) &&
      (list.data.version !== after.data.version || (list.data.records.length === after.data.state.manual_entries.length && list.data.records.every((row, i) => row.id === after.data.state.manual_entries[i].id)));
    if (copy.data.already) {
      if (!listed) throw Error(`Records already have their own rows, but the tracker and the record list do not agree (HTTP ${after.status} and ${list.status}). Nothing was changed by this step.`);
      console.log(`Records already have their own rows: nothing to copy. Version ${after.data.version}: ${tally(after.data.state)}, ${list.data.records.length} listed records.`);
      return;
    }
    const same = listed && after.data.version === version && copy.data.version === version && copy.data.records === entries.length && isDeepStrictEqual(after.data.state, before.data.state);
    if (same) {
      console.log(`Copied ${copy.data.records} manual entries to one row each. Version ${version} before and after; content deep-equal before and after: ${tally(after.data.state)}. The single row now holds ${copy.data.remainder_bytes} bytes.`);
      return;
    }
    if (after.status === 200 && after.data?.version !== version) {
      // Say which mode the tracker is in from a fresh read, not from what the copy answered a moment ago.
      const storage = (await api('/api/version')).data?.storage;
      const where = storage === 'rows' ? 'Records now have their own rows.' : storage === 'document' ? 'The tracker is a single document at this moment.' : 'Its storage mode could not be read.';
      throw Error(`The copy happened and the Worker's own row-by-row comparison passed, but the tracker was saved again (version ${version} then ${after.data?.version}) before this job could compare it. ${where} Run the workflow again to finish the checks.`);
    }
    const undo = await api('/api/admin/restore-document', {expected_version:version});
    throw Error(`After the copy the tracker did not read back the same (state HTTP ${after.status}, list HTTP ${list.status}). `
      + (undo.status === 200 && undo.data?.storage === 'document' ? 'The single document was put back and the Worker serves it as before.' : `Putting the single document back was refused (HTTP ${undo.status}); restore it by hand as described in cloudflare-api/README.md.`));
  }
}

async function verify() {
  requireEnvironment();
  const before = parseJson(readFileSync(checkpoint, 'utf8'), 'Preflight checkpoint');
  const noCode = await fetch(`${workerUrl}/api/state`, {cache:'no-store'});
  if (noCode.status !== 401) throw Error(`Unauthenticated /api/state returned ${noCode.status}, expected 401.`);
  for (const path of ['/api/records', '/api/version']) {
    const open = await fetch(workerUrl + path, {cache:'no-store'});
    if (open.status !== 401) throw Error(`Unauthenticated ${path} returned ${open.status}, expected 401.`);
  }
  const headers = {'X-Tracker-Code':process.env.TRACKER_ACCESS_CODE};
  const response = await fetch(`${workerUrl}/api/state`, {headers, cache:'no-store'});
  if (!response.ok) throw Error(`Authenticated /api/state returned ${response.status}.`);
  const {version,state} = await response.json();
  if (!Number.isSafeInteger(version) || !state || state.applications?.length < 14 || state.leads?.length < 46 || state.record_visibility?.length < 11)
    throw Error('Historical applications, leads or Bin entries are missing.');
  const imported = (state.manual_entries || []).filter(row => /^cloudflare-legacy-job:\d+$/.test(row.id));
  const references = imported.flatMap(row => row.attachments || []).filter(file => /^cloudflare-legacy-file:\d+$/.test(file.id));
  if (state.manual_entries.length < 3 + before.jobs || imported.length < before.jobs || references.length < before.files)
    throw Error('An older job or file reference is missing from the imported tracker state.');

  // A no-op guarded write proves that D1 Save is working without adding a record.
  const saved = await fetch(`${workerUrl}/api/state`, {method:'PUT', headers:{...headers,'Content-Type':'application/json'}, body:JSON.stringify({expected_version:version,state})});
  if (!saved.ok) throw Error(`Version-checked Save failed (${saved.status}); do not connect the frontend.`);
  const write = await saved.json();
  const again = await fetch(`${workerUrl}/api/state`, {headers, cache:'no-store'});
  const current = await again.json();
  if (current.version !== version + 1 || write.version !== current.version)
    throw Error('The saved version was not visible on the next read.');
  const poll = await api('/api/version'), list = await api('/api/records');
  if (poll.status !== 200 || poll.data?.version !== current.version) throw Error('The small version check does not agree with the tracker.');
  if (poll.data.storage === 'rows' ? list.status !== 200 || list.data?.records?.length !== current.state.manual_entries.length : list.status !== 409)
    throw Error(`The record list does not agree with the tracker (storage ${poll.data.storage}, list HTTP ${list.status}).`);
  console.log(`Storage: ${poll.data.storage === 'rows' ? 'one row per record' : 'single document'}.`);
  console.log(`Live verification passed: ${state.applications.length} applications, ${state.leads.length} leads, ${state.manual_entries.length} manual entries, ${state.record_visibility.length} Bin entries; ${imported.length} old jobs and ${references.length} old file references imported; shared D1 version ${current.version}.`);
}

try {
  if (mode === 'prepare') await prepare();
  else if (mode === 'after-migration') await afterMigration();
  else if (mode === 'backfill') await backfill();
  else if (mode === 'verify') await verify();
  else if (mode === 'target') console.log(workerUrl);
  else throw Error('Expected prepare, after-migration, backfill or verify.');
} catch (cause) {
  console.error(cause.message);
  process.exitCode = 1;
}
