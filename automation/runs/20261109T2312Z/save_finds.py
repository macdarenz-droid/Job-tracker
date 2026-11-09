import json, uuid, hashlib, shutil, sys, os
from datetime import datetime, timezone
sys.path.insert(0,'/workspace/job-finds'); from _save_find import save
RUN=open('/tmp/RUN').read().strip()
now=datetime.now(timezone.utc); iso=now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
local=datetime.now().astimezone(); found=local.strftime('%Y-%m-%dT%H:%M+11:00 AEDT')
RES='/workspace/repos/Portfolio/assets/Marc-Darenz-Masarate-Resume.pdf'
def sha(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
P=json.load(open('det/95636735.json')); Y=json.load(open('extra/yarra-city-council.json'))
SW="SEEK 14 day sweep on tick "+RUN+" (1473 seen, 377 past the prefilter, 80 details; widened from 3 days because the previous tick ran five hours earlier) plus an open-web council sweep (WebSearch of council careers, PageUp, Jora, GradConnection)."
CALLW=["Work rights? \u2192 Subclass 485, full working rights until December 2027.","Start date and salary? \u2192 Marc to answer; nothing on record."]
specs=[
 dict(n='yarra',cover='Marc_Masarate_Yarra_City_Council_Civil_Works_Project_Officer_Cover_Letter.pdf',res='Marc_Masarate_Yarra_City_Council_Resume.pdf',pct=68,status='READY_JEREMIE_EMPLOYER_PORTAL',A=Y,source='yarra_pageup',
  rationale=["Band 5 Civil Works Project Officer (temporary full time to 16 Apr 2027, from $80,410 + super + RDO) in Yarra's Development and Civil Engineering team: scoping and inspecting reinstatement works on Council roads and footpaths, supervising contractors, QA and Road Management Plan inspections.",
   "Matches Marc's site coordination target: Philippines site inspections, quality checks, crew and subcontractor coordination and reporting, plus Advanced Diploma road and pavement documentation and Before You Dig enquiries. No minimum years; experience is only 'highly desirable'. Melbourne, commutable from Melton.",
   "Direct employer (council); apply on the Yarra PageUp portal. Named enquiry contact published in the advert."],
  caution="Position Description with the Key Selection Criteria could not be downloaded (site bot protection), so any further essential criteria are unverified; read it before applying. Temporary role. No Australian or council experience.",
  gaps=["Position Description KSC not read (download blocked)","No Australian or local government experience","Road Management Plan and permit work not on record"],
  how=SW+" Found on the Yarra City Council careers site (PageUp job 496994), advertised 9 Nov 2026, closes 11.55pm 22 Nov 2026. The advert names Justin Cochrane, Team Leader Development and Civil Engineering, with his council email for enquiries; applications go through PageUp, so the email draft is kept only for after Marc applies and approves it.",
  call=["Why council? \u2192 Site based inspection and contractor coordination work on public assets is where my site experience fits best.","Inspection experience? \u2192 Site inspections, safety and quality checks in the Philippines 2019 to 2020, escalating issues for corrective action.","Contractor coordination? \u2192 Coordinated 10 to 15 workers a day and worked with subcontractors and suppliers to sort out site issues.","Do you know the Road Management Plan? \u2192 Not yet on a job; Marc to prepare by reading Yarra's Road Management Plan.","Police check? \u2192 Marc to answer; willing to undergo pre-employment checks."]+CALLW),
 dict(n='proterra',cover='Marc_Masarate_Proterra_Civil_Designer_Cover_Letter.pdf',res='Marc_Masarate_Proterra_Resume.pdf',pct=61,status='READY_JEREMIE_SEEK',A=P,source='seek',
  rationale=["Civil Designer at a regional Queensland engineering firm (Toowoomba) working with RPEQ engineers on roads, intersections, subdivisions, drainage, floodways and council projects, from concept to construction.",
   "Discipline match to Marc's Advanced Diploma road, earthworks, pavement and stormwater design in AutoCAD and Civil 3D; advert says 'you don't need to know everything' and lists no minimum years.",
   "Direct employer; apply on SEEK with four screening questions."],
  caution="Ideally wants strong AutoCAD and 12d Model experience and civil infrastructure design experience; Marc's CAD is academic and he has not used 12d. Toowoomba relocation for Marc to confirm. Not pitched as junior, so fit is borderline.",
  gaps=["12d Model not on record","No commercial civil design experience","Toowoomba relocation not confirmed"],
  how=SW+" SEEK advert 95636735 listed 2 Nov 2026, expires 2 Dec 2026. No named contact or application email, so the route is SEEK.",
  call=["Why Proterra? \u2192 Practical regional roads, subdivision and drainage design that I can see built.","12d? \u2192 Not yet; AutoCAD and Civil 3D from my Advanced Diploma, ready to learn 12d.","Years of civil design? \u2192 No paid design role yet; two years of Advanced Diploma design coursework.","Would you move to Toowoomba? \u2192 Marc to answer."]+CALLW),
]
recs=[]
for s in specs:
    d=json.load(open(f"drafts/{s['n']}.json")); a=s['A']
    cover=os.path.abspath(s['cover']); tmp='/tmp/'+s['res']; shutil.copy(RES,tmp)
    how=s['how']+" Dedupe: not blocked by tracker.py check, not in /workspace/job-finds; Gmail in:anywhere (includeSpamTrash) search for the employer on 10 Nov 2026 found no receipt or prior email. Email body and cover letter drafted from facts.json only and passed checks.py tone and facts; cover letter rendered with compact_pdf.py (one page, read back). Nothing was sent. Saved locally only (tracker full, Marc 20 Oct 2026)."
    notes="HOW GROK AI FOUND THIS\n"+how+"\n\nIF THEY CALL, LIKELY QUESTIONS\n"+"\n".join('\u2022 '+c for c in s['call'])
    d['notes']=notes; rid=str(uuid.uuid4())
    portal=d['route']=='EMPLOYER_PORTAL'
    rec={"id":rid,"key":"manual:"+rid,"contributor_name":"Grok AI","created_by":"grok-job-search","record_kind":"AUTOMATED_LEAD","run_id":RUN,"created_at":iso,"updated_at":iso,"version":1,
     "attachments":[{"kind":"cover","filename":s['cover'],"sha256":sha(cover),"stored_in":"local:/workspace/job-finds"},{"kind":"resume","filename":s['res'],"sha256":sha(tmp),"stored_in":"local:/workspace/job-finds"}],
     "company":d['company'],"role":d['role'],"location":d['location'],"job_url":d['job_url'],"company_url":d['company_url'],"status":s['status'],"application_type":"ADVERTISED_VACANCY","vacancy_status":d['vacancy_status'],
     "application_route":d['route'],"application_method":"Company website" if portal else "SEEK","recipient_name":d['recipient_name'],"recipient_role":d['recipient_role'],"recipient_email":d['recipient_email'],"contact_email":d['recipient_email'],
     "contact_evidence_url":d['contact_evidence_url'],"contact_verified_at":iso,"contact_confidence":"published_direct" if d['recipient_email'] else "none","subject":d['subject'],"email_body":d['email_body'],"fit":s['rationale'],"gaps":s['gaps'],
     "match_score":{"percent":s['pct'],"method":"resume-fit-v2","rationale":s['rationale'],"caution":s['caution']},
     "advert":{"source":s['source'],"listed_at":a['listed_at'],"expires_at":a['expires_at'],"verified_at":iso,"apply_instructions":a.get('apply_instructions') or "Apply on SEEK","screening_questions":a.get('screening_questions',[])},
     "screening_answers":d['screening_answers'],"checklist":d['checklist'],"notes":notes,"how_found":how,"call_prep":s['call'],"checked_at":iso,"seek_id":d['seek_id'],
     "duplicate_key":d['company'].lower().split()[0]+"|"+(d['seek_id'] or 'pageup-496994'),"preparation_only":True,"found_at":found}
    readme=(f"# {d['company']}, {d['role']}, {d['location']}\n\n- Status: {s['status']}, fit {s['pct']}%, route {d['route']}\n- Link: {d['job_url']}\n- Why: {' '.join(s['rationale'])}\n- Caution: {s['caution']}\n- Gaps: {'; '.join(s['gaps'])}\n"
      +(f"- Contact (enquiries only, not sent): {d['recipient_name']}, {d['recipient_role']}, {d['recipient_email']}\n" if d['recipient_email'] else "")+
      "- Files: record.json, draft.json (email body and letter), cover letter PDF (1 page, read back), resume PDF.\n\n## Checklist\n"+"\n".join(f"{i+1}. {c}" for i,c in enumerate(d['checklist']))+
      "\n\n## Screening answers\n"+"\n".join(f"- {x['q']}: {x['a']}" for x in d['screening_answers'])+"\n\n## Email draft (not sent)\n\nSubject: "+d['subject']+"\n\n"+d['email_body']+"\n\n"+notes+"\n")
    dp="/tmp/draft.json"; json.dump(d,open(dp,'w'),indent=1,ensure_ascii=False)
    save(rec,[cover,tmp,dp],readme,local.strftime('%Y-%m-%d'))
    json.dump({"percent":s['pct'],"rationale":s['rationale'],"caution":s['caution'],"gaps":s['gaps'],"mandatory_unmet":[],"mandatory_unresolved":[],"route":d['route'],"open":True,"employer_is_agency":False,"company":d['company'],"title":d['role']},open(f"screen/{s['n']}.json",'w'),indent=1)
    recs.append(rec)
json.dump(recs,open('local_records.json','w'),indent=1,ensure_ascii=False)
