import json, uuid, hashlib, os, sys
from datetime import datetime, timezone
sys.path.insert(0,'/workspace/job-finds'); from _save_find import save
RUN='20261111T1520Z'
now=datetime.now(timezone.utc); iso=now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
local=datetime.now().astimezone(); found=local.strftime('%Y-%m-%dT%H:%M+11:00 AEDT')
def sha(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
SW="Tick "+RUN+": open web first (web search across SEEK public pages, Jora, LinkedIn, Indeed, jobau, trabajo.org, Prosple, College Recruiter, council PageUp boards) plus SEEK 3 days/60 details (all 45 new rows already screened on earlier ticks) widened to a 14 day Melbourne graduate search."
GM="Gmail could not be checked on this tick (no Gmail connector attached), so search macdarenz@gmail.com in:anywhere for the employer before applying. Dedupe: tracker.py check new; not in /workspace/job-finds or prior_outreach.json."
P={
'mcd':dict(cover='Marc_Masarate_McConnell_Dowell_Junior_Project_Engineer_Cover_Letter.pdf',res='Marc_Masarate_McConnell_Dowell_Resume.pdf',status='READY_JEREMIE_SEEK',method='SEEK',pct=70,
 rat=["Junior Project Engineer - Traffic with McConnell Dowell on the South Package of the Yan Yean Road Upgrade (project office Yarrambat/Doreen): support engineers on temporary and permanent works, planning and progress tracking, procurement, subcontractor management, safety and quality.",
 "Fits Marc's civil degree and February 2026 Advanced Diploma (road geometry, pavement, earthworks, drainage, Austroads and AS 1742.14 coursework) and his 2019 to 2020 site coordination, inspections and procurement tracking; asks for a recent graduate.",
 "Road infrastructure in Victoria matches his target of junior site and documentation roles."],
 caution="Traffic engineering interest highly regarded; Marc has no traffic engineering experience. BSCE is 2019 (Advanced Diploma Feb 2026), advert asks for a recent graduate. Project office in Yarrambat/Doreen is a long drive from Melton. SEEK expiry 5 Dec 2026. No salary given.",
 gaps=["No traffic engineering experience","No Australian construction experience","Long commute from Melton"],
 listed='2026-11-05',expires='2026-12-05',apply="SEEK Apply on advert 95705736 (no screening questions listed).",
 call=["Why this role? \u2192 Road project with broad exposure; diploma road and pavement design coursework.","Traffic experience? \u2192 None on a job; studied AS 1742.14 and Austroads guides in coursework.","Commute? \u2192 Lives in Melton with own transport and licence.","Work rights? \u2192 Subclass 485, full working rights until December 2027.","Salary and start? \u2192 Marc to answer."],
 how_extra="Found on SEEK advert 95705736 (listed 5 Nov 2026, expires 5 Dec 2026) in a 14 day Melbourne graduate civil search; it had never been screened by earlier ticks. Read in full on 12 Nov 2026."),
'yarra':dict(cover='Marc_Masarate_Yarra_Civil_Works_Project_Officer_Cover_Letter.pdf',res='Marc_Masarate_Yarra_Resume.pdf',status='READY_JEREMIE_EMPLOYER_PORTAL',method='Company website',pct=62,
 rat=["Civil Works Project Officer, Yarra City Council Development and Civil Engineering team (temporary full time to 16 Apr 2027, Band 5 from $80,410 + super + RDO): supervise contractors' reinstatement works on Council roads and footpaths, scope works, site assessments, QA and inspections under the Road Management Plan.",
 "Fits Marc's 2019 to 2020 site inspections, safety and quality checks and contractor coordination, and his road and pavement design coursework; temporary contract sits inside his 485 work rights.",
 "Council civil site role in Melbourne, a core target."],
 caution="Experience in infrastructure project delivery is highly desirable; Marc's site work was a building renovation and subdivision finishing works in the Philippines, none in Australia or on road reserves. Key Selection Criteria are in a Position Description PDF that was not read on this tick; check the letter against it. Police check before start. Closes 22 Nov 2026 11:55pm.",
 gaps=["No Australian or council experience","No road reserve or reinstatement supervision experience","Position Description KSC not yet checked"],
 listed='2026-11-09',expires='2026-11-22',apply="Apply on Yarra's PageUp portal with resume and a 1 page cover letter that briefly addresses the Key Selection Criteria in the Position Description (also on SEEK 95767180). Enquiries: Justin Cochrane, Team Leader Development and Civil Engineering, Justin.cochrane@yarracity.vic.gov.au (published in the advert for further information).",
 call=["Supervision experience? \u2192 Coordinated 10 to 15 workers a day and did site inspections, safety and quality checks in the Philippines (2019 to 2020).","Road Management Plan or permits? \u2192 Not yet; would learn Yarra's processes.","Police check? \u2192 Willing to undergo pre-employment checks.","Work rights? \u2192 Subclass 485, full working rights until December 2027 (contract ends April 2027).","Salary and start? \u2192 Marc to answer."],
 how_extra="Found by open-web search (Yarra PageUp job 496994, advertised 9 Nov 2026, closes 22 Nov 2026) and also on SEEK 95767180; read in full on 12 Nov 2026. The advert names Justin Cochrane for further information; the cover letter is addressed to him, but applications go through the portal, so no email is prepared."),
'portal':dict(cover='Marc_Masarate_Portal_Contractors_Graduate_Civil_Engineer_Cover_Letter.pdf',res='Marc_Masarate_Portal_Contractors_Resume.pdf',status='READY_JEREMIE_EMPLOYER_PORTAL',method='Job board (Indeed / LinkedIn)',pct=70,
 rat=["Graduate Civil Engineer with Portal Contractors, a Williamstown earthworks and retention contractor: set-out and level checks, ITPs, drawing and document control, RFIs, daily subcontractor coordination and concrete pour supervision under the Project Manager; $65k to $75k plus company car.",
 "Fits Marc's civil degree, White Card, licence and own transport (all required), his 2019 to 2020 drawing review, inspections and crew coordination, and his earthworks design coursework; Williamstown is a short drive from Melton.",
 "Hands-on graduate site role in Melbourne's west, a core target."],
 caution="Listing liveness not confirmed: an Indeed 'Graduate Project Engineer' version was seen as expired on an earlier tick, and a new 'Graduate Civil Engineer' version was indexed on trabajo.org 1 day before 12 Nov 2026 (likely a fresh LinkedIn post); confirm it is open before applying. Advert targets the first 1 to 2 years out of a degree; BSCE is 2019. No survey instrument set-out experience on record.",
 gaps=["No set-out or survey instrument experience","No Australian construction experience","BSCE 2019, not a recent degree"],
 listed='2026-11-11',expires='',apply="Apply through the live job board listing (Indeed / LinkedIn). Company site lists only info@portalcontractors.com and tenders@portalcontractors.com, not stated to take applications, so no email is prepared.",
 call=["Site experience? \u2192 About 10 months on site in the Philippines, inspections, drawing checks and crew coordination.","Set-out? \u2192 Not with instruments yet; keen to learn.","Transport? \u2192 Lives in Melton, licence and own transport.","Work rights? \u2192 Subclass 485, full working rights until December 2027.","Salary? \u2192 Advert says $65k to $75k; Marc to confirm."],
 how_extra="Found by open-web search (trabajo.org listing 'Graduate Civil Engineer, Portal Contractors, Williamstown', posted about 11 Nov 2026, and the Indeed Graduate Project Engineer advert with the full duty list). The company contact page (read 12 Nov 2026) lists only info@ and tenders@."),
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
