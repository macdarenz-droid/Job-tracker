import json, uuid, hashlib, os, sys
from datetime import datetime, timezone
sys.path.insert(0,'/workspace/job-finds'); from _save_find import save
RUN='20261112T1617Z'
now=datetime.now(timezone.utc); iso=now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
local=datetime.now().astimezone(); found=local.strftime('%Y-%m-%dT%H:%M+11:00 AEDT')
def sha(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
SW="Tick "+RUN+": open web first (web searches across jobau, Jobstralia, JobMESH, Prosple, publicroles, careersatcouncil, LinkedIn public job search for the last 48 hours, regional VIC/NSW/QLD/WA/TAS/NT/SA searches) plus SEEK 3 days/60 details (803 seen, 182 prefilter) and targeted SEEK keyword searches, widened to SEEK 7 days/80 details."
GM="Gmail could not be checked on this tick (no Gmail connector attached), so search macdarenz@gmail.com in:anywhere for the employer before applying. Dedupe: not in /workspace/job-finds, prior_outreach.json, earlier screen files or the journal."
P={
'civilivic':dict(cover='Marc_Masarate_Civilivic_Site_Engineer_Cover_Letter.pdf',res='Marc_Masarate_Civilivic_Resume.pdf',status='HELD_MANDATORY_UNRESOLVED',method='SEEK',pct=70,
 rat=["Civilivic (South East Queensland civil contractor: roads, drainage, earthworks) wants an experienced Site Engineer or a Graduate Engineer in Gympie, permanent full time, $80k to $115k, company vehicle or allowance.",
 "Duties (check works against drawings, ITPs and quality records, take-offs, subcontractor coordination, site diaries, inspections) match Marc's 2019 to 2020 site work, and the advert asks for working knowledge of roadworks, drainage or earthworks, which his Advanced Diploma design work covers; civil degree and White Card met; site experience preferred not essential.",
 "Direct employer; graduates explicitly welcome."],
 caution="HELD because the advert lists a current Queensland driver's licence and Marc holds a Victorian licence; Queensland lets a new resident transfer an interstate licence, so this resolves only if Marc is willing to move to the Gympie region. Relocation unconfirmed. SEEK asks years as site engineer, road construction and earthworks: answer under 1 year / none on site honestly. Company website not found; check the employer before sharing more than the resume.",
 gaps=["Queensland driver's licence (holds Victorian)","No Australian site experience","Roads and earthworks experience is design study only","Relocation to Gympie unconfirmed"],
 listed='2026-11-12',expires='2026-12-12',apply="Apply on SEEK job 95842971 (SEEK Apply, 7 screening questions, resume and cover letter requested). No email published.",
 call=["Site experience? \u2192 About ten months on site in the Philippines (2019 to 2020): crew coordination, drawing review, inspections, procurement, site and progress reports.","Roads, drainage, earthworks? \u2192 Designed road geometry, earthworks, pavement and stormwater drainage in Civil 3D and AutoCAD in the Advanced Diploma (finished Feb 2026); not yet on an Australian site.","Queensland licence and moving? \u2192 Holds an Australian (Victorian) licence; Marc to confirm a move and licence transfer.","Work rights? \u2192 Subclass 485, full working rights until December 2027.","Salary and start? \u2192 Marc to answer himself."],
 how_extra="Found on SEEK (job 95842971, listed 12 Nov 2026, expires 12 Dec 2026) through a targeted keyword search after it was seen on the SEEK graduate civil engineer page; the automatic sweep missed it because SEEK files it under Project Management. Never screened before."),
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
