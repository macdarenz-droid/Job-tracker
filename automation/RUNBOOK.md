# RUNBOOK: one daily tick

Rewritten 13 Nov 2026. The old runbook produced records; this one produces **submitted
applications**. Read `automation/APPLY.md` first: it is the method, and its rules for
anything submitted in the owner's name apply to every step here. Read both files fresh
each tick. Decide, don't ask; write new decisions to `docs/COACHING-DECISIONS.md`.

Order matters: **submit what is waiting before finding anything new.**

## 0. Trigger prompt

> Job-application tick. Follow `automation/RUNBOOK.md` and `automation/APPLY.md` in
> macdarenz-droid/Job-tracker (branch `claude/job-search-automation-sg3inr`): read replies
> and receipts, clear the apply queue for the routes you can submit, then find and queue
> new adverts only if the queue is short. End with the daily report in APPLY.md section 9.

Cadence (`config.json -> schedule`): one full tick a day, early morning Melbourne time,
and a second submit-only tick (steps 1 to 3) in the early afternoon while the queue is not
empty. No submissions between 21:00 and 07:00 Melbourne time.

## 1. Setup

```
cd <repo> && git fetch origin && git checkout claude/job-search-automation-sg3inr && git pull --rebase origin claude/job-search-automation-sg3inr
cd automation/scripts && RUN=$(python3 journal.py start)
python3 queue.py expire && python3 queue.py stats
```

Say which routes this runner can submit today (SEEK needs the signed-in SEEK session,
EMAIL needs the Gmail connector) and work only those. A route you cannot do stays in the
queue for the runner that can; it is not a reason to stop the tick.

## 2. Replies and receipts (runner with Gmail)

Search Gmail since the last tick for: SEEK receipts (`from:noreply@s.seek.com.au
"successfully submitted"`), SEEK "unlikely to progress" notices, employer replies and
bounces to anything sent, and portal acknowledgements (PageUp, Workday and similar). Use
message-level reads: thread previews show only the oldest five messages. Match each to a
queue entry or to `prior_outreach.json` and record it (`queue.py mark ... applied` for a
receipt of something a person submitted by hand; rejections and replies in the entry's
notes and on the tracker when it accepts writes).

An interview request, a call request or a question from an employer: tell the owner
**now**, in plain words, with the employer, the role and what they asked.

## 3. Submit the queue

Repeat until `queue.py next` refuses (cap reached, nothing open, or too soon):

```
python3 queue.py next --route SEEK --by <runner>     # APPLY.md section 5
python3 queue.py next --route EMAIL --by <runner>    # APPLY.md section 6
python3 queue.py next --route EMPLOYER_PORTAL --by <runner>   # APPLY.md section 7
```

Each submission ends with `queue.py mark`, then `git pull --rebase`, commit, push. Never
hold several marks back for one commit at the end.

## 4. Discover (only when the queue is short)

Skip this step when more than `limits.queue_pause_discovery_above` entries are open, and
do only a light sweep when `limits.queue_target_open` or more are open. Preparing more
packs than can be submitted is how 180 packs went stale.

```
python3 seek.py sweep --daterange 3 --max-details 60 --out ../runs/$RUN/candidates.json
python3 tracker.py check ../runs/$RUN/candidates.json --out ../runs/$RUN/candidates.json
```

Then one sweep agent on the day's rotation (`config.json -> sweep_rotation`): construction
materials testing and geotechnical firms' careers pages; land-development and civil design
consultancies and subdivision contractors; council and state agency job boards. It reads
JavaScript-only portals with `browse.py`. Each advert it finds is saved as
`runs/$RUN/extra/<slug>.json` with the same fields as a SEEK candidate.

Widen only once, to `--daterange 7`. A tick that finds nothing new is a valid result.
There is no quota of records and no speculative enquiry to fill a gap.

## 5. Screen (one agent)

For every new candidate, in this order:

1. **Lane** (`config.json -> lanes`, `seek.py lane_for`): read the duties. Drafter,
   technician, engineer, or none. None means reject: labouring, traffic control, survey
   assistant, administration, document control, estimator, project coordinator,
   student-only roles and formal graduate programs are out.
2. **Mandatory bars**: citizenship or permanent residency, "no temporary visas", a named
   Australian degree, current enrolment, a licence or ticket he lacks, a stated minimum of
   two or more years called essential. Any one: reject. Words like preferred, ideally,
   desirable and typically are not bars.
3. **Fit** (`config.json -> fit`, threshold 65).
4. **Form questions**: answer each with `queue.py answer`. Every mandatory question must be
   answerable from `facts.json -> answers`.

Three outcomes only: `APPLY` (goes to step 6), `ASK_OWNER` (fit is there but one fact is
missing: one plain question to the owner, never more than three open), `REJECT` with the
reason in `runs/$RUN/rejected.json`. There is no hold pile.

Rank what will be applied for: lane, then adverts that ask no paid years in the role,
then newest. Aim to queue an advert within two days of its listing.

## 6. Prepare the pack and queue it

For each `APPLY`:

- `resume_variant`: the lane.
- `cover_letter_text`: at most 200 words, three short paragraphs (APPLY.md section 8). The
  first sentence carries one true, specific line from the advert. No sentence about what
  he lacks. `relocation_line` when the job is outside daily travel distance of Melton VIC.
- Route: `SEEK` when the advert uses SEEK's own apply; `EMAIL` only when the employer
  publishes an address for applications (record where, in `email.evidence_url`);
  `EMPLOYER_PORTAL` or `EMPLOYER_FORM` for link-outs.
- `questions`: every form question with its answer and the `facts.json` line behind it.

```
python3 checks.py draft ../runs/$RUN/drafts/<id>.json      # tone, length, truth
python3 queue.py add ../runs/$RUN/drafts/<id>.json
```

One reviewer agent then reads everything queued in this tick and tries to refute each
sentence and each answer against `facts.json`. One confirmed false or unsupported claim:
fix it or `queue.py mark <id> skipped`.

Go back to step 3 once: fresh adverts are worth submitting the same day.

## 7. Tracker

The queue is the source of truth for what is waiting. The tracker website is the owner's
view of history. When the tracker accepts writes, mirror each queue entry and each change
of status to it with `tracker.py`. If a tracker write fails, say so once in the daily
report and carry on: a full or broken tracker never stops an application again.

## 8. Close

```
python3 queue.py render
python3 journal.py note $RUN stage=end queue_open=<n> applied=<n> seek_submitted=<n> emails_sent=<n> portal_submitted=<n> expired_unsubmitted=<n> replies=<n> interviews=<n> new_adverts_screened=<n> queued=<n> rejected=<n> ask_owner=<n> nothing_new=<true|false>
git add automation docs && git commit -m "Job-application tick <run_id>: <n> applied" && git pull --rebase && git push
```

Then the daily report to the owner, in the form in APPLY.md section 9.

Commit run folders without the full candidate dumps when they are large; `runs/` is a
working log, not the product.

## 9. Stop conditions

Say it, then end the turn: SEEK or a portal challenges, limits or warns the account; a
send whose outcome is uncertain; the branch cannot be pushed; a rule in `AGENTS.md` or
`APPLY.md` would have to be broken to continue. A full tracker, a missing connector or an
empty search is **not** a stop condition: do the other steps.

## 10. Bounds

| Item | Limit |
|---|---|
| SEEK submissions | 6 a day, at least 20 minutes apart |
| Emails | 3 a day (follow-ups included) |
| Portal or form submissions | 3 a day |
| Open questions to the owner | 3 |
| Speculative approaches | 3 a week, labelled, to a published application address only |
| Repeat block | same employer and role, 90 days after a real submission or rejection |
| Email | 130 words |
| Cover letter | 200 words |
| Agents per tick | 4 (sweep, screen, reviewer, one spare) |
