# Job tracker agent instructions

Read this file before editing the website or using tracker records.

## Website and data

- The repository is public. The user explicitly requested publication of the old tracker snapshot and bundled documents. The six-digit screen code is only a visual gate; never claim it protects files from direct download.
- Until `cloud-config.js` contains a deployed Worker URL, edits remain in each browser. The interface must say so. Once Cloudflare D1/R2 is deployed and configured, read and write the shared API with its version guard. Do not silently fall back to browser storage on cloud errors or claim a cloud Save succeeded without a successful response.
- The historical `data.json` is the pinned seed and public baseline. Do not replace it with a stale browser export. The cloud state is authoritative after activation; reconcile browser backups into it by record ID, version and timestamp. A stale concurrent API write must return 409. Preserve automatic history, documents and Bin metadata.
- New cloud attachments are private R2 objects with D1 metadata. Previous browser backups may contain inline base64; upload those bytes to R2 and retain filename, hash and attribution when importing. Do not imply metadata-only old uploads are downloadable.
- Never put a GitHub token in source, a URL, a commit, a log, or a shared reply.
- Preserve automatic application history, manual entries, document metadata and hashes, Bin visibility, actual outcomes, and existing statuses. Do not invent a sent email, submission, delivery, opening, reply or offer.
- Record an **Applied** action only after an application has actually been submitted (by the owner, or by the runner named as submitter in `automation/APPLY.md`), with the actual date, route and receipt. Saving a tracker record never sends an application. The six-digit code is a modest shared credential; the public GitHub files stay downloadable without it.
- On 28 September 2026 the owner authorised resuming the existing discovery worker `6aa1817b36fc8191b9c17b6c848f2e8d`. Since 13 November 2026 every runner follows the shared cadence in `automation/config.json -> schedule` (one discovery tick a day, submit-only ticks while entries wait); the earlier three-hourly Codex and five-hourly Claude schedules are retired. Keep the separate lead reviewer `6aa1ec1bba4481919683b659bc6c1148` stopped. Do not create or enable another worker without the owner's say-so. Since 13 November 2026 the runners' roles (who finds, who submits on SEEK, who sends email) are set in `automation/APPLY.md` section 2, and the cadence in `automation/config.json`. The resumed worker must publish tracker changes to this GitHub Pages site through the guarded Cloudflare D1 API, never the older ChatGPT Site.
- Cloudflare D1 is the current shared tracker. The public `data.json` is a seed only, so a commit to it alone will not update what visitors see. If the API rejects an automatic lead change, save a reconciliation file and implement an append-only, version-guarded route before claiming it is live. Do not mislabel an automated lead as a manual entry made by a person. From 17 October to 14 November 2026 the tracker refused new records (its single-document state had reached the 1.8 MB limit). The per-record storage fix went live from `main` on 14 November 2026 (pull request #3: 253 records copied to one row each, read back identical). The apply queue in `automation/queue/` stays the source of truth for what is waiting; the tracker page's Old packs view is not the apply queue; a failed tracker write never stops an application.

## If independently asked to research or send a job application

The tracker itself has no sending authority. Obtain current, explicit task authority outside this repository. A standing authorised application task does not require routine conversational approval for each suitable email, but actual platform review and every safeguard below remain mandatory.

1. Verify the full current employer advert is still open and the role fits Marc's documented experience and mandatory requirements. Clearly label a speculative enquiry; never present it as an advertised vacancy.
2. Search the employer's advert, official team and relevant project pages, then bounded employer-authored professional sources for a current project-connected site, engineering, drafting, operations or working owner/director contact. Verify the person's current role, relationship to the relevant team, and their exact published **business** email. Do not guess addresses, use private details, unrelated project parties, agencies, or data brokers.
3. If no suitable verified direct contact exists, use an employer HR/careers/application inbox only when it explicitly accepts applications. A generic info/admin inbox needs explicit evidence that it accepts employment enquiries. Follow the employer's mandated channel. SEEK submissions are made only by the runner the owner named for it (`automation/APPLY.md` section 5); Jeremie is no longer involved (owner, 13 November 2026).
4. Check the complete shared application journal, all current manual tracker entries and documents, Gmail Sent and drafts, SEEK receipts, bounce messages, and prior equivalent employer/role outreach. Sent, reported applied, sending, uncertain or unresolved equivalent outreach blocks a repeat. Never resend merely by changing contact or subject.
5. Before **any** email or speculative enquiry, take the send lock in `automation/queue/SEND_LOCK.json` by a pushed commit (`automation/APPLY.md` section 6; the earlier "shared canonical journal lease" is retired because no runner could reach it), perform the final duplicate/eligibility/recipient/evidence checks, inspect both final PDFs, then use actual platform review. Stay inside the daily caps in `automation/config.json` (email 3, SEEK 6, portal 3). Record Gmail success as sent, not delivered or read; preserve message ID and exact content. If the send outcome is ambiguous, stop and reconcile it before any retry.
6. Write briefly and naturally. Avoid phrases such as “here is my tailored résumé and cover letter.” “I've attached my resume and cover letter” is sufficient. Every work claim must trace to Marc's master résumé or an explicit later fact. Do not mention private residency or migration goals in employer material, and never volunteer what he lacks: if an advert makes it mandatory, do not apply.

This public file summarizes process only. The current private operating document and latest direct user instructions control an authorised application task.

## Owner decisions, 13 November 2026

These replace anything above or in older documents that says otherwise.

- The goal is applications **submitted, with a receipt**. Leads and prepared packs do not count. There is no quota of new records per run.
- Apply only for skilled work his qualifications support, in this order: civil drafting and design; civil engineering technician work such as construction materials testing; graduate or junior civil, site or project engineer roles that welcome graduates. Not labouring, traffic control, survey-assistant, administration, estimator or project coordinator roles, and not formal graduate programs (`automation/config.json` -> `lanes`).
- Anywhere in Australia.
- SEEK applications are submitted by Grok from the apply queue. Email applications are sent automatically by the runner with Gmail. Every answer given in his name comes from `automation/facts.json` (`answers`); a question with no answer there is never guessed.
- Everything stays on free plans. No agent adds a paid service without asking first.
- `automation/APPLY.md` is the method; `automation/RUNBOOK.md` is the daily procedure.
