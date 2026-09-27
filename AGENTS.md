# Job tracker agent instructions

Read this file before editing the website or using tracker records.

## Website and data

- The repository is public. The user explicitly requested publication of the old tracker snapshot and bundled documents. The six-digit screen code is only a visual gate; never claim it protects files from direct download.
- Until `cloud-config.js` contains a deployed Worker URL, edits remain in each browser. The interface must say so. Once Cloudflare D1/R2 is deployed and configured, read and write the shared API with its version guard. Do not silently fall back to browser storage on cloud errors or claim a cloud Save succeeded without a successful response.
- The historical `data.json` is the pinned seed and public baseline. Do not replace it with a stale browser export. The cloud state is authoritative after activation; reconcile browser backups into it by record ID, version and timestamp. A stale concurrent API write must return 409. Preserve automatic history, documents and Bin metadata.
- New cloud attachments are private R2 objects with D1 metadata. Previous browser backups may contain inline base64; upload those bytes to R2 and retain filename, hash and attribution when importing. Do not imply metadata-only old uploads are downloadable.
- Never put a GitHub token in source, a URL, a commit, a log, or a shared reply.
- Preserve automatic application history, manual entries, document metadata and hashes, Bin visibility, actual outcomes, and existing statuses. Do not invent a sent email, submission, delivery, opening, reply or offer.
- Record a manual **Applied** action only after Jeremie actually submits through SEEK or the employer website, with the actual date and route. Saving a tracker record never sends an application. The six-digit code is a modest shared credential; the public GitHub files stay downloadable without it.
- Do not enable or recreate the stopped job-research workers.

## If independently asked to research or send a job application

The tracker itself has no sending authority. Obtain current, explicit task authority outside this repository. A standing authorised application task does not require routine conversational approval for each suitable email, but actual platform review and every safeguard below remain mandatory.

1. Verify the full current employer advert is still open and the role fits Marc's documented experience and mandatory requirements. Clearly label a speculative enquiry; never present it as an advertised vacancy.
2. Search the employer's advert, official team and relevant project pages, then bounded employer-authored professional sources for a current project-connected site, engineering, drafting, operations or working owner/director contact. Verify the person's current role, relationship to the relevant team, and their exact published **business** email. Do not guess addresses, use private details, unrelated project parties, agencies, or data brokers.
3. If no suitable verified direct contact exists, use an employer HR/careers/application inbox only when it explicitly accepts applications. A generic info/admin inbox needs explicit evidence that it accepts employment enquiries. Follow the employer's mandated channel; SEEK and employer-portal submissions belong to Jeremie.
4. Check the complete shared application journal, all current manual tracker entries and documents, Gmail Sent and drafts, SEEK receipts, bounce messages, and prior equivalent employer/role outreach. Sent, reported applied, sending, uncertain or unresolved equivalent outreach blocks a repeat. Never resend merely by changing contact or subject.
5. Before **any** email or speculative enquiry, acquire the shared canonical journal lease under a current-version guard, perform the final duplicate/eligibility/recipient/evidence checks, inspect both final PDFs, then use actual platform review. At most one application or enquiry per authorised run. Record Gmail success as sent, not delivered or read; preserve message ID and exact content. If the send outcome is ambiguous, stop and reconcile it before any retry.
6. Write briefly and naturally. Avoid phrases such as “here is my tailored résumé and cover letter.” “I've attached my resume and cover letter” is sufficient. Every work claim must trace to Marc's master résumé or an explicit later fact. Do not mention private residency or migration goals in employer material.

This public file summarizes process only. The current private operating document and latest direct user instructions control an authorised application task.
