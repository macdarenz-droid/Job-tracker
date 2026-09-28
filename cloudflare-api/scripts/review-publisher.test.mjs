import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mergeBatch} from './publish-leads.mjs';

const fixture = () => ({applications:[{key:'sent',status:'SENT'}],leads:[],record_visibility:[{record_key:'old'}],documents:[{id:'d'}],manual_entries:[{id:'r1',company:'Acme',role:'Drafter',version:1,status:'PREPARED_NOT_SENT',created_by:'claude-job-search',contributor_name:'Claude',notes:'Original note',attachments:[{id:'pdf',sha256:'a'.repeat(64)}],email_body:'Original exact draft'}]});
const batch = () => ({batch_id:'review',leads:[],manual_reviews:[{id:'r1',review_id:'r1-review',expected_version:1,expected_status:'PREPARED_NOT_SENT',expected_created_by:'claude-job-search',status:'HELD_MANDATORY_REQUIREMENTS',reviewed_at:'2026-09-28T02:20:00Z',note:'Required software is not documented.',evidence_urls:['https://employer.example/role']}]});

test('review hold preserves all unrelated data and exact documents/draft/creator',()=>{
 const old=fixture(), result=mergeBatch(old,batch());
 assert.equal(result.reviewed,1); assert.equal(old.manual_entries[0].status,'PREPARED_NOT_SENT');
 for(const field of ['applications','leads','record_visibility','documents']) assert.deepEqual(result.state[field],old[field]);
 const row=result.state.manual_entries[0]; assert.equal(row.status,'HELD_MANDATORY_REQUIREMENTS'); assert.equal(row.version,2);
 for(const field of ['attachments','created_by','contributor_name','email_body']) assert.deepEqual(row[field],old.manual_entries[0][field]);
});
test('later Applied outcome or row edit blocks stale review',()=>{
 for(const patch of [{status:'MANUAL_APPLIED'},{version:2},{created_by:'jeremie'}]) {
  const old=fixture();Object.assign(old.manual_entries[0],patch);assert.throws(()=>mergeBatch(old,batch()),/changed since review/);
 }
});
test('idempotent retry preserves a later submission',()=>{
 const once=mergeBatch(fixture(),batch()).state;once.manual_entries[0].status='MANUAL_APPLIED';once.manual_entries[0].version=3;
 const twice=mergeBatch(once,batch());assert.equal(twice.reviewed,0);assert.deepEqual(twice.state,once);
});
test('review cannot invent outcome, delete evidence or change prior review content',()=>{
 const unsafe=batch();unsafe.manual_reviews[0].status='SENT';assert.throws(()=>mergeBatch(fixture(),unsafe),/Review hold/);
 const once=mergeBatch(fixture(),batch()).state;const altered=batch();altered.manual_reviews[0].note='Different';assert.throws(()=>mergeBatch(once,altered),/different evidence/);
});
