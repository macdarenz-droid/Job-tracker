import initialState from './seed.js';

const MAX_STATE_BYTES = 1_800_000;
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
  // Historic automatic records are evidence. Editing a row creates a manual overlay instead.
  if (JSON.stringify(next.applications) !== JSON.stringify(current.applications) || JSON.stringify(next.leads) !== JSON.stringify(current.leads)) return 'Automatic history cannot be replaced. Edit through a manual record.';
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
  if (bytes > MAX_STATE_BYTES) return error('Tracker exceeds the state size limit.', 413);
  let body;
  try { body = await request.json(); } catch { return error('Invalid JSON.'); }
  if (!Number.isSafeInteger(body?.expected_version) || body.expected_version < 1) return error('A current version is required.');
  const current = await getState(env);
  if (current.version !== body.expected_version) return json({error: 'A newer cloud version exists. Refresh before saving.', current_version: current.version}, 409);
  const next = body.state;
  const problem = validateState(next, JSON.parse(current.payload));
  if (problem) return error(problem);
  next.updated_at = now();
  const payload = JSON.stringify(next);
  if (new TextEncoder().encode(payload).byteLength > MAX_STATE_BYTES) return error('Tracker exceeds the state size limit.', 413);
  const result = await env.DB.prepare('UPDATE tracker_state SET payload = ?, version = version + 1, updated_at = ? WHERE id = 1 AND version = ?').bind(payload, next.updated_at, body.expected_version).run();
  if (result.meta?.changes !== 1) return json({error: 'A newer cloud version exists. Refresh before saving.'}, 409);
  return json({version: body.expected_version + 1, updated_at: next.updated_at});
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

export default {
  async fetch(request, env) {
    const origin = request.headers.get('Origin');
    if (origin && origin !== env.ALLOWED_ORIGIN && origin !== env.ALLOWED_DEV_ORIGIN) return error('Origin not allowed.', 403);
    const cors = origin ? {'Access-Control-Allow-Origin': origin} : {};
    const headers = {'Cache-Control': 'no-store', 'Vary': 'Origin', ...cors};
    if (request.method === 'OPTIONS') return new Response(null, {status: 204, headers: {...headers, 'Access-Control-Allow-Methods': 'GET, PUT, POST, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type, X-Tracker-Code, X-Filename, X-Doc-Kind', 'Access-Control-Max-Age': '600'}});
    if (!env.DB || !env.DOCUMENTS || !env.ACCESS_CODE) return error('Cloudflare bindings or access code are not configured.', 503);
    let response;
    try {
      const denied = await authorised(request, env);
      if (denied) response = denied;
      else {
        const path = new URL(request.url).pathname;
        if (path === '/api/state' && request.method === 'GET') {
          const state = await getState(env);
          response = json({version: state.version, state: JSON.parse(state.payload)});
        } else if (path === '/api/state' && request.method === 'PUT') response = await putState(request, env);
        else if (path === '/api/documents' && request.method === 'POST') response = await upload(request, env);
        else if (path.startsWith('/api/documents/') && request.method === 'GET') response = await download(path.slice('/api/documents/'.length), env);
        else if (path.startsWith('/api/legacy-files/') && request.method === 'GET') response = await downloadLegacy(path.slice('/api/legacy-files/'.length), env);
        else response = error('Not found.', 404);
      }
    } catch (cause) {
      console.error('Tracker API failure', cause);
      response = error('Cloud save is temporarily unavailable. Nothing was saved by this request.', 503);
    }
    const final = new Response(response.body, response);
    for (const [key, value] of Object.entries(headers)) final.headers.set(key, value);
    final.headers.set('X-Content-Type-Options', 'nosniff');
    return final;
  }
};
