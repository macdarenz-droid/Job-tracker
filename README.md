# Marc's job tracker

A GitHub Pages version of the existing Australian job tracker, with compact tables, a restrained sidebar, match bars, details, an Applied action, Scroll mode and Bin.

## Access and visibility

The shared code opens the interface. It is a **visual gate only**. This repository is public: `data.json`, documents and source files can be downloaded directly without entering the code. The verifier is in browser code. Do not use this design for information you want to keep secret.

GitHub Pages has no database or anonymous write API. Edits, including new attachments, are saved in the **current browser's IndexedDB**. They do not appear for other visitors until someone exports JSON and commits the updated `data.json` (and any new attachments) to the repository. The Export button includes new attachment bytes inline in the JSON. Grok can update the repository through its own authorised GitHub connection, but the shared screen code cannot grant repository write access.

## Publishing

The included GitHub Actions workflow deploys on a push to `main`. If Pages is not enabled yet, select **Settings → Pages → Build and deployment → GitHub Actions**, then rerun the workflow. The expected URL is `https://macdarenz-droid.github.io/Job-tracker/`; it is live only after a successful Pages deployment.

## Record workflow

Table mode groups Applications, Ready, Leads and outcomes, with six rows per group page. Scroll mode shows every active record. **Applied** on a Ready or Lead row asks who applied, the actual date and the route (SEEK, company website, email, referral or other), plus optional résumé, cover letter and confirmation documents. Saving moves the record into Applications **in this browser**; it **does not submit** an application. Bin moves a row out of the active view without destroying its history or document references. Expired jobs stay out of the active view. Sent email remains a distinct outcome backed by Gmail evidence in the imported record.

This is a tracker, not a mail client. It does not contact employers or enable the previously stopped job workers. `AGENTS.md` describes the rules a separately authorised job agent must follow.

## Migration scope

The public `data.json` and `documents/` come from the old tracker snapshot: 14 automatic applications, 46 leads, three manual records, 11 Bin visibility records and 26 bundled PDFs. `archive/` retains the source snapshot, D1 metadata export and migration manifest. Two manual-upload PDF bytes were not available from the read-only old Site export; their filenames, checksums and attribution remain in the JSON and are labelled unavailable. Three oversized Bin snapshots were truncated by that export; their current rows and Bin metadata remain. The canonical job journal was unavailable during migration and is not replaced by this snapshot.

The old private Site is unchanged.

## Local preview

Serve this directory with `python3 -m http.server 8000`, then open `http://localhost:8000`. Web Crypto works on localhost or HTTPS.
