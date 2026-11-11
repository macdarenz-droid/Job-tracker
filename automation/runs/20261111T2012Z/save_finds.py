import json, uuid, hashlib, os, sys
from datetime import datetime, timezone
sys.path.insert(0,'/workspace/job-finds'); from _save_find import save
RUN='20261111T2012Z'
now=datetime.now(timezone.utc); iso=now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
local=datetime.now().astimezone(); found=local.strftime('%Y-%m-%dT%H:%M+11:00 AEDT')
def sha(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
SW="Tick "+RUN+": open web first (web search across Jora, SEEK public search pages, jobau, College Recruiter, Prosple, Construction Australia jobs and council boards, plus follow ups on TSA Civil Group, WSP, GHD and Stantec) and SEEK 3 days/60 details (1043 seen, 218 prefilter) widened to 7 days/80 details (1205 seen, nothing not already seen on earlier ticks)."
GM="Gmail could not be checked on this tick (no Gmail connector attached), so search macdarenz@gmail.com in:anywhere for the employer before applying. Dedupe: tracker.py check new; not in /workspace/job-finds or prior_outreach.json."
P={
'bmd':dict(cover='Marc_Masarate_BMD_Civil_Site_Engineer_Cover_Letter.pdf',res='Marc_Masarate_BMD_Resume.pdf',status='READY_JEREMIE_EMPLOYER_PORTAL',method='Company website (SEEK link out)',pct=66,
 rat=["Civil Site Engineer with the Tram to Springvale Alliance (BMD, CPB, Arup) on the Eastern Freeway Upgrades, North East Link Program: earthworks, drainage and utilities, pavements, structures; planning and coordination, ITPs, NCRs, permits and daily reports.",
 "Fits Marc's road, earthworks, pavement and stormwater design coursework in Civil 3D and AutoCAD, his 2019 to 2020 site inspections, crew coordination and site reporting, and his civil degree (required); Melbourne based project.",
 "Direct employer, Tier 1 alliance, early career wording (eager to build their careers)."],
 caution="Advert asks for 1 to 5 years in civil infrastructure or construction; Marc has about ten months of site work, overseas, and the letter says so. No Australian ITP/NCR/permit experience. Blackburn North is a long commute from Melton. The separate BMD Site Engineer Adelaide find (11 Nov) is held for EA recognition; this Melbourne advert does not ask for EA.",
 gaps=["About ten months site experience versus 1 to 5 years asked","No Australian construction experience","No ITP/NCR/permit experience on record"],
 listed='2026-11-11',expires='2026-12-11',apply="SEEK 95835638 links out to BMD's own careers portal; apply there with resume and cover letter. No email published.",
 call=["Site experience? \u2192 About ten months on site in the Philippines (2019 to 2020): inspections, drawing checks, crew coordination, site reports.","Earthworks and pavements? \u2192 Designed road geometry, earthworks, pavements and stormwater in Civil 3D during the Advanced Diploma (Feb 2026).","Commute? \u2192 Lives in Melton, licence and own transport.","Work rights? \u2192 Subclass 485, full working rights until December 2027.","Salary and start? \u2192 Marc to answer himself."],
 how_extra="Found on the SEEK sweep (listed 11 Nov 2026, expires 11 Dec 2026); it appeared in the previous tick's candidate list but was not screened then. Not on the tracker, prior_outreach.json or /workspace/job-finds for this role; the only BMD find is the held Adelaide Site Engineer."),
'stanfields':dict(cover='Marc_Masarate_Stanfields_Cadet_Survey_Draftsperson_Cover_Letter.pdf',res='Marc_Masarate_Stanfields_Resume.pdf',status='READY_JEREMIE_SEEK',method='SEEK',pct=60,
 rat=["Cadet Survey Draftsperson at Stanfield's Real Property Drafting, Spring Hill, Brisbane: entry level drafting with on the job training; CAD familiarity or a CAD certificate is an advantage, SurvaCad or surveying experience not essential.",
 "Fits Marc's Advanced Diploma drafting in AutoCAD and Civil 3D, his drawing review and documentation work on site, and the surveying subjects in his BSCE.",
 "Genuine cadet entry point into drafting and documentation, one of Marc's target role types."],
 caution="Brisbane means relocation, which Marc has not confirmed; the letter says only open to discussing relocation. Survey (cadastral) drafting rather than civil design. No SurvaCad. Wages not stated (discussed at interview); a cadet wage may be low.",
 gaps=["No SurvaCad or surveying industry experience","Relocation to Brisbane not confirmed"],
 listed='2026-11-10',expires='2026-12-11',apply="Apply on SEEK 95815474 with resume and cover letter; no screening questions listed.",
 call=["CAD? \u2192 AutoCAD and Civil 3D through the Advanced Diploma of Civil Construction Design (Feb 2026).","Surveying? \u2192 Studied surveying in the BSCE; no SurvaCad yet, keen to learn.","Move to Brisbane? \u2192 Marc to decide; open to discussing.","Work rights? \u2192 Subclass 485, full working rights until December 2027.","Wage? \u2192 Marc to answer himself."],
 how_extra="Found on the SEEK sweep (listed 10 Nov 2026, expires 11 Dec 2026). Not on the tracker, prior_outreach.json or /workspace/job-finds; never screened on earlier ticks. Kept as the second record after the widened sweep found nothing else new and the open web leads (TSA Civil Group graduate Preston, WSP Junior Civil Designer Melbourne) had no live listing."),
}
recs=[]
for k,p in P.items():
    d=json.load(open(f'drafts/{k}.json'))
    cover=os.path.abspath(p['cover']); res=os.path.abspath(p['res'])
    how=SW+" "+p['how_extra']+" "+GM+" Cover letter drafted from facts.json only; checks.py facts OK and tone OK apart from the 220 word email limit, which does not apply to a letter (under 340 words); cover letter and one page resume rendered and read back (1 page each). Status "+p['status']+": nothing was submitted or sent. Saved locally only (tracker full, Marc 20 Oct 2026)."
    notes="HOW GROK AI FOUND THIS\n"+how+"\n\nIF THEY CALL, LIKELY QUESTIONS\n"+"\n".join('\u2022 '+c for c in p['call'])
    d['notes']=notes; rid=str(uuid.uuid4())
    rec={"id":rid,"key":"manual:"+rid,"contributor_name":"Grok AI","created_by":"grok-job-search","record_kind":"AUTOMATED_LEAD","run_id":RUN,"created_at":iso,"updated_at":iso,"version":1,
     "attachments":[{"kind":"cover","filename":p['cover'],"sha256":sha(cover),"stored_in":"local:/workspace/job-finds"},{"kind":"resume","filename":p['res'],"sha256":sha(res),"stored_in":"local:/workspace/job-finds","note":"one page resume built from facts.json"}],
     "company":d['company'],"role":d['role'],"location":d['location'],"job_url":d['job_url'],"company_url":d['company_url'],"status":p['status'],"application_type":"ADVERTISED_VACANCY","vacancy_status":d['vacancy_status'],
     "application_route":d['route'],"application_method":p['method'],"recipient_name":d['recipient_name'],"recipient_role":d['recipient_role'],"recipient_email":"","contact_email":"",
     "contact_evidence_url":d['contact_evidence_url'],"contact_verified_at":iso,"contact_confidence":"none","subject":d['subject'],"email_body":"","fit":p['rat'],"gaps":p['gaps'],
     "match_score":{"percent":p['pct'],"method":"resume-fit-v2","rationale":p['rat'],"caution":p['caution']},
     "advert":{"source":"seek" if d.get('seek_id') else "web","listed_at":p['listed'],"expires_at":p['expires'],"verified_at":iso,"apply_instructions":p['apply'],"screening_questions":[]},
     "screening_answers":[],"checklist":d['checklist'],"notes":notes,"how_found":how,"call_prep":p['call'],"checked_at":iso,"seek_id":d.get('seek_id'),"duplicate_key":(d['company']+'|'+d['role']).lower(),"preparation_only":True,"found_at":found}
    readme=(f"# {d['company']}, {d['role']}, {d['location']}\n\n- Status: {p['status']}, fit {p['pct']}%, route {p['method']}\n- Link: {d['job_url']}\n- Apply: {p['apply']}\n- Closes: {p['expires'] or 'not stated'}\n- Why: {' '.join(p['rat'])}\n- Caution: {p['caution']}\n- Gaps: {'; '.join(p['gaps'])}\n- Files: record.json, draft.json, cover letter PDF and one page resume PDF (both read back).\n\n## Checklist\n"
     +"\n".join(f"{i+1}. {c}" for i,c in enumerate(d['checklist']))+"\n\n"+notes+"\n")
    json.dump(d,open('/tmp/draft.json','w'),indent=1,ensure_ascii=False)
    if save(rec,[cover,res,'/tmp/draft.json'],readme,local.strftime('%Y-%m-%d')): recs.append(rec)
json.dump(recs,open('local_records.json','w'),indent=1,ensure_ascii=False)
print(len(recs))
