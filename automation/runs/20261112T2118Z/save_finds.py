import json, uuid, hashlib, os, sys
from datetime import datetime, timezone
sys.path.insert(0,'/workspace/job-finds'); from _save_find import save
RUN='20261112T2118Z'
now=datetime.now(timezone.utc); iso=now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
local=datetime.now().astimezone(); found=local.strftime('%Y-%m-%dT%H:%M+11:00 AEDT')
def sha(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
SW="Tick "+RUN+": open web first (web searches across ZipRecruiter, job-directory, Jobstralia, jobau, CollegeRecruiter, TheJobsMap, careersatcouncil, Prosple, LinkedIn public job search for the last 24 to 48 hours with six junior keyword sets, employer careers pages for Dalton Consulting Engineers and Mammoet) plus SEEK 2 days/80 details (858 seen, 138 prefilter)."
GM="Gmail could not be checked on this tick (no Gmail connector attached), so search macdarenz@gmail.com in:anywhere for the employer before applying. Dedupe: not in /workspace/job-finds, prior_outreach.json, earlier screen files or the journal."
P={
'mammoet':dict(cover='Marc_Masarate_Mammoet_Graduate_Engineer_Cover_Letter.pdf',res='Marc_Masarate_Mammoet_Resume.pdf',status='READY_JEREMIE_EMPLOYER_PORTAL',method='Employer portal',pct=63,
 rat=["Mammoet (heavy lifting and transport) wants a Graduate Engineer in Henderson WA who has completed or is completing a mechanical, mechatronic, civil or structural degree; structured graduate program with mentor.",
 "Duties (engineering drawings in AutoCAD and 3D software, calculations, technical documentation, site exposure) match Marc's AutoCAD/Civil 3D drawing work in the Advanced Diploma and his 2019 to 2020 site inspection and reporting work; civil degree accepted.",
 "Direct employer, posted 12 Nov 2026 (req 9300); no citizenship or PR requirement stated."],
 caution="Heavy lift planning, crane studies and transport route assessments are a domain gap (said honestly in the letter). Degree finished 2019; the advert says completing or recently completed, so the Feb 2026 Advanced Diploma carries the recency. Perth relocation unconfirmed. Work rights not stated in the advert; check the portal questions.",
 gaps=["Heavy lift and transport engineering is new","Degree 2019 (recent qualification is the Advanced Diploma)","Relocation to Perth unconfirmed","No Australian site experience"],
 listed='2026-11-12',expires='',apply="Apply on the Mammoet careers portal (iCIMS req 9300): https://jobs.mammoet.com/careers-home/jobs/9300 . The advert also offers emailing a CV to a mammoet.com address that was hidden in the public listing, so no email is published.",
 call=["Why heavy lifting? → Wants a graduate role that mixes drawings and documentation with time on site; heavy lift planning would be learnt from the team.","Drawings and software? → Prepared and reviewed technical drawings in AutoCAD and Civil 3D in the Advanced Diploma (finished Feb 2026).","Site experience? → About ten months on site in the Philippines (2019 to 2020): crew coordination, drawing review, inspections, site and progress reports.","Move to Perth? → Open to discussing relocation; Marc to confirm.","Work rights? → Subclass 485, full working rights until December 2027."],
 how_extra="Found on LinkedIn public job search (posted 10 hours earlier) and confirmed on Mammoet's own careers API as req 9300, Graduate Engineer, Henderson WA, posted 12 Nov 2026. Never screened before."),
'moretonbay':dict(cover='Marc_Masarate_MoretonBay_Civil_Services_Engineer_Cover_Letter.pdf',res='Marc_Masarate_MoretonBay_Resume.pdf',status='READY_JEREMIE_EMPLOYER_PORTAL',method='SEEK link-out to council portal',pct=66,
 rat=["City of Moreton Bay wants a graduate Civil Services Engineer in Strathpine (permanent full time, 103,597 dollars plus super, 9 day fortnight, hybrid) for investigations, analysis and design behind facilities investment decisions.",
 "Requirements (tertiary civil qualification, knowledge of civil design, constructability and standards, technical reports and drawings, White Card, C class licence) are met by Marc's BSCE, Advanced Diploma design and documentation work and his White Card and licence.",
 "Council employer; advert says it only seeks current graduates."],
 caution="Facilities engineering is new to Marc. 'Current graduates' wording: Marc's degree is 2019 with the Advanced Diploma finished Feb 2026; check the position description before applying. Brisbane relocation unconfirmed. Closes about 22 Nov 2026.",
 gaps=["Facilities engineering experience","No Australian site experience","Relocation to Brisbane unconfirmed"],
 listed='2026-11-12',expires='2026-11-22',apply="SEEK job 95865921 links out to the City of Moreton Bay careers portal; upload resume and optional cover letter. Questions: careers@moretonbay.qld.gov.au (published in the advert). No email sent.",
 call=["Civil design knowledge? → Road geometry, earthworks, pavement and stormwater drainage design and documentation in AutoCAD and Civil 3D (Advanced Diploma, Feb 2026).","Reports and drawings? → Technical reporting in the Advanced Diploma; site, material and progress reports as a field engineer (2019 to 2020).","Facilities engineering? → New; would learn from senior engineers.","Move to Brisbane? → Open to discussing relocation; Marc to confirm.","Work rights? → Subclass 485, full working rights until December 2027."],
 how_extra="Found in the SEEK sweep (job 95865921, listed 13 Nov 2026 AEDT, closes about 22 Nov 2026); never screened before (an earlier Moreton Bay advert was a different, experienced role)."),
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
