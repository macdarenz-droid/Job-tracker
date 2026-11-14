# APPLY: how applications get submitted

Written 13 Nov 2026 and corrected 14 Nov 2026 after an independent review, on the owner's
instruction: "every agent just sends me their leads and nothing has been applied ... plan and
do where you can directly apply ... then share that method to the repo." This file is the
method. `RUNBOOK.md` is the daily procedure that uses it, and `GROK.md` is the short brief for
the SEEK submitter. Root `AGENTS.md` still applies.

## 1. Why this exists

Measured from this repo on 13 Nov 2026 (each number re-derived by a second agent; details in
`docs/DIAGNOSIS-2026-11-13.md`):

- From 28 Sep to 13 Nov the runners wrote 257 records. 180 of them were ready to act on.
- 2 emails were sent, both on 28 Sep. 2 of the SEEK packs can be matched to a later SEEK
  receipt. Nothing else shows as submitted.
- From 17 Oct the tracker refused every new record. Finds after that were saved only on one
  runner's machine.
- 94 newer adverts were thrown away as "duplicates" of packs nobody had submitted.
- At least 148 applications are on record overall, with 27 rejections and no interview, so
  submitting more of the same is not enough either: see the lanes in `config.json` and the
  writing rules in section 8.

The only number that counts is **applications submitted, with a receipt**.

## 2. Who does what

| Step | Who | Notes |
|---|---|---|
| Find and screen adverts, put applications in the queue | any runner | `RUNBOOK.md` steps 4 to 6 |
| Submit on SEEK | **Grok** | owner's decision, 13 Nov 2026; section 5 |
| Employer websites and web forms (`EMPLOYER_PORTAL`, `EMPLOYER_FORM`) | **Grok** only | section 7 |
| Send email applications (`EMAIL`) | the **Claude** runner that has the Gmail connector | automatic, at most 3 a day; section 6 |
| Read receipts, rejections and replies from Gmail | the same Claude runner | every day; section 9 |
| Answer a question only he can answer | the owner | at most three a day in the report |

Jeremie is no longer involved (owner, 13 Nov 2026). Records made before that date carry
`READY_JEREMIE_*` statuses; read them as history.

A runner that cannot do a step leaves the entry for the runner that can. That is never a
reason to stop the tick.

## 3. The apply queue

The queue lives in this repo so every runner and the owner see the same thing, and so it cannot
fill up the way the tracker did.

- `automation/queue/open/<id>.json`: one file per application that is waiting
  (`OPEN`, `ASK_OWNER` or `UNCERTAIN`).
- `automation/queue/done/<YYYY-MM>/<id>.json`: finished entries (`APPLIED`, `SKIPPED`,
  `EXPIRED`, `FAILED`).
- `automation/queue/APPLY_QUEUE.md`: the same list for people, rebuilt by `queue.py render`.
- `automation/scripts/queue.py` is the only tool that writes these files. Never edit them by
  hand. Run it from `automation/scripts`.

Statuses: `OPEN` (ready, or held for a reason `next` names), `ASK_OWNER` (needs one answer),
`UNCERTAIN` (nobody knows whether it went: it is never handed out again and counts as an
application until someone checks), `APPLIED` (receipt recorded), `SKIPPED`, `EXPIRED`,
`FAILED`.

**Run id.** Every session starts with `python3 journal.py start`, which prints a run id such as
`20261114T020230Z`. Write it down and type it in full wherever a command below says
`RUN_ID`: a shell variable does not survive from one command to the next.

**Committing.** Two rules keep two runners from submitting the same thing:

1. After `next --by`, run the git line it prints **before** submitting anything. If any step of
   it fails (a rejected push, a rebase conflict), do not submit: run `git rebase --abort` if a
   rebase stopped, then stop and report it.
2. After every `mark`, `outcome`, `verify`, `answer` on an entry, or `lock`, commit and push
   at once:
   ```
   git add -A -- ../queue && git commit -m "queue: <id> <what happened>" && git pull --rebase --autostash && git push
   ```
   `git add -A` matters: `mark` moves a file from `open/` to `done/`, and the deletion must be
   committed too. A stale copy left in `open/` makes `queue.py check` fail, and `next` then
   hands out nothing until it is fixed.

The commands:

```
python3 queue.py stats                       # what is waiting
python3 queue.py list [--route R] [--status S]
python3 queue.py list --started              # starts nobody has marked yet
python3 queue.py show ID
python3 queue.py check                       # must print "0 problems" before anything is handed out
python3 queue.py next --route R              # a look only; claims nothing
python3 queue.py next --route R --by NAME --run RUN_ID   # the claim: one entry for you to submit
```

`next` hands out one entry at a time: advertised vacancies before speculative enquiries, then
lane (drafter, technician, engineer), then the soonest stated closing date, then the newest
advert. Before handing out, it works out every answer again from `facts.json` as it is now.
On stderr it prints, for the entry: each form question as `Q: <question> | give: <answer>`,
the resume file to use with its sha256, `BEFORE SUBMITTING, CHECK:` lines, and the entry's
notes. Read all of it. A condition in the notes is a check too.

Exit codes: `0` done; `1` refused, nothing changed (the reason is on stderr; if it names
`queue.py check`, stop and report); `2` the command was typed wrong; `3` the day's cap, the
20-minute SEEK spacing or the quiet hours (21:00 to 07:00 Melbourne time): stop for now; `4`
nothing to hand out (the reasons are listed); `5` a form question has no standing answer: do
not submit.

Finishing an entry. Every entry `next --by` gives you ends with exactly one of these:

```
python3 queue.py mark ID applied   --by NAME --kind KIND --ref "plain words" --run RUN_ID
python3 queue.py mark ID skipped   --by NAME --reason "advert closed" --run RUN_ID
python3 queue.py mark ID linkout   --by NAME --run RUN_ID          # SEEK's button leads to the employer's site
python3 queue.py mark ID failed    --by NAME --note "what stopped it" --run RUN_ID   # only when it is CERTAIN nothing was submitted
python3 queue.py mark ID uncertain --by NAME --note "what happened"                # when you do not know whether it went
python3 queue.py mark ID ask       --by NAME --question "one plain line for the owner" --run RUN_ID
```

`KIND` is `seek_confirmation_screen`, `seek_receipt_email`, `portal_confirmation` or
`gmail_message_id`. `--ref` is plain words, such as "SEEK confirmation screen shown"; it is
refused if it holds an email address, a web address, a phone number, a long number or an
application or reference number, because the queue is public. For `gmail_message_id`, `--ref`
is the 16-character message id and `--thread` the thread id.

A start can be released (`skipped`, `linkout`, `failed`, `ask`, `open`) only by the same
runner with the same run id. A new session of the same runner, or anyone else, can only record
`applied` (with a receipt) or `uncertain`. `mark ID open --by NAME --note "checked: not
submitted (<where you looked>)"` returns an `UNCERTAIN` entry to the queue, and only after
checking. An entry waiting on the owner is reopened only with `--note "owner: <his answer and
the date>"`.

## 4. Rules for anything submitted in the owner's name

1. **Facts only.** Every answer, sentence and ticked box comes from `facts.json`. The
   `answers` block holds his standing answers.
2. **Never answer a form question yourself.** For every question on screen, run
   `queue.py answer ID --question "<exact text>" --option "<each option on screen>" --by NAME
   --run RUN_ID` and give exactly what it prints. Exit `5` means there is no standing answer:
   leave the form without submitting. The command has already recorded the question, set the
   entry to `ASK_OWNER` and released your start.
3. **Never inflate.** Years of experience are the lowest option the facts support. Work rights
   are the temporary graduate visa option, never citizen or permanent resident.
4. **One application per advert, one channel.** The same advert is always a duplicate. The
   same employer and the same role is blocked for ever once applied for, and for 90 days after
   an application recorded in `prior_outreach.json`. A different role at that employer is
   allowed. `next` enforces this.
5. **Check the advert is still open and still the same role** immediately before submitting.
   Closed or changed: `mark skipped`. If the site shows that he has already applied, `mark
   skipped --reason "already applied on SEEK"` and say so in the report.
6. **Caps and hours** (`config.json -> limits`), enforced by `next`: 6 SEEK, 3 email and 3
   employer-site submissions a day; SEEK at least 20 minutes apart; at most 3 speculative
   enquiries a week; nothing between 21:00 and 07:00 Melbourne time.
7. **Count only receipts.** An application exists when a confirmation screen, a receipt email or
   a Gmail message id is recorded on the entry.
8. **Stop on anything unusual**: an identity or right-to-work verification step, a CAPTCHA, a
   warning about the account, a payment screen, a request for a document that is not in the
   pack. Do not work around it. `mark uncertain` if a form may have gone; otherwise `mark
   failed --note "<what appeared>"`. Tell the owner.
9. **Nothing private in the repo.** No password, one-time code, tracker code, licence number,
   date of birth, reference number, person's name, quoted email text or screenshot in any
   file, commit, log or message. The queue refuses the obvious cases; the rest is on you.
10. **Free only.** No paid service, plan or subscription without asking the owner first.

## 5. SEEK (Grok)

Owner's decision, 13 Nov 2026, made after reading SEEK's Terms of Use: Grok submits SEEK
applications from the machine where his SEEK account is signed in. If SEEK ever challenges,
limits or warns the account, stop every SEEK submission at once and tell the owner. Never try
to get round a check.

For each entry from `queue.py next --route SEEK --by Grok --run RUN_ID`:

1. Run the claim git line it printed. If it fails, stop.
2. Do every `BEFORE SUBMITTING, CHECK:` line and every condition in the notes.
3. Open `url`. Confirm the advert is open, the title and employer match the entry, and the
   apply button is SEEK's own. If it leads to the employer's site: `mark ID linkout`; the entry
   moves to the employer-site route.
4. Resume: the file `next` named (`documents/resume/Marc_Masarate_Resume_<Variant>.pdf`). If
   its sha256 differs from the copy last uploaded to SEEK (see `automation/queue/SEEK_UPLOADS.md`
   if it exists), upload it again and note the new sha256 there.
5. Cover letter: choose "write a cover letter" and paste `cover_letter_text` exactly as it is.
   It already contains the relocation sentence where one is needed; add nothing.
6. Employer questions: for each one, run `queue.py answer` with the exact text and every option
   on screen (section 4 rule 2) and give exactly what it prints. Exit `5`: leave without
   submitting and move on.
7. Review page: check the name, the resume file name and every answer.
8. Submit. Then `mark ID applied --kind seek_confirmation_screen --ref "SEEK confirmation screen
   shown"`, commit and push.
9. If you cannot tell whether it went (a time-out, an error page, a lost session): `mark ID
   uncertain --note "<what happened>"`. Never submit it again yourself.

Keep the SEEK profile itself in step with the resume: `automation/SEEK_PROFILE.md`.

## 6. Email (the Claude runner with Gmail)

Owner, 13 Nov 2026: email applications go out automatically, without per-email approval, at
most 3 a day, only to an address the employer itself publishes for applications
(`email.evidence_url`). A runner that cannot search Gmail must not send.

1. `python3 queue.py lock take --by Claude --run RUN_ID`, then run the git line it prints. If
   the lock is refused or the push fails, someone else is sending: stop.
2. `python3 queue.py next --route EMAIL --by Claude --run RUN_ID`, then run its claim git line.
3. Search Gmail (`in:anywhere`) for the employer's name and email domain. Any earlier
   application, reply, bounce or rejection for this role: `mark skipped` with the reason.
4. Build the letter: `python3 letter_pdf.py ID /tmp/<id>-letter.pdf`. It refuses a letter that
   breaks the writing rules. The resume is the file `next` named.
5. Send with the Gmail tool: to `email.to`, subject `email.subject`, body `email.body`, the
   letter PDF and the resume PDF attached. From the result record the message id and thread
   id: `mark ID applied --kind gmail_message_id --ref <message id> --thread <thread id>`.
6. An error after the send call, or no message id: `mark ID uncertain --note "<the error>"`.
   Nothing is retried until Gmail Sent has been checked.
7. `python3 queue.py lock release --by Claude --run RUN_ID`, commit and push.

No follow-up emails for now: there is no command that counts them against the cap.

## 7. Employer websites and forms (Grok)

Routes `EMPLOYER_PORTAL` and `EMPLOYER_FORM`, at most 3 a day. Same steps as section 5: claim
and push, checks, advert open, answers only through `queue.py answer`, review, submit, then
`mark applied --kind portal_confirmation --ref "<plain words>"`. An account is created only
with the owner's own email address. An identity check, a question with no standing answer, or
an upload the pack does not have: stop, as section 4 says.

## 8. What goes in an application

- Resume: the variant for the lane. The headline is never "Graduate Civil Engineer".
- Email at most 130 words, letter at most 200 words: a greeting line, three short paragraphs,
  the sign-off. Paragraph 1: the role and one true, specific line from the advert. Paragraph 2:
  what he has done, matched to the advert's top two tasks. Paragraph 3: where he is, work rights
  in the short form, start in two weeks, one ask.
- Never say what he lacks. If the advert makes it mandatory, the advert is rejected at
  screening instead.
- Work rights are written "Full working rights in Australia (Subclass 485 visa), no
  sponsorship needed". The end date appears only in the resume's eligibility section and in
  form answers about work rights.
- Outside daily travel distance of Melton VIC: "I will relocate to <city or region> for this
  role and can start two weeks after an offer."

`queue.py` and `checks.py` enforce these with the same checks (`checks.letter_issues` and
`checks.email_issues`).

## 9. Receipts, replies and the daily report

Every day the Claude runner with Gmail searches for SEEK receipts ("successfully submitted"),
SEEK "unlikely to progress" notices, employer replies, bounces and portal acknowledgements
since the last check, and records them:

- A receipt for a queue entry: `mark ID applied --kind seek_receipt_email --ref "SEEK receipt
  email <date>"` (also accepted on `UNCERTAIN`, `SKIPPED`, `FAILED` or `EXPIRED` entries: it
  went after all).
- A SEEK receipt that matches no queue entry (the owner applied himself): add `date`,
  `company`, `role` and the Gmail message id to `automation/prior_outreach.json`.
- A reply: `queue.py outcome ID --kind acknowledged|rejected|reply|interview|offer --at
  YYYY-MM-DD --by Claude [--note "<your own words, no names, no quotes>"]`.

An interview request, a phone-call request or any question from an employer goes to the owner
**immediately**, not in the daily report.

The owner gets one short report a day (from the first tick after 17:00 Melbourne time). It is a
report, not a to-do list:

```
Applied today (with receipt): 4  (SEEK 3, email 1)
  - <company>, <role>, <location>
Replies: 1 rejection (<company>). No interview requests.
Waiting in the queue: 7. Unknown whether it went: 0.
Questions for you (at most three, soonest closing first): <one line each>
```

A week with zero submitted applications is a failure of the pipeline: say so and name the
blocker.

## 10. Weekly review

Once a week: `queue.py report --days 7` (applications by lane, state and route, outcomes) and
`journal.py weekly`, and one change to targeting or wording based on them, written in
`docs/COACHING-DECISIONS.md`.
