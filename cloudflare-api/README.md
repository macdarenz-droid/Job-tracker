# Marc job tracker API

Cloudflare Worker API for the [GitHub Pages tracker](https://macdarenz-droid.github.io/Job-tracker/). D1 stores the shared tracker snapshot with a version guard. R2 stores new attachments privately. The original public `data.json` and bundled PDFs remain in GitHub Pages; the initial D1 snapshot is pinned in `src/seed.js` so first deployment starts with every existing record, manual entry and Bin item. The initial repository's `/api/jobs` code and schema are retained under `archive/`; they are not deployed or run.

The Worker shown in Marc's Cloudflare screenshots on 27 September 2026 is the **older `/api/jobs` API with no authentication**. Its live D1 `jobs`/`files` tables may hold edits not present in GitHub Pages. On first `/api/state` read, this Worker copies those legacy jobs to manual tracker records and preserves their attachment references via authenticated `/api/legacy-files/:id`. It does not delete the source tables or R2 objects. Do not point `cloud-config.js` at that URL until this updated Worker and the server-side access code are deployed and verified.

## One-time Cloudflare setup

Run these commands on a computer where you can sign into your Cloudflare account. Do not send an API token or passcode in chat or commit either to git. First inspect and export the **existing** database, then use that exact database ID in `wrangler.jsonc`:

```bash
npm ci
npx wrangler login
npx wrangler d1 list
npx wrangler r2 bucket list
npx wrangler d1 execute job-tracker-db --remote --command="SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
npx wrangler d1 export job-tracker-db --remote --output=./before-tracker-upgrade.sql
```

Keep the SQL export private; it may contain personal records. Copy the existing `database_id` into `wrangler.jsonc`, replacing `YOUR_D1_DATABASE_ID`. The existing `job-tracker-files` R2 bucket must be bound as `DOCUMENTS` to keep the old file objects reachable. If a resource name differs, use the actual existing name; do not create a second D1 database or bucket and do not delete old tables. Then:

```bash
npm run db:migrate:remote
npx wrangler secret put ACCESS_CODE
npm run deploy
```

At the secret prompt, enter the shared six-digit code. Copy the resulting `https://…workers.dev` URL into the frontend repository's `cloud-config.js` as `window.TRACKER_API_URL`, commit that one-time configuration, and let GitHub Pages redeploy. From then on, Save writes to D1 and new attachment bytes go to R2 for every visitor with the code. Do a two-browser save/read test before treating it as live. `GET /api/state` without the code must return 401.

Before changing the frontend, check that `GET /api/state` with the code includes the baseline 14 applications, 46 leads, 3 manual entries and 11 Bin entries **plus any imported legacy jobs**. Compare the legacy `jobs` and `files` counts against the imported entries and document references. Verify one old attachment download if present, and verify an authenticated edit from one browser appears in another. If the import does not match, keep the frontend in browser-only mode and restore/inspect from the SQL export instead of continuing.

The Worker allows browser requests only from `https://macdarenz-droid.github.io`; local development may set `ALLOWED_DEV_ORIGIN=http://localhost:8000` in ignored `.dev.vars`. Set `ACCESS_CODE` there as well for local testing. The six-digit code is a limited shared credential, not a strong account system. Five failed requests per IP in 15 minutes are throttled. The public GitHub `data.json` and old bundled PDFs remain directly downloadable, regardless of this API code.

## API behavior

- `GET /api/state` returns `{version,state}` and seeds D1 from the pinned public snapshot once.
- `PUT /api/state` requires `{expected_version,state}`. A stale version gets 409, so one editor cannot silently erase another's save. Historical automatic applications/leads, manual IDs, document references and Bin keys cannot be removed through this endpoint. Editing a row creates a manual overlay.
- `POST /api/documents` accepts up to 10 MB of PDF, DOCX, PNG or JPEG bytes with `X-Filename` (URL encoded) and `X-Doc-Kind` (`resume`, `cover`, `confirmation`). It returns metadata and a private `/api/documents/:id` path. The separate state save adds that reference to the record.
- `GET /api/documents/:id` returns the bytes after code verification. Every request carries `X-Tracker-Code`. The frontend keeps the code in memory during the unlocked tab only.
- `GET /api/legacy-files/:id` serves old `/api/jobs` attachments from the same R2 bucket after code verification. The original D1 tables and R2 objects remain intact.

If cloud Save fails, the frontend does **not** pretend that an IndexedDB fallback was shared. Previous browser-only edits are exportable as a separate backup after cloud setup; import merges them with current cloud records and uploads inline attachment bytes. Review any conflicts and ensure a backup exists before removing local browser data.

## Tests

`npm test` checks initial record preservation, version conflicts, code throttling and attachment bytes with a D1/R2 test double. `npm run db:migrate:local` applies the schema to Wrangler's local database. Local `wrangler dev` may be unavailable in restricted execution environments; deployment and two-browser verification still require the account setup above.
