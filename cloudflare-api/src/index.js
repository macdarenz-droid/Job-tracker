import initialState from './seed.js';

const MAX_STATE_BYTES = 1_800_000;    // the single document; after the copy, everything that is not a manual record
const MAX_RECORD_BYTES = 200_000;     // one manual record once each has its own row
const MAX_SAVE_BYTES = 1_800_000;     // what one request may write to D1 (the size one statement already carries today)
const MAX_REQUEST_BYTES = 10_000_000; // body of a whole-tracker PUT once records have their own rows
const MAX_NEW_RECORDS = 50;           // POST /api/records, also keeps its id lookup under D1's 100 bound parameters
const COPY_BATCH = 40;                // rows per D1 batch during the one-time copy
// Storage has two modes. "document": tracker_state.payload is the whole tracker (as before migration 0002).
// "rows": the payload starts with this marker and holds everything except manual_entries and updated_at;
// each manual entry is one row in records. Only POST /api/admin/backfill moves from the first to the second.
const ROWS_PREFIX = '{"storage":"rows-v1",';
const IS_ROWS = `substr(payload, 1, ${ROWS_PREFIX.length}) = '${ROWS_PREFIX}'`;
const FIXED_FIELDS = ['id', 'key', 'created_at', 'created_by'];
const SUMMARY_EXTRAS = ['key', 'job_url', 'duplicate_key', 'origin_key', 'seek_id', 'applied_date', 'sent_at', 'checked_at', 'created_at', 'created_by', 'contributor_name', 'application_method'];
const MAX_FILE_BYTES = 10 * 1024 * 1024;
const WINDOW_MS = 15 * 60 * 1000;
const ALLOWED_EXTENSIONS = {
  pdf: 'application/pdf',
  docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  png: 'image/png',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg'
};

const json = (data, status = 200, headers = {}) => new Response(JSON.stringify(data), {
  status,
  headers: {'Content-Type': 'application/json; charset=utf-8', ...headers}
});
const error = (message, status = 400) => json({error: message}, status);
const now = () => new Date().toISOString();
const hash = async value => new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value)));
const hex = bytes => [...bytes].map(v => v.toString(16).padStart(2, '0')).join('');
const text = (body, status = 200) => new Response(body, {status, headers: {'Content-Type': 'application/json; charset=utf-8'}});
const bytesOf = value => new TextEncoder().encode(value).byteLength;
const isRows = payload => payload.startsWith(ROWS_PREFIX);
const notActive = () => error('Per-record storage is not active yet. Use /api/state.', 409);
const conflict = current_version => json({error: 'A newer cloud version exists. Refresh before saving.', ...(current_version ? {current_version} : {})}, 409);

async function sameCode(candidate, secret) {
  const [left, right] = await Promise.all([hash(candidate), hash(secret)]);
  let difference = 0;
  for (let i = 0; i < left.length; i++) difference |= left[i] ^ right[i];
  return difference === 0;
}

async function authorised(request, env) {
  const code = request.headers.get('X-Tracker-Code') || '';
  const ip = request.headers.get('CF-Connecting-IP') || 'unknown';
  const slot = Math.floor(Date.now() / WINDOW_MS);
  const attempt = await env.DB.prepare('SELECT window_start, failures FROM auth_attempts WHERE ip = ?').bind(ip).first();
  if (attempt?.window_start === slot && attempt.failures >= 5) return error('Too many code attempts. Try again later.', 429);
  if (/^\d{6}$/.test(code) && await sameCode(code, env.ACCESS_CODE)) {
    if (attempt) await env.DB.prepare('DELETE FROM auth_attempts WHERE ip = ?').bind(ip).run();
    return null;
  }
  await env.DB.prepare('INSERT INTO auth_attempts (ip, window_start, failures) VALUES (?, ?, 1) ON CONFLICT(ip) DO UPDATE SET window_start = excluded.window_start, failures = CASE WHEN auth_attempts.window_start = excluded.window_start THEN auth_attempts.failures + 1 ELSE 1 END').bind(ip, slot).run();
  return error('Code not recognised.', 401);
}

async function legacySnapshot(env) {
  // The first Worker used separate jobs/files tables. Keep their records when
  // switching this same D1 database to the versioned tracker API.
  const tables = await env.DB.prepare("SELECT name FROM sqlite_master WHERE type = 'table' AND name IN ('jobs', 'files')").all();
  const names = new Set((tables.results || []).map(row => row.name));
  if (!names.has('jobs')) return initialState;
  const jobs = (await env.DB.prepare('SELECT * FROM jobs ORDER BY id').all()).results || [];
  if (!jobs.length) return initialState;
  const files = names.has('files') ? (await env.DB.prepare('SELECT * FROM files ORDER BY id').all()).results || [] : [];
  const next = structuredClone(initialState);
  const existing = new Set(next.manual_entries.map(row => row.id));
  for (const job of jobs) {
    const id = `cloudflare-legacy-job:${job.id}`;
    if (existing.has(id)) continue;
    const oldStatus = String(job.status || '').toLowerCase();
    const status = ({applied:'MANUAL_APPLIED',submitted:'MANUAL_APPLIED',interview:'INTERVIEW',offer:'OFFER',rejected:'REJECTED',lead:'LEAD'})[oldStatus] || 'LEAD';
    const attachments = files.filter(file => String(file.job_id) === String(job.id)).map(file => ({
      id: `cloudflare-legacy-file:${file.id}`,
      path: `/api/legacy-files/${file.id}`,
      filename: file.filename,
      size_bytes: file.size,
      mime_type: file.content_type,
      uploaded_at: file.created_at,
      stored_in: 'cloudflare_r2'
    }));
    next.manual_entries.push({
      id, key: `manual:${id}`, company: job.company || '', role: job.title || '',
      status, location: job.location || '', job_url: job.url || '',
      applied_date: job.applied_date || '', application_method: 'Unverified legacy entry',
      contributor_name: 'Legacy Cloudflare API',
      notes: [job.notes, job.salary ? `Recorded salary: ${job.salary}` : '',
        `Imported from former Cloudflare jobs API (job ${job.id}; recorded status ${job.status || 'unknown'}). Submission and route have not been independently verified.`].filter(Boolean).join('\n'),
      created_at: job.created_at || now(), updated_at: job.updated_at || now(), version: 1,
      attachments
    });
  }
  next.migration_notes = [...(next.migration_notes || []),
    `Imported ${jobs.length} job records and ${files.length} attachment references from the former Cloudflare jobs/files tables on first cloud read. The source tables and R2 objects were retained.`];
  return next;
}

async function getState(env) {
  const existing = await env.DB.prepare('SELECT version, payload, updated_at FROM tracker_state WHERE id = 1').first();
  if (existing) return existing;
  const seed = await legacySnapshot(env);
  await env.DB.prepare('INSERT OR IGNORE INTO tracker_state (id, version, payload, updated_at) VALUES (1, 1, ?, ?)').bind(JSON.stringify(seed), now()).run();
  return env.DB.prepare('SELECT version, payload, updated_at FROM tracker_state WHERE id = 1').first();
}

function validateState(next, current) {
  if (!next || typeof next !== 'object' || !Array.isArray(next.applications) || !Array.isArray(next.leads) || !Array.isArray(next.manual_entries) || !Array.isArray(next.record_visibility)) return 'Invalid tracker format.';
  // Sent applications remain immutable. Research can append new leads and
  // record a later status check without replacing existing lead evidence.
  if (JSON.stringify(next.applications) !== JSON.stringify(current.applications)) return 'Automatic application history cannot be replaced.';
  if (next.leads.length < current.leads.length) return 'Existing lead history must be preserved.';
  const statusFields = ['status', 'checked_at', 'status_evidence_url', 'status_check_note'];
  for (let i = 0; i < current.leads.length; i++) {
    const previous = current.leads[i], updated = next.leads[i];
    if (!updated || updated.key !== previous.key) return 'Existing lead history must be preserved in order.';
    const before = {...previous}, after = {...updated};
    for (const field of statusFields) { delete before[field]; delete after[field]; }
    if (JSON.stringify(before) !== JSON.stringify(after)) return 'Existing lead evidence cannot be replaced.';
    if (updated.status !== previous.status && (!updated.checked_at || !/^https:\/\//.test(updated.status_evidence_url || '')))
      return 'A changed lead status needs a check date and evidence URL.';
  }
  const knownKeys = new Set([...current.applications, ...current.leads].map(record => record.key));
  for (const lead of next.leads.slice(current.leads.length)) {
    if (!lead || typeof lead.key !== 'string' || !lead.key || knownKeys.has(lead.key) ||
        typeof lead.company !== 'string' || !lead.company.trim() || typeof lead.role !== 'string' || !lead.role.trim() ||
        !lead.checked_at || Number.isNaN(Date.parse(lead.checked_at)) ||
        !/^https:\/\//.test(lead.job_url || lead.company_url || '') ||
        /^(SENT|EOI_SENT|MANUAL_APPLIED|APPLICATION_UNDER_REVIEW)$/.test(lead.status || ''))
      return 'New lead needs a unique key, employer, role, dated HTTPS evidence and a pending status.';
    knownKeys.add(lead.key);
  }
  const oldManual = new Map(current.manual_entries.map(record => [record.id, record]));
  const ids = new Set();
  for (const record of next.manual_entries) {
    if (!record?.id || ids.has(record.id) || typeof record.company !== 'string' || typeof record.role !== 'string' || !Array.isArray(record.attachments || [])) return 'Invalid or duplicate manual record.';
    ids.add(record.id);
    const prior = oldManual.get(record.id);
    if (prior) {
      const kept = new Set((record.attachments || []).map(doc => doc.id || doc.path || doc.sha256));
      if ((prior.attachments || []).some(doc => !kept.has(doc.id || doc.path || doc.sha256))) return 'Existing document references must be preserved.';
    }
    if ((record.attachments || []).some(doc => doc.data_base64)) return 'Upload attachment bytes to Cloudflare before saving the record.';
  }
  if ([...oldManual.keys()].some(id => !ids.has(id))) return 'Existing manual records must be preserved. Move them to Bin instead.';
  const oldVisibility = new Set(current.record_visibility.map(record => record.record_key));
  const visibility = new Set(next.record_visibility.map(record => record.record_key));
  if ([...oldVisibility].some(key => !visibility.has(key)) || visibility.size !== next.record_visibility.length) return 'Existing Bin history must be preserved.';
  return null;
}

async function putState(request, env) {
  const bytes = Number(request.headers.get('Content-Length') || 0);
  if (bytes > MAX_REQUEST_BYTES) return error('Tracker exceeds the state size limit.', 413);
  let current = null;
  if (bytes > MAX_STATE_BYTES) {
    // Only the single document has this limit, so the storage mode has to be known first.
    current = await getState(env);
    if (!isRows(current.payload)) return error('Tracker exceeds the state size limit.', 413);
  }
  let body;
  try { body = await request.json(); } catch { return error('Invalid JSON.'); }
  if (!Number.isSafeInteger(body?.expected_version) || body.expected_version < 1) return error('A current version is required.');
  current = current || await getState(env);
  if (current.version !== body.expected_version) return conflict(current.version);
  if (isRows(current.payload)) return putRows(env, body);
  const next = body.state;
  const problem = validateState(next, JSON.parse(current.payload));
  if (problem) return error(problem);
  next.updated_at = now();
  const payload = JSON.stringify(next);
  if (isRows(payload)) return error('Invalid tracker format.');
  if (new TextEncoder().encode(payload).byteLength > MAX_STATE_BYTES) return error('Tracker exceeds the state size limit.', 413);
  // The copy does not move the version, so the statement also requires that the tracker is still a single document:
  // a save that was under way when the copy switched modes gets the usual 409 instead of undoing the switch.
  const result = await env.DB.prepare(`UPDATE tracker_state SET payload = ?, version = version + 1, updated_at = ? WHERE id = 1 AND version = ? AND NOT ${IS_ROWS}`).bind(payload, next.updated_at, body.expected_version).run();
  if (result.meta?.changes !== 1) return conflict();
  return json({version: body.expected_version + 1, updated_at: next.updated_at});
}

// ---- One row per manual record ("rows" mode) ----

// The stored remainder as JSON object text, and the remainder of a client's state as it is stored.
const restOf = payload => '{' + payload.slice(ROWS_PREFIX.length);
const baseOf = state => { const {manual_entries, updated_at, storage, ...rest} = state; return ROWS_PREFIX + JSON.stringify(rest).slice(1); };
const rowsState = env => env.DB.prepare(`SELECT version, updated_at FROM tracker_state WHERE id = 1 AND ${IS_ROWS}`);
const plain = value => typeof value === 'string' || typeof value === 'number' ? value : '';

// The slim list entry, stored next to the full record so that a list is served without opening any record.
function summaryOf(record, version) {
  const percent = record.match_score?.percent;
  const out = {id: record.id, row_version: version, company: plain(record.company), role: plain(record.role), location: plain(record.location), status: plain(record.status),
    route: plain(record.application_route || record.route), closes_at: plain(record.closes_at || record.advert?.expires_at),
    fit_percent: typeof percent === 'number' && Number.isFinite(percent) ? percent : null, updated_at: plain(record.updated_at)};
  for (const key of SUMMARY_EXTRAS) if (plain(record[key]) !== '') out[key] = record[key];
  out.files = Array.isArray(record.attachments) ? record.attachments.length : 0;
  return JSON.stringify(out);
}

function recordProblem(record) {
  if (!record || typeof record.id !== 'string' || !record.id || record.id.length > 200 || typeof record.company !== 'string' || typeof record.role !== 'string' ||
      !Array.isArray(record.attachments || []) || (record.attachments || []).some(doc => !doc || typeof doc !== 'object')) return 'Invalid manual record.';
  if (record.attachments?.some(doc => doc.data_base64)) return 'Upload attachment bytes to Cloudflare before saving the record.';
  return null;
}
const tooLarge = record => error(`Record ${record.id} (${record.company}) is larger than ${MAX_RECORD_BYTES} bytes.`, 413);
const tooMuch = () => error('This save writes too much at once. Save fewer records at a time.', 413);

async function readState(env) {
  const state = await getState(env);
  if (!isRows(state.payload)) return json({version: state.version, state: JSON.parse(state.payload)});
  // One batch is one transaction, so the version and the rows belong together.
  const [head, list] = await env.DB.batch([
    env.DB.prepare('SELECT version, payload, updated_at FROM tracker_state WHERE id = 1'),
    env.DB.prepare('SELECT version, body FROM records ORDER BY position, id')]);
  const base = head.results[0];
  if (!isRows(base.payload)) return json({version: base.version, state: JSON.parse(base.payload)});
  // Joined from stored JSON text: no record is parsed or re-serialised to answer a read. row_versions[i] is the
  // guard of state.manual_entries[i], so a client can change one record without reading it again first.
  return text(`{"version":${base.version},"state":${restOf(base.payload).slice(0, -1)},"updated_at":${JSON.stringify(base.updated_at)},"manual_entries":[${list.results.map(row => row.body).join(',')}]},"row_versions":[${list.results.map(row => row.version).join(',')}]}`);
}

async function versionInfo(env) {
  // What the page polls instead of downloading the tracker: one small row, in either storage mode.
  const read = () => env.DB.prepare(`SELECT version, updated_at, ${IS_ROWS} AS is_rows FROM tracker_state WHERE id = 1`).first();
  let row = await read();
  if (!row) { await getState(env); row = await read(); }
  return json({version: row.version, updated_at: row.updated_at, storage: row.is_rows ? 'rows' : 'document'});
}

// The whole-tracker PUT kept for existing clients. Same validation as before; only changed rows are written.
async function putRows(env, body) {
  const next = body.state;
  // One batch is one transaction, so the version that is checked and the rows that are compared belong together.
  // Read apart, a record another writer added in between looked like one this save had dropped.
  const [head, list] = await env.DB.batch([
    env.DB.prepare('SELECT version, payload FROM tracker_state WHERE id = 1'),
    env.DB.prepare('SELECT id, version, body FROM records ORDER BY position, id')]);
  const current = head.results[0], stored = list.results;
  if (current.version !== body.expected_version || !isRows(current.payload)) return conflict(current.version);
  const sent = new Map();
  for (const record of Array.isArray(next?.manual_entries) ? next.manual_entries : [])
    if (record && typeof record.id === 'string' && !sent.has(record.id)) sent.set(record.id, {record, body: JSON.stringify(record)});
  // validateState compares against the current tracker. A record that arrives unchanged stands in for its stored
  // copy, so only changed records are parsed; a record that was left out keeps its id and fails the check.
  const before = JSON.parse(restOf(current.payload));
  before.manual_entries = stored.map(row => { const twin = sent.get(row.id); return !twin ? {id: row.id} : twin.body === row.body ? twin.record : JSON.parse(row.body); });
  const problem = validateState(next, before) || (next.manual_entries.some(record => typeof record.id !== 'string') ? 'Invalid or duplicate manual record.' : null);
  if (problem) return error(problem);
  const known = new Map(stored.map(row => [row.id, row]));
  const unmoved = `(SELECT version FROM tracker_state WHERE id = 1 AND ${IS_ROWS}) = ?`;
  const statements = [];
  let written = 0;
  for (const [id, {record, body: content}] of sent) {
    const prior = known.get(id);
    if (prior?.body === content) continue;
    if (!prior && id.length > 200) return error('Invalid or duplicate manual record.');
    const size = bytesOf(content);
    if (size > MAX_RECORD_BYTES) return tooLarge(record);
    written += size;
    statements.push(prior
      ? env.DB.prepare(`UPDATE records SET version = ?, summary = ?, body = ? WHERE id = ? AND ${unmoved}`).bind(prior.version + 1, summaryOf(record, prior.version + 1), content, id, body.expected_version)
      : env.DB.prepare(`INSERT INTO records (id, position, version, summary, body) SELECT ?, (SELECT COALESCE(MAX(position), -1) + 1 FROM records), 1, ?, ? WHERE ${unmoved}`).bind(id, summaryOf(record, 1), content, body.expected_version));
  }
  const payload = baseOf(next), stamp = now(), baseChanged = payload !== current.payload;
  if (baseChanged) {
    const size = bytesOf(payload);
    if (size > MAX_STATE_BYTES) return error('Tracker exceeds the state size limit.', 413);
    written += size;
  }
  if (written > MAX_SAVE_BYTES) return tooMuch();
  // The row statements come first and each one tests the version, so a stale save writes nothing at all.
  // The last statement moves the version, and its result says whether the save happened.
  statements.push(baseChanged
    ? env.DB.prepare(`UPDATE tracker_state SET payload = ?, version = version + 1, updated_at = ? WHERE id = 1 AND version = ? AND ${IS_ROWS}`).bind(payload, stamp, body.expected_version)
    : env.DB.prepare(`UPDATE tracker_state SET version = version + 1, updated_at = ? WHERE id = 1 AND version = ? AND ${IS_ROWS}`).bind(stamp, body.expected_version));
  const results = await env.DB.batch(statements);
  if (results.at(-1).meta?.changes !== 1) return conflict();
  return json({version: body.expected_version + 1, updated_at: stamp});
}

async function listRecords(env) {
  const [head, list] = await env.DB.batch([rowsState(env), env.DB.prepare('SELECT summary FROM records ORDER BY position, id')]);
  const state = head.results[0];
  if (!state) return notActive();
  return text(`{"version":${state.version},"updated_at":${JSON.stringify(state.updated_at)},"records":[${list.results.map(row => row.summary).join(',')}]}`);
}

async function getRecord(id, env) {
  const [head, found] = await env.DB.batch([rowsState(env), env.DB.prepare('SELECT version, body FROM records WHERE id = ?').bind(id)]);
  if (!head.results[0]) return notActive();
  const row = found.results[0];
  return row ? text(`{"row_version":${row.version},"record":${row.body}}`) : error('Record not found.', 404);
}

// Append only. Without expected_version an add never collides with someone else's save. With it (the version that
// came with the list the caller checked for duplicates) the add applies only if nothing was saved since that list.
async function addRecords(request, env) {
  if (Number(request.headers.get('Content-Length') || 0) > 2 * MAX_SAVE_BYTES) return error('Request is too large.', 413);
  let body;
  try { body = await request.json(); } catch { return error('Invalid JSON.'); }
  const wanted = body?.expected_version;
  if (wanted !== undefined && (!Number.isSafeInteger(wanted) || wanted < 1)) return error('A current version is required.');
  const records = Array.isArray(body?.records) ? body.records : body?.record ? [body.record] : [];
  if (!records.length || records.length > MAX_NEW_RECORDS) return error(`Send 1 to ${MAX_NEW_RECORDS} records.`);
  const rows = [], ids = new Set();
  let written = 0;
  for (const record of records) {
    const problem = recordProblem(record) || (ids.has(record.id) ? 'The request repeats a record id.' : null);
    if (problem) return error(problem);
    ids.add(record.id);
    const content = JSON.stringify(record), size = bytesOf(content);
    if (size > MAX_RECORD_BYTES) return tooLarge(record);
    written += size;
    rows.push({id: record.id, content, summary: summaryOf(record, 1)});
  }
  if (written > MAX_SAVE_BYTES) return tooMuch();
  const taken = () => env.DB.prepare(`SELECT id FROM records WHERE id IN (${rows.map(() => '?').join(', ')})`).bind(...rows.map(row => row.id));
  const refused = found => json({error: 'A record with this id already exists. Nothing was added.', existing_ids: found.map(row => row.id)}, 409);
  const [head, found] = await env.DB.batch([rowsState(env), taken()]);
  if (!head.results[0]) return notActive();
  if (wanted !== undefined && head.results[0].version !== wanted) return conflict(head.results[0].version);
  if (found.results.length) return refused(found.results);
  const guarded = wanted !== undefined, same = guarded ? [wanted] : [], stamp = now();
  const unmoved = guarded ? `(SELECT version FROM tracker_state WHERE id = 1 AND ${IS_ROWS}) = ?` : `EXISTS (SELECT 1 FROM tracker_state WHERE id = 1 AND ${IS_ROWS})`;
  const statements = rows.map(row => env.DB.prepare(`INSERT INTO records (id, position, version, summary, body) SELECT ?, (SELECT COALESCE(MAX(position), -1) + 1 FROM records), 1, ?, ? WHERE ${unmoved}`).bind(row.id, row.summary, row.content, ...same));
  statements.push(env.DB.prepare(`UPDATE tracker_state SET version = version + 1, updated_at = ? WHERE id = 1 AND ${IS_ROWS}${guarded ? ' AND version = ?' : ''}`).bind(stamp, ...same));
  statements.push(env.DB.prepare('SELECT version FROM tracker_state WHERE id = 1'));
  let results;
  try { results = await env.DB.batch(statements); } catch (cause) {
    // A batch is one transaction. If another writer took one of these ids after the check, nothing was added.
    const late = (await taken().all()).results || [];
    if (!late.length) throw cause;
    return refused(late);
  }
  if (results.at(-2).meta?.changes !== 1) return guarded ? conflict() : notActive();
  return json({added: rows.map(row => row.id), version: results.at(-1).results[0].version, updated_at: stamp}, 201);
}

async function patchRecord(id, request, env) {
  if (Number(request.headers.get('Content-Length') || 0) > 3 * MAX_RECORD_BYTES) return error('Request is too large.', 413);
  let body;
  try { body = await request.json(); } catch { return error('Invalid JSON.'); }
  const patch = body?.patch;
  if (!Number.isSafeInteger(body?.expected_version) || body.expected_version < 1 || !patch || typeof patch !== 'object' || Array.isArray(patch)) return error('A record version and a patch are required.');
  const [head, found] = await env.DB.batch([rowsState(env), env.DB.prepare('SELECT version, body FROM records WHERE id = ?').bind(id)]);
  if (!head.results[0]) return notActive();
  const row = found.results[0];
  if (!row) return error('Record not found.', 404);
  if (row.version !== body.expected_version) return json({error: 'This record changed. Refresh it before saving.', current_row_version: row.version}, 409);
  const prior = JSON.parse(row.body), next = {...prior};
  for (const [key, value] of Object.entries(patch)) if (!FIXED_FIELDS.includes(key)) next[key] = value;
  const problem = recordProblem(next);
  if (problem) return error(problem);
  const kept = new Set((next.attachments || []).map(doc => doc.id || doc.path || doc.sha256));
  if ((prior.attachments || []).some(doc => !kept.has(doc.id || doc.path || doc.sha256))) return error('Existing document references must be preserved.');
  next.updated_at = now();
  next.version = (Number(prior.version) || 0) + 1;
  const content = JSON.stringify(next), version = row.version + 1;
  if (bytesOf(content) > MAX_RECORD_BYTES) return tooLarge(next);
  // Both statements test the record as it was read, so a stale patch changes nothing, not even the tracker version.
  const results = await env.DB.batch([
    env.DB.prepare(`UPDATE tracker_state SET version = version + 1, updated_at = ? WHERE id = 1 AND ${IS_ROWS} AND EXISTS (SELECT 1 FROM records WHERE id = ? AND version = ?)`).bind(next.updated_at, id, row.version),
    env.DB.prepare(`UPDATE records SET version = ?, summary = ?, body = ? WHERE id = ? AND version = ? AND EXISTS (SELECT 1 FROM tracker_state WHERE id = 1 AND ${IS_ROWS})`).bind(version, summaryOf(next, version), content, id, row.version),
    env.DB.prepare('SELECT version FROM tracker_state WHERE id = 1')]);
  if (results[1].meta?.changes !== 1) return json({error: 'This record changed. Refresh it before saving.'}, 409);
  // "version" is the whole tracker's, as everywhere else; "row_version" is this record's guard for the next change.
  return text(`{"version":${results[2].results[0].version},"updated_at":${JSON.stringify(next.updated_at)},"row_version":${version},"record":${content}}`);
}

// Moves one job to the Bin or back: the one change to the remainder that the page makes. It opens the remainder
// (the frozen history and the Bin, about 120 KB) and no record. Bin entries are added or changed, never removed.
async function setVisibility(request, env) {
  if (Number(request.headers.get('Content-Length') || 0) > 4_000) return error('Request is too large.', 413);
  let body;
  try { body = await request.json(); } catch { return error('Invalid JSON.'); }
  const key = body?.record_key;
  if (typeof key !== 'string' || !key || key.length > 400 || typeof body.deleted !== 'boolean') return error('A record key and deleted (true or false) are required.');
  const current = await env.DB.prepare(`SELECT version, payload FROM tracker_state WHERE id = 1 AND ${IS_ROWS}`).first();
  if (!current) return notActive();
  const rest = JSON.parse(restOf(current.payload)), stamp = now();
  let entry = rest.record_visibility.find(item => item.record_key === key);
  if (entry) Object.assign(entry, {deleted: body.deleted ? 1 : 0, version: (Number(entry.version) || 0) + 1, updated_at: stamp});
  else rest.record_visibility.push(entry = {record_key: key, deleted: body.deleted ? 1 : 0, version: 1, updated_at: stamp});
  const payload = baseOf(rest);
  if (bytesOf(payload) > MAX_STATE_BYTES) return error('Tracker exceeds the state size limit.', 413);
  const result = await env.DB.prepare(`UPDATE tracker_state SET payload = ?, version = version + 1, updated_at = ? WHERE id = 1 AND version = ? AND ${IS_ROWS}`).bind(payload, stamp, current.version).run();
  if (result.meta?.changes !== 1) return conflict();
  return json({version: current.version + 1, updated_at: stamp, entry});
}

// One-time copy of every manual entry into its own row. Until its last statement the tracker stays a single
// document and nothing this Worker serves has changed; running it again is safe at every point.
async function backfill(request, env) {
  let wanted;
  try { wanted = JSON.parse(await request.text() || '{}')?.expected_version; } catch { return error('Invalid JSON.'); }
  if (wanted !== undefined && !Number.isSafeInteger(wanted)) return error('A current version is required.');
  const base = await getState(env);
  if (isRows(base.payload)) {
    const count = await env.DB.prepare('SELECT COUNT(*) AS records FROM records').first();
    return json({storage: 'rows', already: true, version: base.version, records: count.records});
  }
  if (wanted !== undefined && wanted !== base.version) return conflict(base.version);
  const doc = JSON.parse(base.payload), entries = doc.manual_entries;
  if (!Array.isArray(entries) || typeof doc.updated_at !== 'string' || !Array.isArray(doc.applications) || !Array.isArray(doc.leads) || !Array.isArray(doc.record_visibility))
    return error('The tracker document cannot be copied as it is. Nothing was changed.');
  const rows = [], ids = new Set();
  for (const record of entries) {
    // Whatever the document holds is copied as it is. A row only needs what the table needs: a text id, used once.
    if (!record || typeof record !== 'object' || typeof record.id !== 'string' || !record.id || ids.has(record.id)) return error('Invalid or duplicate manual record. Nothing was changed.');
    ids.add(record.id);
    const content = JSON.stringify(record);
    if (content.length > MAX_RECORD_BYTES || (content.length * 3 > MAX_RECORD_BYTES && bytesOf(content) > MAX_RECORD_BYTES)) return error(`Record ${record.id} (${record.company}) is larger than ${MAX_RECORD_BYTES} bytes. Nothing was changed.`, 413);
    const version = Number.isSafeInteger(record.version) && record.version > 0 ? record.version : 1;
    rows.push({id: record.id, version, content, summary: summaryOf(record, version)});
  }
  await env.DB.prepare('INSERT OR IGNORE INTO tracker_state_backup (version, payload, saved_at) VALUES (?, ?, ?)').bind(base.version, base.payload, now()).run();
  // Every row statement applies only while the tracker is still this version of the single document, so a copy that
  // lost a race cannot overwrite newer rows. Rows left by an earlier, interrupted run are brought up to date.
  const copy = `INSERT INTO records (id, position, version, summary, body) SELECT ?, ?, ?, ?, ? WHERE (SELECT version FROM tracker_state WHERE id = 1 AND NOT ${IS_ROWS}) = ? ON CONFLICT(id) DO UPDATE SET position = excluded.position, version = excluded.version, summary = excluded.summary, body = excluded.body`;
  const size = Math.max(COPY_BATCH, Math.ceil(rows.length / 40));
  for (let i = 0; i < rows.length; i += size)
    await env.DB.batch(rows.slice(i, i + size).map((row, offset) => env.DB.prepare(copy).bind(row.id, i + offset, row.version, row.summary, row.content, base.version)));
  // Read everything back and compare it byte for byte before the one statement that switches modes.
  const stored = (await env.DB.prepare('SELECT id, position, version, body FROM records ORDER BY position, id').all()).results || [];
  if (stored.length !== rows.length || stored.some((row, i) => row.id !== rows[i].id || row.position !== i || row.version !== rows[i].version || row.body !== rows[i].content))
    return error('The copied rows do not match the tracker document. The tracker still uses the single document.', 409);
  const slim = baseOf(doc);
  // The version is not moved: what clients read is unchanged. The statement applies only if the document is still
  // exactly the one saved in the backup table and the row count is the one just verified.
  const result = await env.DB.prepare(`UPDATE tracker_state SET payload = ?, updated_at = ? WHERE id = 1 AND version = ? AND payload = (SELECT payload FROM tracker_state_backup WHERE version = ?) AND (SELECT COUNT(*) FROM records) = ?`).bind(slim, doc.updated_at, base.version, base.version, rows.length).run();
  if (result.meta?.changes !== 1) return json({error: 'The tracker changed during the copy. The tracker still uses the single document. Run the copy again.'}, 409);
  return json({storage: 'rows', already: false, version: base.version, records: rows.length, remainder_bytes: bytesOf(slim)});
}

// Puts the saved single document back. Possible only while nothing has been saved since the copy, which the
// unchanged version proves: every save in rows mode moves it.
async function restoreDocument(request, env) {
  let wanted;
  try { wanted = (await request.json())?.expected_version; } catch { return error('Invalid JSON.'); }
  if (!Number.isSafeInteger(wanted)) return error('A current version is required.');
  const current = await getState(env);
  if (!isRows(current.payload)) return json({storage: 'document', already: true, version: current.version});
  const result = await env.DB.prepare(`UPDATE tracker_state SET payload = (SELECT payload FROM tracker_state_backup WHERE version = ?) WHERE id = 1 AND version = ? AND ${IS_ROWS} AND EXISTS (SELECT 1 FROM tracker_state_backup WHERE version = ?)`).bind(wanted, wanted, wanted).run();
  if (result.meta?.changes !== 1) return json({error: 'Records were saved after the copy, or no saved document exists for this version. Nothing was changed.', current_version: current.version}, 409);
  return json({storage: 'document', already: false, version: wanted});
}

function fileSignature(bytes, ext) {
  if (ext === 'pdf') return bytes.length > 4 && String.fromCharCode(...bytes.slice(0, 4)) === '%PDF';
  if (ext === 'png') return bytes.length > 8 && [137,80,78,71,13,10,26,10].every((v,i) => bytes[i] === v);
  if (ext === 'jpg' || ext === 'jpeg') return bytes.length > 3 && bytes[0] === 255 && bytes[1] === 216 && bytes[2] === 255;
  return bytes.length > 4 && bytes[0] === 80 && bytes[1] === 75; // DOCX ZIP header
}

async function upload(request, env) {
  let filename;
  try { filename = decodeURIComponent(request.headers.get('X-Filename') || ''); } catch { return error('Invalid filename.'); }
  filename = filename.replace(/[\\/\x00-\x1f\x7f]/g, '').trim().slice(0, 180);
  const ext = filename.split('.').pop()?.toLowerCase();
  if (!filename || !ALLOWED_EXTENSIONS[ext]) return error('Use PDF, DOCX, PNG or JPG files.');
  const kind = request.headers.get('X-Doc-Kind');
  if (!['resume', 'cover', 'confirmation'].includes(kind)) return error('Invalid document kind.');
  if (Number(request.headers.get('Content-Length') || 0) > MAX_FILE_BYTES) return error('Document exceeds 10 MB.', 413);
  const bytes = new Uint8Array(await request.arrayBuffer());
  if (bytes.byteLength > MAX_FILE_BYTES) return error('Document exceeds 10 MB.', 413);
  if (!fileSignature(bytes, ext)) return error('The document content does not match its extension.');
  const id = crypto.randomUUID(), objectKey = 'uploads/' + id;
  const uploadedAt = now(), digest = hex(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)));
  await env.DOCUMENTS.put(objectKey, bytes, {httpMetadata: {contentType: ALLOWED_EXTENSIONS[ext]}});
  try {
    await env.DB.prepare('INSERT INTO document_index (id, object_key, filename, mime_type, size_bytes, sha256, uploaded_at) VALUES (?, ?, ?, ?, ?, ?, ?)').bind(id, objectKey, filename, ALLOWED_EXTENSIONS[ext], bytes.byteLength, digest, uploadedAt).run();
  } catch (cause) {
    await env.DOCUMENTS.delete(objectKey);
    throw cause;
  }
  return json({id, path: '/api/documents/' + id, filename, sha256: digest, size_bytes: bytes.byteLength, kind, uploaded_at: uploadedAt, stored_in: 'cloudflare_r2'}, 201);
}

async function download(id, env) {
  if (!/^[0-9a-f-]{36}$/i.test(id)) return error('Document not found.', 404);
  const meta = await env.DB.prepare('SELECT object_key, filename, mime_type FROM document_index WHERE id = ?').bind(id).first();
  if (!meta) return error('Document not found.', 404);
  const object = await env.DOCUMENTS.get(meta.object_key);
  if (!object) return error('Document bytes are missing.', 404);
  return new Response(object.body, {headers: {
    'Content-Type': meta.mime_type,
    'Content-Disposition': `attachment; filename*=UTF-8''${encodeURIComponent(meta.filename)}`,
    'X-Content-Type-Options': 'nosniff'
  }});
}

async function downloadLegacy(id, env) {
  if (!/^\d+$/.test(id)) return error('Document not found.', 404);
  const file = await env.DB.prepare('SELECT r2_key, filename, content_type FROM files WHERE id = ?').bind(id).first();
  if (!file) return error('Document not found.', 404);
  const object = await env.DOCUMENTS.get(file.r2_key);
  if (!object) return error('Document bytes are missing.', 404);
  return new Response(object.body, {headers: {
    'Content-Type': file.content_type || 'application/octet-stream',
    'Content-Disposition': `attachment; filename*=UTF-8''${encodeURIComponent(file.filename)}`,
    'X-Content-Type-Options': 'nosniff'
  }});
}

function recordId(path) {
  try { return decodeURIComponent(path.slice('/api/records/'.length)); } catch { return ''; }
}
// The route without any record or document id, for the failure log.
const routeName = url => new URL(url).pathname.split('/').slice(0, 3).join('/');

export default {
  async fetch(request, env) {
    const origin = request.headers.get('Origin');
    if (origin && origin !== env.ALLOWED_ORIGIN && origin !== env.ALLOWED_DEV_ORIGIN) return error('Origin not allowed.', 403);
    const cors = origin ? {'Access-Control-Allow-Origin': origin} : {};
    const headers = {'Cache-Control': 'no-store', 'Vary': 'Origin', ...cors};
    if (request.method === 'OPTIONS') return new Response(null, {status: 204, headers: {...headers, 'Access-Control-Allow-Methods': 'GET, PUT, POST, PATCH, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type, X-Tracker-Code, X-Filename, X-Doc-Kind', 'Access-Control-Max-Age': '600'}});
    if (!env.DB || !env.DOCUMENTS || !env.ACCESS_CODE) return error('Cloudflare bindings or access code are not configured.', 503);
    let response;
    try {
      const denied = await authorised(request, env);
      if (denied) response = denied;
      else {
        const path = new URL(request.url).pathname;
        if (path === '/api/state' && request.method === 'GET') response = await readState(env);
        else if (path === '/api/state' && request.method === 'PUT') response = await putState(request, env);
        else if (path === '/api/version' && request.method === 'GET') response = await versionInfo(env);
        else if (path === '/api/records' && request.method === 'GET') response = await listRecords(env);
        else if (path === '/api/records' && request.method === 'POST') response = await addRecords(request, env);
        else if (path.startsWith('/api/records/') && request.method === 'GET') response = await getRecord(recordId(path), env);
        else if (path.startsWith('/api/records/') && request.method === 'PATCH') response = await patchRecord(recordId(path), request, env);
        else if (path === '/api/visibility' && request.method === 'POST') response = await setVisibility(request, env);
        else if (path === '/api/admin/backfill' && request.method === 'POST') response = await backfill(request, env);
        else if (path === '/api/admin/restore-document' && request.method === 'POST') response = await restoreDocument(request, env);
        else if (path === '/api/documents' && request.method === 'POST') response = await upload(request, env);
        else if (path.startsWith('/api/documents/') && request.method === 'GET') response = await download(path.slice('/api/documents/'.length), env);
        else if (path.startsWith('/api/legacy-files/') && request.method === 'GET') response = await downloadLegacy(path.slice('/api/legacy-files/'.length), env);
        else response = error('Not found.', 404);
      }
    } catch (cause) {
      // Never the error text itself: a JSON or database message can quote tracker content.
      console.error('Tracker API failure', request.method, routeName(request.url), cause?.name || 'Error', String(cause?.message || '').match(/^D1_[A-Z_]+/)?.[0] || '');
      response = error('Cloud save is temporarily unavailable. Nothing was saved by this request.', 503);
    }
    const final = new Response(response.body, response);
    for (const [key, value] of Object.entries(headers)) final.headers.set(key, value);
    final.headers.set('X-Content-Type-Options', 'nosniff');
    return final;
  }
};
