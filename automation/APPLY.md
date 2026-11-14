# APPLY: how applications get submitted

Written 13 Nov 2026 and corrected 14 Nov 2026 after two independent reviews, on the owner's
instruction: "every agent just sends me their leads and nothing has been applied ... plan and
do where you can directly apply ... then share that method to the repo." This file is the
method. `RUNBOOK.md` is the daily procedure that uses it, and `GROK.md` is the short brief for
the SEEK and employer-site submitter. Root `AGENTS.md` still applies.

## 1. Why this exists

Measured from this repo on 13 Nov 2026 (details in `docs/DIAGNOSIS-2026-11-13.md`):

- From 28 Sep to 13 Nov the runners wrote 257 records; 180 were ready to act on.
- 2 emails were sent, both on 28 Sep. 2 of the SEEK packs can be matched to a later SEEK
  receipt. Nothing else shows as submitted.
- From 17 Oct the tracker refused every new record.
- 94 newer adverts were thrown away as "duplicates" of packs nobody had submitted.
- At least 148 applications are on record overall, with 27 rejections and no interview, so
  more of the same is not enough either: see the lanes in `config.json` and section 8.

The only number that counts is **applications submitted, with a receipt**.

## 2. Who does what

| Step | Who |
|---|---|
| Find and screen adverts, put applications in the queue | any runner (`RUNBOOK.md` steps 4 to 6) |
| Submit on SEEK | **Grok** (section 5) |
| Employer websites and web forms (`EMPLOYER_PORTAL`, `EMPLOYER_FORM`) | **Grok** (section 7) |
| Send email applications (`EMAIL`) | the **Claude** runner with the Gmail connector (section 6) |
| Read receipts, rejections and replies; record the owner's answers | the same Claude runner (sections 9 and 10) |
| Answer a question only he can answer | the owner |

Jeremie is no longer involved (owner, 13 Nov 2026). Records made before that date carry
`READY_JEREMIE_*` statuses; read them as history. A runner that cannot do a step leaves the
entry for the runner that can; that is never a reason to stop the tick.

## 3. The apply queue

- `automation/queue/open/<id>.json`: applications waiting (`OPEN`, `ASK_OWNER`, `UNCERTAIN`).
- `automation/queue/done/<YYYY-MM>/<id>.json`: finished (`APPLIED`, `SKIPPED`, `EXPIRED`, `FAILED`).
- `automation/queue/APPLY_QUEUE.md`: the same list for people (`queue.py render`).
- `automation/scripts/queue.py` is the only tool that writes these files. Never edit them by
  hand. Run every command from `automation/scripts`.

`UNCERTAIN` means nobody knows whether it went: it is never handed out again and counts as an
application until someone checks.

**Run id.** Every session starts with `python3 journal.py start`, which prints a run id such as
`20261114T020230Z`. Type it in full wherever a command says `RUN_ID`; a shell variable does not
survive from one command to the next. **Never type the run id of an earlier session**, even if
`queue.py show` displays it.

**Typed text.** Write anything copied from a form or an advert (questions, options, pay) into a
JSON file with a quoted heredoc, so the shell keeps every `$` and apostrophe:

```
cat > /tmp/q.json <<'EOF'
{"question": "What's your expected annual base salary?", "options": ["$60k-$70k", "$70k-$80k", "$80k+"], "advert_pay": "$80,000 per year"}
EOF
python3 queue.py answer ID --from-file /tmp/q.json --by NAME --run RUN_ID
```

Other free text (notes, reasons) goes in single quotes and must not contain a double quotation
mark, an apostrophe or a `$`.

**Committing.**

1. After `next --by`, run the git line it prints **before** submitting anything.
2. After every `mark`, `outcome`, `verify`, `answer` on an entry, `lock`, `expire` or `add`:
   ```
   git add -A -- ../queue ../journal.jsonl && git commit -m 'queue: <id> <what happened>' && git pull --rebase --autostash && git push
   ```
   `git add -A` matters: a `mark` moves a file from `open/` to `done/`, and the deletion must be
   committed too.
3. **If any git step fails** (a rejected push, a rebase conflict), someone else changed the
   queue at the same time. Do not submit. Run `git rebase --abort` (if a rebase stopped), then
   `git fetch origin && git reset --hard origin/claude/job-search-automation-sg3inr`, then
   start the session again from `journal.py start`. The reset drops only your own unpushed
   commits, which never took effect.

**The commands** (from `automation/scripts`):

```
python3 queue.py stats                       # what is waiting
python3 queue.py list [--route R] [--status S]
python3 queue.py list --started              # starts nobody has marked yet
python3 queue.py show ID
python3 queue.py check                       # must say "0 problems" before anything is handed out
python3 queue.py next --route R              # a look only; claims nothing
python3 queue.py next --route R --by NAME --run RUN_ID   # the claim: one entry for you to submit
```

`next` hands out one entry at a time: advertised vacancies before speculative enquiries, then
lane (drafter, technician, engineer), then the soonest stated closing date, then the newest
advert. It works out every answer again from `facts.json` before handing out. On stderr it
prints, for the entry: each form question as `Q: <question> | give: <answer>`, a block
`COVER LETTER TO PASTE (exactly, between the lines):`, the resume file to use with its sha256,
`BEFORE SUBMITTING, CHECK:` lines and the entry's notes. Read all of it; a condition in the
notes is a check too.

Exit codes: `0` done; `1` refused, nothing changed (the reason is on stderr; if it names `queue.py
check`, stop and report); `2` typed wrong; `3` this route's daily cap, the 20-minute SEEK spacing
or the quiet hours (the message says which other routes may still be tried); `4` nothing to hand
out on this route; `5` a form question has no standing answer: do not submit.

**Finishing an entry.** Every entry `next --by` gives you ends with exactly one of:

```
python3 queue.py mark ID applied   --by NAME --kind KIND --ref 'plain words' --run RUN_ID
python3 queue.py mark ID applied   --by NAME --kind already_applied --ref 'SEEK shows he already applied' --at YYYY-MM-DD --run RUN_ID
python3 queue.py mark ID skipped   --by NAME --reason 'advert closed' --run RUN_ID
python3 queue.py mark ID linkout   --by NAME --run RUN_ID          # SEEK's apply button leads to the employer's site
python3 queue.py mark ID ask       --by NAME --question 'one plain line for the owner' --run RUN_ID
python3 queue.py mark ID failed    --by NAME --note 'what stopped it' --run RUN_ID   # only when it is CERTAIN nothing was submitted
python3 queue.py mark ID uncertain --by NAME --note 'what happened'                # when you do not know whether it went
```

`KIND` is `seek_confirmation_screen`, `seek_receipt_email`, `portal_confirmation` or
`gmail_message_id`. `--ref` is plain words, such as `'SEEK confirmation screen shown'`: never a
confirmation code, application, candidate or reference number (the queue is public, and the tool
refuses them). For `gmail_message_id`, `--ref` is the 16-character message id and `--thread`
the thread id. `already_applied` is for a job the site says he applied for before; `--at` is the
date the site shows.

A start can be released (`skipped`, `linkout`, `ask`, `failed`, `open`) only by the same runner
in the same session. Anyone else can record only `applied` (with a receipt) or `uncertain`.
`mark ID open --by NAME --note 'checked: not submitted (where you looked)'` returns an
`UNCERTAIN` entry to the queue, and only after checking (section 9).

## 4. Rules for anything submitted in the owner's name

1. **Facts only.** Every answer, sentence and ticked box comes from `facts.json`.
2. **Never answer a form question yourself.** For every question on screen, write it and every
   option into a JSON file (section 3) and run `queue.py answer ID --from-file FILE --by NAME
   --run RUN_ID`. Give exactly what it prints. Exit `5`: leave the form without submitting; the
   tool has recorded the question and released your start. If the message says the advert's
   pay is not recorded, add the advert's own pay text (or `not stated`) as `advert_pay` to the
   same file and run it again.
3. **Never inflate.** Years of experience are the lowest option the facts support. Work rights
   are the temporary graduate visa option, never citizen or permanent resident.
4. **One application per advert, one channel.** The same advert is always a duplicate; the same
   employer and role is blocked for ever once applied for, and for 90 days after an application
   in `prior_outreach.json`. `next` enforces this.
5. **Check the advert is still open and still the same role** immediately before submitting.
   Closed or changed: `mark skipped`. The site shows he already applied: `mark applied --kind
   already_applied` with the date it shows.
6. **Caps and hours** (`config.json -> limits`), enforced by `next`: 6 SEEK, 3 email and 3
   employer-site submissions a day; SEEK at least 20 minutes apart; at most 3 speculative
   enquiries a week; nothing between 21:00 and 07:00 Melbourne time. Do not claim an entry
   after 20:45: the quiet hours start before you finish.
7. **Count only receipts.** An application exists when a confirmation screen, a receipt email or
   a Gmail message id is recorded on the entry.
8. **Stop on anything unusual**: an identity or right-to-work verification step, a CAPTCHA, a
   warning about the account, a payment screen, a document the pack does not have. Do not work
   around it. If a form may have gone: `mark uncertain`. Otherwise `mark ask --question 'what
   appeared, in plain words'`, which puts it in front of the owner.
9. **Nothing private in the repo.** No password, one-time code, tracker code, licence number,
   date of birth, reference number, person's name, quoted email text or screenshot in any file,
   commit, log or message.
10. **Free only.** No paid service, plan or subscription without asking the owner first.

## 5. SEEK (Grok)

Owner's decision, 13 Nov 2026, made after reading SEEK's Terms of Use: Grok submits SEEK
applications from the machine where his SEEK account is signed in. If SEEK ever challenges,
limits or warns the account, stop every SEEK submission at once and tell the owner. Never try to
get round a check.

For each entry from `python3 queue.py next --route SEEK --by Grok --run RUN_ID`:

1. Run the claim git line it printed. If it fails, follow section 3 rule 3.
2. Do every `BEFORE SUBMITTING, CHECK:` line and every condition in the notes.
3. Open `url`. Confirm the advert is open, the title and employer match, and the apply button
   is SEEK's own. If it leads to the employer's site:
   `python3 queue.py mark ID linkout --by Grok --run RUN_ID`. If SEEK shows he already applied:
   `python3 queue.py mark ID applied --by Grok --kind already_applied --ref 'SEEK shows he already applied' --at YYYY-MM-DD --run RUN_ID`.
4. Resume: the file `next` named. If its sha256 differs from the one recorded in
   `automation/queue/SEEK_UPLOADS.md`, upload it again and record the new sha256 there.
5. Cover letter: choose "write a cover letter" and paste the text between the dashed lines of
   `COVER LETTER TO PASTE`, exactly.
6. Employer questions: section 4 rule 2, for every one.
7. Review page: check the name, the resume file name and every answer.
8. Submit, then `python3 queue.py mark ID applied --by Grok --kind seek_confirmation_screen --ref 'SEEK confirmation screen shown' --run RUN_ID`, commit and push.
9. If you cannot tell whether it went (a time-out, an error page, a lost session):
   `python3 queue.py mark ID uncertain --by Grok --note 'what happened'`. Never submit it again
   yourself.

Keep the SEEK profile in step with the resume: `automation/SEEK_PROFILE.md`.

## 6. Email (the Claude runner with Gmail)

Owner, 13 Nov 2026: email applications go out automatically, without per-email approval, at most
3 a day, only to an address the employer itself publishes for applications
(`email.evidence_url`). A runner that cannot search Gmail must not send.

1. `python3 queue.py lock take --by Claude --run RUN_ID`, then commit and push the lock. If it is
   refused or the push fails, someone else is sending: stop.
2. `python3 queue.py next --route EMAIL --by Claude --run RUN_ID`, then run its claim git line.
3. Search Gmail (`in:anywhere`) for the employer's name and email domain. Any earlier
   application, reply, bounce or rejection for this role: `mark skipped` with the reason.
4. `python3 letter_pdf.py ID /tmp/ID-letter.pdf` builds the letter (the same text as the paste
   block). The resume is the file `next` named.
5. Send with the Gmail tool: to `email.to`, subject `email.subject`, body `email.body`, both PDFs
   attached. Then `python3 queue.py mark ID applied --by Claude --kind gmail_message_id --ref <message id> --thread <thread id> --run RUN_ID`.
6. An error after the send call, or no message id: `python3 queue.py mark ID uncertain --by Claude --note 'the error'`.
   Nothing is retried until Gmail Sent has been checked (section 9).
7. `python3 queue.py lock release --by Claude --run RUN_ID`, commit and push.

No follow-up emails for now: there is no command that counts them against the cap.

## 7. Employer websites and forms (Grok)

Routes `EMPLOYER_PORTAL` and `EMPLOYER_FORM`, at most 3 a day:
`python3 queue.py next --route EMPLOYER_PORTAL --by Grok --run RUN_ID` (then `EMPLOYER_FORM`).
Same steps as section 5. Where the site asks for a cover letter file, upload
`python3 letter_pdf.py ID /tmp/ID-letter.pdf`; where it has a text box, paste the block. An
account is created only with the owner's own email address. Finish with
`python3 queue.py mark ID applied --by Grok --kind portal_confirmation --ref 'employer confirmation page shown' --run RUN_ID`,
or one of the other marks in section 3.

## 8. What goes in an application

- Resume: the variant for the lane. The headline is never "Graduate Civil Engineer".
- Email at most 130 words; letter at most 200 words: a greeting line, three short paragraphs,
  the sign-off. Paragraph 1: the role and one true, specific line from the advert. Paragraph 2:
  what he has done, matched to the advert's top two tasks. Paragraph 3: where he is, work rights
  in the short form, start in two weeks, one ask.
- Never say what he lacks; never mention residency, migration or visa plans. If the advert makes
  something he lacks mandatory, it is rejected at screening instead.
- Work rights: "Full working rights in Australia (Subclass 485 visa), no sponsorship needed".
  The end date appears only in the resume's eligibility section and in form answers about work
  rights.
- Outside daily travel distance of Melton VIC: "I will relocate to <city or region> for this
  role and can start two weeks after an offer."

`queue.py`, `letter_pdf.py` and `checks.py` enforce these with the same checks.

## 9. Receipts, replies, uncertain entries and the report (Claude runner with Gmail)

Every session, from the last check to now (the first time: from 21 Oct 2026):

- SEEK receipts ("successfully submitted") and portal acknowledgements: for a queue entry,
  `python3 queue.py mark ID applied --by Claude --kind seek_receipt_email --ref 'SEEK receipt email' --at <the email's date and time> --run RUN_ID`
  (also accepted on `UNCERTAIN`, `SKIPPED`, `FAILED` or `EXPIRED` entries: it went after all).
  A SEEK receipt that matches no entry (he applied himself): add `date`, `company`, `role` and the
  Gmail message id to `automation/prior_outreach.json`.
- Replies: `python3 queue.py outcome ID --kind acknowledged|rejected|reply|interview|offer --at YYYY-MM-DD --by Claude --note 'your own words, no names'`.
- `UNCERTAIN` and unmarked `EMAIL` starts from earlier sessions (`queue.py list --started`): look
  in Gmail Sent. Found: `mark applied` with the message id. Not found: `mark ID uncertain` (for a
  start), then `mark ID open --by Claude --note 'checked: not in Gmail Sent'`. For SEEK and
  employer-site entries, Grok checks SEEK's applied jobs list or the site's confirmation email the
  same way.

An interview request, a call request or any question from an employer goes to the owner
**immediately**.

Each runner reports its own routes to the owner once a day, from its first session after 17:00
Melbourne time. A report, not a to-do list:

```
Applied today (with receipt): 4  (SEEK 3, employer site 1)
  - <company>, <role>, <location>
Replies: 1 rejection (<company>). No interview requests.
Waiting in the queue: 7. Unknown whether it went: 0.
Questions for you (at most three, soonest closing first): <one line each>
```

A week with zero submitted applications is a failure of the pipeline: say so and name the
blocker.

## 10. The owner's answers

When the owner answers a question:

- **A form question** (the entry is `ASK_OWNER` with "No standing answer for ..."): add a row to
  `facts.json -> answers -> owner_answers`:
  `{"question": "<the exact form question>", "options": [<the options, if any>], "answer": "<his answer>", "date": "YYYY-MM-DD"}`,
  with `"entry": "<queue id>"` when the question is about that one job or its pay. A question
  asking for a private detail (date of birth, licence number, tax file number and the like) is
  never stored: he types it on the form himself. Then `python3 queue.py answer ID` reopens the
  entry; `python3 queue.py check` must still say 0 problems.
- **A decision** ("apply anyway?"): `python3 queue.py mark ID open --by Claude --note 'owner: <his answer and the date>'`,
  or `mark ID skipped --reason 'owner: drop it'`.
- **A new standing fact** (for example his English rating): the orchestrator adds it to
  `facts.json`, runs `python3 resume.py build` and commits both.

## 11. Weekly review

Once a week: `queue.py report --days 7` and `journal.py weekly`, and one change to targeting or
wording based on them, written in `docs/COACHING-DECISIONS.md`.
