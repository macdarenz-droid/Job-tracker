import {readFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';

const endpoint = 'https://job-tracker-api.mmarcdarenz.workers.dev/api/state';
const expired = new Set(['SKIPPED_EXPIRED', 'SKIPPED_CLOSED', 'VACANCY_REMOVED']);
const reviewHolds = new Set(['HELD_MANDATORY_REQUIREMENTS', 'HELD_ELIGIBILITY_UNCONFIRMED', 'HELD_PACK_VERIFICATION']);
const norm = value => String(value || '').toLowerCase().replace(/[^a-z0-9]/g, '');
const location = value => { try { const u = new URL(value); return u.hostname.toLowerCase() + u.pathname.replace(/\/$/, '').toLowerCase(); } catch { return ''; } };

export function mergeBatch(state, batch) {
  if (!batch || typeof batch.batch_id !== 'string' || !Array.isArray(batch.leads) || !Array.isArray(batch.status_updates || []) || !Array.isArray(batch.manual_reviews || []))
    throw Error('The research batch format is invalid.');
  const next = structuredClone(state);
  const keys = new Map([...next.applications, ...next.leads].map(row => [row.key, row]));
  const manual = next.manual_entries || [];
  let added = 0, changed = 0, reviewed = 0;
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
  for (const review of batch.manual_reviews || []) {
    const row = manual.find(record => record.id === review.id);
    if (!row || !reviewHolds.has(review.status) || !review.review_id || !review.note ||
        !Number.isSafeInteger(review.expected_version) || !review.expected_status ||
        !review.reviewed_at || Number.isNaN(Date.parse(review.reviewed_at)) ||
        !Array.isArray(review.evidence_urls) || !review.evidence_urls.length ||
        review.evidence_urls.some(url => !/^https:\/\//.test(url)))
      throw Error('Review hold requires an existing record, exact version/status, dated rationale and HTTPS evidence.');
    const previousReview = (row.review_history || []).find(item => item.review_id === review.review_id);
    const entry = {review_id:review.review_id, reviewer:'Codex', reviewed_at:review.reviewed_at,
      status:review.status, note:review.note, evidence_urls:review.evidence_urls};
    if (previousReview) {
      if (JSON.stringify(previousReview) !== JSON.stringify(entry)) throw Error('Review ID exists with different evidence; reconcile first.');
      continue; // Never reset a later application outcome on a rerun.
    }
    if (row.version !== review.expected_version || row.status !== review.expected_status ||
        !/^(PREPARED_NOT_SENT|READY_[A-Z_]+)$/.test(row.status) || row.created_by !== review.expected_created_by)
      throw Error(`Record changed since review: ${review.id}; preserve it and reconcile.`);
    row.status = review.status;
    row.version += 1;
    row.updated_at = review.reviewed_at;
    row.review_history = [...(row.review_history || []), entry];
    row.notes = [row.notes, `Review hold (${review.reviewed_at.slice(0,10)}): ${review.note}`].filter(Boolean).join('\n');
    reviewed++;
  }
  return {state:next, added, changed, reviewed};
}

async function main() {
  const code = process.env.TRACKER_ACCESS_CODE;
  if (!/^\d{6}$/.test(code || '')) throw Error('The private tracker code secret is unavailable.');
  const batch = JSON.parse(readFileSync(process.argv[2] || 'research/lead-updates.json', 'utf8'));
  if (!batch.leads?.length && !batch.status_updates?.length && !batch.manual_reviews?.length) { console.log('No research changes in this batch.'); return; }
  const headers = {'X-Tracker-Code':code};
  const get = async () => {
    const response = await fetch(endpoint, {headers, cache:'no-store'});
    if (!response.ok) throw Error(`Cloud state read failed (${response.status}).`);
    return response.json();
  };
  const current = await get();
  if (!Number.isSafeInteger(current.version) || !current.state?.applications || !current.state?.leads || !current.state?.manual_entries)
    throw Error('Incomplete cloud state; publication stopped.');
  if (batch.inspect_only === true) {
    const ids = new Set((batch.manual_reviews || []).map(review => review.id));
    const rows = current.state.manual_entries.filter(row => ids.has(row.id)).map(row => ({
      id:row.id, version:row.version, status:row.status, created_by:row.created_by,
      updated_at:row.updated_at, review_ids:(row.review_history || []).map(review => review.review_id)
    }));
    console.log(JSON.stringify({inspection_only:true, cloud_version:current.version, records:rows}));
    return;
  }
  const result = mergeBatch(current.state, batch);
  if (!result.added && !result.changed && !result.reviewed) { console.log('Batch already present; no write needed.'); return; }
  const saved = await fetch(endpoint, {method:'PUT', headers:{...headers,'Content-Type':'application/json'},
    body:JSON.stringify({expected_version:current.version,state:result.state})});
  if (!saved.ok) throw Error(`Version-guarded Save failed (${saved.status}); no blind retry.`);
  const verified = await get();
  const content = state => { const value = structuredClone(state); delete value.updated_at; return JSON.stringify(value); };
  if (verified.version !== current.version + 1 || content(verified.state) !== content(result.state) ||
      JSON.stringify(verified.state.applications) !== JSON.stringify(current.state.applications) ||
      verified.state.manual_entries.length !== current.state.manual_entries.length ||
      verified.state.record_visibility.length !== current.state.record_visibility.length ||
      batch.leads.some(lead => !verified.state.leads.some(row => row.key === lead.key)))
    throw Error('The live read did not confirm preservation and the new lead keys.');
  console.log(`Verified cloud state version ${verified.version}: ${result.added} new leads, ${result.changed} closed/expired updates, ${result.reviewed} guarded review holds; prior applications, attachments, attribution and Bin retained.`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href)
  main().catch(error => { console.error(error.message); process.exitCode = 1; });
