# Grok: brief for the SEEK and employer-site submitter

Owner's decision, 13 Nov 2026: you submit the SEEK applications, and the employer-website
applications. The method is `automation/APPLY.md` (read sections 3, 4, 5 and 7 in full every
day); this page is the short version. The daily procedure is `automation/RUNBOOK.md`.

Run every command from `automation/scripts`. Type every id in full: a shell variable does not
survive from one command to the next.

## Every session

1. `git pull --rebase --autostash`
2. `python3 journal.py start` and write down the run id it prints (for example
   `20261114T020230Z`). Below it is `RUN_ID`.
3. `python3 queue.py expire`, then `python3 queue.py check`. If check reports any problem,
   stop and report it: nothing will be handed out until it is fixed.
4. `python3 queue.py stats`

## Each application

1. `python3 queue.py next --route SEEK --by Grok --run RUN_ID`
   - Exit 3: the day's cap, the 20-minute spacing or the quiet hours. Stop for now.
   - Exit 4: nothing ready on this route. Try `--route EMPLOYER_PORTAL`, then
     `--route EMPLOYER_FORM`, then stop.
   - Exit 1: read the reason; if it names `queue.py check`, stop and report.
2. Run the git line it prints under "Commit and push this claim" **before** anything else. If
   it fails, do not submit: `git rebase --abort` if a rebase stopped, then stop and report.
3. Read everything it printed: the `Q: ... | give: ...` lines, the resume file, every
   `BEFORE SUBMITTING, CHECK:` line and every note. Do every check.
4. Submit exactly as APPLY.md section 5 (SEEK) or section 7 (employer site) says:
   - the resume file it named;
   - `cover_letter_text` pasted exactly as it is (it already has the relocation sentence where
     one is needed);
   - for every question on screen: `python3 queue.py answer ID --question "<exact text>"
     --option "<each option on screen>" --by Grok --run RUN_ID`, and give exactly what it
     prints. Exit 5: leave the form without submitting and go to the next entry.
5. Finish with exactly one mark, then commit and push
   (`git add -A -- ../queue && git commit -m "queue: <id> <result>" && git pull --rebase --autostash && git push`):
   - submitted: `python3 queue.py mark ID applied --by Grok --kind seek_confirmation_screen --ref "SEEK confirmation screen shown" --run RUN_ID`
     (employer site: `--kind portal_confirmation --ref "employer confirmation page shown"`);
   - the apply button leads to the employer's site: `python3 queue.py mark ID linkout --by Grok --run RUN_ID`;
   - the advert has closed or changed role, or SEEK shows he already applied:
     `python3 queue.py mark ID skipped --by Grok --reason "advert closed" --run RUN_ID`;
   - not submitted, and you are certain of that: `python3 queue.py mark ID failed --by Grok --note "<what stopped it>" --run RUN_ID`;
   - you do not know whether it went: `python3 queue.py mark ID uncertain --by Grok --note "<what happened>"`.
6. Wait at least 20 minutes before the next SEEK submission (`next` enforces it).

If you lose track (a crash, lost output): `python3 queue.py list --started`. An entry started
in an earlier session can only be marked `applied` (if SEEK's applied list shows it, with the
receipt) or `uncertain`.

## Never

- Never answer a form question yourself or pick the nearest option.
- Never choose a higher option than the facts support (years of experience, licence,
  citizenship or residency).
- Never submit twice, never use a second route for the same job, never resubmit an
  `uncertain` entry.
- Never continue past a verification step, CAPTCHA or account warning. Stop all SEEK
  submissions and tell the owner what appeared.
- Never write a password, code, reference number, person's name, quoted email text or account
  detail into the repo, a commit or a message.
- Never save finds to a local folder. A find that is not in the repo queue does not exist for
  anyone else.

## Finding new adverts

Only when the queue is short (RUNBOOK step 4), and only through RUNBOOK steps 4 to 6: screen,
write the entry, `queue.py add`.

## Tell the owner

One short report a day, in the form in APPLY.md section 9, from the first session after 17:00
Melbourne time. An interview or call request, or a SEEK warning, is reported at once.

## Once, before the first submission

- Upload the three resumes from `documents/resume/` to SEEK and name them so the variant is
  obvious. Record each file's sha256 (shown by `next`) in `automation/queue/SEEK_UPLOADS.md`,
  and upload again whenever `next` shows a different sha256.
- Bring the SEEK profile into line with `automation/SEEK_PROFILE.md`.
