# Marc job tracker API

Cloudflare Worker API for the [GitHub Pages tracker](https://macdarenz-droid.github.io/Job-tracker/). D1 stores the shared tracker with a version guard: one row per record since migration `0002` (see "Storage" below), one JSON document before it. R2 stores new attachments privately. The original public `data.json` and bundled PDFs remain in GitHub Pages; the initial D1 snapshot is pinned in `src/seed.js` so first deployment starts with every existing record, manual entry and Bin item. The initial repository's `/api/jobs` code and schema are retained under `archive/`; they are not deployed or run.

The Worker shown in Marc's Cloudflare screenshots on 27 September 2026 is the **older `/api/jobs` API with no authentication**. Its live D1 `jobs`/`files` tables may hold edits not present in GitHub Pages. On first `/api/state` read, this Worker copies those legacy jobs to manual tracker records and preserves their attachment references via authenticated `/api/legacy-files/:id`. It does not delete the source tables or R2 objects. Do not point `cloud-config.js` at that URL until this updated Worker and the server-side access code are deployed and verified.

## One-time Cloudflare setup

### From a phone using GitHub Actions

The repository has a [guarded Upgrade existing tracker API](https://github.com/macdarenz-droid/Job-tracker/actions/workflows/deploy-tracker-api.yml) workflow. It reads this `cloudflare-api/` directory and deploys the existing Worker without pasting source files into the dashboard editor. In the Cloudflare dashboard, create an API token scoped to the account with **Workers Scripts Edit** and **D1 Edit** permissions. In the GitHub repository's Settings → Secrets and variables → Actions, add `CLOUDFLARE_API_TOKEN` and `TRACKER_ACCESS_CODE` (the existing six-digit code). Never put either value in source, a workflow input, a screenshot or a chat message. Run the manual workflow from Actions for initial setup. Later source changes to this Worker trigger the same guarded deployment workflow automatically.

The workflow discovers the existing D1 ID by its exact name, verifies the production database, captures a Time Travel recovery bookmark, checks old `jobs` and `files` counts, runs the additive migrations, checks that every table the migrations create exists and that no old row is gone, sets the Worker secret, deploys the same Worker, gives each record its own row (the `backfill` step, see "Storage"), and tests authentication, imported history and a harmless version-checked Save. If any preflight fails, it stops before changing D1 or Worker code. It does not switch on the GitHub Pages cloud adapter; connect that only after the completed workflow and a second-browser check are reviewed. The prefilled Cloudflare account ID came from the existing Worker's dashboard URL; an incorrect account fails at D1 discovery.

Do not paste `src/index.js` alone into the Cloudflare dashboard editor. It imports `src/seed.js`, so that single-file action would break the Worker. The old agent's `src/index.ts` path refers to the archived starter, not this upgrade.

### From a computer with Wrangler

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

## Storage: one row per record

Until 13 November 2026 the whole tracker was one JSON string in one D1 row (`tracker_state`, id 1). D1 allows 2,000,000 bytes per string or row and the Worker refused a tracker over 1,800,000 bytes, so on 17 October 2026 it filled up and every new record got HTTP 413. Raising the number could not help. Migration `0002_records.sql` adds two tables, and nothing else:

- `records`: one row per manual record (`id`, `position`, `version`, `summary`, `body`). `body` is the record's JSON text exactly as a client saved it. `summary` is the slim list entry, stored ready-made so a list is served without opening any record. `version` is that record's own guard.
- `tracker_state_backup`: the untouched single document as it was at the moment of the copy, keyed by its version.

The Worker has two storage modes and serves the same `/api/state` in both:

- **document** (before the copy): exactly the old behaviour, including the 1.8 MB limit. The per-record routes answer 409 "not active".
- **rows** (after the copy): `tracker_state` keeps everything that is not a manual record (the frozen `applications` and `leads`, the Bin, notes; roughly 120 KB), marked by a fixed prefix, and each manual record is a row. The tracker as a whole has no size limit any more. One record may be up to 200,000 bytes, the remainder up to 1,800,000 bytes, and one request may write up to 1,800,000 bytes.

`POST /api/admin/backfill` (same access code; optional `{expected_version}`) moves from the first mode to the second. It saves the untouched payload to `tracker_state_backup`, writes each manual entry as a row in D1 batches of 40 (each statement applies only while the tracker is still that version of the single document), reads every row back and compares it byte for byte, then switches with one guarded `UPDATE` that applies only if the version has not moved, the document is still the one in the backup table and the row count is the one just compared. The whole-tracker version does not change. Until that last statement nothing a client reads has changed, so a failure at any earlier point leaves the single document serving; running it again is safe and brings rows from an interrupted run up to date. `POST /api/admin/restore-document` with `{expected_version}` puts the saved document back; it is refused once anything has been saved in rows mode (every such save moves the version).

The deploy workflow does this itself (`node scripts/deploy-checks.mjs backfill`, after the Worker is deployed): it reads the tracker, calls the copy with that version, reads the tracker and the record list again, and requires the same version and deep-equal content. If they differ it calls `restore-document` and fails the job. On later runs it reports "nothing to copy". The Actions log is public, so the step prints counts and version numbers only.

### Cloudflare Free plan limits

The owner's account is on the free plans: 50 D1 queries per Worker invocation (a `batch()` counts as one), 100 bound parameters per query, 100,000 bytes per SQL statement, 2,000,000 bytes per string or row, 10 ms of CPU per request. D1 queries per request, including the one access-code lookup (one more `DELETE` when the caller's address had a failed attempt on record):

| Request | single document | one row per record |
|---|---|---|
| `GET /api/state` | 2 | 3 (the second read is one batch, so version and rows belong together) |
| `PUT /api/state` | 3 | 4 |
| `GET /api/version` | 2 | 2 |
| `GET /api/records`, `GET /api/records/<id>` | 2 (answers 409) | 2 |
| `POST /api/records` | 2 (answers 409) | 3 |
| `PATCH /api/records/<id>` | 2 (answers 409) | 3 |
| `POST /api/admin/backfill` | 5 + one per 40 records (16 for 403 records; never more than 45) | 3 |
| `POST /api/admin/restore-document` | 2 | 3 |
| `POST /api/documents`, `GET /api/documents/<id>` | 2 | 2 |
| any route with a wrong code | 2 (1 when throttled) | the same |

The longest SQL statement is 332 bytes and the most bound parameters is 50 (the id lookup of a 50-record `POST`). Reads in rows mode join stored JSON text: `GET /api/state`, `GET /api/records`, `GET /api/records/<id>` and `GET /api/version` parse and re-serialise nothing, and `PATCH` opens one record. The kept `PUT /api/state` still has to read the whole request, so its cost grows with the tracker; it is there so existing clients keep working, and new code should use the per-record routes.

### Rolling back

- Before the copy has run: revert the commit and redeploy. The data has not changed; the two new tables are simply unused.
- After the copy, before anything else has been saved: `POST /api/admin/restore-document` with the current version, then redeploy the older Worker if wanted. The rows stay in `records` and are ignored.
- After records have been saved in rows mode: fix forward. An older Worker would read `tracker_state` and show no manual records, so do not deploy one. Nothing in this design deletes a row. The pre-copy document stays in `tracker_state_backup`, and the workflow prints a D1 Time Travel bookmark before each migration (7 days on the free plan).

## API behavior

- `GET /api/state` returns `{version,state}` and seeds D1 from the pinned public snapshot once. In rows mode `state.updated_at` is the time of the last save of any kind.
- `PUT /api/state` requires `{expected_version,state}`. A stale version gets 409, so one editor cannot silently erase another's save. Historical automatic applications/leads, manual IDs, document references and Bin keys cannot be removed through this endpoint. Editing a row creates a manual overlay. In rows mode the same checks apply and only the records whose JSON changed are written (a save that changes one record among hundreds writes one row); new records are appended, and the order of existing records cannot be changed.
- `GET /api/version` returns `{version,updated_at,storage}` (`storage` is `document` or `rows`). The page polls this instead of downloading the tracker.
- `GET /api/records` returns `{version,updated_at,records}`: one slim entry per manual record with `id`, `version` (the record's own), `company`, `role`, `location`, `status`, `route`, `closes_at`, `fit_percent`, `updated_at`, `files`, and, when the record has them, `key`, `job_url`, `duplicate_key`, `origin_key`, `seek_id`, `applied_date`, `sent_at`, `checked_at`, `created_at`, `created_by`, `contributor_name`, `application_method`. `route` is the record's `application_route` (or `route`), `closes_at` its `closes_at` (or `advert.expires_at`), `fit_percent` its `match_score.percent`. It does not know about the Bin; that is in `state.record_visibility`.
- `GET /api/records/<id>` returns `{version,record}`. URL-encode the id.
- `POST /api/records` takes `{records:[...]}` (1 to 50) or `{record:{...}}` and appends them. Each needs a text `id`, `company` and `role`; attachments must already be uploaded. If any id already exists the answer is 409 with `existing_ids` and nothing is added. It needs no whole-tracker version, so it never collides with someone else's save. Success is 201 `{added:[ids]}`.
- `PATCH /api/records/<id>` takes `{expected_version,patch}`, where `expected_version` is that record's `version` from the list or from a read. The patch's fields replace the record's (`id`, `key`, `created_at` and `created_by` are ignored), existing document references must stay, and the Worker sets `updated_at` and adds one to the record's own `version` field. A stale version gets 409 with `current_version` and changes nothing. Success returns `{version,record}`.
- Every `POST /api/records` and `PATCH` also moves the whole-tracker version, so the page and whole-tracker clients notice the change (and a whole-tracker save made from an older copy gets 409 instead of overwriting it).
- `POST /api/documents` accepts up to 10 MB of PDF, DOCX, PNG or JPEG bytes with `X-Filename` (URL encoded) and `X-Doc-Kind` (`resume`, `cover`, `confirmation`). It returns metadata and a private `/api/documents/:id` path. The separate state save adds that reference to the record.
- `GET /api/documents/:id` returns the bytes after code verification. Every request carries `X-Tracker-Code`. The frontend keeps the code in memory during the unlocked tab only.
- `GET /api/legacy-files/:id` serves old `/api/jobs` attachments from the same R2 bucket after code verification. The original D1 tables and R2 objects remain intact.

If cloud Save fails, the frontend does **not** pretend that an IndexedDB fallback was shared. Previous browser-only edits are exportable as a separate backup after cloud setup; import merges them with current cloud records and uploads inline attachment bytes. Review any conflicts and ensure a backup exists before removing local browser data.

## Tests

`npm test` (Node 22.13 or later, offline) checks initial record preservation, version conflicts, code throttling and attachment bytes with a D1/R2 test double (`tests/api.test.js`, unchanged from before the migration). `tests/records.test.js` runs the Worker on `tests/d1sqlite.js`, a D1 stand-in on a real SQLite engine that enforces the free-plan numbers above on every request: the copy (lossless, repeatable, guarded against a save in the middle), growth past 2 MB, per-record version conflicts, refusal to drop records or documents, a one-record change among 400 writing one row, the code on every route, and a failure log with no record content. `tests/deploy-backfill.test.js` runs the workflow's own checks against the Worker on this machine. The stand-in is not D1: the size of one `batch()` request (up to about 1.8 MB here), the CPU limit and real network behaviour are only exercised by the deploy workflow itself. `npm run db:migrate:local` applies the schema to Wrangler's local database. Local `wrangler dev` may be unavailable in restricted execution environments; deployment and two-browser verification still require the account setup above.

## Automated research updates

The existing discovery worker writes only public, dated findings into `../research/lead-updates.json`. A separate GitHub Action uses the existing `TRACKER_ACCESS_CODE` secret to GET the latest state and PUT an append-only lead batch under `expected_version`; it verifies the result with a second GET. Existing applications, manual entries, documents and Bin records remain unchanged. Existing leads may only change status/check evidence; closures require an official HTTPS evidence URL and check date. The action refuses an equivalent record, stale research (over 48 hours), and conflicts. It does not send job applications and does not commit the code or Cloudflare API token.
