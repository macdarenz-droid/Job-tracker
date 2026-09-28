import {readFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';

const endpoint = 'https://job-tracker-api.mmarcdarenz.workers.dev/api/state';
const expired = new Set(['SKIPPED_EXPIRED', 'SKIPPED_CLOSED', 'VACANCY_REMOVED']);
const norm = value => String(value || '').toLowerCase().replace(/[^a-z0-9]/g, '');
const location = value => { try { const u = new URL(value); return u.hostname.toLowerCase() + u.pathname.replace(/\/$/, '').toLowerCase(); } catch { return ''; } };

export function mergeBatch(state, batch) {
  if (!batch || typeof batch.batch_id !== 'string' || !Array.isArray(batch.leads) || !Array.isArray(batch.status_updates || []))
    throw Error('The research batch format is invalid.');
  const next = structuredClone(state);
  const keys = new Map([...next.applications, ...next.leads].map(row => [row.key, row]));
  const manual = next.manual_entries || [];
  let added = 0, changed = 0;
  for (const lead of batch.leads) {
    if (!lead || !lead.key || !lead.company || !lead.role || !lead.checked_at || Number.isNaN(Date.parse(lead.checked_at)) ||
        !/^https:\/\//.test(lead.job_url || lead.company_url || '') ||
        /^(SENT|EOI_SENT|MANUAL_APPLIED|APPLICATION_UNDER_REVIEW)$/.test(lead.status || ''))
      throw Error('Research lead lacks a unique key, dated source, pending status, company or role.');
    const sameKey = keys.get(lead.key);
    if (sameKey) {
      if (JSON.stringify(sameKey) !== JSON.stringify(lead)) throw Error(`Existing key differs: ${lead.key}. Reconcile first.`);
      continue;
    }
    const age = Date.now() - Date.parse(lead.checked_at);
    if (age > 48 * 60 * 60 * 1000 || age < -15 * 60 * 1000)
      throw Error(`Source check date is outside the 48-hour window for ${lead.key}; reverify before publishing.`);
    const identity = norm(lead.company) + '|' + norm(lead.role);
    const url = location(lead.job_url);
    const equivalent = [...next.applications, ...next.leads, ...manual].find(row =>
      (url && location(row.job_url) === url) ||
      (norm(row.company) + '|' + norm(row.role) === identity));
    if (equivalent) throw Error(`Potential equivalent record exists for ${lead.key}. Reconcile first.`);
    next.leads.push(lead); keys.set(lead.key, lead); added++;
  }
  for (const update of batch.status_updates || []) {
    const row = next.leads.find(lead => lead.key === update.key);
    if (!row || !expired.has(update.status) || !update.checked_at || Number.isNaN(Date.parse(update.checked_at)) ||
        !/^https:\/\//.test(update.status_evidence_url || ''))
      throw Error('A closed/expired update needs an existing lead, date and HTTPS evidence.');
    if (row.status === update.status && row.checked_at === update.checked_at && row.status_evidence_url === update.status_evidence_url) continue;
    Object.assign(row, {status:update.status, checked_at:update.checked_at,
      status_evidence_url:update.status_evidence_url, status_check_note:update.status_check_note || ''});
    changed++;
  }
  return {state:next, added, changed};
}

async function main() {
  const code = process.env.TRACKER_ACCESS_CODE;
  if (!/^\d{6}$/.test(code || '')) throw Error('The private tracker code secret is unavailable.');
  const batch = JSON.parse(readFileSync(process.argv[2] || 'research/lead-updates.json', 'utf8'));
  if (!batch.leads?.length && !batch.status_updates?.length) { console.log('No research changes in this batch.'); return; }
  const headers = {'X-Tracker-Code':code};
  const get = async () => {
    const response = await fetch(endpoint, {headers, cache:'no-store'});
    if (!response.ok) throw Error(`Cloud state read failed (${response.status}).`);
    return response.json();
  };
  const current = await get();
  if (!Number.isSafeInteger(current.version) || !current.state?.applications || !current.state?.leads || !current.state?.manual_entries)
    throw Error('Incomplete cloud state; publication stopped.');
  const result = mergeBatch(current.state, batch);
  if (!result.added && !result.changed) { console.log('Batch already present; no write needed.'); return; }
  const saved = await fetch(endpoint, {method:'PUT', headers:{...headers,'Content-Type':'application/json'},
    body:JSON.stringify({expected_version:current.version,state:result.state})});
  if (!saved.ok) throw Error(`Version-guarded Save failed (${saved.status}); no blind retry.`);
  const verified = await get();
  if (verified.version !== current.version + 1 ||
      JSON.stringify(verified.state.applications) !== JSON.stringify(current.state.applications) ||
      verified.state.manual_entries.length !== current.state.manual_entries.length ||
      verified.state.record_visibility.length !== current.state.record_visibility.length ||
      batch.leads.some(lead => !verified.state.leads.some(row => row.key === lead.key)))
    throw Error('The live read did not confirm preservation and the new lead keys.');
  console.log(`Verified cloud state version ${verified.version}: ${result.added} new leads, ${result.changed} closed/expired updates; prior applications, manual entries and Bin retained.`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href)
  main().catch(error => { console.error(error.message); process.exitCode = 1; });
