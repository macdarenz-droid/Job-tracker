# Job tracker agent instructions

Read this file before editing the website or using tracker records.

## Website and data

- The repository is public. The user explicitly requested publication of the old tracker snapshot and bundled documents. The six-digit screen code is only a visual gate; never claim it protects files from direct download.
- Until `cloud-config.js` contains a deployed Worker URL, edits remain in each browser. The interface must say so. Once Cloudflare D1/R2 is deployed and configured, read and write the shared API with its version guard. Do not silently fall back to browser storage on cloud errors or claim a cloud Save succeeded without a successful response.
- The historical `data.json` is the pinned seed and public baseline. Do not replace it with a stale browser export. The cloud state is authoritative after activation; reconcile browser backups into it by record ID, version and timestamp. A stale concurrent API write must return 409. Preserve automatic history, documents and Bin metadata.
- New cloud attachments are private R2 objects with D1 metadata. Previous browser backups may contain inline base64; upload those bytes to R2 and retain filename, hash and attribution when importing. Do not imply metadata-only old uploads are downloadable.
- Never put a GitHub token in source, a URL, a commit, a log, or a shared reply.
- Preserve automatic application history, manual entries, document metadata and hashes, Bin visibility, actual outcomes, and existing statuses. Do not invent a sent email, submission, delivery, opening, reply or offer.
- Record an **Applied** action only after an application has actually been submitted (by the owner, or by the runner named as submitter in `automation/APPLY.md` on the automation branch), with the actual date, route and receipt. Saving a tracker record never sends an application. The six-digit code is a modest shared credential; the public GitHub files stay downloadable without it.
- On 28 September 2026 the owner authorised resuming the existing two-hour discovery worker `6aa1817b36fc8191b9c17b6c848f2e8d`. Keep the separate lead reviewer `6aa1ec1bba4481919683b659bc6c1148` stopped. Do not create or enable another worker. The resumed worker must publish tracker changes to this GitHub Pages site through the guarded Cloudflare D1 API, never the older ChatGPT Site.
- Cloudflare D1 is the current shared tracker. The public `data.json` is a seed only. To publish verified automatic leads or documented closures, update the single `research/lead-updates.json` batch on `main`; its GitHub Actions workflow applies a current-version guarded cloud write and verifies preservation. Check that workflow and a fresh live read before saying a row is live. Never mislabel an automated lead as a Jeremie manual entry, overwrite an equivalent record, or expose private employment details in the public batch.

## If independently asked to research or send a job application

The tracker itself has no sending authority. Obtain current, explicit task authority outside this repository. A standing authorised application task does not require routine conversational approval for each suitable email, but actual platform review and every safeguard below remain mandatory.

1. Verify the full current employer advert is still open and the role fits Marc's documented experience and mandatory requirements. Clearly label a speculative enquiry; never present it as an advertised vacancy.
2. Search the employer's advert, official team and relevant project pages, then bounded employer-authored professional sources for a current project-connected site, engineering, drafting, operations or working owner/director contact. Verify the person's current role, relationship to the relevant team, and their exact published **business** email. Do not guess addresses, use private details, unrelated project parties, agencies, or data brokers.
3. If no suitable verified direct contact exists, use an employer HR/careers/application inbox only when it explicitly accepts applications. A generic info/admin inbox needs explicit evidence that it accepts employment enquiries. Follow the employer's mandated channel. SEEK submissions are made only by the runner the owner named for it; Jeremie is no longer involved (owner, 13 November 2026).
4. Check the complete shared application journal, all current manual tracker entries and documents, Gmail Sent and drafts, SEEK receipts, bounce messages, and prior equivalent employer/role outreach. Sent, reported applied, sending, uncertain or unresolved equivalent outreach blocks a repeat. Never resend merely by changing contact or subject.
5. Before **any** email or speculative enquiry, take the send lock described in `automation/APPLY.md` on the automation branch (the earlier "shared canonical journal lease" is retired because no runner could reach it), perform the final duplicate/eligibility/recipient/evidence checks, inspect both final PDFs, then use actual platform review. Stay inside the daily caps in `automation/config.json`. Record Gmail success as sent, not delivered or read; preserve message ID and exact content. If the send outcome is ambiguous, stop and reconcile it before any retry.
6. Write briefly and naturally. Avoid phrases such as “here is my tailored résumé and cover letter.” “I've attached my resume and cover letter” is sufficient. Every work claim must trace to Marc's master résumé or an explicit later fact. Do not mention private residency or migration goals in employer material, and never volunteer what he lacks: if an advert makes it mandatory, do not apply.

This public file summarizes process only. The current private operating document and latest direct user instructions control an authorised application task.

## Owner decisions, 13 November 2026

These replace anything above that says otherwise. The working rules for the runners live on the automation branch (`claude/job-search-automation-sg3inr`): `automation/APPLY.md` is the method and `automation/RUNBOOK.md` the daily procedure.

- The goal is applications **submitted, with a receipt**. Leads and prepared packs do not count.
- SEEK applications are submitted by Grok from the apply queue; email applications are sent automatically by the runner with Gmail; Jeremie is no longer involved.
- The tracker stores each record in its own database row (`cloudflare-api/README.md`). It is the owner's history view and apply-queue view; a failed tracker write never stops an application.
- Everything stays on free plans. No agent adds a paid service without asking first.
