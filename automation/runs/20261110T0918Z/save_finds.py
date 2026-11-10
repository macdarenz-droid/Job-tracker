import json, uuid, hashlib, os, sys
from datetime import datetime, timezone
sys.path.insert(0,'/workspace/job-finds'); from _save_find import save
RUN=open('/tmp/RUN').read().strip()
now=datetime.now(timezone.utc); iso=now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
local=datetime.now().astimezone(); found=local.strftime('%Y-%m-%dT%H:%M+11:00 AEDT')
def sha(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
SW="SEEK 4 day sweep on tick "+RUN+" (80 details; fresh SEEK leads mostly experienced-only, mechanical/electrical, or already screened on earlier ticks), widened with SEEK keyword searches over 14 days (junior draftsperson, graduate civil, junior civil designer, site administrator civil, project coordinator civil) and an open-web sweep (WebSearch of jobau, Prosple, Employment Hero, council boards, LinkedIn listings)."
GM="Gmail could not be checked on this tick (Gmail connector needs sign-in), so search macdarenz@gmail.com in:anywhere for the employer before applying. Dedupe: tracker.py check new; not in /workspace/job-finds or prior_outreach.json."
CALLW=["Work rights? \u2192 Subclass 485, full working rights until December 2027.","Start date and salary? \u2192 Marc to answer; nothing on record."]
specs=[
 dict(n='carelli',cover='Marc_Masarate_Carelli_Graduate_Project_Management_Cover_Letter.pdf',res='Marc_Masarate_Carelli_Resume.pdf',pct=66,status='READY_JEREMIE_EMPLOYER_PORTAL',source='open_web_employmenthero',listed='2026-10-26',expires=None,
  apply="Apply now on the Employment Hero job page (Employment Hero account). No application email published.",
  rationale=["Permanent full time entry level Graduate/Undergraduate Project Management role with a Notting Hill commercial builder: coordination, drawing registers and revision control, RFIs, procurement, progress claims and site inspections.",
   "Asks for a recent Engineering or related qualification and site exposure (highly desirable); Marc has the Advanced Diploma (Feb 2026), BSCE and 2019 to 2020 site coordination, inspections and procurement tracking. Matches his site coordination and documentation target.",
   "Direct employer; apply on Employment Hero."],
  caution="Commercial building rather than civil works; Procore and MS Project (advantageous) are not on record. Notting Hill is a long drive from Melton (own car). Jobau shows the listing as paused, but the Employment Hero page (posted 26 Oct 2026) still shows Apply now on 10 Nov 2026. No closing date.",
  gaps=["No Australian construction experience","Procore / MS Project not on record","Commercial building, not civil"],
  how="Found on the open web (Employment Hero job page, also on ViewJobs and jobau, posted 26 Oct 2026) and read in full on 10 Nov 2026. No published application email or named hiring contact, so no email is prepared.",
  call=["Why commercial construction? \u2192 It builds on my site coordination, drawing review and procurement tracking from 2019 to 2020.","Software? \u2192 Microsoft Office, AutoCAD, Civil 3D and Revit; no Procore yet.","Australian experience? \u2192 None yet; my site work was in the Philippines."]),
 dict(n='tigerform',cover='Marc_Masarate_Tigerform_Project_Coordinator_Cover_Letter.pdf',res='Marc_Masarate_Tigerform_Resume.pdf',pct=61,status='READY_JEREMIE_SEEK',source='seek',listed='2026-11-10',expires='2026-12-10T23:59+11:00',
  apply="SEEK quick apply (advert 95756453) with resume and cover letter; five SEEK questions.",
  rationale=["Full time Project Coordinator with a Moorabbin commercial concrete structure contractor: shop drawing review, procurement tracking, RFIs, document registers, ITPs and QA records, lookahead programs.",
   "Duties line up with Marc's drawing review, procurement and materials tracking, progress reporting and crew coordination on site in 2019 to 2020; documentation and site coordination are his target.",
   "Direct employer on SEEK."],
  caution="Asks for proven experience as a Project Coordinator or similar in construction; Marc has about 10 months of site coordination in the Philippines and no Australian experience. SEEK asks years as project coordinator (answer: less than 1 year). Commercial concrete, not civil.",
  gaps=["Under one year of coordination experience","No Australian construction experience","Project management software not on record"],
  how="Found in the SEEK 14 day keyword search 'project coordinator civil' (refreshed 10 Nov 2026, expires 10 Dec 2026). SEEK route, so no email is prepared.",
  call=["Coordination experience? \u2192 Project-in-charge on a community hall renovation (10 to 15 workers a day) and field engineer on subdivision finishing works, 2019 to 2020.","Shop drawings? \u2192 I reviewed structural and architectural drawings against project requirements on site.","Concrete structures? \u2192 Not yet; keen to learn."]),
]
recs=[]
for s in specs:
    d=json.load(open(f"drafts/{s['n']}.json"))
    cover=os.path.abspath(s['cover']); res=os.path.abspath(s['res'])
    how=SW+" "+s['how']+" "+GM+" Drafted from facts.json only; checks.py facts and tone OK; cover letter (compact_pdf.py) and tailored resume both one page, read back. Nothing was sent. Saved locally only (tracker full, Marc 20 Oct 2026)."
    call=s['call']+CALLW
    notes="HOW GROK AI FOUND THIS\n"+how+"\n\nIF THEY CALL, LIKELY QUESTIONS\n"+"\n".join('\u2022 '+c for c in call)
    d['notes']=notes; rid=str(uuid.uuid4())
    rec={"id":rid,"key":"manual:"+rid,"contributor_name":"Grok AI","created_by":"grok-job-search","record_kind":"AUTOMATED_LEAD","run_id":RUN,"created_at":iso,"updated_at":iso,"version":1,
     "attachments":[{"kind":"cover","filename":s['cover'],"sha256":sha(cover),"stored_in":"local:/workspace/job-finds"},{"kind":"resume","filename":s['res'],"sha256":sha(res),"stored_in":"local:/workspace/job-finds","note":"tailored one page resume built from facts.json"}],
     "company":d['company'],"role":d['role'],"location":d['location'],"job_url":d['job_url'],"company_url":d['company_url'],"status":s['status'],"application_type":"ADVERTISED_VACANCY","vacancy_status":d['vacancy_status'],
     "application_route":d['route'],"application_method":{"EMPLOYER_PORTAL":"Company website","SEEK":"SEEK"}[d['route']],"recipient_name":"","recipient_role":d['recipient_role'],"recipient_email":"","contact_email":"",
     "contact_evidence_url":d['contact_evidence_url'],"contact_verified_at":iso,"contact_confidence":"none","subject":d['subject'],"email_body":d['email_body'],"fit":s['rationale'],"gaps":s['gaps'],
     "match_score":{"percent":s['pct'],"method":"resume-fit-v2","rationale":s['rationale'],"caution":s['caution']},
     "advert":{"source":s['source'],"listed_at":s['listed'],"expires_at":s['expires'],"verified_at":iso,"apply_instructions":s['apply'],"screening_questions":[x['q'] for x in d['screening_answers']] if s['n']=='tigerform' else []},
     "screening_answers":d['screening_answers'],"checklist":d['checklist'],"notes":notes,"how_found":how,"call_prep":call,"checked_at":iso,"seek_id":d['seek_id'],
     "duplicate_key":d['company'].lower().split()[0]+"|"+s['n'],"preparation_only":True,"found_at":found}
    readme=(f"# {d['company']}, {d['role']}, {d['location']}\n\n- Status: {s['status']}, fit {s['pct']}%, route {d['route']}\n- Link: {d['job_url']}\n- Apply: {s['apply']}\n- Closes: {s['expires'] or 'no closing date shown'}\n- Why: {' '.join(s['rationale'])}\n- Caution: {s['caution']}\n- Gaps: {'; '.join(s['gaps'])}\n"
      "- Files: record.json, draft.json (letter), cover letter PDF (1 page, read back), tailored resume PDF (1 page).\n\n## Checklist\n"+"\n".join(f"{i+1}. {c}" for i,c in enumerate(d['checklist']))+
      "\n\n## Screening answers\n"+"\n".join(f"- {x['q']}: {x['a']}" for x in d['screening_answers'])+"\n\n"+notes+"\n")
    dp="/tmp/draft.json"; json.dump(d,open(dp,'w'),indent=1,ensure_ascii=False)
    save(rec,[cover,res,dp],readme,local.strftime('%Y-%m-%d'))
    json.dump({"percent":s['pct'],"rationale":s['rationale'],"caution":s['caution'],"gaps":s['gaps'],"mandatory_unmet":[],"mandatory_unresolved":[],"route":d['route'],"open":True,"employer_is_agency":False,"company":d['company'],"title":d['role'],"location":d['location'],"url":d['job_url']},open(f"screen/{s['n']}.json",'w'),indent=1)
    recs.append(rec)
json.dump(recs,open('local_records.json','w'),indent=1,ensure_ascii=False)
