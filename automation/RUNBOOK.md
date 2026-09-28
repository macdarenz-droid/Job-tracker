# RUNBOOK: one discovery tick

Claude follows this every five hours. Read it fresh each tick (`git show origin/claude/job-search-automation-sg3inr:automation/RUNBOOK.md` if the checkout may be stale). Keep the whole tick under about 25 minutes. Decide, don't ask; write new decisions to `docs/COACHING-DECISIONS.md`.

## 0. Routine prompt (what the schedule sends)

> Job-search tick. Follow `automation/RUNBOOK.md` in macdarenz-droid/Job-tracker (branch `claude/job-search-automation-sg3inr`) end to end: sweep, screen, dedupe, contact research, draft, verify, publish to the tracker as Claude, send at most one email only if the Gmail connector is attached, journal, commit and push. At the end write one line: "tick <run_id> done · new <n> · prepared <n> · sent <n> · held <n>". Speak only at a STOP condition otherwise.

## 1. Setup (2 min)

```
cd /home/user/Job-tracker && git fetch origin && git checkout claude/job-search-automation-sg3inr && git pull --ff-only origin claude/job-search-automation-sg3inr
test -f /root/.job-tracker-code || echo "tracker code file missing: re-create it from the six digits the owner gave in this session (never commit it); if the session has lost them, STOP"
test -f /home/user/Portfolio/assets/Marc-Darenz-Masarate-Resume.pdf || (cd /home/user && git clone -q https://github.com/macdarenz-droid/Portfolio)
cd /home/user/Job-tracker/automation/scripts && RUN=$(python3 journal.py start) && python3 tracker.py state
```

## 2. Discover (5 min)

```
python3 seek.py sweep --daterange 3 --max-details 60 --out ../runs/$RUN/candidates.json
python3 tracker.py check ../runs/$RUN/candidates.json --out ../runs/$RUN/candidates.json
```

Then, in parallel with WebSearch/WebFetch (one Workflow, see §9): (a) twelve employers from `config.json → target_employers` (rotate by run number; record what was checked in `employers.json`), (b) three WebSearch angles: council job boards, state government graduate programs, "graduate civil engineer" or "civil drafter" plus a region. Any advert found outside SEEK is added to `candidates.json` with `source`, `url`, `company`, `title`, `location`, `content_text`, `listed_at` if shown, then re-checked with `tracker.py check`.

Fewer than three new candidates after dedupe → widen: `--daterange 7`, then `--max-details 100`. Still nothing → journal "nothing new" and go to §8. Never lower the fit threshold to hit a number.

## 3. Screen (parallel agents, 5 min)

For every candidate not blocked as duplicate: score with the rubric in `config.json → fit`, against `facts.json` only. Output per candidate: `percent`, `rationale` (3 lines), `caution`, `gaps` (list), `mandatory_unmet` (list or empty), `route` (SEEK, EMPLOYER_PORTAL, EMPLOYER_FORM, EMAIL), `apply_instructions` quoted from the advert, `open` (true only if `is_expired` is false and `expires_at`, if given, is in the future).

Keep: `percent >= 60`, `open`, `mandatory_unmet` empty. Everything else with `percent >= 60` but a mandatory problem becomes a `HELD_<REASON>` record (still tracked, still visible, never emailed). Rank kept candidates by percent, then by listed date (newest first). Take at most `max_new_records_per_run` (5).

## 4. Contact research (parallel agents, 8 min)

For each kept candidate, find the hiring person per `config.json → contact`:
1. Employer website: about, team, people, leadership, contact, projects, news pages. Capability statements and PDFs on the site.
2. WebSearch: `"<employer>" (engineering manager OR director OR civil engineer OR drafting manager) email`, `"<employer>" "@<employer domain>"`, `site:<employer domain> contact`.
3. Employer-authored public documents (tenders, council minutes, press releases) that print a name, role and business address.
Record: `recipient_name`, `recipient_role`, `recipient_email`, `contact_evidence_url`, `contact_verified_at`, `contact_confidence` (`published_direct`, `published_inbox`, `none`). A person whose email is not published is still noted by name and role for the SEEK pack (the cover letter can be addressed to them). Never guess, never pattern-build, never use a personal mailbox, never use a finder service. If only an HR or careers inbox exists and it says it accepts applications: `published_inbox`. Otherwise `none` and the route is SEEK or portal.

## 5. Draft (parallel agents, 5 min)

Per kept candidate write `drafts/<seek_id>.json` in the run folder with: `subject`, `email_body` (under 220 words, plain, first person, no banned phrases, no dashes, one specific line from the advert, the three scan facts, one clear ask, "I've attached my resume and cover letter"), `letter` (recipient block, subject, greeting, 4 to 5 short paragraphs under 340 words, closing), and for SEEK or portal routes `screening_answers` (truthful answers to the advert's `screening_questions`) and a five-step `checklist`.

Facts allowed: only `facts.json`. Style: how Marc writes on the Portfolio (short sentences, Australian English, no hype). Address the named person if one was found even when the email goes to an inbox. Speculative enquiry (no advert): say so in the first line.

## 6. Verify (parallel agents, 4 min)

Two independent checks per draft, both must pass:
- `python3 checks.py tone` on the email and on the letter text (`--kind letter`), and `python3 checks.py facts` on both. Zero issues.
- A reviewer agent that tries to refute every sentence of the email and letter against `facts.json` and the advert. Output: `false_claims` (list), `weak_lines` (list), `human_tone` (1 to 5). One false claim rejects the draft; the drafter fixes and the reviewer re-checks once. `human_tone` under 4 sends it back once.

## 7. Publish to the tracker (3 min)

`publish.py` does all of this from the run folder; the steps are listed so a failure can be finished by hand. For each verified candidate:
1. `python3 render_pdf.py letter drafts/<id>.json ../runs/$RUN/Marc_Masarate_<Company>_<Role>_Cover_Letter.pdf`, then open the PDF and read it back (page count 1, name and role correct).
2. Upload both PDFs: `python3 tracker.py upload <cover.pdf> cover` and `python3 tracker.py upload /home/user/Portfolio/assets/Marc-Darenz-Masarate-Resume.pdf resume --filename Marc_Masarate_<Company>_Resume.pdf`. Keep the returned objects as `attachments` (each carries `kind`, `sha256`, `stored_in: cloudflare_r2`).
3. Build the record with `tracker.new_record(...)`: `company`, `role`, `location`, `job_url`, `company_url`, `status`, `application_type` (`ADVERTISED_VACANCY` or `SPECULATIVE_ENQUIRY`), `application_route`, `application_method` (display: Email, SEEK, Company website), `recipient_*`, `contact_email` (same as recipient_email), `contact_evidence_url`, `contact_verified_at`, `subject`, `email_body`, `fit`, `gaps`, `match_score {percent, method, rationale, caution}`, `advert {source, listed_at, expires_at, verified_at, apply_instructions, screening_questions}`, `screening_answers`, `checklist`, `notes`, `checked_at`, `attachments`, `seek_id`.
   Status: `PREPARED_NOT_SENT` when a verified email recipient exists; `READY_JEREMIE_SEEK` or `READY_JEREMIE_EMPLOYER_PORTAL` otherwise; `HELD_<REASON>` for mandatory problems.
4. `python3 checks.py record <record.json>` must print OK for every `PREPARED_NOT_SENT` record.
5. `python3 tracker.py add ../runs/$RUN/records.json`. Read the response: records the guard skipped as duplicates are journaled, not retried.
6. Confirm on the live state: `python3 tracker.py list --mine`.

## 8. Send (only when the Gmail connector is attached; otherwise skip)

At most one per run. Pick the highest-fit `PREPARED_NOT_SENT` record whose advert is still open (re-check with `seek.py details`).
1. Lease: `tracker.py update <id> '{"status":"SENDING"}' --expect-status PREPARED_NOT_SENT`. A 409 or a status mismatch means stop and re-read.
2. Final checks: `tracker.py check` on the record again (no new outreach to the employer since), `checks.py record`, open both PDFs from R2 and read them, confirm the recipient against `contact_evidence_url` once more.
3. Send with the Gmail tool: to `recipient_email`, subject, body, both PDFs attached, from macdarenz@gmail.com. Record the returned message id.
4. `tracker.py update <id> '{"status":"SENT","sent_at":"<now>","gmail_message_id":"<id>","application_method":"Email"}' --expect-status SENDING`.
5. No message id or an error after the send call: `SEND_UNCERTAIN` with the error text; do not retry in this or any later run until Gmail Sent is checked. A bounce seen later: `DELIVERY_FAILED`.
6. Double touch: an email to a direct contact about an advert that must go through SEEK or a portal is sent only after that record is `MANUAL_APPLIED` (Marc or Jeremie pressed Applied).

Follow-ups: a `SENT` record older than `follow_up_after_days` with no reply noted (`reply_at` empty) and `follow_ups` under `max_follow_ups` is eligible; it counts as the run's one email, uses the same lease, and is a three-sentence note.

## 9. Workflow shape (ultracode)

One Workflow per tick, the script is in the repo: `automation/workflow/tick.js`. Run it with
`Workflow({scriptPath: "/home/user/Job-tracker/automation/workflow/tick.js", args: {...}})` where args carry
`run_id`, `run_dir`, `repo`, `today` ("28 September 2026"), `today_iso`, `candidate_ids` (the seek_ids marked new by
`tracker.py check`), `employers` (the next twelve names from `config.json → target_employers`, rotating by run), `top_n` (8).
Shape: sweeps (employer pages, councils and government, Victoria) run alongside screening (one low-effort agent per candidate);
a barrier ranks eligible candidates (fit ≥ 60, open, no mandatory problem, direct employers before agencies); then
`pipeline(top, contact, draft, verify → fix once → reverify)`. Agents write `screen/<id>.json`, `contacts/<id>.json`,
`drafts/<id>.json` and `extra/<slug>.json` in the run folder. Effort: `low` for screening, default for contact research and
drafting, `high` for the refuting reviewer.

Then publish deterministically: `python3 publish.py build $RUN` (inspect `records.json` and `rejected.json`), then
`python3 publish.py go $RUN` (renders letters, uploads both PDFs, adds records under the guard) and `python3 publish.py held $RUN`.

## 10. Close (2 min)

```
python3 journal.py note $RUN stage=end new=<n> prepared=<n> ready=<n> held=<n> sent=<n> duplicates=<n> nothing_new=<true|false>
cd /home/user/Job-tracker && git add automation docs && git commit -m "Job-search tick <run_id>: <n> new records" && git push -u origin claude/job-search-automation-sg3inr
```

STOP conditions (say them, then end the turn): tracker code missing; tracker API down for the whole tick; Gmail connector needed for a send; the branch cannot be pushed; a `SEND_UNCERTAIN` record exists.

## 11. Bounds

| Item | Limit |
|---|---|
| SEEK detail fetches | 60 (100 when widening) |
| New records per run | 5 |
| Emails per run | 1 |
| Speculative enquiries per run | 1 |
| Repeat block per employer | 90 days |
| Email length | 220 words |
| Cover letter | one page, 340 words |
