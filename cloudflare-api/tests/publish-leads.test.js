import test from 'node:test';
import assert from 'node:assert/strict';
import {mergeBatch} from '../scripts/publish-leads.mjs';

const prior = () => ({applications:[{key:'sent|civil',company:'Sent Civil',role:'Engineer',job_url:'https://sent.test/jobs/1'}],
  leads:[{key:'old|drafter',company:'Old Civil',role:'Drafter',job_url:'https://old.test/jobs/1',status:'READY_FOR_JEREMIE'}],
  manual_entries:[{id:'jeremie-1',company:'Manual Civil',role:'Engineer',job_url:'https://manual.test/jobs/1',status:'MANUAL_APPLIED'}],
  record_visibility:[{record_key:'old|other',deleted:1}]});
const lead = () => ({key:'new|graduate',company:'New Civil',role:'Graduate Engineer',job_url:'https://new.test/jobs/1',
  checked_at:new Date().toISOString(),status:'READY_FOR_JEREMIE',application_route:'SEEK',gaps:[],attachments:[]});

test('publisher appends one researched lead while preserving application, manual and Bin data',()=>{
  const original=prior(), batch={batch_id:'run-1',leads:[lead()]};
  const {state,added}=mergeBatch(original,batch);
  assert.equal(added,1);
  assert.equal(state.leads.length,2);
  assert.deepEqual(original,prior());
  assert.deepEqual(state.applications,original.applications);
  assert.deepEqual(state.manual_entries,original.manual_entries);
  assert.deepEqual(state.record_visibility,original.record_visibility);
  assert.equal(mergeBatch(state,batch).added,0);
});

test('publisher refuses an equivalent applied record, a stale check and unverified closure',()=>{
  const duplicate={...lead(),key:'duplicate',company:'Manual Civil',role:'Engineer'};
  assert.throws(()=>mergeBatch(prior(),{batch_id:'run-2',leads:[duplicate]}),/Potential equivalent/);
  const stale={...lead(),checked_at:'2026-09-01T00:00:00Z'};
  assert.throws(()=>mergeBatch(prior(),{batch_id:'run-3',leads:[stale]}),/48-hour window/);
  assert.throws(()=>mergeBatch(prior(),{batch_id:'run-4',leads:[],status_updates:[{key:'old|drafter',status:'SKIPPED_EXPIRED',checked_at:new Date().toISOString()}]}),/HTTPS evidence/);
});
