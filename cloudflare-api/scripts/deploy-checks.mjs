import {readFileSync, writeFileSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {join} from 'node:path';

const mode = process.argv[2];
const dbName = 'job-tracker-db';
const workerUrl = 'https://job-tracker-api.mmarcdarenz.workers.dev';
const checkpoint = join(process.env.RUNNER_TEMP || '/tmp', 'job-tracker-deploy-preflight.json');

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

function tableCounts() {
  const tables = new Set(queryRows("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('jobs','files','tracker_state','document_index','auth_attempts')").map(row => row.name));
  const count = table => tables.has(table) ? Number(queryRows(`SELECT COUNT(*) AS count FROM ${table}`)[0]?.count) : 0;
  const jobs = count('jobs'), files = count('files'), states = count('tracker_state');
  if (![jobs, files, states].every(Number.isSafeInteger)) throw Error('Could not verify D1 row counts.');
  if (files && !jobs) throw Error('Old file rows exist without a jobs table; manual reconciliation is required.');
  if (files && Number(queryRows('SELECT COUNT(*) AS count FROM files f LEFT JOIN jobs j ON j.id=f.job_id WHERE j.id IS NULL')[0]?.count))
    throw Error('Orphaned old file references need manual reconciliation before deployment.');
  return {jobs, files, states, tables:[...tables]};
}

function assertExistingStateReconciled(counts) {
  if (!counts.states || !counts.jobs) return;
  const saved = queryRows('SELECT payload FROM tracker_state WHERE id=1')[0];
  if (!saved?.payload) throw Error('Existing tracker state cannot be inspected.');
  const state = parseJson(saved.payload, 'Existing tracker state');
  const existing = new Set((state.manual_entries || []).map(row => row.id));
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
  console.log(`Existing D1 verified: ${counts.jobs} jobs, ${counts.files} files, ${counts.states} tracker state rows.`);
  console.log('Recovery bookmark before migration:');
  console.log(wrangler('d1', 'time-travel', 'info', dbName));
  writeFileSync(checkpoint, JSON.stringify(counts));
}

async function afterMigration() {
  const before = parseJson(readFileSync(checkpoint, 'utf8'), 'Preflight checkpoint');
  const after = tableCounts();
  if (after.jobs < before.jobs || after.files < before.files || !after.tables.includes('tracker_state') || !after.tables.includes('document_index') || !after.tables.includes('auth_attempts'))
    throw Error('Existing rows decreased or new tables are missing after migration. Deployment stopped.');
  console.log(`Additive migration verified: ${after.jobs} old jobs and ${after.files} old files retained.`);
  writeFileSync(checkpoint, JSON.stringify({...after,previous:before}));
}

async function verify() {
  requireEnvironment();
  const before = parseJson(readFileSync(checkpoint, 'utf8'), 'Preflight checkpoint');
  const noCode = await fetch(`${workerUrl}/api/state`, {cache:'no-store'});
  if (noCode.status !== 401) throw Error(`Unauthenticated /api/state returned ${noCode.status}, expected 401.`);
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
  console.log(`Live verification passed: ${state.applications.length} applications, ${state.leads.length} leads, ${state.manual_entries.length} manual entries, ${state.record_visibility.length} Bin entries; ${imported.length} old jobs and ${references.length} old file references imported; shared D1 version ${current.version}.`);
}

try {
  if (mode === 'prepare') await prepare();
  else if (mode === 'after-migration') await afterMigration();
  else if (mode === 'verify') await verify();
  else throw Error('Expected prepare, after-migration or verify.');
} catch (cause) {
  console.error(cause.message);
  process.exitCode = 1;
}
