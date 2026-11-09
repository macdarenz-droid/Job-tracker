# Job-search recovery and conversion design

Review date: 9 November 2026. Source commit: `a571724cd8e8d8dc149952e44e3f034bfdfab10e` on `claude/job-search-automation-sg3inr`.

This change is an isolated engineering proposal and local hardening. It does not deploy the API, publish tracker data, send applications, change any external schedule or replace the canonical private journal. Current direct instructions and the existing application safeguards still control execution.

## What the code actually does

The automation branch, not `main`, contains the search engine. A scheduled runner follows the RUNBOOK, fetches SEEK and employer adverts, screens against documented facts, checks duplicates, researches contacts, builds PDFs and prepares tracker records. Email sending is a separate gated step. The GitHub Pages frontend reads shared Cloudflare state; `data.json` is only a historical seed.

Each tracker edit currently reads and rewrites one complete JSON snapshot under a global version guard. `cloudflare-api/src/index.js` caps that snapshot/request at 1,800,000 bytes. The run journal records HTTP 413 and `skipped_tracker_full`, with local-only packs instead of tracker publication. The newest committed end event is 31 October 2026 at 04:19:19 UTC. This is evidence about the committed engine history, not proof that all other runners are stopped.

Other concrete findings:

- `journal.jsonl` contains unresolved merge markers. Raw sums are not an application funnel and cannot establish verified sends or interviews.
- The saved config selects Grok AI while historical documentation describes Claude and Codex. Attribution must be selected explicitly per process; do not relabel existing records or assume a mixed history is wrong.
- An omitted `mandatory_unresolved` passed the old eligibility check. The final built row also dropped the mandatory-check arrays.
- `publish.py go` uploaded attachments before rejecting invalid letter/email content.
- Blanket title filtering removed junior civil project-manager and junior estimator/contract-administrator roles before reading their adverts.
- Routine new-record counts combine useful packs with work that still requires submission. They do not measure applications completed, human replies or interviews.

These findings explain operational loss and unreliable measurement. They do not establish a general reason for any employer's hiring decision.

## Implemented in this isolated branch

1. Missing or malformed mandatory arrays fail closed; built rows retain both arrays and ready-record validation checks them.
2. Text and record checks run before rendering/uploading. Existing post-upload hash/metadata checks remain.
3. `JOB_SEARCH_RUNNER=codex|claude|grok` explicitly selects identity for one process. No override preserves the saved config. No silent Grok identity import is performed. Existing author fields are untouched.
4. Tracker capacity diagnostics measure the actual JSON request encoding and stop an oversized write before attempting it. They do not repair storage or remove data.
5. The title prefilter admits narrowly scoped junior civil/construction support titles for full screening. Senior and unrelated-discipline exclusions remain. This is not eligibility approval.
6. `JOB_SEARCH_PDF_BACKEND=reportlab` explicitly uses the already-supported portable renderer when Chromium cannot run. This does not replace visual inspection of final application PDFs.
7. `health.py` diagnoses the local journal and optional exported snapshot without network access or credentials. It excludes conflicted journal content and counts the active effective queue after manual replacement, historical collection precedence and visibility rules. Receipt-confirmed and under-review states are applications, not human replies. Reported status is distinct from local date-and-reference evidence; neither is a live outcome verification.

Run locally:

```sh
JOB_SEARCH_RUNNER=codex JOB_SEARCH_PDF_BACKEND=reportlab \
  python3 -m unittest discover -s automation/tests -v
python3 automation/scripts/health.py --now 2026-11-09T17:51:00Z
# Optional, only with an authorised current private export:
python3 automation/scripts/health.py --tracker-snapshot /private/current-export.json
```

No commands above fetch a tracker secret. Do not commit private exports, raw inbox content, credentials or new applicant documents to this public repository.

## Recovery priority 1: unblock reliable storage

Do not merely increase the snapshot cap, delete history, trim attachments or replay all local packs. First obtain an authorised current export and recovery bookmark, compare it with the canonical journal and local unpublished packs, then build a reviewed additive migration in the same D1 database.

Proposed storage contract:

- One row per opportunity/application, retaining original stable IDs, authors, timestamps, status history and document references.
- Append-only application events with a unique event/idempotency key, evidence reference and source date.
- Separate private immutable advert/pack objects where necessary, rather than embedding growing text and bytes in every mutation.
- Paginated reads and bounded append/update commands. Use a record version plus atomic database transaction/CAS, not a full-snapshot rewrite.
- Keep the existing global send lease as a distinct resource. Row versions do not authorise or serialize outbound messages.
- A compatibility layer for the frontend during migration, with verified counts/hashes and a reversible cutover. Do not remove the old tables or snapshot during this change.

Acceptance tests: stale writes return 409; repeated idempotency keys cannot create duplicates; 413 does not lose local work; attachment bytes and references survive; attribution and Bin history survive; a concurrent user edit wins or conflicts explicitly; uncertain send outcomes cannot be retried; two clients read the same saved record; no public endpoint exposes private document bytes.

Before deploying, reconcile `main`'s guarded research-publisher changes with this automation branch. Deploying the older branch's Worker over production would risk losing newer review safeguards. Deployment and live migration are not included here.

## Recovery priority 2: make status represent reality

Use separate dimensions instead of one overloaded status:

- Vacancy: open, closed, stale/unverified. Store employer closing time separately from job-board metadata; use the earlier verified applicable deadline.
- Eligibility: pass, unresolved, unmet, with each essential criterion linked to the advert/form and documented applicant fact. An empty array alone is not evidence of a correct review.
- Preparation: not started, drafted, exact PDFs inspected, final pack verified.
- Submission: not submitted, awaiting applicant action, submitting, submitted with evidence, uncertain, delivery failed.
- Employer outcome: acknowledged, screening outstanding, human reply, interview, declined, withdrawn. Only an actual source may advance an outcome.

Continue blocking equivalent outreach across all sources. Reconcile Gmail by individual message plus employer, role and vacancy ID/URL, never thread ID alone. A receipt may request further screening; a sent message may bounce. Do not infer that either is a completed application.

The canonical journal remains the authoritative send coordination point. Its inaccessible lease means research can continue but sending stays held. No alternate sender or route may bypass it.

## Recovery priority 3: a five-hour loop that produces decisions

The cadence is an external scheduler setting, not a JSON field. Updating this document cannot confirm a live schedule. Reuse the authorised existing task and keep other workers' settings unchanged unless explicitly instructed.

Each tick should:

1. Check health, capacity and the latest authoritative tracker/journal. Reconcile current inbox outcomes, changed manual submissions and outstanding screening before searching.
2. Review the top pending packs for deadlines, liveness and completeness. Return at most three ranked next actions with the exact application route and remaining requirement. Do not regenerate an existing pack merely to count a new result.
3. Prioritise trainee/cadet/junior drafting roles that accept academic CAD experience. Keep graduate civil/site support as a separately screened lane. Residence, licence, degree recency and enrolment requirements must be checked, not inferred.
4. Search fresh direct-employer adverts and bounded alternate sources only after the pending queue is handled. No minimum record quota; zero eligible opportunities is valid. Prefer a verified eligible opportunity over a speculative enquiry added to meet a target.
5. Preserve full-advert/form evidence and factual claims. Keep original documents unchanged unless a separately authorised document task requests edits. Produce no external draft/send without the applicable authority.
6. Record a structured end event with counts for discovered, eligible, prepared, unpublished, submission-required, verified submitted, human replies and interviews. Surface new actionable blockers; do not report repeated routine failures as successful progress.

Human action queue: each item needs one owner, vacancy key, closing time, current route, pack location, unresolved requirements and the next exact step. A pack waiting for the applicant is not a completed application. Do not claim a three-minute application without inspecting its real form.

## Measurement and review

Track weekly cohorts by role lane and source: eligible vacancies, verified completed applications, delivery failures, screening outstanding, human responses and interviews. Store timestamps to measure preparation-to-submission delay. Keep machine acknowledgements separate from human replies. Preserve explicit rejection reasons; otherwise use reason unknown.

Review after a meaningful set of comparable completed applications, not every empty five-hour tick. Test one change at a time, such as junior drafting positioning or ordering of verified portfolio evidence. Fit percentages are triage scores, never interview probabilities. Do not diagnose ATS, visa or CV problems from silence alone.

## Not fixed by this patch

The production capacity incident, unavailable canonical lease, malformed historical journal, stale prepared packs, live schedule verification and applicant-side submissions still need reconciliation. `publish.py go` still relies on the runbook's independent review and exact-PDF inspection; this patch is not a complete machine-enforced sending system. No source or test here grants sending authority.
