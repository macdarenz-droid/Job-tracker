# APPLY: how applications get submitted

Written 13 Nov 2026 on the owner's instruction: "every agent just sends me their leads and
nothing has been applied ... plan and do where you can directly apply ... then share that
method to the repo." This file is the method. `RUNBOOK.md` is the daily procedure that uses
it. Root `AGENTS.md` still applies.

## 1. Why this exists

Measured from this repo on 13 Nov 2026 (each number re-derived by a second agent):

- From 28 Sep to 13 Nov the runners wrote 257 records. 180 of them were ready to act on
  (121 packs for SEEK or an employer site, 59 prepared emails).
- 2 emails were sent, both on 28 Sep. 2 of the SEEK packs can be matched to a later SEEK
  receipt. Nothing else shows as submitted.
- From 17 Oct the tracker refused every new record (it is full). 63 finds since then were
  saved only on one runner's machine.
- 94 newer adverts were thrown away as "duplicates" of packs that nobody had submitted.
- Over the whole record there are at least 148 applications by the owner, 27 rejections
  and no interview. So submitting more of the same is not enough either: see the lanes in
  `config.json` and the writing rules in section 8.

The loop counted records. From now on the only number that counts is **applications
submitted, with a receipt**.

## 2. Who does what

| Step | Who | Notes |
|---|---|---|
| Find and screen adverts | any runner | daily, `RUNBOOK.md` |
| Prepare the pack and put it in the queue | the runner that screened it | section 3 |
| Submit on SEEK | **Grok**, on its own machine | owner's decision, 13 Nov 2026; section 5 |
| Send email applications | the runner that has the Gmail connector | automatic, at most 3 a day; section 6 |
| Employer portals and web forms | Grok when it can finish them; otherwise `ASK_OWNER` | section 7 |
| Read receipts, rejections and replies | the runner that has Gmail | every day; section 9 |
| Answer a question only he can answer | the owner | at most three open at a time |

Jeremie is no longer involved (owner, 13 Nov 2026). Records made before that date carry
`READY_JEREMIE_*` statuses; read them as `READY_*`.

A runner that cannot do a step does not hold the work: it leaves the entry `OPEN` in the
queue for the runner that can.

## 3. The apply queue

The queue lives in this repo so every runner and the owner see the same thing, and so it
cannot "fill up" the way the tracker did.

- `automation/queue/open/<id>.json`: one file per application waiting to be submitted.
- `automation/queue/done/<YYYY-MM>/<id>.json`: applied, skipped or expired entries.
- `automation/queue/APPLY_QUEUE.md`: the same list for people, rebuilt by `queue.py render`.
- `automation/scripts/queue.py`: the only tool that writes these files.

An entry holds everything needed to submit without thinking: `lane`, `route`
(`SEEK`, `EMAIL`, `EMPLOYER_PORTAL`, `EMPLOYER_FORM`), `company`, `role`, `location`,
`url`, `closes_at`, `resume_variant`, `relocation_line`, `cover_letter_text`, `email`
(to, subject, body, where the address was published), `questions` (each form question
with the answer to give and the line of `facts.json` it comes from), `status`, `attempts`
and `receipt`.

```
cd automation/scripts
python3 queue.py list                       # what is waiting, by route
python3 queue.py next --route SEEK --by Grok    # the one entry to submit now (or why not)
python3 queue.py mark <id> applied --by Grok --kind seek_confirmation_screen --ref "<text or id>"
python3 queue.py mark <id> skipped --by Grok --reason "advert closed"
python3 queue.py mark <id> failed  --by Grok --note "new question: <exact text and options>"
python3 queue.py expire                     # closes entries whose advert has shut
python3 queue.py render                     # rebuilds APPLY_QUEUE.md
python3 queue.py stats --json               # numbers for the journal and the daily report
```

`next` gives one entry at a time, in this order: lane (drafter, technician, engineer),
then the soonest real closing date, then the newest advert. It refuses when the day's cap
for that route is reached, when the last SEEK submission was less than 20 minutes ago, and
it never hands out an entry with an unanswered mandatory question.

After every `mark`, commit and push at once (`git pull --rebase` first), so no other
runner submits the same entry.

## 4. Rules for anything submitted in the owner's name

1. **Facts only.** Every answer, sentence and ticked box comes from `facts.json`. The
   `answers` block there holds the owner's standing answers (work rights, notice, salary
   band, licence, police check, years in each kind of role, software).
2. **Never guess.** A mandatory question with no answer in the entry or in
   `facts.json -> answers`: do not submit. `mark <id> failed` with the exact question and
   its options. The owner answers it once and it goes into `facts.json`.
3. **Never inflate.** Years of experience are the lowest option the facts support. Work
   rights are the temporary graduate visa option, never citizen or permanent resident.
4. **One application per advert, one channel.** Never apply again through another route.
   The same employer and the same role is blocked for 90 days after a real submission or a
   rejection. A different role at that employer is allowed.
5. **Check the advert is still open and still the same role** immediately before
   submitting. Closed or changed: `mark skipped`.
6. **Daily caps** (`config.json -> limits`): 6 SEEK, 3 email, 3 portal. No submissions
   between 21:00 and 07:00 Melbourne time.
7. **Count only receipts.** An application exists when there is a confirmation screen, a
   receipt email or a Gmail message id recorded in the entry.
8. **Stop on anything unusual**: an identity or right-to-work verification step, a
   CAPTCHA, a warning about the account, a payment screen, a request for a document that
   is not in the pack. Do not work around it. Record it and tell the owner.
9. **Nothing private in the repo.** No password, one-time code, tracker code, licence
   number, date of birth or referee detail in any file, commit, log or message.
10. **Free only.** No paid service, plan or subscription without asking the owner first.

## 5. SEEK (Grok)

Owner's decision, 13 Nov 2026: Grok submits SEEK applications from the machine where the
owner's SEEK account is signed in.

Recorded so nobody is surprised later. SEEK's Terms of Use (the page headed "Last updated on
20 July 2026", read on 13 Nov 2026) say its websites and apps "are designed for individual
human use", tell users not to "share with a third party any login credentials" and not to
"apply for any job on behalf of another party", and say SEEK may suspend a candidate account
it reasonably believes is used in a way that violates the terms. The terms do not mention AI
agents filling in an application; two reviewers read this route as a likely breach, at SEEK's
discretion. The owner was told this on 13 Nov 2026 and chose this route for his own account.
If SEEK ever challenges, limits or warns the account, stop every SEEK submission at once and
tell the owner. Never try to get round a check: the terms say circumventing their measures
against automated access "is prohibited and may result in suspension or termination".

For each entry from `queue.py next --route SEEK --by Grok`:

1. Open `url`. Confirm the advert is open, the title and employer match the entry, and the
   apply button is SEEK's own (Quick apply). If the button leads to the employer's site,
   the route is wrong: `mark failed --note "link-out"`; the entry is re-routed to
   `EMPLOYER_PORTAL`.
2. Resume: choose the stored resume named for `resume_variant`
   (`documents/resume/Marc_Masarate_Resume_<Variant>.pdf`; upload it once if SEEK does not
   have it yet).
3. Cover letter: choose "write a cover letter" and paste `cover_letter_text` exactly,
   followed by `relocation_line` when it is not empty. If `cover_letter_text` is empty,
   choose no cover letter.
4. Employer questions: give each answer exactly as written in `questions`. If SEEK shows a
   question that is not in the entry, or the options do not include the written answer,
   stop: `mark failed` with the exact question and options. Do not pick the nearest one.
5. Review page: check the name, the resume file name and every answer against the entry.
6. Submit. Copy the confirmation text (or the application reference) into
   `mark <id> applied --kind seek_confirmation_screen --ref "..."`.
7. Commit and push. Wait at least 20 minutes before the next SEEK submission.

Keep the SEEK profile itself in step with the resume: `automation/SEEK_PROFILE.md` has the
text for each profile section.

## 6. Email (the runner with Gmail)

Owner, 13 Nov 2026: email applications go out automatically, without per-email approval,
at most 3 a day. Only to an address the employer itself publishes for applications
(`email.evidence_url` in the entry).

1. Take the lock: write `automation/queue/SEND_LOCK.json` with your name, the entry id and
   the time, commit and push. If the push is rejected or a lock younger than 30 minutes
   from another runner exists, stop. (This replaces the "shared canonical journal lease",
   which no runner could reach and which blocked every send for six weeks.)
2. Search Gmail (`in:anywhere`) for the employer's name and domain. Any earlier
   application, reply, bounce or rejection inside 90 days for the same role: `mark skipped`.
3. Run `checks.py` on the email and the letter. Attach the resume PDF for the entry's lane
   and the cover letter PDF. Both must be small files; verify the bytes before sending.
4. Send with the Gmail tool: `to`, `subject`, plain `body`, `htmlBody` from
   `email_html.py`, the two attachments. Record the returned message id:
   `mark <id> applied --kind gmail_message_id --ref <id>`.
5. No message id, or an error after the call: `mark failed --note "send uncertain"`; do
   not retry until Gmail Sent has been checked.
6. Remove the lock, commit and push.

One follow-up after 8 days without a reply (three sentences, same thread) counts toward the
day's cap.

## 7. Employer portals and forms

Queue route `EMPLOYER_PORTAL` or `EMPLOYER_FORM`. The same rules apply: answers from the
entry only, stop on anything unusual, receipt recorded. An account is created only with
the owner's own email address. If a portal cannot be finished (identity check, a
question outside `facts.json`, an upload the pack does not have): `mark failed` with the
reason; after three failures the entry becomes `ASK_OWNER`.

## 8. What goes in an application

- Resume: the variant for the lane. The headline is never "Graduate Civil Engineer".
- Email at most 130 words, letter at most 200 words, three short paragraphs: the role and
  one true, specific line from the advert; what he has done, matched to the advert's top
  two tasks; where he is, work rights in the short form, start in two weeks, one ask.
- Never say what he lacks. If the advert makes it mandatory, the advert is rejected at
  screening instead.
- Work rights are written "Full working rights in Australia (Subclass 485 visa), no
  sponsorship needed". The end date appears only in the resume's eligibility section and
  where a form or advert asks.
- Outside daily travel distance of Melton VIC: "I will relocate to <city or region> for
  this role and can start two weeks after an offer."

`checks.py` enforces these mechanically. One reviewer agent reads everything that will be
sent or submitted that day and tries to refute each sentence against `facts.json`.

## 9. Receipts, replies and the daily report

Every day the runner with Gmail searches for SEEK receipts ("successfully submitted"),
SEEK "unlikely to progress" notices, employer replies, bounces and portal
acknowledgements since the last check, matches them to queue entries and records them.
An interview request, a phone-call request or any question from an employer is sent to
the owner **immediately**, not in the daily report.

The owner gets one short report a day, and it is a report, not a to-do list:

```
Applied today (with receipt): 4  (SEEK 3, email 1)
  - <company>, <role>, <location>
Replies: 1 rejection (<company>). No interview requests.
Waiting in the queue: 7. Closed unsubmitted: 0.
Needs you: 1 question: <the one line>
```

A week with zero submitted applications is a failure of the pipeline: say so in the
report and name the blocker.

## 10. Weekly review

Once a week: applications, acknowledgements, rejections, replies and interviews by lane
and by state (`journal.py weekly`), and one change to targeting or wording based on them.
Write the change in `docs/COACHING-DECISIONS.md`.
