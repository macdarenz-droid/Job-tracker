import { Hono } from 'hono';

export interface Env {
  FILES_BUCKET: R2Bucket;
  DB: D1Database;
}

interface JobRow {
  id: number;
  company: string;
  title: string;
  status: string;
  salary: string | null;
  location: string | null;
  url: string | null;
  notes: string | null;
  applied_date: string;
  created_at: string;
  updated_at: string;
}

interface FileRow {
  id: number;
  job_id: number;
  filename: string;
  r2_key: string;
  content_type: string | null;
  size: number | null;
  created_at: string;
}

const app = new Hono<{ Bindings: Env }>();

// ─── Health check ───────────────────────────────────────────
app.get('/', (c) => c.json({ status: 'ok', service: 'job-tracker-api' }));

// ─── Jobs ──────────────────────────────────────────────────

// List all jobs
app.get('/api/jobs', async (c) => {
  const results = await c.env.DB.prepare(
    'SELECT * FROM jobs ORDER BY applied_date DESC'
  ).all<JobRow>();
  return c.json(results.results);
});

// Get single job
app.get('/api/jobs/:id', async (c) => {
  const job = await c.env.DB.prepare('SELECT * FROM jobs WHERE id = ?')
    .bind(c.req.param('id'))
    .first<JobRow>();
  if (!job) return c.json({ error: 'Job not found' }, 404);
  return c.json(job);
});

// Create job
app.post('/api/jobs', async (c) => {
  const { company, title, status, salary, location, url, notes } = await c.req.json();
  if (!company || !title) return c.json({ error: 'company and title are required' }, 400);

  const result = await c.env.DB.prepare(
    `INSERT INTO jobs (company, title, status, salary, location, url, notes)
     VALUES (?, ?, ?, ?, ?, ?, ?)`
  )
    .bind(company, title, status || 'applied', salary || null, location || null, url || null, notes || null)
    .run();

  const newJob = await c.env.DB.prepare('SELECT * FROM jobs WHERE id = ?')
    .bind(result.meta.last_row_id)
    .first<JobRow>();
  return c.json(newJob, 201);
});

// Update job
app.put('/api/jobs/:id', async (c) => {
  const id = c.req.param('id');
  const { company, title, status, salary, location, url, notes } = await c.req.json();

  const result = await c.env.DB.prepare(
    `UPDATE jobs SET
       company = COALESCE(?, company),
       title = COALESCE(?, title),
       status = COALESCE(?, status),
       salary = COALESCE(?, salary),
       location = COALESCE(?, location),
       url = COALESCE(?, url),
       notes = COALESCE(?, notes),
       updated_at = datetime('now')
     WHERE id = ?`
  )
    .bind(company ?? null, title ?? null, status ?? null, salary ?? null, location ?? null, url ?? null, notes ?? null, id)
    .run();

  if (result.meta.changes === 0) return c.json({ error: 'Job not found' }, 404);
  const updated = await c.env.DB.prepare('SELECT * FROM jobs WHERE id = ?').bind(id).first<JobRow>();
  return c.json(updated);
});

// Delete job (also removes files from R2)
app.delete('/api/jobs/:id', async (c) => {
  const id = c.req.param('id');

  const files = await c.env.DB.prepare('SELECT r2_key FROM files WHERE job_id = ?')
    .bind(id)
    .all<{ r2_key: string }>();

  for (const file of files.results) {
    await c.env.FILES_BUCKET.delete(file.r2_key);
  }

  await c.env.DB.prepare('DELETE FROM files WHERE job_id = ?').bind(id).run();
  await c.env.DB.prepare('DELETE FROM jobs WHERE id = ?').bind(id).run();

  return c.json({ success: true });
});

// ─── Files ─────────────────────────────────────────────────

// List files for a job
app.get('/api/jobs/:id/files', async (c) => {
  const results = await c.env.DB.prepare(
    'SELECT * FROM files WHERE job_id = ? ORDER BY created_at DESC'
  )
    .bind(c.req.param('id'))
    .all<FileRow>();
  return c.json(results.results);
});

// Upload file to a job
app.post('/api/jobs/:id/files', async (c) => {
  const jobId = c.req.param('id');

  const job = await c.env.DB.prepare('SELECT id FROM jobs WHERE id = ?').bind(jobId).first();
  if (!job) return c.json({ error: 'Job not found' }, 404);

  const formData = await c.req.formData();
  const file = formData.get('file') as File;
  if (!file) return c.json({ error: 'No file provided' }, 400);

  const r2Key = `jobs/${jobId}/${Date.now()}-${file.name}`;

  await c.env.FILES_BUCKET.put(r2Key, file.stream(), {
    httpMetadata: { contentType: file.type || 'application/octet-stream' },
  });

  const result = await c.env.DB.prepare(
    'INSERT INTO files (job_id, filename, r2_key, content_type, size) VALUES (?, ?, ?, ?, ?)'
  )
    .bind(jobId, file.name, r2Key, file.type || null, file.size)
    .run();

  const fileRow = await c.env.DB.prepare('SELECT * FROM files WHERE id = ?')
    .bind(result.meta.last_row_id)
    .first<FileRow>();
  return c.json(fileRow, 201);
});

// Download a file
app.get('/api/files/:fileId/download', async (c) => {
  const fileRow = await c.env.DB.prepare('SELECT * FROM files WHERE id = ?')
    .bind(c.req.param('fileId'))
    .first<FileRow>();
  if (!fileRow) return c.json({ error: 'File not found' }, 404);

  const object = await c.env.FILES_BUCKET.get(fileRow.r2_key);
  if (!object) return c.json({ error: 'Object not found in R2' }, 404);

  const headers = new Headers();
  object.writeHttpMetadata(headers);
  headers.set('Content-Disposition', `attachment; filename="${fileRow.filename}"`);

  return new Response(object.body, { headers });
});

// Delete a file
app.delete('/api/files/:fileId', async (c) => {
  const fileRow = await c.env.DB.prepare('SELECT * FROM files WHERE id = ?')
    .bind(c.req.param('fileId'))
    .first<FileRow>();
  if (!fileRow) return c.json({ error: 'File not found' }, 404);

  await c.env.FILES_BUCKET.delete(fileRow.r2_key);
  await c.env.DB.prepare('DELETE FROM files WHERE id = ?').bind(c.req.param('fileId')).run();

  return c.json({ success: true });
});

export default app;
