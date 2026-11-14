// The page's own script against the Worker (see page.js): the apply queue's detail on the record shapes the
// published runs really use, and what the page sends when a job is marked Applied, added, given a file or binned.
// The records are made up; only their shapes are taken from the published run records.
import test from 'node:test';
import assert from 'node:assert/strict';
import api from '../src/index.js';
import {openPage} from './page.js';
import {CODE, tracker, environment} from './helpers.js';

const day = offset => new Date(Date.now() + offset * 86_400_000).toISOString().slice(0, 10);
const LETTER = 'Dear hiring team,\n\nA short made-up letter of two paragraphs.', MOVE = 'I will relocate to Perth for this role and can start two weeks after an offer.';
function job(id, extra) {
  return {id, key: 'manual:' + id, company: 'Example ' + id, role: 'Civil Drafter', location: 'Perth WA', status: 'READY_JEREMIE_SEEK', application_route: 'SEEK', application_method: 'SEEK',
    job_url: 'https://www.seek.com.au/job/9000' + id.length, contributor_name: 'Grok AI', created_by: 'grok-job-search', created_at: '2026-10-01T00:00:00.000Z', updated_at: '2026-10-01T00:00:00.000Z',
    version: 1, attachments: [], ...extra};
}
// In closing order. The first runner stored prepared answers as one {question: answer} object, later ones as a list.
function shapes() {
  const state = tracker(0);
  state.manual_entries.push(
    job('answers-object', {advert: {expires_at: day(1), apply_instructions: 'Apply on SEEK.', screening_questions: ['Do you have a White Card?', 'Expected salary?']},
      screening_answers: {'Do you have a White Card?': 'Yes.', 'Notice period?': 'None.'}, fit: ['Matches the drafting lane', 'AutoCAD from study'], checklist: ['Attach the resume'], match_score: {percent: 72}}),
    job('answers-list', {advert: {expires_at: day(2), screening_questions: []}, screening_answers: [{question: 'Right to work?', answer: 'Full working rights.'}], fit: 'One sentence of fit.'}),
    job('answers-in-questions', {status: 'READY_EMPLOYER_PORTAL', application_route: undefined, application_method: undefined, route: 'EMPLOYER_PORTAL', job_url: undefined, url: 'https://careers.example.test/apply/7',
      closes_at: day(3), screening_answers: [], questions: [{question: 'Driver licence?', options: ['Yes', 'No'], answer: 'Yes', status: 'answered'}, {question: 'Years of 12d?', answer: '', status: 'unanswered'}],
      fit: 66, cover_letter_text: LETTER, relocation_line: MOVE}),
    job('seek-url-only', {status: 'READY_SEEK', application_route: undefined, application_method: undefined, closes_at: day(4)}),
    job('odd-values', {status: 'ASK_OWNER', closes_at: day(5), advert: {screening_questions: 'not a list'}, screening_answers: 'n/a', questions: 7, fit: {text: 'x'}, checklist: 'none',
      ask_owner: ['Is the salary acceptable?', null, {question: 'Relocate to Darwin?', why: 'the advert says on site'}]}));
  return state;
}
const ids = ['answers-object', 'answers-list', 'answers-in-questions', 'seek-url-only', 'odd-values'];
async function request(ctx, path, method, body) {
  ctx.invocation();
  const response = await api.fetch(new Request('https://tracker.example' + path, {method, headers: {'X-Tracker-Code': CODE, 'Content-Type': 'application/json'}, body: body && JSON.stringify(body)}), ctx.env);
  return {status: response.status, data: await response.json()};
}
// `rows` true: each record has its own row, as after the deploy's one-time copy. False: the single document.
async function start(rows, state = shapes()) {
  const ctx = environment(state);
  if (rows) assert.equal((await request(ctx, '/api/admin/backfill', 'POST')).status, 200);
  const page = await openPage(ctx);
  page.run("setView('queue')");
  page.calls.length = 0;
  return {ctx, page, stored: id => JSON.parse(ctx.db.prepare('SELECT body FROM records WHERE id = ?').get(id)?.body || 'null'), sent: () => page.calls.map(call => [call.method, call.path, call.status])};
}
// The made-up jobs come first: the seed's own ready leads have no closing date and follow them.
const queue = page => page.find('records', '.queue-row').map(row => row.querySelector('b').textContent).filter(name => name.startsWith('Example '));
const rowOf = (page, id) => page.find('records', '.queue-row').find(row => row.querySelector('b').textContent === 'Example ' + id);
const tapApplied = (page, id) => page.tap(rowOf(page, id).querySelector('.apply-btn'));
const today = new Intl.DateTimeFormat('en-CA', {timeZone: 'Australia/Sydney', year: 'numeric', month: '2-digit', day: '2-digit'}).format(new Date());

test('the apply queue detail opens for every shape of prepared answers, and shows why a job fits', async () => {
  const {page} = await start(true);
  assert.deepEqual(page.find('records', '.queue-row').slice(0, 5).map(row => row.querySelector('b').textContent), ids.map(id => 'Example ' + id), 'soonest closing first');
  const open = id => { page.$('detail').close(); page.tap(rowOf(page, id)); const detail = page.detail(); assert.deepEqual([detail.open, detail.title], [true, 'Example ' + id]); return detail.sections; };

  const object = open('answers-object');
  assert.equal(object['Form questions'], 'Form questions' + 'Do you have a White Card?CopyYes.' + 'Notice period?CopyNone.' + 'Expected salary?No prepared answer. Don\'t guess this one.');
  assert.equal(object['Why it fits'], 'Why it fits• Matches the drafting lane\n• AutoCAD from study');
  assert.equal(object['How to apply'], 'How to applyCopyApply on SEEK.\n1. Attach the resume');

  const list = open('answers-list');
  assert.equal(list['Form questions'], 'Form questionsRight to work?CopyFull working rights.');
  assert.equal(list['Why it fits'], 'Why it fitsOne sentence of fit.');

  const queued = open('answers-in-questions');
  assert.equal(queued['Form questions'], 'Form questionsDriver licence?CopyYes' + 'Years of 12d?No prepared answer. Don\'t guess this one.');
  assert.equal(queued['Cover letter'], 'Cover letterCopy' + LETTER + '\n\n' + MOVE);
  assert.equal('Why it fits' in queued, false, 'a bare number is not a reason');
  await page.tap(page.find('detail-body', '.copy-btn')[0]);
  assert.deepEqual(page.clipboard, [LETTER + '\n\n' + MOVE]);

  assert.deepEqual(Object.keys(open('seek-url-only')), []);
  const odd = open('odd-values');
  assert.equal(odd['Question for you'], 'Question for you• Is the salary acceptable?\n• Relocate to Darwin? (the advert says on site)');
  assert.equal('Form questions' in odd, false);
  // Every other row of the tracker opens as well, in the queue or not.
  assert.equal(page.run('allRows().active.map(r => { openDetail(r); return document.getElementById("detail").open; }).every(Boolean)'), true);
});

test('with a row per record, Applied sends the changed fields of that one record under its own guard', async () => {
  const {ctx, page, stored, sent} = await start(true);
  const before = stored('answers-object');
  await tapApplied(page, 'answers-object');
  assert.equal(page.$('editor').open, true);
  assert.deepEqual([page.form.status.value, page.form.applied_date.value, page.form.application_method.value, page.form.contributor_name.value], ['MANUAL_APPLIED', today, 'SEEK', 'Marc']);
  await page.submit();
  assert.deepEqual(sent(), [['PATCH', '/api/records/answers-object', 200]], 'one small request, no whole-tracker save');
  assert.ok(page.calls[0].bytes < 200 && page.calls[0].queries === 3, `${page.calls[0].bytes} bytes sent`);
  const after = stored('answers-object');
  assert.deepEqual(after, {...before, status: 'MANUAL_APPLIED', applied_date: today, contributor_name: 'Marc', updated_at: after.updated_at, version: 2}, 'every other field is as the runner wrote it');
  assert.equal(page.$('editor').open, false);
  assert.match(page.$('status').textContent, /^Marked as applied\./);
  assert.deepEqual(queue(page), ids.slice(1).map(id => 'Example ' + id), 'the job has left the queue');
  // The page's copy followed its own save, so the next check for changes downloads nothing.
  page.calls.length = 0;
  await page.run('checkPublishedChanges()');
  assert.deepEqual(sent(), [['GET', '/api/version', 200]]);
  // A SEEK advert is on seek.com.au: with no route recorded, the form still starts on SEEK.
  await tapApplied(page, 'seek-url-only');
  assert.equal(page.$('editor-kicker').textContent + '|' + page.form.company.value + '|' + page.form.application_method.value, 'Only once you\'ve actually applied|Example seek-url-only|SEEK');
  // A company-site job starts on Company website, from the record's own route.
  page.$('editor').close();
  await tapApplied(page, 'answers-in-questions');
  assert.equal(page.form.company.value + '|' + page.form.application_method.value, 'Example answers-in-questions|Company website');
  assert.equal(rowOf(page, 'odd-values').querySelector('.apply-btn'), null, 'a job with an open question has no Applied button');
  // Saving the editor with nothing changed sends nothing.
  page.$('editor').close();
  page.run('openEditor(allRows().active.find(r => r.id === "answers-list"), false)');
  page.calls.length = 0;
  await page.submit();
  assert.deepEqual(sent(), []);
  assert.equal(ctx.db.prepare('SELECT version FROM tracker_state WHERE id = 1').get().version, 226);
});

test('with a row per record, a new job is one added row and a file is one more small change', async () => {
  const {ctx, page, stored, sent} = await start(true);
  page.run('openEditor()');
  Object.assign(page.form.company, {value: 'Hand Entered Pty Ltd'});
  Object.assign(page.form.role, {value: 'Materials Testing Technician'});
  Object.assign(page.form.confirmation, {files: [new File(['%PDF-1.4 made-up receipt'], 'receipt.pdf')]});
  await page.submit();
  const id = ctx.db.prepare("SELECT id FROM records WHERE summary LIKE '%Hand Entered%'").get().id;
  assert.deepEqual(sent(), [['POST', '/api/records', 201], ['POST', '/api/documents', 201], ['PATCH', '/api/records/' + id, 200]]);
  const saved = stored(id);
  assert.deepEqual([saved.company, saved.role, saved.status, saved.key, saved.attachments.map(doc => doc.filename)], ['Hand Entered Pty Ltd', 'Materials Testing Technician', 'LEAD', 'manual:' + id, ['receipt.pdf']]);
  assert.equal(ctx.env.DOCUMENTS.objects.size, 1);
  assert.equal(page.$('editor').open, false);
  assert.equal(page.form.confirmation.value, '', 'the file field is cleared once the file is on the job');
  // A second file goes on top of the first: existing document references are never dropped.
  page.run(`openEditor(allRows().active.find(r => r.id === ${JSON.stringify(id)}), false)`);
  Object.assign(page.form.resume, {files: [new File(['%PDF-1.4 made-up resume'], 'resume.pdf')]});
  page.calls.length = 0;
  await page.submit();
  assert.deepEqual(sent(), [['POST', '/api/documents', 201], ['PATCH', '/api/records/' + id, 200]]);
  assert.deepEqual(stored(id).attachments.map(doc => doc.filename), ['receipt.pdf', 'resume.pdf']);
  page.calls.length = 0;
  await page.run('checkPublishedChanges()');
  assert.deepEqual(sent(), [['GET', '/api/version', 200]]);
  // Applied on a lead from the frozen history adds a record that points back at it; the lead itself is not touched.
  const lead = page.run('queueRows(allRows().active).find(r => !r.manual_entry_id)'), leads = JSON.stringify((await request(ctx, '/api/state', 'GET')).data.state.leads);
  page.run('openEditor(queueRows(allRows().active).find(r => !r.manual_entry_id), true)');
  Object.assign(page.form.application_method, {value: 'Company website'});
  page.calls.length = 0;
  await page.submit();
  assert.deepEqual(sent(), [['POST', '/api/records', 201]]);
  const made = JSON.parse(ctx.db.prepare('SELECT body FROM records ORDER BY position DESC LIMIT 1').get().body);
  assert.deepEqual([made.origin_key, made.company, made.status, made.key], [lead.key, lead.company, 'MANUAL_APPLIED', 'manual:' + made.id]);
  assert.equal(page.run(`queueRows(allRows().active).some(r => r.key === ${JSON.stringify(lead.key)})`), false, 'the lead has left the queue');
  assert.equal(JSON.stringify((await request(ctx, '/api/state', 'GET')).data.state.leads), leads);
});

test('with a row per record, Bin and Restore send one Bin entry', async () => {
  const {ctx, page, sent} = await start(true);
  const rows = () => ctx.db.prepare('SELECT COUNT(*) AS n, SUM(version) AS versions FROM records').get(), before = rows();
  page.run('askDelete(allRows().active.find(r => r.id === "answers-list"))');
  await page.$('confirm-delete').onclick();
  assert.deepEqual(sent(), [['POST', '/api/visibility', 200]]);
  assert.ok(page.calls[0].bytes < 100 && page.calls[0].queries === 3);
  assert.match(page.$('status').textContent, /^Moved to the Bin\./);
  assert.deepEqual(queue(page), ids.filter(id => id !== 'answers-list').map(id => 'Example ' + id));
  assert.equal(page.run('allRows().bin.some(r => r.id === "answers-list")'), true);
  await page.run('setDeleted(allRows().bin.find(r => r.id === "answers-list"), false)');
  assert.deepEqual(sent().at(-1), ['POST', '/api/visibility', 200]);
  assert.deepEqual(queue(page), ids.map(id => 'Example ' + id));
  const entry = (await request(ctx, '/api/state', 'GET')).data.state.record_visibility.at(-1);
  assert.deepEqual([entry.record_key, entry.deleted, entry.version], ['manual:answers-list', 0, 2]);
  assert.deepEqual(rows(), before, 'no record row was written');
});

test('with a row per record, a job someone else changed first is not saved over; a change to another job does not block', async () => {
  const {ctx, page, stored, sent} = await start(true);
  // A runner records the SEEK receipt for the first job while the phone still shows it as ready.
  assert.equal((await request(ctx, '/api/records/answers-object', 'PATCH', {expected_version: 1, patch: {status: 'MANUAL_APPLIED_SEEK_RECEIPT_CONFIRMED', applied_date: '2026-11-12'}})).status, 200);
  await tapApplied(page, 'answers-object');
  await page.submit();
  assert.deepEqual(sent(), [['PATCH', '/api/records/answers-object', 409], ['GET', '/api/state', 200]]);
  assert.deepEqual([stored('answers-object').status, stored('answers-object').applied_date], ['MANUAL_APPLIED_SEEK_RECEIPT_CONFIRMED', '2026-11-12'], 'the runner\'s receipt stands');
  assert.equal(page.$('editor').open, false);
  assert.match(page.$('status').textContent, /^Someone else changed this job just now, so nothing was saved\./);
  assert.deepEqual(queue(page), ids.slice(1).map(id => 'Example ' + id), 'the page now shows what the runner saved');
  // Meanwhile a runner changes a different job. The phone's save of its own job still goes through...
  assert.equal((await request(ctx, '/api/records/odd-values', 'PATCH', {expected_version: 1, patch: {notes: 'from a runner'}})).status, 200);
  page.calls.length = 0;
  await tapApplied(page, 'answers-list');
  await page.submit();
  assert.deepEqual(sent(), [['PATCH', '/api/records/answers-list', 200]]);
  assert.equal(stored('answers-list').status, 'MANUAL_APPLIED');
  // ...and because someone else saved in between, the next check downloads the tracker and shows the runner's note.
  page.calls.length = 0;
  await page.run('checkPublishedChanges()');
  assert.deepEqual(sent(), [['GET', '/api/version', 200], ['GET', '/api/state', 200]]);
  assert.equal(page.run('tracker.manual_entries.find(r => r.id === "odd-values").notes'), 'from a runner');
});

test('before the copy the page saves the whole tracker as it always did, and a refused edit is not reported as saved', async () => {
  const {ctx, page, sent} = await start(false);
  const document = () => JSON.parse(ctx.db.prepare('SELECT payload FROM tracker_state WHERE id = 1').get().payload);
  await tapApplied(page, 'answers-object');
  assert.equal(page.form.application_method.value, 'SEEK');
  await page.submit();
  assert.deepEqual(sent(), [['PUT', '/api/state', 200]]);
  assert.deepEqual([document().manual_entries.find(row => row.id === 'answers-object').status, document().manual_entries.length], ['MANUAL_APPLIED', 3 + ids.length]);
  page.run('askDelete(allRows().active.find(r => r.id === "answers-list"))');
  await page.$('confirm-delete').onclick();
  assert.deepEqual(sent().at(-1), ['PUT', '/api/state', 200]);
  assert.equal(document().record_visibility.at(-1).record_key, 'manual:answers-list');
  // Someone else saves; the page's edit of an existing job is refused and must not claim it was saved.
  const current = (await request(ctx, '/api/state', 'GET')).data;
  assert.equal((await request(ctx, '/api/state', 'PUT', {expected_version: current.version, state: current.state})).status, 200);
  page.run('openEditor(allRows().active.find(r => r.id === "odd-values"), false)');
  Object.assign(page.form.notes, {value: 'typed on the phone'});
  page.calls.length = 0;
  await page.submit();
  assert.deepEqual(sent(), [['PUT', '/api/state', 409], ['GET', '/api/state', 200]]);
  assert.equal(page.$('editor-error').textContent, 'A newer cloud version exists. Refresh before saving.');
  assert.equal(document().manual_entries.find(row => row.id === 'odd-values').notes, undefined);
});

test('with a row per record, a file still lands on a job that someone else changed during the upload', async () => {
  const {ctx, page, stored, sent} = await start(true);
  page.run('openEditor(allRows().active.find(r => r.id === "answers-list"), false)');
  Object.assign(page.form.confirmation, {files: [new File(['%PDF-1.4 made-up receipt'], 'receipt.pdf')]});
  // While the file is going up, a runner adds a note to the same job.
  const put = ctx.env.DOCUMENTS.put;
  ctx.env.DOCUMENTS.put = async (...args) => { ctx.env.DOCUMENTS.put = put; assert.equal((await request(ctx, '/api/records/answers-list', 'PATCH', {expected_version: 1, patch: {notes: 'from a runner'}})).status, 200); return put(...args); };
  await page.submit();
  assert.deepEqual(sent(), [['POST', '/api/documents', 201], ['PATCH', '/api/records/answers-list', 409], ['GET', '/api/state', 200], ['PATCH', '/api/records/answers-list', 200]]);
  assert.deepEqual([stored('answers-list').notes, stored('answers-list').attachments.map(doc => doc.filename)], ['from a runner', ['receipt.pdf']]);
  assert.equal(page.$('editor').open, false);
});

test('with a row per record, Import backup is the one whole-tracker save left, and the page reads the new guards after it', async () => {
  const {ctx, page, stored, sent} = await start(true);
  const backup = (await request(ctx, '/api/state', 'GET')).data.state;
  backup.manual_entries.push(job('from-backup', {status: 'LEAD', closes_at: day(20)}));
  await page.$('import-file').onchange({target: {files: [new File([JSON.stringify(backup)], 'tracker-backup.json')], value: 'x'}});
  assert.deepEqual(sent(), [['PUT', '/api/state', 200], ['GET', '/api/state', 200]]);
  assert.equal(page.$('status').textContent, 'Backup imported.');
  assert.equal(stored('from-backup').company, 'Example from-backup');
  // The imported job can be changed straight away under its own guard.
  page.run('openEditor(allRows().active.find(r => r.id === "from-backup"), true)');
  page.calls.length = 0;
  await page.submit();
  assert.deepEqual(sent(), [['PATCH', '/api/records/from-backup', 200]]);
  assert.equal(stored('from-backup').status, 'MANUAL_APPLIED');
});
