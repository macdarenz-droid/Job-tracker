# Claude job-search loop: architecture

Plain description of how Claude finds suitable jobs for Marc every five hours, prepares
truthful applications, and tracks everything on the shared tracker under the name
**Claude**. The rules in `AGENTS.md` apply to every run.

## 1. Goal and limits

- Find at least one or two new, suitable, open adverts per run (five-hourly), Australia-wide,
  for junior civil roles Marc can honestly do: graduate or junior civil engineer, civil
  drafter or draftsperson, trainee or cadet, junior site engineer, junior estimator, project
  coordinator, civil designer, engineering officer.
- No duplicates: nothing is added that the tracker already holds (any source, any author).
- Highest interview chance: apply fast (fresh adverts), reach the person who hires (a named
  engineer, manager, director or owner with a published business address), keep the writing
  short and human, and put the formal application in through the channel the employer asks for.
- Truth only: every claim traces to `automation/facts.json`, which is built from the Portfolio
  résumé. No invented experience, tools, years or amounts.
- Sending is the only step that needs a credential Claude does not have yet (see §7).

## 2. Components

```
 every 5 h ──▶ Routine (Claude Code) ──▶ RUNBOOK tick
                                          │
       ┌──────────────────────────────────┼──────────────────────────────────┐
       ▼                                  ▼                                  ▼
 A. Discover                        B. Screen                          C. Track
 seek.py sweep (SEEK search API     fit score vs facts.json            tracker.py add/update
 + GraphQL job details)             mandatory-requirement check        (D1 via Worker API,
 WebSearch angles                   advert open? (isExpired,           version guard, retry
 employer careers pages             expiresAt, listed date)            on 409); R2 uploads
 (rotating target list)             tracker.py check (dedupe)
       │                                  │                                  ▲
       └──────────────▶ D. Contact research ──▶ E. Draft ──▶ F. Verify ──────┘
                        employer-published        email +      truth (facts.json)
                        business email of a       cover        tone (checks.py)
                        named hiring person;      letter PDF   separate reviewer
                        else careers inbox;       + résumé     agent tries to
                        else SEEK/portal pack      PDF          refute every claim
                                                   │
                                                   ▼
                                   G. Send (Gmail) ── only with the Gmail
                                   connector; one email per run; journal
                                   lease (SENDING) under the version guard
```

Files:

| Path | What it is |
|---|---|
| `automation/config.json` | Search terms, filters, limits, tone rules, contact rules, target employers, statuses |
| `automation/facts.json` | The only allowed source of claims about Marc |
| `automation/RUNBOOK.md` | The exact tick procedure the Routine follows |
| `automation/scripts/seek.py` | SEEK search + job details, cheap title prefilter |
| `automation/scripts/tracker.py` | Live tracker client: read, duplicate index, guarded writes, uploads |
| `automation/scripts/render_pdf.py` | Cover letter PDF (headless Chromium) and master résumé path |
| `automation/scripts/checks.py` | Tone, truth and completeness checks before anything is saved as prepared |
| `automation/scripts/journal.py` | Append-only run journal `automation/journal.jsonl` and `automation/runs/<id>/` |
| `automation/employers.json` | Careers pages and contacts verified in earlier runs (cache, grows over time) |
| `automation/tests/` | Unit tests: `cd automation && python3 -m unittest discover -s tests` |
| `docs/COACHING-DECISIONS.md` | Every decision the plan was silent on, with the reason |

## 3. Discovery (A)

1. **SEEK** is the primary source. The public search API (`/api/jobsearch/v5/search`) returns
   JSON with no login; the GraphQL `jobDetails` query returns the full advert, listed and
   expiry dates, `isExpired`, `isLinkOut` (external apply) and the screening questions. Twenty
   keyword sets, newest first, last three days (fourteen on the first run). Jora, Indeed and
   LinkedIn block automated reads and mostly mirror SEEK, so they are not used.
2. **Employer careers pages.** A rotating slice of `target_employers` (twelve per run) is
   checked with WebSearch and WebFetch for open junior roles. Anything verified is cached in
   `employers.json` (careers URL, apply route, contacts) so later runs are cheaper.
3. **WebSearch angles** for adverts SEEK does not carry: council job boards, government
   graduate programs, Engineers Australia listings, "graduate civil engineer" + region.
4. **Prefilter** (`seek.py prefilter`): title must carry a junior or civil signal and must not
   carry a senior, management or other-discipline word; classification must be engineering,
   construction, design, government or resources. Cheap and deliberately loose; the fit score
   does the real work.

## 4. Screening (B)

- **Fit score** (`resume-fit-v2`, rubric in `config.json`): a percentage with a rationale and
  a caution line, scored against `facts.json` only. Threshold 60. It is a rough fit, never an
  interview forecast, and the tracker labels it that way.
- **Mandatory requirements**: citizenship or PR only, a licence Marc does not hold, a
  qualification he does not have, or a hard "years of commercial experience" line makes the
  advert `HELD_…` with the reason, not a silent skip. Unknown details become a gap to check.
- **Open advert**: `isExpired` false, `expiresAt` in the future, listed date recorded. A
  company-site advert is fetched and its wording checked in the same run.
- **Duplicates** (`tracker.py check`): same SEEK id, same URL, same employer + role, or any
  outreach or rejection at the same employer within 90 days blocks the record. Employer names
  are normalised ("Pty Ltd", "Group", "Australia" and brackets ignored). Older contact with the
  employer is a note on the record, not a block.

## 5. Contact research (D)

Marc asked for the person who hires, not the HR inbox. The rule (`config.json → contact`):

- A **direct contact** is a named person in an engineering, drafting, design, operations,
  project or owner/director role at the employer, whose **business** email the employer itself
  publishes: team or contact page, project page, capability statement, press release, tender or
  council document. The record stores `contact_evidence_url` and `contact_verified_at`.
- Never: guessed or pattern-built addresses, personal mailboxes, data brokers or email-finder
  tools, recruiters, unrelated project parties, or generic info@ inboxes unless the employer
  says they accept applications.
- Fallback order: an employer careers or application inbox that explicitly accepts
  applications; otherwise SEEK apply or the employer portal, prepared as a pack for Marc or
  Jeremie.
- **Double touch**: when the advert must go through SEEK or a portal and a verified direct
  contact exists, prepare both the portal pack and a short note to the contact. The note goes
  only after the portal application is marked Applied.

## 6. Drafting and verification (E, F)

- **Email**: under 220 words, plain Australian English, first person, one specific line about
  the employer or the role from the advert, the three facts employers scan for (Advanced
  Diploma completed February 2026 with Civil 3D and AutoCAD work; site experience in the
  Philippines; White Card, licence, 485 work rights to December 2027), and one clear ask.
  "I've attached my resume and cover letter" is enough. No banned phrases, no dashes.
- **Cover letter**: one page, same header as the résumé, under 340 words, rendered to PDF by
  `render_pdf.py`. The résumé is the master PDF from the Portfolio, unchanged.
- **Truth**: `checks.py facts` blocks unknown tools, years, amounts, residency, registration and
  experience claims. A separate reviewer agent then tries to refute every sentence against
  `facts.json`; one confirmed false claim rejects the draft.
- **Ready pack** for SEEK or portal routes: the record holds the job URL, the screening
  questions from the advert with suggested truthful answers, the two PDFs, and a five-step
  checklist. Status `READY_JEREMIE_SEEK` or `READY_JEREMIE_EMPLOYER_PORTAL`.

## 7. Sending (G) and what it needs

- Channel: Gmail as macdarenz@gmail.com, through the **Gmail connector** attached to the
  Routine. Nothing else may send. Until the connector is attached, every email record stays
  `PREPARED_NOT_SENT` with the full text and both PDFs on the tracker; the tracker shows a
  "Send from Gmail" button that opens the drafted email for Marc.
- Lease: before a send the record is set to `SENDING` under the version guard (a 409 means
  someone changed the tracker; re-read and re-check). Then the final duplicate, eligibility,
  recipient and attachment checks run again, both PDFs are opened and read, and the send
  happens. Success is recorded as `SENT` with the Gmail message id and exact content, never as
  delivered or read. Ambiguous outcome: `SEND_UNCERTAIN`, and no retry until reconciled.
- At most one email per run and one speculative enquiry per run. A follow-up (one, after
  eight days without a reply) counts as that run's email.

## 8. Routes other than email (how Claude "applies" without a login)

1. **SEEK Quick Apply and employer portals need Marc's login.** Claude prepares the pack so the
   submission takes about three minutes, then Marc or Jeremie presses Applied on the tracker
   with the real date and route.
2. **Claude in Chrome** (the browser extension on Marc's own computer) can drive SEEK with
   Marc's saved profile while he watches. That is the path to true one-click SEEK applications;
   it needs the extension installed and a desktop session linked to his machine, so it is a
   later phase and never runs unattended.
3. **Direct email to the hiring person** is the route Claude can run end to end once Gmail is
   attached.
4. **Speculative enquiries** to target employers with no advert: at most one per run, clearly
   labelled as speculative, only to a verified direct contact.
5. **Follow-ups** after eight days without a reply: one polite note, same journal checks.

## 9. Tracking (C)

- Claude's records are manual entries with `contributor_name: "Claude"`,
  `created_by: "claude-job-search"`, `record_kind: "AUTOMATED_LEAD"`. They are never labelled
  as Jeremie's. The frozen ChatGPT-era `applications` and `leads` arrays are not touched, and
  the API would reject that anyway.
- Fields the tracker shows: company, role, location, job URL, status, contact name, their
  role, contact email, subject, email body, why it fits, things to check, fit score with
  rationale, attachments, added by, checked date. Extra fields (`advert`, `contact_evidence_url`,
  `screening_questions`, `run_id`) ride along and survive edits made in the tracker.
- Every write is version-guarded and retried from a fresh read on 409. Claude only edits its own
  records; Marc can edit them in the tracker like any other row.

## 10. Schedule and operations

- A Claude Code Routine fires every five hours into the session that built this loop, with the
  prompt in `RUNBOOK.md` §0. Each tick is bounded: at most 40 SEEK details, 25 screened, 4 new
  records, 1 email, about 25 minutes, and at most seven agents (owner's budget: about 5 to 6 on
  a 10 scale; one sweep, one screener, up to four contact researchers, one reviewer; Claude
  drafts and publishes itself).
- Each run writes `automation/runs/<run_id>/` (candidates, decisions, drafts) and appends to
  `automation/journal.jsonl`, then commits to branch `claude/job-search-automation-sg3inr`.
- The six-digit tracker code is read from the `TRACKER_CODE` environment variable or
  `/root/.job-tracker-code`; it is never committed.
- If a run finds nothing new, it says so in the journal; it does not lower the bar to hit a
  number.

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| SEEK changes or blocks its API | `seek.py` fails loudly; the tick falls back to WebSearch and employer pages and logs it |
| A false claim slips into a letter | `checks.py facts` plus an independent refuting reviewer; one confirmed false claim rejects the draft |
| Duplicate outreach to an employer | Index over every record, normalised employer names, 90-day block on any outreach or rejection |
| Sending to a wrong or guessed address | Only employer-published addresses with an evidence URL; personal mailboxes rejected by `checks.py record` |
| Two writers save at once | D1 version guard; Claude retries from a fresh read and re-runs the duplicate check |
| Session summarised or restarted | State lives in the tracker, `journal.jsonl` and the run folders; the RUNBOOK is self-contained |
| Over-reach in tone or volume | Banned-phrase list, word limits, one email per run, one speculative enquiry per run |

## 12. Handover to another session

Everything needed to run a tick is in this folder and `docs/COACHING-DECISIONS.md`. A new session needs only:
1. This repository on branch `claude/job-search-automation-sg3inr`, and the Portfolio repository cloned beside it (for the master résumé PDF).
2. The six-digit tracker code in `/root/.job-tracker-code` (given by the owner in chat; never committed).
3. The instruction: "Follow `automation/RUNBOOK.md` end to end for one tick."
The Routine that fires every five hours is bound to the session that built this loop (see D17); a new session needs its own Routine with the RUNBOOK §0 prompt.
