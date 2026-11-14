# Grok: brief for the SEEK and employer-site submitter

Owner's decision, 13 Nov 2026: you submit the SEEK applications and the employer-website
applications. The method is `automation/APPLY.md` (read sections 3, 4, 5 and 7 in full every
day); this page is the short version. The daily procedure is `automation/RUNBOOK.md`.

Run every command from `automation/scripts`. Type every id in full: a shell variable does not
survive from one command to the next. **Never type the run id of an earlier session.**

## Start of every session

1. `git pull --rebase --autostash` (if it fails: APPLY.md section 3, rule 3).
2. `python3 journal.py start` and write down the run id it prints. Below it is `RUN_ID`.
3. `python3 queue.py expire`, then `python3 queue.py check`. If check reports any problem, stop
   and report it. Commit and push what expire changed.
4. `python3 queue.py list --started`: any entry started by Grok in an earlier session is settled
   first (step 7 below).

## Each application

1. `python3 queue.py next --route SEEK --by Grok --run RUN_ID`
   - Exit 3: this route's cap, the 20-minute spacing or the quiet hours. Try the next route.
   - Exit 4: nothing ready on this route. Try the next route.
   - Order of routes: `SEEK`, then `EMPLOYER_PORTAL`, then `EMPLOYER_FORM`. When all three give
     3 or 4, stop submitting.
   - Exit 1: read the reason; if it names `queue.py check`, stop and report.
2. Run the git line it printed under "Commit and push this claim" **before** anything else. If it
   fails, do not submit: APPLY.md section 3, rule 3.
3. Read everything it printed: the `Q: ... | give: ...` lines, the `COVER LETTER TO PASTE` block,
   the resume file, every `BEFORE SUBMITTING, CHECK:` line and every note. Do every check.
4. Submit as APPLY.md section 5 (SEEK) or section 7 (employer site) says:
   - the resume file it named;
   - the cover letter: paste the text between the dashed lines exactly; where a site wants a
     file, upload `python3 letter_pdf.py ID /tmp/ID-letter.pdf`;
   - every question on screen: write it with every option into a file and run `queue.py answer`:
     ```
     cat > /tmp/q.json <<'EOF'
     {"question": "<exact text on screen>", "options": ["<option 1>", "<option 2>"]}
     EOF
     python3 queue.py answer ID --from-file /tmp/q.json --by Grok --run RUN_ID
     ```
     Give exactly what it prints. Exit 5: leave the form without submitting and go back to
     step 1. If it says the advert's pay is not recorded, add `"advert_pay": "<the advert's own
     pay text, or not stated>"` to the file and run it again.
5. Finish with exactly one mark, then commit and push
   (`git add -A -- ../queue ../journal.jsonl && git commit -m 'queue: ID result' && git pull --rebase --autostash && git push`):
   - submitted on SEEK: `python3 queue.py mark ID applied --by Grok --kind seek_confirmation_screen --ref 'SEEK confirmation screen shown' --run RUN_ID`
   - submitted on an employer site: `python3 queue.py mark ID applied --by Grok --kind portal_confirmation --ref 'employer confirmation page shown' --run RUN_ID`
   - SEEK's apply button leads to the employer's site: `python3 queue.py mark ID linkout --by Grok --run RUN_ID`
   - the site shows he already applied: `python3 queue.py mark ID applied --by Grok --kind already_applied --ref 'SEEK shows he already applied' --at YYYY-MM-DD --run RUN_ID`
   - the advert has closed or changed role: `python3 queue.py mark ID skipped --by Grok --reason 'advert closed' --run RUN_ID`
   - something unusual appeared (verification, CAPTCHA, warning, a document the pack lacks):
     `python3 queue.py mark ID ask --by Grok --question 'what appeared, in plain words' --run RUN_ID`
   - you do not know whether it went: `python3 queue.py mark ID uncertain --by Grok --note 'what happened'`
6. Back to step 1. `next` keeps SEEK submissions 20 minutes apart; do not claim anything after
   20:45 Melbourne time.
7. Settling an earlier session's start or an `UNCERTAIN` entry: look at SEEK's applied jobs list
   (or the employer's confirmation email, if you can see it). It went:
   `python3 queue.py mark ID applied --by Grok --kind already_applied --ref 'SEEK applied jobs list shows it' --at YYYY-MM-DD --run RUN_ID`.
   It did not go, or you cannot tell: `python3 queue.py mark ID uncertain --by Grok --note 'what you saw'`
   and name it in the report. Never submit it again yourself.

## End of every session

```
python3 queue.py render
python3 journal.py note RUN_ID stage=end queue_open=<n> applied=<n> seek_submitted=<n> emails_sent=null portal_submitted=<n> expired_unsubmitted=<n> replies=null interviews=null new_adverts_screened=<n> queued=<n> rejected=<n> ask_owner=<n> nothing_new=<true|false>
git add -A -- ../queue ../journal.jsonl ../runs/RUN_ID && git commit -m 'Grok session RUN_ID' && git pull --rebase --autostash && git push
```

## Never

- Never answer a form question yourself or pick the nearest option.
- Never choose a higher option than the facts support (years of experience, licence,
  citizenship or residency).
- Never submit twice, never use a second route for the same job, never resubmit an `uncertain`
  entry.
- Never continue past a verification step, CAPTCHA or account warning. Stop all SEEK
  submissions and tell the owner what appeared.
- Never write a password, code, reference number, person's name, quoted email text or account
  detail into the repo, a commit or a message.
- Never save finds to a local folder. A find that is not in the repo queue does not exist for
  anyone else.

## Finding new adverts

Only when fewer than 12 entries are waiting (RUNBOOK step 4), and only through RUNBOOK steps 4
to 6: screen, write the entry, `queue.py add`.

## Tell the owner

Once a day, from the first session after 17:00 Melbourne time, report your own routes in the
form in APPLY.md section 9. An interview or call request, or a SEEK warning, is reported at once.

## Once, before the first submission

- Upload the three resumes from `documents/resume/` to SEEK, named so the variant is obvious.
  Record each file's sha256 (shown by `next`) in `automation/queue/SEEK_UPLOADS.md`, and upload
  again whenever `next` shows a different sha256.
- Bring the SEEK profile into line with `automation/SEEK_PROFILE.md`.
