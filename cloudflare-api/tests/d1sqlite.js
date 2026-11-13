// A D1 stand-in backed by a real SQLite engine (node:sqlite), so the SQL, the transactions and the guards really run.
// It refuses what Cloudflare documents D1 as refusing on the Workers Free plan and counts queries the way D1 does
// (a batch is one query). It is not D1: see README "Tests" for what it cannot show.
import {DatabaseSync} from 'node:sqlite';
import {readFileSync, readdirSync} from 'node:fs';

export const LIMITS = {queries: 50, statementBytes: 100_000, parameters: 100, valueBytes: 2_000_000};

export function makeD1(migrationsDir) {
  const db = new DatabaseSync(':memory:');
  // Twice, because every migration has to be safe to apply again.
  for (let pass = 0; pass < 2; pass++)
    for (const file of readdirSync(migrationsDir).filter(name => name.endsWith('.sql')).sort()) db.exec(readFileSync(migrationsDir + '/' + file, 'utf8'));
  const fresh = () => ({queries: 0, batches: 0, statements: 0, writes: [], largestStatement: 0, mostParameters: 0, largestValue: 0, largestBatch: 0});
  const counters = fresh();
  const check = (sql, args) => {
    let bytes = 0;
    for (const value of args) {
      if (value === undefined) throw Error('D1_TYPE_ERROR: undefined is not a bindable value');
      if (typeof value === 'string') bytes += Buffer.byteLength(value);
    }
    counters.statements++;
    counters.largestStatement = Math.max(counters.largestStatement, Buffer.byteLength(sql));
    counters.mostParameters = Math.max(counters.mostParameters, args.length);
    counters.largestValue = Math.max(counters.largestValue, bytes);
    if (Buffer.byteLength(sql) > LIMITS.statementBytes) throw Error('D1 limit: SQL statement longer than 100,000 bytes');
    if (args.length > LIMITS.parameters) throw Error('D1 limit: more than 100 bound parameters');
    if (bytes > LIMITS.valueBytes) throw Error('D1 limit: string or row larger than 2,000,000 bytes');
    return bytes;
  };
  const query = () => { if (++counters.queries > LIMITS.queries) throw Error('D1 limit: more than 50 queries in one Worker invocation'); };
  const execute = (sql, args) => {
    const prepared = db.prepare(sql);
    if (/^\s*(SELECT|WITH)\b/i.test(sql)) return {success: true, results: prepared.all(...args), meta: {changes: 0}};
    const changes = Number(prepared.run(...args).changes);
    counters.writes.push({sql, changes});
    return {success: true, results: [], meta: {changes}};
  };
  const statement = (sql, args = []) => ({
    sql, args,
    bind(...values) { return statement(sql, values); },
    async first() { query(); check(sql, args); return db.prepare(sql).get(...args) ?? null; },
    async all() { query(); check(sql, args); return execute(sql, args); },
    async run() { query(); check(sql, args); return execute(sql, args); }
  });
  const DB = {
    prepare: sql => statement(sql),
    async batch(list) {
      query(); counters.batches++;
      counters.largestBatch = Math.max(counters.largestBatch, list.reduce((sum, item) => sum + check(item.sql, item.args), 0));
      db.exec('BEGIN');
      try {
        const out = list.map(item => execute(item.sql, item.args));
        db.exec('COMMIT');
        return out;
      } catch (cause) { db.exec('ROLLBACK'); throw cause; }
    }
  };
  // Call at the start of each request: the limits are per Worker invocation.
  const invocation = () => Object.assign(counters, fresh());
  return {DB, db, counters, invocation};
}
