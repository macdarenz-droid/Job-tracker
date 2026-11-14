# Codex runner handoff

> **13 November 2026:** `APPLY.md` and `RUNBOOK.md` were rewritten and take priority over anything below that conflicts with them. The loop's goal is now submitted applications with a receipt, not records. Roles, lanes, daily caps and the send lock are in `APPLY.md`. The sections below remain for the evidence standards they set.

Adopted by Marc on 28 September 2026. Use this branch's README, RUNBOOK, config, facts,
scripts, tests, employer cache and run history for the existing Codex discovery task.
Read current remote files each tick; never substitute an old local checkout.

## Identity and schedule

- Keep the existing discovery task; do not create another task or enable the separate reviewer.
- Owner instruction, 28 September 2026: Codex wakes every three hours, Australia/Melbourne. Since 13 November 2026 the shared cadence in `config.json -> schedule` is one discovery sweep a day and two submit passes; a runner that still wakes more often does steps 1 to 3 of the RUNBOOK (replies, receipts, submit) and skips discovery.
- Codex creates records as `contributor_name: Codex`, `created_by: codex-job-search`.
  Override these two `common.CONFIG` values explicitly in the running process; leave the
  repository's Claude defaults intact. Preserve the original author on existing records.
- The tracker is https://macdarenz-droid.github.io/Job-tracker/ with shared Cloudflare D1/R2.
  `data.json` and run snapshots are not live state. Never commit the access code or tokens.

## Shared sending safeguards

Root `AGENTS.md` applies. A D1 `expected_version` check prevents a stale save; it does not
prevent two workers from sending to different recipients simultaneously. A row's `SENDING`
status is not a shared global lease. Since 13 November 2026 the lease is the lock file
`automation/queue/SEND_LOCK.json`, taken with `queue.py lock take` and a pushed commit (`APPLY.md` section 6). The earlier
"canonical-journal lease" is retired: it had no implementation any runner could reach, and
63 of 127 runs named it as the reason no email went out.
Complete the current queue, tracker and Gmail duplicate checks immediately before sending.
Do not copy private journal contents into this public repo.

Standing owner authority permits eligible applications without routine per-email approval.
Actual platform review remains mandatory. Daily caps are in `config.json -> limits` (3 emails a day). Never turn
an ambiguous outcome into a retry or change routes to bypass a prior application.

## Evidence before readiness

- Read the complete current advert, linked position description and essential questionnaire.
  A digest is a triage aid. Required skills and experience outrank fit percentages.
- Record `mandatory_unmet` and `mandatory_unresolved`. Neither may be nonempty for a queued
  application: unmet means reject, unresolved means one `ASK_OWNER` question (there is no hold pile).
  Disclosing a mandatory gap does not waive it, and gaps are never volunteered in the application. April 2019 to February 2020 is under one year;
  do not double-count the September transition or call it a full year to clear a minimum.
- Apply the current `facts.json`. The resume is the lane variant built by `scripts/resume.py`
  (the Portfolio master headed "Graduate Civil Engineer" is retired for applications). Software
  experience remains coursework and is described as what he did, without apology. Referees on request.
- Apply through the channel the advert asks for. Contact research is only for adverts that name
  a person or an application address. A phone or information contact is not an email application route.
- Do not send a second CV package just because a portal application was submitted. Any proposed
  post-portal note must independently satisfy AGENTS, owner authority, recipient purpose and
  duplicate checks. Do not say an application was lodged until an actual submission is verified.
- Speculative drafts use `application_type: SPECULATIVE_ENQUIRY`,
  `vacancy_status: NO_ADVERTISED_VACANCY_VERIFIED`, and a screen with
  `company_work_verified: true`, three supported contributions and verified contact evidence.
  This is a company/work-scope assessment, not an invented advert.
- `publish.py build` creates preparation-only records. They cannot be added directly. Inspect
  every page of the exact final PDFs, then upload and verify SHA-256, ID and authenticated path.
  A placeholder hash or successful HTML build does not establish PDF QA.
- Never claim certificates or other files are attached unless the actual final pack includes them.
  Employer closing dates in the advert take precedence over later job-board metadata expiry.

## Records made before 13 November 2026

Tracker records from the 28 September review (JHA, Waverley, Gunnedah and others) are history.
Do not send or submit anything from them: an application goes out only through the apply queue
(`APPLY.md` section 3), with its caps, duplicate checks and send lock.

## Verification and checkpoint

Use `python -m unittest discover -s automation/tests -v`. PDF rendering/master tests may
skip when their dependencies are absent; that never counts as completed PDF inspection.
Record actual test outcomes, source commit, evidence dates, held reasons, exact next actions,
and actual publication/send evidence. Commit to this branch without forcing; reload/merge a
concurrent change. There is no target number of records; nothing is ever permission to invent or lower eligibility.
