# Marc's job tracker

The GitHub Pages frontend for Marc's Australian job search: [open the tracker](https://macdarenz-droid.github.io/Job-tracker/). It has a shared-code screen gate, Applications/Ready/Leads, six-row grouped Table mode, continuous Scroll mode, an Applied action with the actual date and route, optional files, outcomes, Bin, search and progress charts. The restrained dark workspace and subtle motion draw on Linear's [interface refresh](https://linear.app/now/behind-the-latest-design-refresh), Vercel's [dashboard navigation](https://vercel.com/changelog/dashboard-navigation-redesign-rollout), Height's [in-context editing](https://height.app/blog/whats-new-gantt-charts-0-104) and Attio's [records and reports](https://attio.com/help/reference/managing-your-data/dashboard-and-reports/dashboards); no design assets or templates were copied.

## Shared Save setup

The matching Cloudflare Worker is in `cloudflare-api/` in this repository and is deployed at `https://job-tracker-api.mmarcdarenz.workers.dev`. The frontend points to it through `cloud-config.js`. It stores the shared tracker snapshot in D1 under a version guard and new attachment bytes in private R2. Edits are shared for everyone with the code; stale concurrent edits get a conflict instead of overwriting newer work. On a cloud failure, Save does not silently fall back to this browser.

**Shared Save is active.** The Worker deployment verified authenticated reading, historical records and a version-checked write. An Export JSON backup remains available; a browser with older local edits can export its previous browser backup and import it into the cloud with current records retained. Inline attachment bytes in old backups are uploaded to R2 during import.

The six-digit code is only a modest shared credential. The Cloudflare Worker checks it on each API request and throttles wrong attempts, but the public GitHub repository's `data.json`, original PDFs and source remain directly downloadable. New R2 uploads require the Worker code. Do not publish private documents to the public repository or call this a private account system.

## Records and provenance

The initial published `data.json` includes 14 automatic applications, 46 leads, three manual records, 11 Bin visibility records and 26 PDFs from the old tracker. `archive/` holds migration evidence. Two old manual-upload PDFs were unavailable in the read-only export; their filenames and checksums are retained and labelled unavailable. Three oversized Bin snapshots were truncated, but their current rows and Bin metadata remain. The canonical job journal was inaccessible during migration and is not replaced by this snapshot.

**Applied** records an actual submission reported by Jeremie through SEEK or an employer website. It asks for actual date and route, and can attach a résumé, cover letter or confirmation. Saving a row never submits an application. Automatic sent history remains distinct from contributor-reported outcomes. Expired rows are hidden from the active view. The 28-day activity bars include sent or reported applications with dates, the pipeline shows current status counts, and fit distribution is qualitative, not an interview forecast.

The old owner-private Site is unchanged. This frontend does not send email or enable the stopped job-research workers. `AGENTS.md` describes the rules for a separately authorised job agent.

## Publishing and preview

The GitHub Actions workflow deploys `main` to GitHub Pages. Source edits should be committed through an authorised GitHub connection, never by exposing a GitHub token to the browser. Preview locally with `python3 -m http.server 8000`, then open `http://localhost:8000`. Use `cloudflare-api/README.md` for Worker deployment steps. After any API change, verify that a save and upload appear in another browser and a stale concurrent Save reports a conflict.
