import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync, mkdirSync, writeFileSync, readFileSync, chmodSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {spawnSync} from 'node:child_process';

const checks = resolve('scripts/deploy-checks.mjs');
const originalConfig = readFileSync('wrangler.jsonc', 'utf8');

function fixture(duplicate=false) {
  const dir = mkdtempSync(join(tmpdir(), 'tracker-deploy-'));
  mkdirSync(join(dir, 'node_modules/.bin'), {recursive:true});
  writeFileSync(join(dir, 'wrangler.jsonc'), originalConfig);
  const cli = `#!/usr/bin/env node
const fs=require('node:fs');
const args=process.argv.slice(2),sql=args[args.indexOf('--command')+1]||'';
const migrated=fs.existsSync('.migrated');
if(args.join(' ').startsWith('d1 list')) console.log(JSON.stringify([{
  name:'job-tracker-db',uuid:'12345678-1234-1234-1234-123456789abc',version:'production'
}${duplicate?",{name:'job-tracker-db',uuid:'abcdefab-1234-1234-1234-123456789abc',version:'production'}":''}]));
else if(args.join(' ').startsWith('d1 time-travel info')) console.log('Current recovery bookmark: 00000085-0000024c');
else if(sql.includes('sqlite_master')) console.log(JSON.stringify([{results:[{name:'jobs'},{name:'files'},...(migrated?[{name:'tracker_state'},{name:'document_index'},{name:'auth_attempts'}]:[])]}]));
else if(sql.includes('LEFT JOIN')) console.log(JSON.stringify([{results:[{count:0}]}]));
else if(sql.includes('COUNT(*)')) console.log(JSON.stringify([{results:[{count:1}]}]));
else throw Error('Unrecognised fixture query: '+sql);
`;
  const path = join(dir, 'node_modules/.bin/wrangler');
  writeFileSync(path, cli); chmodSync(path, 0o755);
  const env = {...process.env,RUNNER_TEMP:dir,CLOUDFLARE_ACCOUNT_ID:'test-account',CLOUDFLARE_API_TOKEN:'fixture-token',TRACKER_ACCESS_CODE:'654321'};
  const run = mode => spawnSync(process.execPath, [checks, mode], {cwd:dir,env,encoding:'utf8'});
  return {dir,run};
}

test('deployment preflight finds the existing D1, saves counts and checks additive migration',()=>{
  const {dir,run}=fixture();
  try {
    const before=run('prepare');
    assert.equal(before.status,0,before.stderr);
    assert.match(before.stdout,/1 jobs, 1 files/);
    const config=JSON.parse(readFileSync(join(dir,'wrangler.jsonc'),'utf8'));
    assert.equal(config.d1_databases[0].database_id,'12345678-1234-1234-1234-123456789abc');
    assert.equal(config.r2_buckets[0].bucket_name,'job-tracker-files');
    writeFileSync(join(dir,'.migrated'),'');
    assert.equal(run('after-migration').status,0);
  } finally { rmSync(dir,{recursive:true,force:true}); }
});

test('ambiguous D1 name stops before config or database change',()=>{
  const {dir,run}=fixture(true);
  try {
    const result=run('prepare');
    assert.equal(result.status,1);
    assert.match(result.stderr,/exactly one existing/);
    assert.equal(readFileSync(join(dir,'wrangler.jsonc'),'utf8'),originalConfig);
  } finally { rmSync(dir,{recursive:true,force:true}); }
});
