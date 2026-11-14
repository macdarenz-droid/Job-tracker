# RUNBOOK: one tick

Rewritten 13 Nov 2026 and corrected 14 Nov 2026. The old runbook produced records; this one
produces **submitted applications**. Read `automation/APPLY.md` first: it is the method, and
its rules for anything submitted in the owner's name apply to every step here. Read both files
fresh each tick. Decide, don't ask; write new decisions to `docs/COACHING-DECISIONS.md`.

Order matters: **submit what is waiting before finding anything new.**

Run every command from `automation/scripts`. Type ids in full; shell variables do not survive
between commands. Never type the run id of an earlier session. Text copied from a form or an
advert goes into a JSON file with a quoted heredoc (APPLY.md section 3, "Typed text").

## 0. Trigger prompt and cadence

> Job-application tick. Follow `automation/RUNBOOK.md` and `automation/APPLY.md` in
> macdarenz-droid/Job-tracker (branch `claude/job-search-automation-sg3inr`): read replies and
> receipts if you have Gmail, submit the queue on the routes you can submit, then find and
> queue new adverts only if the queue is short. Send the daily report if it is the first tick
> after 17:00 Melbourne time.

Cadence (`config.json -> schedule`): one full tick a day, early morning Melbourne time, and
submit-only ticks (steps 1 to 3) later in the day while entries are waiting. `next` refuses
between 21:00 and 07:00 Melbourne time.

Who runs what (APPLY.md section 2): Grok submits `SEEK`, `EMPLOYER_PORTAL` and `EMPLOYER_FORM`
and may run discovery; the Claude runner with Gmail sends `EMAIL`, reads replies and receipts,
and may run discovery.

## 1. Setup

```
git pull --rebase --autostash
cd automation/scripts
python3 journal.py start            # prints RUN_ID: write it down
python3 queue.py expire
python3 queue.py check              # anything other than "0 problems": stop and report
python3 queue.py stats
python3 queue.py list --started     # earlier sessions' starts: settle them first (APPLY.md section 9, GROK.md step 7)
python3 browse.py trust             # only a runner that will sweep JavaScript careers pages (idempotent)
```

Commit and push what `expire` changed. If any git step fails: APPLY.md section 3, rule 3.

Say which routes this runner can submit today. A route you cannot do stays in the queue for
the runner that can.

## 2. Replies and receipts (runner with Gmail)

APPLY.md section 9: record receipts with `mark ID applied` (with `--at` the email's date),
replies with `queue.py outcome`, unmatched SEEK receipts in `automation/prior_outreach.json`, and
settle `UNCERTAIN` email entries against Gmail Sent. Record any answer the owner gave since the
last tick (APPLY.md section 10). Read messages one by one: search
previews show only the oldest five messages of a thread. An interview or call request goes to
the owner **now**.

## 3. Submit the queue

For each route this runner submits, repeat until `next` gives exit 3 or 4 on that route, then
move to the next route:

```
python3 queue.py next --route SEEK --by Grok --run RUN_ID              # APPLY.md section 5
python3 queue.py next --route EMPLOYER_PORTAL --by Grok --run RUN_ID   # APPLY.md section 7
python3 queue.py next --route EMPLOYER_FORM --by Grok --run RUN_ID     # APPLY.md section 7
python3 queue.py next --route EMAIL --by Claude --run RUN_ID           # APPLY.md section 6, after lock take
```

Run the claim git line before submitting. Finish every entry with one `mark`, then
`git add -A -- ../queue ../journal.jsonl && git commit -m 'queue: ID result' && git pull --rebase --autostash && git push`.
Never hold several marks back for one commit at the end. Do not claim anything after 20:45
Melbourne time.

Entries that `next` holds as "letter to rewrite" (written under the old rules): a Claude runner
rewrites them from the saved advert under APPLY.md section 8 and saves the new text with
`python3 queue.py letter ID --file <letter.txt>` (EMAIL entries also `--subject` and
`--body-file`), at most five a tick, soonest closing first.

## 4. Discover (only when the queue is short)

"Waiting" means `queue_open` in `queue.py stats` (status `OPEN` only). Skip this step when more
than `limits.queue_pause_discovery_above` (25) are waiting, and do only a light sweep when
`limits.queue_target_open` (12) or more are waiting.

```
python3 seek.py sweep --daterange 3 --max-details 60 --out ../runs/RUN_ID/candidates.json
python3 tracker.py check ../runs/RUN_ID/candidates.json --out ../runs/RUN_ID/candidates.json   # only with TRACKER_CODE; otherwise skip
```

`tracker.py check` needs the six-digit tracker code (`TRACKER_CODE`). A runner without it skips
it: `queue.py add` checks duplicates against the queue and `prior_outreach.json` anyway.

Then one sweep agent on the day's rotation (`config.json -> sweep_rotation`): construction
materials testing and geotechnical firms' careers pages; land-development and civil design
consultancies and subdivision contractors; council and state agency job boards. It reads
JavaScript-only portals with `python3 browse.py text URL` and `python3 browse.py links URL
--match job`. Each advert it finds is saved as `../runs/RUN_ID/extra/<slug>.json` with the same
fields as a SEEK candidate, including the full advert text.

Widen only once, to `--daterange 7`. A tick that finds nothing new is a valid result. There is
no quota and no speculative enquiry to fill a gap.

## 5. Screen (one agent)

For every new candidate, in this order:

1. **Lane**: read the duties. `python3 seek.py lane "<title>" --text-file <advert.txt>` gives a
   first guess (drafter, technician, engineer or none); the duties decide. None means reject:
   labouring, traffic control, survey assistant, administration, document control, estimator,
   project coordinator, student-only roles and formal graduate programs are out.
2. **Mandatory bars**: citizenship or permanent residency, "no temporary visas", a named
   Australian degree or Engineers Australia eligibility called essential, current enrolment, a
   licence or ticket he lacks, a stated minimum of two or more years of paid experience (unless
   the advert calls it preferred, desirable, ideal or advantageous), a tool called essential or
   required that facts.json does not list. Any one: reject. Words like preferred, ideally,
   desirable and typically are not bars.
3. **Fit** (`config.json -> fit`, threshold 65).
4. **Form questions** (SEEK adverts list them): for each, write
   `{"question": "...", "advert_pay": "<the advert's pay text, or not stated>"}` into a file
   with a quoted heredoc and run `python3 queue.py answer --from-file FILE`. Exit 5 means the
   owner would have to answer it.

Three outcomes: `APPLY` (step 6), `ASK_OWNER` (fit is there but one fact is missing: queue it;
`queue.py add` sets `ASK_OWNER` itself for an unanswered form question, and for any other owner
question put it in `ask_owner` in your own words), `REJECT` with the reason in
`../runs/RUN_ID/rejected.json`. There is no hold pile.

## 6. Write the entry and queue it

For each `APPLY` or `ASK_OWNER`, write `../runs/RUN_ID/drafts/<slug>.json` with these fields
(`python3 queue.py add --help` lists them all):

- required: `lane`, `route` (`SEEK` when the advert uses SEEK's own apply; `EMAIL` only when
  the employer publishes an address for applications; `EMPLOYER_PORTAL` or `EMPLOYER_FORM` for
  link-outs), `company`, `role` (or `title`), `url`; `seek_id` for SEEK (taken from the url when
  it is a seek.com.au job link); for `EMAIL` an `email` object with `to`, `subject`, `body` and
  `evidence_url` (where the employer publishes that address);
- `advert_pay`: the advert's own pay text, or "not stated" (required when the form asks about
  salary);
- `closes_at` (YYYY-MM-DD) with `closes_source` `advert` when the advert states a closing date,
  `listing_expiry` when it is only SEEK's listing end;
- `location`, `listed_at`, `fit`, `resume_variant` (the lane), `relocation_line` (when the job
  is outside daily travel of Melton VIC), `application_type` (`SPECULATIVE_ENQUIRY` for an
  enquiry with no advert), `questions` (each question text, with its options if known),
  `verify_before_submit` (one-line checks for the submitter), `notes`, `source_run`;
- `cover_letter_text`: a greeting line, three short paragraphs, the sign-off, at most 200
  words (APPLY.md section 8), with the relocation sentence inside the third paragraph when
  `relocation_line` is set. The first paragraph carries one true, specific line from the
  advert. No sentence about what he lacks.

```
python3 checks.py draft ../runs/RUN_ID/drafts/<slug>.json      # tone, length, truth
python3 queue.py add ../runs/RUN_ID/drafts/<slug>.json --by <runner>
git add -A -- ../queue ../runs/RUN_ID && git commit -m 'queue: added <slug>' && git pull --rebase --autostash && git push
```

One reviewer agent then reads everything queued in this tick and tries to refute each sentence
and each answer against `facts.json`. One confirmed false or unsupported claim: fix the letter
with `python3 queue.py letter ID --file <letter.txt>` or `mark ID skipped`.

Then go back to step 3 once: fresh adverts are worth submitting the same day.

When `facts.json` changes, rebuild the resumes and the SEEK profile text and commit them with
it:

```
python3 resume.py build
git add -A -- ../facts.json ../SEEK_PROFILE.md ../../documents/resume && git commit -m "Facts changed: resumes rebuilt" && git pull --rebase --autostash && git push
```

## 7. Tracker

The queue is the source of truth for what is waiting and what was submitted. The tracker
website is the owner's history view. When the tracker accepts writes and the runner has the
tracker code, mirror applications to it with `tracker.py`. A failed tracker write is mentioned
once in the daily report and never stops an application.

## 8. Close

```
python3 queue.py render
python3 journal.py note RUN_ID stage=end queue_open=<n> applied=<n> seek_submitted=<n> emails_sent=<n> portal_submitted=<n> expired_unsubmitted=<n> replies=<n> interviews=<n> new_adverts_screened=<n> queued=<n> rejected=<n> ask_owner=<n> nothing_new=<true|false>
git add -A -- ../queue ../journal.jsonl ../runs/RUN_ID ../prior_outreach.json && git commit -m "Job-application tick RUN_ID: <n> applied" && git pull --rebase --autostash && git push
```

Counts this runner could not check are written as `null` (no Gmail: `replies=null`). Then the
daily report for this runner's own routes, if it is due (APPLY.md section 9).

## 9. Stop conditions

Say it, then end the turn: SEEK or a site challenges, limits or warns the account; `queue.py
check` reports a problem; a claim or lock cannot be pushed; a rule in `AGENTS.md` or
`APPLY.md` would have to be broken to continue. A full tracker, a missing connector or an
empty search is **not** a stop condition: do the other steps.

## 10. Bounds

| Item | Limit |
|---|---|
| SEEK submissions | 6 a day, at least 20 minutes apart |
| Emails | 3 a day |
| Employer-site submissions | 3 a day |
| Speculative enquiries | 3 a week, to a published application address only |
| Quiet hours | 21:00 to 07:00 Melbourne time |
| Repeat block | same employer and role: for ever after an application in the queue, 90 days after one in `prior_outreach.json` |
| Questions to the owner | at most three a day in each runner's report |
| Claims | none after 20:45 Melbourne time |
| Email | 130 words |
| Cover letter | 200 words, three paragraphs |
| Agents per tick | 4 (sweep, screen, reviewer, one spare) |
