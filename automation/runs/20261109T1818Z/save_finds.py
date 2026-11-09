import json, uuid, hashlib, shutil, sys, os
from datetime import datetime, timezone
sys.path.insert(0,'/workspace/job-finds'); from _save_find import save
RUN='20261109T1818Z'
now=datetime.now(timezone.utc); iso=now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
local=datetime.now().astimezone(); found=local.strftime('%Y-%m-%dT%H:%M+11:00 AEDT')
RES='/workspace/repos/Portfolio/assets/Marc-Darenz-Masarate-Resume.pdf'
def sha(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
A={i:json.load(open(f'det/{i}.json')) for i in ['95773573','95695784','95655998','95736615']}
SW="SEEK 7 day sweep on tick "+RUN+" (1305 seen, 278 past the prefilter, 60 details; SEEK detail endpoint had moved to au.seek.com/graphql and was fixed this tick, then details refetched for the shortlist)."
CALLW=["Work rights? \u2192 Subclass 485, full working rights until December 2027.","Start date and salary? \u2192 Marc to answer; nothing on record."]
specs=[
 dict(n='bench',cover='Marc_Masarate_BenchHDC_Graduate_Civil_Engineer_Cover_Letter.pdf',res='Marc_Masarate_BenchHDC_Resume.pdf',pct=66,status='READY_JEREMIE_SEEK',
  rationale=["Graduate Civil Engineer, newly created role at a South Australian HDD and underground infrastructure contractor: project coordination, scheduling, tender preparation and estimating, QA documentation, client and subcontractor liaison, site inspections. $80,000 to $100,000.",
   "Recent graduates encouraged and no drilling experience needed; matches Marc's BSCE (2019), Advanced Diploma estimates and bills of quantities, and Philippines site inspections, procurement tracking and progress reporting.",
   "Direct employer; apply on SEEK with five screening questions."],
  caution="Advert asks for a civil degree 'or equivalent recognised in Australia'; Marc's BSCE is from the Philippines and no Engineers Australia assessment is on record. Adelaide relocation for Marc to confirm.",
  gaps=["No HDD or Australian underground infrastructure experience","Australian recognition of the Philippine BSCE not on record","Adelaide relocation not confirmed"],
  how=SW+" Advert 95773573 listed 9 Nov 2026, expires 9 Dec 2026. No named contact or application email in the advert, so the route is SEEK.",
  call=["Why BenchHDC? \u2192 A broad graduate role across coordination, estimating, QA and site work is the start I want.","Estimating experience? \u2192 Cost estimates and bills of quantities in my Advanced Diploma; materials and procurement tracking on site in the Philippines.","Is your degree recognised here? \u2192 Marc to answer; BSCE 2019 from the Philippines plus the Australian Advanced Diploma (2026).","Would you move to Adelaide? \u2192 Marc to answer; applications only say open to discussing relocation."]+CALLW),
 dict(n='martinus',cover='Marc_Masarate_Martinus_Rail_Graduate_Engineer_Cover_Letter.pdf',res='Marc_Masarate_Martinus_Rail_Resume.pdf',pct=62,status='READY_JEREMIE_EMPLOYER_PORTAL',
  rationale=["Civil and Structural Graduate Engineers for the Inland Rail Albury to Parkes Enhancement Project near Forbes NSW, with a rail contractor that hires for coachability and drive.",
   "Matches Marc's civil degree plus 2026 Advanced Diploma, site inspections, quality checks and crew coordination in the Philippines, and his availability for regional project work.",
   "Direct employer; SEEK links out to the Martinus application page."],
  caution="Asks for recent graduate qualifications; Marc's BSCE is 2019, his Australian Advanced Diploma is February 2026. No rail experience. Regional NSW (Forbes) posting; relocation for Marc to confirm.",
  gaps=["No rail experience","BSCE not recent (2019)","Forbes NSW relocation not confirmed"],
  how=SW+" Advert 95695784 listed about 4 Nov 2026, expires 4 Dec 2026; link out to the Martinus site, so the route is the employer portal. No named contact.",
  call=["Why rail? \u2192 A major regional project with a team that trains graduates is how I want to start on Australian infrastructure.","Site experience? \u2192 Field engineer and project-in-charge in the Philippines 2019 to 2020: inspections, quality checks, 10 to 15 workers a day, progress reports.","Would you live near Forbes? \u2192 Marc to answer; available for regional project work."]+CALLW),
 dict(n='ttw',cover='Marc_Masarate_TTW_Trainee_Civil_Drafter_Cover_Letter.pdf',res='Marc_Masarate_TTW_Resume.pdf',pct=60,status='READY_JEREMIE_SEEK',
  rationale=["Three year Trainee Civil Drafter role at a major consulting engineer (TTW, North Sydney), trained in AutoCAD, AutoTURN, Civil 3D and 12d with mentoring.",
   "Fits Marc's target of junior civil drafting: Advanced Diploma road, earthworks, pavement and stormwater documentation in AutoCAD and Civil 3D, plus drawing review on Philippines sites.",
   "Direct employer; apply on SEEK with six screening questions."],
  caution="Traineeship requires full attendance at TAFE Ultimo for the Diploma of Civil Construction Design, which Marc already exceeds with the Advanced Diploma; likely pitched at school leavers and pay may be trainee level. Sydney relocation for Marc to confirm.",
  gaps=["12d and AutoTURN not on record","No consulting office drafting experience","Sydney relocation not confirmed"],
  how=SW+" Advert 95655998 listed 3 Nov 2026, expires 27 Nov 2026. No named contact, so the route is SEEK.",
  call=["Why a traineeship when you have an Advanced Diploma? \u2192 I want structured mentoring in a consulting drafting office to turn my coursework into professional drafting.","Software? \u2192 AutoCAD and Civil 3D from my Advanced Diploma; not yet 12d or AutoTURN.","Would you move to Sydney? \u2192 Marc to answer."]+CALLW),
]
recs=[]
for s in specs:
    d=json.load(open(f"drafts/{s['n']}.json")); a=A[d['seek_id']]
    cover=os.path.abspath(s['cover']); tmp='/tmp/'+s['res']; shutil.copy(RES,tmp)
    how=s['how']+" Dedupe: not blocked by tracker.py check, not in /workspace/job-finds; Gmail in:anywhere search for the employer on 10 Nov 2026 found no receipt or prior email. Email body and cover letter drafted from facts.json only and passed checks.py tone and facts; cover letter rendered with compact_pdf.py (one page, read back). Nothing was sent. Saved locally only (tracker full, Marc 20 Oct 2026)."
    notes="HOW GROK AI FOUND THIS\n"+how+"\n\nIF THEY CALL, LIKELY QUESTIONS\n"+"\n".join('\u2022 '+c for c in s['call'])
    d['notes']=notes; rid=str(uuid.uuid4())
    rec={"id":rid,"key":"manual:"+rid,"contributor_name":"Grok AI","created_by":"grok-job-search","record_kind":"AUTOMATED_LEAD","run_id":RUN,"created_at":iso,"updated_at":iso,"version":1,
     "attachments":[{"kind":"cover","filename":s['cover'],"sha256":sha(cover),"stored_in":"local:/workspace/job-finds"},{"kind":"resume","filename":s['res'],"sha256":sha(tmp),"stored_in":"local:/workspace/job-finds"}],
     "company":d['company'],"role":d['role'],"location":d['location'],"job_url":d['job_url'],"company_url":d['company_url'],"status":s['status'],"application_type":"ADVERTISED_VACANCY","vacancy_status":"OPEN_SEEK",
     "application_route":d['route'],"application_method":"Company website" if d['route']=='EMPLOYER_PORTAL' else "SEEK","recipient_name":"","recipient_role":d['recipient_role'],"recipient_email":"","contact_email":"",
     "contact_evidence_url":d['contact_evidence_url'],"contact_verified_at":iso,"contact_confidence":"none","subject":d['subject'],"email_body":d['email_body'],"fit":s['rationale'],"gaps":s['gaps'],
     "match_score":{"percent":s['pct'],"method":"resume-fit-v2","rationale":s['rationale'],"caution":s['caution']},
     "advert":{"source":"seek","listed_at":a['listed_at'],"expires_at":a['expires_at'],"verified_at":iso,"apply_instructions":"Apply on SEEK" if d['route']=='SEEK' else "SEEK links out to the employer's application page","screening_questions":a['screening_questions']},
     "screening_answers":d['screening_answers'],"checklist":d['checklist'],"notes":notes,"how_found":how,"call_prep":s['call'],"checked_at":iso,"seek_id":d['seek_id'],
     "duplicate_key":d['company'].lower().split()[0]+"|"+d['seek_id'],"preparation_only":True,"found_at":found}
    readme=(f"# {d['company']}, {d['role']}, {d['location']}\n\n- Status: {s['status']}, fit {s['pct']}%, route {d['route']}\n- Link: {d['job_url']}\n- Why: {' '.join(s['rationale'])}\n- Caution: {s['caution']}\n- Gaps: {'; '.join(s['gaps'])}\n"
      "- Files: record.json, draft.json (email body and letter), cover letter PDF (1 page, read back), resume PDF.\n\n## Checklist\n"+"\n".join(f"{i+1}. {c}" for i,c in enumerate(d['checklist']))+
      "\n\n## Screening answers\n"+"\n".join(f"- {x['q']}: {x['a']}" for x in d['screening_answers'])+"\n\n## Email draft\n\nSubject: "+d['subject']+"\n\n"+d['email_body']+"\n\n"+notes+"\n")
    dp="/tmp/draft.json"; json.dump(d,open(dp,'w'),indent=1,ensure_ascii=False)
    save(rec,[cover,tmp,dp],readme,local.strftime('%Y-%m-%d'))
    json.dump({"percent":s['pct'],"rationale":s['rationale'],"caution":s['caution'],"gaps":s['gaps'],"mandatory_unmet":[],"mandatory_unresolved":[],"route":d['route'],"open":True,"employer_is_agency":False,"company":d['company'],"title":d['role']},open(f"screen/{s['n']}.json",'w'),indent=1)
    recs.append(rec)
# Held: Fyfe (citizenship/PR required)
f=A['95736615']; rid=str(uuid.uuid4())
held={"id":rid,"key":"manual:"+rid,"contributor_name":"Grok AI","created_by":"grok-job-search","record_kind":"AUTOMATED_LEAD","run_id":RUN,"created_at":iso,"updated_at":iso,"version":1,"attachments":[],
 "company":"Fyfe Pty Ltd","role":"Graduate Civil Engineer (Property & Infrastructure)","location":"Adelaide SA","job_url":"https://www.seek.com.au/job/95736615","status":"HELD_MANDATORY_UNMET","application_type":"ADVERTISED_VACANCY",
 "application_route":"SEEK","match_score":{"percent":68,"method":"resume-fit-v2","rationale":["Graduate civil design role: stormwater drainage, erosion control, waterway, rail and road crossings, quantity estimates, supervised site inspections; strong match to Marc's Advanced Diploma design work."],"caution":"Advert lists Australian citizenship or permanent residency as required; Marc holds a Subclass 485 visa, so this is held, not prepared."},
 "gaps":["Australian citizenship or PR required (Marc on 485)"],"advert":{"source":"seek","listed_at":f['listed_at'],"expires_at":f['expires_at'],"verified_at":iso,"screening_questions":f['screening_questions']},
 "notes":"HOW GROK AI FOUND THIS\n"+SW+" Held because the advert requires Australian citizenship or permanent residency. No draft prepared, nothing sent.","checked_at":iso,"seek_id":"95736615","preparation_only":True,"found_at":found}
save(held,[],"# Fyfe Pty Ltd, Graduate Civil Engineer, Adelaide SA\n\n- Status: HELD_MANDATORY_UNMET, fit 68%\n- Link: https://www.seek.com.au/job/95736615\n- Why held: advert requires Australian citizenship or permanent residency; Marc is on a Subclass 485 visa.\n- Otherwise a strong design match (stormwater, roads, rail crossings, estimates). Only apply if Marc's status changes.\n",local.strftime('%Y-%m-%d'))
recs.append(held)
json.dump(recs,open('local_records.json','w'),indent=1,ensure_ascii=False)
