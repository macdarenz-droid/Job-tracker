import test from 'node:test';
import assert from 'node:assert/strict';
import api from '../src/index.js';

function environment({legacyJobs=[],legacyFiles=[]}={}) {
  const rows = {state: null, docs: new Map(), attempts: new Map(), objects: new Map(), legacyJobs, legacyFiles};
  const DB = {prepare(sql) {let args=[];return {
    bind(...values){args=values;return this},
    async all(){
      if(sql.includes('FROM sqlite_master'))return {results:legacyJobs.length?[{name:'jobs'},{name:'files'}]:[]};
      if(sql.startsWith('SELECT * FROM jobs'))return {results:rows.legacyJobs};
      if(sql.startsWith('SELECT * FROM files'))return {results:rows.legacyFiles};
      throw Error('Unexpected list: '+sql);
    },
    async first(){
      if(sql.includes('FROM auth_attempts'))return rows.attempts.get(args[0])||null;
      if(sql.includes('FROM tracker_state'))return rows.state;
      if(sql.includes('FROM document_index'))return rows.docs.get(args[0])||null;
      if(sql.includes('FROM files'))return rows.legacyFiles.find(file=>String(file.id)===String(args[0]))||null;
      throw Error('Unexpected read: '+sql);
    },
    async run(){
      if(sql.startsWith('INSERT OR IGNORE INTO tracker_state')){if(!rows.state)rows.state={version:1,payload:args[0],updated_at:args[1]};return {meta:{changes:1}}}
      if(sql.startsWith('UPDATE tracker_state')){if(rows.state?.version!==args[2])return {meta:{changes:0}};rows.state={version:rows.state.version+1,payload:args[0],updated_at:args[1]};return {meta:{changes:1}}}
      if(sql.startsWith('INSERT INTO document_index')){rows.docs.set(args[0],{object_key:args[1],filename:args[2],mime_type:args[3]});return {meta:{changes:1}}}
      if(sql.startsWith('INSERT INTO auth_attempts')){const previous=rows.attempts.get(args[0]);rows.attempts.set(args[0],{window_start:args[1],failures:previous?.window_start===args[1]?previous.failures+1:1});return {meta:{changes:1}}}
      if(sql.startsWith('DELETE FROM auth_attempts')){rows.attempts.delete(args[0]);return {meta:{changes:1}}}
      throw Error('Unexpected write: '+sql);
    }
  }}};
  const DOCUMENTS={async put(key,bytes){rows.objects.set(key,bytes)},async get(key){const value=rows.objects.get(key);return value?new Response(value):null},async delete(key){rows.objects.delete(key)}};
  return {env:{DB,DOCUMENTS,ACCESS_CODE:'654321',ALLOWED_ORIGIN:'https://macdarenz-droid.github.io'},rows};
}

const request=(path,options={})=>new Request('https://tracker.example'+path,{...options,headers:{Origin:'https://macdarenz-droid.github.io','X-Tracker-Code':'654321',...options.headers}});

test('authorised state is seeded and concurrent stale writes cannot erase another editor',async()=>{
  const {env}=environment();
  const initial=await api.fetch(request('/api/state'),env);
  assert.equal(initial.status,200);
  const {version,state}=await initial.json();
  assert.equal(version,1);assert.equal(state.applications.length,14);assert.equal(state.manual_entries.length,3);
  state.manual_entries.push({id:'new',company:'Example',role:'Junior civil',status:'MANUAL_APPLIED',attachments:[]});
  const write=()=>api.fetch(request('/api/state',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({expected_version:version,state})}),env);
  assert.equal((await write()).status,200);
  const stale=await write();assert.equal(stale.status,409);
  const current=await (await api.fetch(request('/api/state'),env)).json();
  assert.equal(current.version,2);assert.equal(current.state.manual_entries.at(-1).company,'Example');
  current.state.applications=[];
  const invalid=await api.fetch(request('/api/state',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({expected_version:2,state:current.state})}),env);
  assert.equal(invalid.status,400);
});

test('new research leads append under a version guard without changing older evidence',async()=>{
  const {env}=environment();
  const initial=await (await api.fetch(request('/api/state'),env)).json();
  const next=structuredClone(initial.state);
  const lead={key:'example.test|graduate-civil-2026-09-28',company:'Example Civil',role:'Graduate Civil Engineer',
    status:'READY_FOR_JEREMIE',checked_at:'2026-09-28T01:00:00Z',job_url:'https://example.test/careers/graduate',
    application_type:'ADVERTISED_VACANCY',application_route:'SEEK',fit:'Example evidence only',gaps:[],attachments:[]};
  next.leads.push(lead);
  const write=(version,state)=>api.fetch(request('/api/state',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({expected_version:version,state})}),env);
  assert.equal((await write(initial.version,next)).status,200);
  assert.equal((await write(initial.version,next)).status,409);
  const current=await (await api.fetch(request('/api/state'),env)).json();
  assert.equal(current.state.leads.length,initial.state.leads.length+1);
  assert.deepEqual(current.state.applications,initial.state.applications);
  assert.deepEqual(current.state.manual_entries,initial.state.manual_entries);
  assert.deepEqual(current.state.record_visibility,initial.state.record_visibility);
  const altered=structuredClone(current.state);
  altered.leads[0].role='An altered old role';
  assert.equal((await write(current.version,altered)).status,400);
  const duplicate=structuredClone(current.state);
  duplicate.leads.push({...lead});
  assert.equal((await write(current.version,duplicate)).status,400);
  const expired=structuredClone(current.state);
  expired.leads.at(-1).status='SKIPPED_EXPIRED';
  assert.equal((await write(current.version,expired)).status,400);
  expired.leads.at(-1).status_evidence_url='https://example.test/careers/graduate';
  expired.leads.at(-1).checked_at='2026-09-28T02:00:00Z';
  assert.equal((await write(current.version,expired)).status,200);
});

test('the code is required, CORS is restricted, and repeated invalid codes are throttled',async()=>{
  const {env}=environment();
  for(let i=0;i<5;i++)assert.equal((await api.fetch(request('/api/state',{headers:{'X-Tracker-Code':'000000'}}),env)).status,401);
  assert.equal((await api.fetch(request('/api/state',{headers:{'X-Tracker-Code':'000000'}}),env)).status,429);
  const other=await api.fetch(new Request('https://tracker.example/api/state',{headers:{Origin:'https://other.example','X-Tracker-Code':'654321'}}),env);
  assert.equal(other.status,403);
});

test('uploaded PDF bytes live in R2 and can be retrieved after a separate save',async()=>{
  const {env,rows}=environment();
  const pdf=new TextEncoder().encode('%PDF-1.7\nTest');
  const uploaded=await api.fetch(request('/api/documents',{method:'POST',headers:{'Content-Type':'application/octet-stream','X-Filename':'resume.pdf','X-Doc-Kind':'resume'},body:pdf}),env);
  assert.equal(uploaded.status,201);
  const meta=await uploaded.json();assert.equal(meta.stored_in,'cloudflare_r2');assert.equal(rows.objects.size,1);
  const fetched=await api.fetch(request(meta.path),env);
  assert.equal(fetched.status,200);assert.equal(await fetched.text(),'%PDF-1.7\nTest');
  const fake=await api.fetch(request('/api/documents',{method:'POST',headers:{'Content-Type':'application/octet-stream','X-Filename':'resume.pdf','X-Doc-Kind':'resume'},body:'not a PDF'}),env);
  assert.equal(fake.status,400);
});

test('first read imports former Cloudflare jobs and attachment references without deleting their tables or R2 bytes',async()=>{
  const {env,rows}=environment({
    legacyJobs:[{id:7,company:'Example Civil',title:'Junior Drafter',status:'applied',location:'Melbourne',url:'https://example.test/job',notes:'Reported via earlier site',applied_date:'2026-09-26',created_at:'2026-09-26T01:00:00Z'}],
    legacyFiles:[{id:3,job_id:7,filename:'resume.pdf',r2_key:'jobs/7/resume.pdf',content_type:'application/pdf',size:8,created_at:'2026-09-26T01:00:00Z'}]
  });
  rows.objects.set('jobs/7/resume.pdf',new TextEncoder().encode('%PDF-1.7'));
  const response=await api.fetch(request('/api/state'),env);
  assert.equal(response.status,200);
  const {state}=await response.json();
  assert.equal(state.applications.length,14);
  const legacy=state.manual_entries.find(row=>row.id==='cloudflare-legacy-job:7');
  assert.equal(legacy.status,'MANUAL_APPLIED');
  assert.match(legacy.notes,/not been independently verified/);
  assert.equal(legacy.attachments[0].path,'/api/legacy-files/3');
  const document=await api.fetch(request(legacy.attachments[0].path),env);
  assert.equal(document.status,200);
  assert.equal(await document.text(),'%PDF-1.7');
  assert.equal(rows.legacyJobs.length,1);
  assert.equal(rows.legacyFiles.length,1);
});
