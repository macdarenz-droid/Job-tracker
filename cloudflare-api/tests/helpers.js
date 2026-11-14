// Made-up tracker content for the tests: nothing here comes from the live tracker.
import seed from '../src/seed.js';
import {makeD1} from './d1sqlite.js';

const MIGRATIONS = new URL('../migrations', import.meta.url).pathname;
export const CODE = '654321';
export const size = value => Buffer.byteLength(typeof value === 'string' ? value : JSON.stringify(value));
const STATUSES = ['READY_SEEK', 'PREPARED_NOT_SENT', 'ASK_OWNER', 'READY_JEREMIE_EMPLOYER_PORTAL', 'HELD_MANDATORY_REQUIREMENTS'];
export const file = (n, kind) => ({id: `doc-${n}-${kind}`, path: `/api/documents/doc-${n}-${kind}`, filename: kind + '.pdf', sha256: `${kind}${n}`, kind, stored_in: 'cloudflare_r2'});

export function record(n, extra = {}) {
  const id = 'rec-' + String(n).padStart(4, '0'), day = String(1 + (n % 28)).padStart(2, '0');
  return {id, key: 'manual:' + id, company: 'Example Civil ' + n, role: n % 3 ? 'Junior Civil Drafter' : 'Materials Testing Technician', location: 'Melton VIC',
    job_url: 'https://jobs.example.test/job/' + n, status: STATUSES[n % 5], application_route: ['SEEK', 'EMAIL', 'EMPLOYER_PORTAL'][n % 3], created_by: 'test-runner',
    contributor_name: 'Test', created_at: '2026-10-01T00:00:00.000Z', updated_at: `2026-10-${day}T00:00:00.000Z`, version: 1 + (n % 3),
    attachments: n % 2 ? [file(n, 'resume'), file(n, 'cover')] : [], advert: {expires_at: `2026-12-${day}T12:59:59.999Z`, apply_instructions: 'Apply on the careers page.'},
    screening_answers: [{question: 'Do you have a White Card?', answer: 'Yes.'}], match_score: {percent: 55 + (n % 40)},
    notes: 'Café – “quoted” \u2028 line 😀 ' + 'n'.repeat(3150), ...extra};
}
// The seed plus `count` made-up records: 400 of them is about 1.7 MB, just under the old single-document limit.
export function tracker(count) {
  const state = structuredClone(seed);
  for (let n = 0; n < count; n++) state.manual_entries.push(record(n));
  return state;
}
export function environment(state = tracker(400), version = 225) {
  const d1 = makeD1(MIGRATIONS);
  d1.db.prepare('INSERT INTO tracker_state (id, version, payload, updated_at) VALUES (1, ?, ?, ?)').run(version, JSON.stringify(state), state.updated_at || '2026-09-13T20:18:00Z');
  const objects = new Map();
  const DOCUMENTS = {objects, async put(key, bytes) { objects.set(key, bytes); }, async get(key) { return objects.has(key) ? new Response(objects.get(key)) : null; }, async delete(key) { objects.delete(key); }};
  return {...d1, env: {DB: d1.DB, DOCUMENTS, ACCESS_CODE: CODE, ALLOWED_ORIGIN: 'https://macdarenz-droid.github.io'}};
}
