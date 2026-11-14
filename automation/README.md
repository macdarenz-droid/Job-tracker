# Job-application pipeline: architecture

How the runners (Claude, Grok, Codex) get applications **submitted** for Marc and keep an
honest record of them. Rewritten 13 Nov 2026; the earlier design found leads and left them
for a person who was no longer there. `AGENTS.md` at the repo root applies to every run.

Read in this order: `APPLY.md` (the method), `RUNBOOK.md` (the daily tick),
`config.json` (settings), `facts.json` (the only source of claims about Marc).

## 1. Goal

Applications submitted with a receipt, for work his qualifications support, anywhere in
Australia. Three lanes, in order (`config.json -> lanes`):

1. **Drafter**: civil drafting and design (the work his 2026 Advanced Diploma trains for).
2. **Technician**: construction materials testing, civil and geotechnical lab and field
   technician work.
3. **Engineer**: graduate or junior civil, site or project engineer roles that welcome
   graduates.

Out: labouring, traffic control, survey assistant, administration, estimator, project
coordinator, student-only roles, formal graduate programs.

## 2. Flow

```
 daily tick
   │
   ├─ 1 replies and receipts (Gmail) ──────────────▶ queue entries updated, owner told at once
   │                                                 about any interview or call request
   ├─ 2 SUBMIT the queue ──┬─ SEEK   (Grok, signed-in SEEK session)
   │                       ├─ EMAIL  (runner with Gmail, automatic, 3 a day)
   │                       └─ PORTAL / FORM (Grok when it can; else ASK_OWNER)
   │                         every submission: receipt recorded, commit, push
   │
   ├─ 3 discover (only when the queue is short)
   │      seek.py sweep + one sweep agent on the rotation
   ├─ 4 screen: lane → mandatory bars → fit ≥ 65 → form questions answerable
   │      APPLY / ASK_OWNER / REJECT (no hold pile)
   ├─ 5 prepare: resume variant, 200-word letter, answers from facts.json → queue.py add
   │      checks.py + one reviewer agent
   └─ 6 close: journal end row, APPLY_QUEUE.md, daily report to the owner
```

## 3. Files

| Path | What it is |
|---|---|
| `automation/APPLY.md` | The method: who submits what, the queue, rules for anything in the owner's name |
| `automation/RUNBOOK.md` | The daily tick |
| `automation/GROK.md` | Short brief for the SEEK submitter |
| `automation/config.json` | Lanes, search terms, filters, fit rubric, daily caps, writing rules, statuses |
| `automation/facts.json` | The only allowed source of claims about Marc, and his standing answers for forms (`answers`) |
| `automation/queue/` | The apply queue: `open/`, `done/`, `APPLY_QUEUE.md`, `SEND_LOCK.json` |
| `automation/scripts/queue.py` | The only tool that writes the queue (claims, marks, answers, outcomes, send lock, report) |
| `automation/scripts/answers.py` | The one answer gate: every form answer comes from `facts.json` through it; `queue.py` and `checks.py` both use it |
| `automation/scripts/letter_pdf.py` | One-page cover-letter PDF for an email application, from a queue entry |
| `automation/scripts/seek.py` | SEEK search and job details, title prefilter, `lane_for` |
| `automation/scripts/checks.py` | Tone, length and truth checks before anything is queued or sent |
| `automation/scripts/resume.py` | Builds the three resume variants from `facts.json` into `documents/resume/` |
| `automation/SEEK_PROFILE.md` | Text for the SEEK profile so it matches the resume |
| `automation/scripts/tracker.py`, `publish.py` | Tracker client and record builder (history view; never a gate) |
| `automation/scripts/email_html.py` | Email HTML |
| `automation/scripts/compact_pdf.py`, `render_pdf.py` | Retired for applications (attach `documents/resume/` and `letter_pdf.py` output instead) |
| `automation/scripts/journal.py` | Run journal `automation/journal.jsonl` and `automation/runs/<id>/` |
| `automation/prior_outreach.json` | Applications already made (from receipts), for the duplicate check |
| `automation/tests/` | `cd automation && python3 -m unittest discover -s tests` |
| `docs/COACHING-DECISIONS.md` | Every decision, with the reason |
| `docs/DIAGNOSIS-2026-11-13.md` | Why two months produced no interview, with the numbers |

## 4. What changed on 13 Nov 2026, and why

| Before | Now | Why |
|---|---|---|
| "At least two new tracker records per tick" | No quota; the headline number is applications submitted with a receipt | 257 records, 2 emails sent |
| SEEK and portal packs marked `READY_JEREMIE_*` and left | Queue entries submitted by a named runner | The named person was no longer involved |
| Every send needed a "shared canonical journal lease" | A lock file in this repo | No runner could reach the lease; it blocked every send for six weeks |
| One email per run | 3 emails, 6 SEEK and 3 portal submissions a day | The cap was per run, and nothing was sent anyway |
| Unsubmitted leads blocked the employer for 90 days | Only real submissions and rejections block, and only the same role | 94 adverts were dropped as duplicates of packs nobody submitted |
| Mandatory doubts became `HELD_*` records | `ASK_OWNER` (one plain question, three open at most) or reject | 77 holds waited for answers nobody asked for |
| Engineer and graduate-program titles first | Drafter and technician lanes first; graduate programs out | Most past applications were engineer titles; the roles his diploma fits were barely tried |
| Emails and letters stated the visa end date and "the honest limit" | Short work-rights line; never volunteer a limit | The letters led with reasons to say no |
| One master resume headed "Graduate Civil Engineer" | Three variants, current Australian job listed, no gap | A 2019 degree is not "graduate" to an employer |
| Tracker write required before anything else | Queue in the repo; the tracker is a history view | The tracker was full from 17 Oct and stopped the whole loop |
| Five-hourly sweeps | One discovery sweep a day, two submit passes | Adverts were found within hours already |

## 5. Tracking

- The queue (`automation/queue/`) says what is waiting and what was submitted, with
  receipts. `journal.jsonl` end rows carry `queue_open`, `applied`, `seek_submitted`,
  `emails_sent`, `portal_submitted`, `expired_unsubmitted`, `replies`, `interviews`.
- The tracker website (Cloudflare Worker, D1, R2) is the owner's history view. Runner
  records are manual entries with the runner's own `contributor_name`; nobody edits
  another author's records or the frozen arrays. The storage fix that stops it filling up
  (one row per record) went live from `main` on 14 Nov 2026; its code lives on `main`, not on
  this branch. The page's Old packs view lists packs the old automation prepared, not this queue.
- The six-digit tracker code is read from `TRACKER_CODE` or the file named in
  `config.json`; it is never committed.

## 6. Risks and how they are handled

| Risk | Handling |
|---|---|
| A false or unsupported answer in the owner's name | Answers only from `facts.json`; an unanswerable mandatory question stops that application; reviewer agent on everything sent |
| The same job applied for twice | One queue entry per advert; commit and push after every submission; Gmail search before every email; 90-day same-role block |
| SEEK challenges, limits or warns the account | Stop all SEEK submissions and tell the owner (APPLY.md section 5) |
| Packs go stale again | Discovery pauses when the queue is long; `queue.py expire` every tick; a week with zero submissions is reported as a failure |
| Two runners send at once | `SEND_LOCK.json` taken by a pushed commit |
| Private details in a public repo | Nothing beyond what `facts.json` already holds; no secrets, codes, licence numbers or referee details anywhere |
| Cost | Free plans only; four agents a tick at most |

## 7. Handover to another session

A new session needs: this branch; the tracker code in its environment if it will write to
the tracker; the Gmail connector if it will send or read mail; and the instruction in
`RUNBOOK.md` section 0. Everything else is in the repo.
