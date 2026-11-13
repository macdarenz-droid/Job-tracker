# Grok: SEEK submitter brief

Owner's decision, 13 Nov 2026: you submit the SEEK applications. The method is
`automation/APPLY.md` (read sections 3, 4 and 5 in full every day); this page is the short
version. The daily procedure is `automation/RUNBOOK.md`.

## Every day

1. `git pull --rebase`, then `cd automation/scripts && python3 queue.py expire && python3 queue.py stats`.
2. `python3 queue.py next --route SEEK --by Grok`. It prints one entry, or the reason there
   is none (exit code 3: cap reached or too soon after the last one; exit code 4: nothing
   ready). Once it has given you an entry, that entry is yours until you mark it: always
   finish with `mark ... applied`, `skipped`, `failed`, `uncertain` or `ask`.
3. Submit that one entry on SEEK exactly as APPLY.md section 5 says: the resume named in
   `resume_variant`, the cover letter text pasted unchanged, each question answered exactly
   as the entry says.
4. `python3 queue.py mark <id> applied --by Grok --kind seek_confirmation_screen --ref "<confirmation text or reference>"`,
   then commit and push straight away.
5. Wait at least 20 minutes. Repeat from step 2. At most 6 a day, none between 21:00 and
   07:00 Melbourne time.
6. When you also run discovery: follow RUNBOOK steps 4 to 6 and put new applications in the
   queue with `queue.py add`. Do not save finds to a local folder; a find that is not in the
   repo queue does not exist for anyone else.

## Never

- Never answer a question that is not in the entry. Run
  `python3 queue.py answer <id> --question "<exact text>" --option "<each option>"`; use the
  answer it prints, and if it prints none, leave the form without submitting and move on.
- If you cannot tell whether an application went through, `mark <id> uncertain` with what
  happened. Never try it again yourself.
- Never choose a higher option than the facts support (years of experience, licence class,
  citizenship or residency).
- Never submit an advert that has closed, changed role, or leads to an employer site
  (mark it failed with "link-out").
- Never apply twice to the same advert, and never use a second channel for it.
- Never continue past a verification step, CAPTCHA or account warning. Stop all SEEK
  submissions and tell the owner what SEEK showed.
- Never write a password, code or any account detail into the repo, a commit or a log.

## Tell the owner

One short report a day in the form in APPLY.md section 9: what was applied for (with
receipts), any replies, what is waiting, and at most three questions. An interview or call
request is reported the moment it is seen.

## Once, before the first submission

- Upload the three resume files from `documents/resume/` to SEEK and name them so the
  variant is obvious.
- Bring the SEEK profile into line with `automation/SEEK_PROFILE.md`.
- Check the profile's right-to-work details match `facts.json -> eligibility`.
