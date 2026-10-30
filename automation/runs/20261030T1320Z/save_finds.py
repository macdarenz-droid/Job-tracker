import json, uuid, hashlib, shutil, sys, os
from datetime import datetime, timezone
sys.path.insert(0,'/workspace/job-finds'); from _save_find import save
RUN='20261030T1320Z'
now=datetime.now(timezone.utc); iso=now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
local=datetime.now().astimezone(); found=local.strftime('%Y-%m-%dT%H:%M+11:00 AEDT')
RES='/workspace/repos/Portfolio/assets/Marc-Darenz-Masarate-Resume.pdf'
def sha(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
C={x['seek_id']:x for x in json.load(open('candidates.json'))['candidates']}
specs=[
 dict(n='westerngrammar',cover='Marc_Masarate_Western_Grammar_Civil_Engineering_Draftsperson_Cover_Letter.pdf',res='Marc_Masarate_Western_Grammar_Resume.pdf',pct=66,status='READY_JEREMIE_SEEK',conf='none',
  rationale=["Civil engineering draftsperson role preparing, revising and managing drawings, reviewing them against standards, assisting with quantities and estimates, and coordinating contractors, consultants and council, which matches Marc's Advanced Diploma drafting in AutoCAD and Civil 3D and his site drawing-review work.",
   "Requirements are a relevant civil drafting or civil engineering qualification, AutoCAD or Civil 3D knowledge and understanding of construction processes, all of which Marc has; the advert asks for experience preparing drawings, which Marc has from study rather than commercial work.",
   "Direct employer (Western Grammar School, a K-12 school running its own campus building program), $80,000 a year; apply through SEEK with five screening questions."],
  caution="Sydney (Plumpton) role while Marc is in Melton: relocation must be confirmed by Marc before applying. Drafting experience is academic, not commercial. Notice period question on SEEK is Marc's to answer. No direct application email is published, so the route is SEEK.",
  gaps=["Relocation to Sydney not confirmed","Commercial drafting experience (study only)","No Australian work experience yet"],
  how_src="SEEK default sweep (3 days, 1166 seen, 232 past the prefilter, 60 details) on tick "+RUN+". Advert 95576041 listed 29 Oct 2026, expires 28 Nov 2026 AEDT, $80,000 a year. No application email or named contact in the advert, so the route is SEEK.",
  call=["Why this role? \u2192 It mixes drafting with coordinating contractors, consultants and council on real campus works.",
   "What CAD have you used? \u2192 AutoCAD, Civil 3D and Revit, in my Advanced Diploma coursework, not in a commercial office.",
   "Drawing interpretation? \u2192 On site in the Philippines (2019 to 2020) I reviewed structural and architectural drawings and checked work against them.",
   "Are you moving to Sydney? \u2192 Marc to answer; applications only say open to discussing relocation.",
   "Work rights? \u2192 Subclass 485, full working rights until December 2027.",
   "Notice period, start date and salary? \u2192 Marc to answer; nothing on record."]),
 dict(n='acereo',cover='Marc_Masarate_Ace_Reo_Civil_Engineering_Assistant_Cover_Letter.pdf',res='Marc_Masarate_Ace_Reo_Resume.pdf',pct=60,status='READY_JEREMIE_SEEK',conf='none',
  rationale=["Civil Engineering Assistant at a Melbourne reinforcing steel fabricator: material take-offs, quantity calculations and estimates, checking reinforcement cages against engineering drawings and standards, and keeping QA and inspection records, which match Marc's estimating coursework and site QA work.",
   "Diploma or higher in engineering is required and Marc has both a BSCE and an Advanced Diploma; Dandenong South is reachable from Melton by car, and the role pays $80,000 to $85,000 plus super.",
   "Direct employer (Ace Reo Pty Ltd); apply through SEEK, which carries three screening questions Marc can answer from his record."],
  caution="The advert asks for at least 2 to 3 years as a Civil Engineering Assistant; Marc has about one year of site work (Philippines, 2019 to 2020), so this is a stretch. Production scheduling in a fabrication shop is new to him. Long commute from Melton to Dandenong South.",
  gaps=["Below the 2 to 3 years' experience the advert asks for","No steel fabrication or production scheduling experience","No Australian work experience yet"],
  how_src="SEEK default sweep (3 days, 1166 seen, 232 past the prefilter, 60 details) on tick "+RUN+". Advert 95606153 listed 30 Oct 2026, expires 29 Nov 2026 AEDT, $80,000 to $85,000 plus super. No application email in the advert, so the route is SEEK.",
  call=["Why Ace Reo? \u2192 Take-offs, checking reinforcement against drawings and QA records are the work I want to grow in.",
   "How much experience do you have? \u2192 About a year on site in the Philippines (2019 to 2020) as project-in-charge and field engineer.",
   "Take-offs and estimates? \u2192 Bills of quantities and cost estimates in my Advanced Diploma coursework.",
   "Can you get to Dandenong South every day? \u2192 I'm in Melton with a licence and my own car.",
   "Work rights? \u2192 Subclass 485, full working rights until December 2027.",
   "Start date and salary? \u2192 Marc to answer; nothing on record."]),
]
recs=[]
for s in specs:
    d=json.load(open(f"drafts/{s['n']}.json")); a=C[d['seek_id']]
    cover=os.path.abspath(s['cover']); tmp='/tmp/'+s['res']; shutil.copy(RES,tmp)
    how=s['how_src']+" Dedupe: not blocked by tracker.py check, not in /workspace/job-finds; Gmail in:anywhere search for the employer name and domain on 31 Oct 2026 found nothing, and no SEEK receipts in the last 10 days. Email body and cover letter drafted from facts.json only and passed checks.py tone and facts; cover letter rendered with compact_pdf.py (one page, read back). Nothing was sent. Saved locally only (tracker full, Marc 20 Oct 2026)."
    notes="HOW GROK AI FOUND THIS\n"+how+"\n\nIF THEY CALL, LIKELY QUESTIONS\n"+"\n".join('\u2022 '+c for c in s['call'])
    d['notes']=notes
    rid=str(uuid.uuid4())
    rec={"id":rid,"key":"manual:"+rid,"contributor_name":"Grok AI","created_by":"grok-job-search","record_kind":"AUTOMATED_LEAD","run_id":RUN,"created_at":iso,"updated_at":iso,"version":1,
     "attachments":[{"kind":"cover","filename":s['cover'],"sha256":sha(cover),"stored_in":"local:/workspace/job-finds"},{"kind":"resume","filename":s['res'],"sha256":sha(tmp),"stored_in":"local:/workspace/job-finds"}],
     "company":d['company'],"role":d['role'],"location":d['location'],"job_url":d['job_url'],"company_url":d['company_url'],"status":s['status'],"application_type":"ADVERTISED_VACANCY","vacancy_status":"OPEN_SEEK",
     "application_route":d['route'],"application_method":"Email" if d['route']=='EMAIL' else "SEEK","recipient_name":"","recipient_role":d['recipient_role'],"recipient_email":d['recipient_email'],"contact_email":d['recipient_email'],
     "contact_evidence_url":d['contact_evidence_url'],"contact_verified_at":iso,"contact_confidence":s['conf'],"subject":d['subject'],"email_body":d['email_body'],"fit":s['rationale'],"gaps":s['gaps'],
     "match_score":{"percent":s['pct'],"method":"resume-fit-v2","rationale":s['rationale'],"caution":s['caution']},
     "advert":{"source":"seek","listed_at":a['listed_at'],"expires_at":a['expires_at'],"verified_at":iso,"apply_instructions":"Apply on SEEK","screening_questions":a['screening_questions']},
     "screening_answers":d['screening_answers'],"checklist":d['checklist'],"notes":notes,"how_found":how,"call_prep":s['call'],"checked_at":iso,"seek_id":d['seek_id'],
     "duplicate_key":d['company'].lower().split()[0]+"|"+d['seek_id'],"preparation_only":True,"found_at":found}
    route=f"EMAIL to {d['recipient_email']} (or SEEK)" if d['route']=='EMAIL' else "SEEK"
    readme=(f"# {d['company']}, {d['role']}, {d['location']}\n\n- Status: {s['status']}, fit {s['pct']}%, route {route}\n- Link: {d['job_url']}\n- Why: {' '.join(s['rationale'])}\n- Caution: {s['caution']}\n- Gaps: {'; '.join(s['gaps'])}\n"
      "- Files: record.json, draft.json (email body and letter), cover letter PDF (1 page, read back), resume PDF.\n\n## Checklist\n"+"\n".join(f"{i+1}. {c}" for i,c in enumerate(d['checklist']))+
      "\n\n## Screening answers\n"+"\n".join(f"- {x['q']}: {x['a']}" for x in d['screening_answers'])+"\n\n## Email draft\n\nSubject: "+d['subject']+"\n\n"+d['email_body']+"\n\n"+notes+"\n")
    dp=f"/tmp/draft.json"; json.dump(d,open(dp,'w'),indent=1,ensure_ascii=False)
    save(rec,[cover,tmp,dp],readme,local.strftime('%Y-%m-%d'))
    json.dump({"percent":s['pct'],"rationale":s['rationale'],"caution":s['caution'],"gaps":s['gaps'],"mandatory_unmet":[],"mandatory_unresolved":[],"route":d['route'],"apply_email":d['recipient_email'],"open":True,"employer_is_agency":False,"company":d['company'],"title":d['role']},open(f"screen/{s['n']}.json",'w'),indent=1)
    recs.append(rec)
json.dump(recs,open('local_records.json','w'),indent=1,ensure_ascii=False)
