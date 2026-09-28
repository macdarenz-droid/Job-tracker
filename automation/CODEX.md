# Codex runner handoff

Adopted by Marc on 28 September 2026. Use this branch's README, RUNBOOK, config, facts,
scripts, tests, employer cache and run history for the existing Codex discovery task.
Read current remote files each tick; never substitute an old local checkout.

## Identity and schedule

- Keep the existing discovery task; do not create another task or enable the separate reviewer.
- The adopted cadence is five hours, Australia/Melbourne. Claude's separate Routine is managed separately.
- Codex creates records as `contributor_name: Codex`, `created_by: codex-job-search`.
  Override these two `common.CONFIG` values explicitly in the running process; leave the
  repository's Claude defaults intact. Preserve the original author on existing records.
- The tracker is https://macdarenz-droid.github.io/Job-tracker/ with shared Cloudflare D1/R2.
  `data.json` and run snapshots are not live state. Never commit the access code or tokens.

## Shared sending safeguards

Root `AGENTS.md` applies. A D1 `expected_version` check prevents a stale save; it does not
prevent two workers from sending to different recipients simultaneously. A row's `SENDING`
status is not a shared global lease. Acquire the actual bounded canonical-journal lease
with a unique owner and current-version guard before any send or private-journal mutation.
Recheck owner/expiry and complete current tracker/Gmail/journal duplicates immediately before sending.
If a runner cannot access that journal, it may research and publish guarded tracker-only
changes, but must hold sending. Do not copy private journal contents into this public repo.

Standing owner authority permits eligible applications without routine per-email approval.
Actual platform review remains mandatory. At most one outbound email per tick. Never turn
an ambiguous outcome into a retry or change routes to bypass a prior application.

## Evidence before readiness

- Read the complete current advert, linked position description and essential questionnaire.
  A digest is a triage aid. Required skills and experience outrank fit percentages.
- Record `mandatory_unmet` and `mandatory_unresolved`. Neither may be nonempty for a ready pack.
  Disclosing a mandatory gap does not waive it. April 2019 to February 2020 is under one year;
  do not double-count the September transition or call it a full year to clear a minimum.
- Apply the current `facts.json` and unmodified Portfolio master. Software experience remains
  academic. Referees are on request under this newly adopted facts file.
- Named employer business contacts remain preferred; HR is the last verified employment-channel
  fallback. A phone or information contact is not an email application route.
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

## Current continuation

Review `runs/20260928T0123Z/review-codex.json` and `.md` before selecting those records.
The audit found three mandatory failures (Waverley, Melbourne Truss, Excel), unresolved
mandatory knowledge/licence requirements for Vincent, and an unverified qualification-attachment
claim in Gunnedah's pack. JHA passed content review conditionally and still needs a fresh
specific vacancy/recipient check plus every normal send gate. Preserve all newer real outcomes.

The guarded publisher on main can apply dated research and narrow review holds through its
existing private Actions secret. It reads live state, checks row version/status, preserves
documents/history/attribution, uses expected_version, and verifies the entire saved state.
If it rejects a changed record, reconcile the new evidence instead of repeating the write.

## Verification and checkpoint

Use `python -m unittest discover -s automation/tests -v`. PDF rendering/master tests may
skip when their dependencies are absent; that never counts as completed PDF inspection.
Record actual test outcomes, source commit, evidence dates, held reasons, exact next actions,
and actual publication/send evidence. Commit to this branch without forcing; reload/merge a
concurrent change. The target of two results is never permission to invent or lower eligibility.
