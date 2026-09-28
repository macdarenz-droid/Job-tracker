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

Then one sweep Agent (see §9) on this run's rotation: (a) six employers from `config.json → target_employers` (rotate by run number; record what was checked in `employers.json`), or (b) council job boards and state government graduate programs, or (c) Victoria off-SEEK adverts (Melbourne west first). Each advert found is saved as `extra/<slug>.json` (`id`, `source`, `company`, `title`, `location`, `url`, `listed_at`, `expires_at`, `content_text`, `apply_instructions`, `screening_questions`, `is_expired`, `is_link_out`) and then checked with `tracker.py check` (write the list to `extra/_check.json`).

Fewer than three new candidates after dedupe → widen: `--daterange 7`, then `--max-details 100`. Still nothing → journal "nothing new" and go to §8. Never lower the fit threshold to hit a number.

## 3. Screen (one agent, low effort)

```
python3 seek.py digest ../runs/$RUN            # compact view of the new candidates, at most 25
```
One Agent (effort low) reads `screen_input.json`, `facts.json` and `config.json → fit`, scores every candidate with the rubric, and writes `screen/<id>.json` per candidate: `percent`, `rationale` (3 lines), `caution`, `gaps`, `mandatory_unmet`, `route` (SEEK, EMPLOYER_PORTAL, EMPLOYER_FORM, EMAIL), `apply_email`, `apply_instructions`, `open`, `employer_is_agency`, plus `company`, `title`, `location`, `url`, `listed_at`, `expires_at`, `screening_questions` copied from the input. It returns a ranked table (id, company, title, percent, open, mandatory, route, agency).

Keep: `percent >= 60`, `open`, `mandatory_unmet` empty; direct employers before agencies; then by percent and listed date. Take at most `contact_research_max_per_run` (4). Adverts at 60+ with a mandatory problem become `HELD_…` records through `publish.py held`.

## 4. Contact research (one agent per kept employer, at most 4, in parallel)

Each agent gets the advert (`candidates.json` id or the `extra/` file), the contact rule from `config.json → contact`, and writes `contacts/<id>.json`: `company_url`, `careers_url`, `recipient_name`, `recipient_role`, `recipient_email`, `contact_evidence_url`, `evidence_quote`, `contact_confidence` (`published_direct`, `published_inbox`, `none`), `named_people` (name, role, email if published, evidence_url), `employer_line` (one true, specific line about the employer or role from their site or the advert), `notes`. Sources in order: employer website (about, team, contact, projects, news, capability PDFs), WebSearch for `"<employer>" engineering manager OR director email` and `"@<domain>"`, employer-authored public documents. Never guess or pattern-build, never personal mailboxes, never finder or broker sites, never recruiters. A generic info@ inbox only if the site says it takes applications.

## 5. Draft (Claude itself, no agent)

Claude writes `drafts/<id>.json` for each kept candidate from the advert, the screen file, the contact file and `facts.json`: `subject`, `email_body` (under 220 words: which advert and where seen; if writing to a named person, that Marc wanted to reach them directly; one paragraph with the three scan facts: Advanced Diploma of Civil Construction Design finished February 2026 with road, earthworks, pavement and stormwater design in Civil 3D and AutoCAD; site work in the Philippines 2019 to 2020 as field engineer and project-in-charge; Melton based, White Card, licence and transport, full working rights to December 2027 on a 485 visa, available for site, regional and FIFO work; one specific line from the advert or the employer_line; the honest limit in one clause if the advert asks for something Marc lacks; one clear ask; "I've attached my resume and cover letter."; sign-off with name, phone and the portfolio address), `letter` (`recipient_name`, `recipient_role`, `company`, `company_line`, `subject`, `greeting`, 4 or 5 short paragraphs under 340 words, `closing`), and for SEEK or portal routes `screening_answers` and a five-step `checklist`. Also `company`, `role`, `location`, `job_url`, `route`, `recipient_*`, `contact_evidence_url`, `application_type`, `notes`. No banned phrases, no dashes, no exclamation marks, nothing outside `facts.json`.

## 6. Verify (checks.py, then one reviewer agent for all drafts)

```
python3 publish.py build $RUN        # runs checks.py on every draft; rejected.json lists what failed
```
Then one Agent (effort high) reads every `drafts/<id>.json` with `facts.json`, the adverts and the contact files and tries to refute each sentence; returns per draft `false_claims`, `weak_lines`, `tone_issues`, `human_tone` (1 to 5), `specific_to_advert`, `pass`. Claude fixes what it flags and re-runs `publish.py build`. A draft that still fails is dropped from this run, not sent.

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

## 9. Agent budget (owner: about 5 to 6 on a 10 scale)

Per tick at most seven agents: one sweep (rotating: employers, councils and government, Victoria off-site, see `config.json → sweep_rotation` by run number), one screening agent, up to four contact-research agents in parallel, one reviewer. Claude drafts and publishes itself. No per-candidate screening agents, no panels, no duplicate reviewers. Use the Agent tool directly; no Workflow orchestration.

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
