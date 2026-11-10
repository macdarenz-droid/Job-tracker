import json, uuid, hashlib, shutil, sys, os
from datetime import datetime, timezone
sys.path.insert(0,'/workspace/job-finds'); from _save_find import save
RUN=open('/tmp/RUN').read().strip()
now=datetime.now(timezone.utc); iso=now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
local=datetime.now().astimezone(); found=local.strftime('%Y-%m-%dT%H:%M+11:00 AEDT')
RES='/workspace/repos/Portfolio/assets/Marc-Darenz-Masarate-Resume.pdf'
def sha(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
SW="SEEK 5 day sweep on tick "+RUN+" (1125 seen, 255 past the prefilter, 80 details; every fresh SEEK lead was experienced-only, already screened, or blocked by recent outreach, e.g. Egis and City of Canada Bay) widened to an open-web sweep (WebSearch of council careers, Prosple, jobau, employer careers pages)."
CALLW=["Work rights? \u2192 Subclass 485, full working rights until December 2027.","Start date and salary? \u2192 Marc to answer; nothing on record."]
specs=[
 dict(n='hobsons',cover='Marc_Masarate_Hobsons_Bay_Graduate_Drainage_and_Development_Engineer_Cover_Letter.pdf',res='Marc_Masarate_Hobsons_Bay_Resume.pdf',pct=72,status='READY_JEREMIE_EMPLOYER_PORTAL',source='open_web_prosple_glassdoor',listed='2026-11-03',expires='2026-11-16T23:30+11:00',apply="Apply via Hobsons Bay Council's online portal (Work opportunities page); email and late applications not accepted. Max 2 page cover letter plus CV.",
  rationale=["Band 5 Graduate Drainage and Development Engineer, Altona (full time, fixed term to Oct 2028, $78,155 to $90,691 + RDO + super): drainage investigations, development assessments, flood mitigation, LPOD and build-over-easement requests, GIS.",
   "Built for a recent civil graduate with under two years' experience; matches Marc's BSCE plus Advanced Diploma stormwater drainage design, Before You Dig work and site inspection background. Altona is a short drive from Melton.",
   "Direct employer (council); visa holders with full working rights accepted; apply on the council portal."],
  caution="Asks for eligibility for Engineers Australia membership; Marc's BSCE is from the Philippines and no EA assessment is on record, so Marc must decide how to answer. Requires a Victorian licence (on record) and a police check. Closes 16 Nov 2026, so apply this week.",
  gaps=["Engineers Australia eligibility not confirmed","No local government experience","GIS and flood modelling not on record"],
  how="Found on the open web (Prosple, Glassdoor, SimplyHired listings of the Hobsons Bay advert; also in Marc's LinkedIn job alert of 4 Nov 2026). Enquiries go to Nicholas Daglas via careers@hobsonsbay.vic.gov.au; applications only through the portal, so no email is prepared.",
  call=["Why council drainage? \u2192 Stormwater drainage design was core to my Advanced Diploma and I want to see it applied to real catchments near home.","Development assessment? \u2192 Not yet on a job; I reviewed drawings against requirements on site in 2019 to 2020.","EA membership? \u2192 Marc to answer."]),
 dict(n='coreep',cover='Marc_Masarate_Core-EP_Junior_Drafter_Cover_Letter.pdf',res='Marc_Masarate_Core-EP_Resume.pdf',pct=66,status='PREPARED_NOT_SENT',source='core-ep_careers',listed='2026-10-28',expires=None,apply="Send an introductory letter with updated CV to aditiagarwal@core-ep.com.au (per advert).",
  rationale=["Permanent full time Junior Drafter in Core-EP's Melbourne office, reporting to the Senior Drafter: 2D and 3D CAD drawings for landfill, gas management and remediation projects, drawing registers and as-builts.",
   "Asks only for Cert III or IV in drafting or engineering and AutoCAD with Civil 3D or willingness to learn; Marc's Advanced Diploma and AutoCAD/Civil 3D coursework exceed that. Matches his junior civil drafting and documentation target.",
   "Direct employer with a published application email, so an email application is prepared (not sent)."],
  caution="Environmental (landfill and gas) drafting rather than roads; Marc has no office drafting experience. Office suburb not stated on the advert. No closing date shown.",
  gaps=["No design office drafting experience","No environmental or landfill drafting on record"],
  how="Found on the open web (jobau and TheBigJobsite listings, published 28 Oct 2026) and verified live on the Core-EP careers page on 10 Nov 2026. The advert says to send an introductory letter and CV to aditiagarwal@core-ep.com.au. Email prepared, not sent: finds are saved locally only per Marc's 20 Oct 2026 instruction, so Marc approves any send.",
  call=["Why environmental drafting? \u2192 It builds on my earthworks and drainage design study and gives real project drawing work.","Software? \u2192 AutoCAD 2D and Civil 3D from my Advanced Diploma.","Office experience? \u2192 None yet; site experience 2019 to 2020 using drawings in the field."]),
]
recs=[]
for s in specs:
    d=json.load(open(f"drafts/{s['n']}.json"))
    cover=os.path.abspath(s['cover']); tmp='/tmp/'+s['res']; shutil.copy(RES,tmp)
    how=SW+" "+s['how']+" Dedupe: tracker.py check new, not in /workspace/job-finds; Gmail in:anywhere (includeSpamTrash) search for the employer on 10 Nov 2026 found no receipt or prior email (only a LinkedIn alert for Hobsons Bay). Drafted from facts.json only; checks.py facts OK; cover letter rendered with compact_pdf.py (one page, read back). Nothing was sent. Saved locally only (tracker full, Marc 20 Oct 2026)."
    call=s['call']+CALLW
    notes="HOW GROK AI FOUND THIS\n"+how+"\n\nIF THEY CALL, LIKELY QUESTIONS\n"+"\n".join('\u2022 '+c for c in call)
    d['notes']=notes; rid=str(uuid.uuid4())
    rec={"id":rid,"key":"manual:"+rid,"contributor_name":"Grok AI","created_by":"grok-job-search","record_kind":"AUTOMATED_LEAD","run_id":RUN,"created_at":iso,"updated_at":iso,"version":1,
     "attachments":[{"kind":"cover","filename":s['cover'],"sha256":sha(cover),"stored_in":"local:/workspace/job-finds"},{"kind":"resume","filename":s['res'],"sha256":sha(tmp),"stored_in":"local:/workspace/job-finds"}],
     "company":d['company'],"role":d['role'],"location":d['location'],"job_url":d['job_url'],"company_url":d['company_url'],"status":s['status'],"application_type":"ADVERTISED_VACANCY","vacancy_status":d['vacancy_status'],
     "application_route":d['route'],"application_method":"Company website" if d['route']=='EMPLOYER_PORTAL' else "Email","recipient_name":d['recipient_name'],"recipient_role":d['recipient_role'],"recipient_email":d['recipient_email'],"contact_email":d['recipient_email'],
     "contact_evidence_url":d['contact_evidence_url'],"contact_verified_at":iso,"contact_confidence":"published_direct" if d['recipient_email'] else "none","subject":d['subject'],"email_body":d['email_body'],"fit":s['rationale'],"gaps":s['gaps'],
     "match_score":{"percent":s['pct'],"method":"resume-fit-v2","rationale":s['rationale'],"caution":s['caution']},
     "advert":{"source":s['source'],"listed_at":s['listed'],"expires_at":s['expires'],"verified_at":iso,"apply_instructions":s['apply'],"screening_questions":[]},
     "screening_answers":d['screening_answers'],"checklist":d['checklist'],"notes":notes,"how_found":how,"call_prep":call,"checked_at":iso,"seek_id":None,
     "duplicate_key":d['company'].lower().split()[0]+"|"+s['n'],"preparation_only":True,"found_at":found}
    readme=(f"# {d['company']}, {d['role']}, {d['location']}\n\n- Status: {s['status']}, fit {s['pct']}%, route {d['route']}\n- Link: {d['job_url']}\n- Apply: {s['apply']}\n- Why: {' '.join(s['rationale'])}\n- Caution: {s['caution']}\n- Gaps: {'; '.join(s['gaps'])}\n"
      +(f"- Application email (published in advert, not sent): {d['recipient_email']}\n" if d['recipient_email'] else "")+
      "- Files: record.json, draft.json (email body and letter), cover letter PDF (1 page, read back), resume PDF.\n\n## Checklist\n"+"\n".join(f"{i+1}. {c}" for i,c in enumerate(d['checklist']))+
      ("\n\n## Screening answers\n"+"\n".join(f"- {x['q']}: {x['a']}" for x in d['screening_answers']) if d['screening_answers'] else "")+"\n\n## Email draft (not sent)\n\nSubject: "+d['subject']+"\n\n"+d['email_body']+"\n\n"+notes+"\n")
    dp="/tmp/draft.json"; json.dump(d,open(dp,'w'),indent=1,ensure_ascii=False)
    save(rec,[cover,tmp,dp],readme,local.strftime('%Y-%m-%d'))
    json.dump({"percent":s['pct'],"rationale":s['rationale'],"caution":s['caution'],"gaps":s['gaps'],"mandatory_unmet":[],"mandatory_unresolved":["Engineers Australia eligibility"] if s['n']=='hobsons' else [],"route":d['route'],"open":True,"employer_is_agency":False,"company":d['company'],"title":d['role']},open(f"screen/{s['n']}.json",'w'),indent=1)
    recs.append(rec)
json.dump(recs,open('local_records.json','w'),indent=1,ensure_ascii=False)
