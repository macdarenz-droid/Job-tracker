import json, uuid, hashlib, os, sys
from datetime import datetime, timezone
sys.path.insert(0,'/workspace/job-finds'); from _save_find import save
RUN='20261112T1110Z'
now=datetime.now(timezone.utc); iso=now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
local=datetime.now().astimezone(); found=local.strftime('%Y-%m-%dT%H:%M+11:00 AEDT')
def sha(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
SW="Tick "+RUN+": open web first (web searches across jobau, Jobstralia, Jora (headless), Prosple, GradConnection, LiveHire/Calibre, Locanto, council and regional VIC/NSW/QLD/WA/NT/TAS/ACT searches, TradeTech and CivilPlus careers pages) plus SEEK 3 days/60 details (1195 seen, 260 prefilter) widened to 7 days/80 details (1369 seen, 335 prefilter)."
GM="Gmail could not be checked on this tick (no Gmail connector attached), so search macdarenz@gmail.com in:anywhere for the employer before applying. Dedupe: tracker.py check new; not in /workspace/job-finds or prior_outreach.json."
P={
'poweron':dict(cover='Marc_Masarate_Power_On_Cabling_Civil_Site_Engineer_Cover_Letter.pdf',res='Marc_Masarate_Power_On_Cabling_Resume.pdf',status='READY_JEREMIE_SEEK',method='SEEK',pct=62,
 rat=["Civil Site Engineer with Power On Cabling (underground assets, excavation, cable laying, formwork, earthworks), Perth based / site based FIFO, permanent full time, immediate start, initial 4 to 6 month project.",
 "Duties match Marc's 2019 to 2020 site work: reading drawings, daily ITPs and QA records, procuring materials, weekly and monthly progress reports, liaising with site staff; mandatory items (civil engineering qualification, White Card, licence, medical and D&A, full work rights) are all met.",
 "Direct employer; Marc is available for FIFO; no minimum years stated."],
 caution="Advert wants someone to work autonomously and manage MS Project timelines, variations and EOTs, which Marc has not done; his site experience is about ten months and overseas. Perth / FIFO means relocation or fly in fly out, Marc to decide. SEEK asks years as a Civil Site Engineer and in construction: answer under 1 year honestly. Company website not found; check the employer before sharing more than the resume.",
 gaps=["No Australian site experience","No MS Project, variations or EOT experience","Perth based / FIFO"],
 listed='2026-11-11',expires='2026-12-12',apply="Apply on SEEK job 95841578 (SEEK Apply, 8 screening questions). No email published.",
 call=["Site experience? \u2192 About ten months on site in the Philippines (2019 to 2020): crew coordination, drawing review, inspections, procurement, site and progress reports.","ITPs and QA? \u2192 Quality checks and inspections on site; Australian ITP format still to learn.","FIFO or Perth move? \u2192 Available for FIFO and site work; Marc to confirm Perth arrangements.","Work rights? \u2192 Subclass 485, full working rights until December 2027.","Salary and start? \u2192 Marc to answer himself."],
 how_extra="Found in this tick's SEEK sweep (job 95841578, listed 11 Nov 2026, expires 12 Dec 2026). Not on the tracker, prior_outreach.json or /workspace/job-finds; never screened before."),
}
recs=[]
for k,p in P.items():
    d=json.load(open(f'drafts/{k}.json'))
    cover=os.path.abspath(p['cover']); res=os.path.abspath(p['res'])
    how=SW+" "+p['how_extra']+" "+GM+" Cover letter drafted from facts.json only; checks.py facts OK and tone OK (letter under 340 words); cover letter and one page resume rendered and read back (1 page each). Status "+p['status']+": nothing was submitted or sent. Saved locally only (tracker full, Marc 20 Oct 2026)."
    notes="HOW GROK AI FOUND THIS\n"+how+"\n\nIF THEY CALL, LIKELY QUESTIONS\n"+"\n".join('\u2022 '+c for c in p['call'])
    d['notes']=notes; rid=str(uuid.uuid4())
    rec={"id":rid,"key":"manual:"+rid,"contributor_name":"Grok AI","created_by":"grok-job-search","record_kind":"AUTOMATED_LEAD","run_id":RUN,"created_at":iso,"updated_at":iso,"version":1,
     "attachments":[{"kind":"cover","filename":p['cover'],"sha256":sha(cover),"stored_in":"local:/workspace/job-finds"},{"kind":"resume","filename":p['res'],"sha256":sha(res),"stored_in":"local:/workspace/job-finds","note":"one page resume built from facts.json"}],
     "company":d['company'],"role":d['role'],"location":d['location'],"job_url":d['job_url'],"company_url":d['company_url'],"status":p['status'],"application_type":"ADVERTISED_VACANCY","vacancy_status":d['vacancy_status'],
     "application_route":d['route'],"application_method":p['method'],"recipient_name":d['recipient_name'],"recipient_role":d['recipient_role'],"recipient_email":"","contact_email":"",
     "contact_evidence_url":d['contact_evidence_url'],"contact_verified_at":iso,"contact_confidence":"none","subject":d['subject'],"email_body":"","fit":p['rat'],"gaps":p['gaps'],
     "match_score":{"percent":p['pct'],"method":"resume-fit-v2","rationale":p['rat'],"caution":p['caution']},
     "advert":{"source":("seek" if d.get('seek_id') else "web"),"listed_at":p['listed'],"expires_at":p['expires'],"verified_at":iso,"apply_instructions":p['apply'],"screening_questions":[]},
     "screening_answers":[],"checklist":d['checklist'],"notes":notes,"how_found":how,"call_prep":p['call'],"checked_at":iso,"seek_id":d.get('seek_id'),"duplicate_key":(d['company']+'|'+d['role']).lower(),"preparation_only":True,"found_at":found}
    readme=(f"# {d['company']}, {d['role']}, {d['location']}\n\n- Status: {p['status']}, fit {p['pct']}%, route {p['method']}\n- Link: {d['job_url']}\n- Apply: {p['apply']}\n- Closes: {p['expires'] or 'not stated'}\n- Why: {' '.join(p['rat'])}\n- Caution: {p['caution']}\n- Gaps: {'; '.join(p['gaps'])}\n- Files: record.json, draft.json, cover letter PDF and one page resume PDF (both read back).\n\n## Checklist\n"
     +"\n".join(f"{i+1}. {c}" for i,c in enumerate(d['checklist']))+"\n\n"+notes+"\n")
    json.dump(d,open('/tmp/draft.json','w'),indent=1,ensure_ascii=False)
    if save(rec,[cover,res,'/tmp/draft.json'],readme,local.strftime('%Y-%m-%d')): recs.append(rec)
json.dump(recs,open('local_records.json','w'),indent=1,ensure_ascii=False)
print(len(recs))
