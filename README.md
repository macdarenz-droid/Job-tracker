# Marc's job tracker

The GitHub Pages frontend for Marc's Australian job search: [open the tracker](https://macdarenz-droid.github.io/Job-tracker/). It has a six-digit code screen, an overview dashboard with charts, a list and board view of every job, a details panel, an Applied button that records the real date and route, file uploads, outcomes, a Bin, search and sorting. Press ⌘K (Ctrl K on Windows) to search, `C` to add a job and `/` to jump to the search box.

It uses a dark theme by default with a light theme you can switch to from the sidebar. Each status has its own icon as well as a colour. Animations are kept short and turn off if your device is set to reduce motion. The style takes cues from Linear, Vercel's Geist and job trackers like Huntr, but nothing was copied from them. The Geist fonts are stored in `fonts/` under the SIL Open Font License (`fonts/OFL.txt`), because the page's security policy only allows fonts from the same site.

## Shared Save setup

The matching Cloudflare Worker is in `cloudflare-api/` in this repository and is deployed at `https://job-tracker-api.mmarcdarenz.workers.dev`. The frontend points to it through `cloud-config.js`. It stores the shared tracker snapshot in D1 under a version guard and new attachment bytes in private R2. Edits are shared for everyone with the code; stale concurrent edits get a conflict instead of overwriting newer work. On a cloud failure, Save does not silently fall back to this browser.

**Shared Save is active.** The Worker deployment verified authenticated reading, historical records and a version-checked write. An Export JSON backup remains available; a browser with older local edits can export its previous browser backup and import it into the cloud with current records retained. Inline attachment bytes in old backups are uploaded to R2 during import.

The six-digit code is only a modest shared credential. The Cloudflare Worker checks it on each API request and throttles wrong attempts, but the public GitHub repository's `data.json`, original PDFs and source remain directly downloadable. New R2 uploads require the Worker code. Do not publish private documents to the public repository or call this a private account system.

## Records and provenance

The initial published `data.json` includes 14 automatic applications, 46 leads, three manual records, 11 Bin visibility records and 26 PDFs from the old tracker. `archive/` holds migration evidence. Two old manual-upload PDFs were unavailable in the read-only export; their filenames and checksums are retained and labelled unavailable. Three oversized Bin snapshots were truncated, but their current rows and Bin metadata remain. The canonical job journal was inaccessible during migration and is not replaced by this snapshot.

**Applied** records an actual submission reported by Jeremie through SEEK or an employer website. It asks for actual date and route, and can attach a résumé, cover letter or confirmation. Saving a row never submits an application. Automatic sent history remains distinct from contributor-reported outcomes. Expired rows are hidden from the active view. The activity chart (14 days, 28 days, or 13 weeks) counts sent or reported applications with dates, the pipeline shows current status counts, application routes group recorded applications by how they were submitted, and fit distribution is qualitative, not an interview forecast.

The old owner-private Site is unchanged. This frontend does not send email. The existing two-hour discovery worker was resumed by the owner on 28 September 2026 and must update this GitHub Pages tracker through the guarded shared Cloudflare state. The separate lead reviewer remains stopped. `AGENTS.md` describes the application safeguards. New automatic leads need a version-guarded publication path: changing public `data.json` alone does not change the live cloud state.

## Publishing and preview

The GitHub Actions workflow deploys `main` to GitHub Pages. Source edits should be committed through an authorised GitHub connection, never by exposing a GitHub token to the browser. Preview locally with `python3 -m http.server 8000`, then open `http://localhost:8000`. Use `cloudflare-api/README.md` for Worker deployment steps. After any API change, verify that a save and upload appear in another browser and a stale concurrent Save reports a conflict.
