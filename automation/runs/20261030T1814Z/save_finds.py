import json, uuid, hashlib, shutil, sys, os
from datetime import datetime, timezone
sys.path.insert(0,'/workspace/job-finds'); from _save_find import save
RUN='20261030T1814Z'
now=datetime.now(timezone.utc); iso=now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
local=datetime.now().astimezone(); found=local.strftime('%Y-%m-%dT%H:%M+11:00 AEDT')
RES='/workspace/repos/Portfolio/assets/Marc-Darenz-Masarate-Resume.pdf'
def sha(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
C={x['seek_id']:x for f in ['candidates.json','candidates_d7.json'] for x in json.load(open(f))['candidates']}
import json as _j
C['95532229']=_j.load(open('/tmp/det/95532229.json'))
specs=[
 dict(n='etheredge',cover='Marc_Masarate_Etheredge_Mintern_Project_Coordinator_Cover_Letter.pdf',res='Marc_Masarate_Etheredge_Mintern_Resume.pdf',pct=62,status='READY_JEREMIE_SEEK',conf='none',
  rationale=["Project Coordinator at a Melbourne civil contractor (road reconstruction, drainage, earthworks, local government works): coordinating subcontractors, suppliers and deliveries, keeping project documentation, tracking progress and procurement, which match Marc's Philippines site coordination, procurement tracking and progress reporting.",
   "Civil design coursework (roads, earthworks, drainage) and cost estimates and bills of quantities from the Advanced Diploma support the programme and cost tracking side; Kilsyth is drivable from Melton with his licence and car.",
   "Direct employer; apply through SEEK with two screening questions Marc can answer from his record."],
  caution="The advert asks for an experienced, highly organised Project Coordinator and ideally previous coordinator or project administrator experience in construction; Marc has about a year of site coordination in the Philippines and no Australian experience, so this is a stretch at junior level. Long daily drive from Melton to Kilsyth (outer east). No salary listed.",
  gaps=["No project coordinator or project administrator title held before","No Australian construction experience yet","Progress claims, variations and SWMS administration not on record"],
  how_src="SEEK sweep on tick "+RUN+": advert 95532229 surfaced in the 3 day sweep's not-detailed list (171 listings never detailed) and was hand-checked with seek.py details. Listed 28 Oct 2026, expires 27 Nov 2026 AEDT, full time, no salary shown. No application email or named contact in the advert, so the route is SEEK.",
  call=["Why Etheredge Mintern? \u2192 Your road, drainage and earthworks jobs for councils are the civil work I want to coordinate and learn.",
   "Have you coordinated subcontractors before? \u2192 Yes, on site in the Philippines (2019 to 2020): 10 to 15 workers a day, plus engineers, subcontractors and suppliers.",
   "Documentation experience? \u2192 Site reports, material records, progress reports and procurement tracking as a field engineer.",
   "Can you get to Kilsyth every day? \u2192 I'm in Melton with a licence and my own car; Marc to confirm the commute.",
   "Work rights? \u2192 Subclass 485, full working rights until December 2027.",
   "Start date and salary? \u2192 Marc to answer; nothing on record."]),
 dict(n='ndc',cover='Marc_Masarate_Newton_Denny_Chapelle_Civil_Design_Engineer_Cover_Letter.pdf',res='Marc_Masarate_Newton_Denny_Chapelle_Resume.pdf',pct=62,status='READY_JEREMIE_SEEK',conf='none',
  rationale=["Civil Engineer / Design Engineer at a Northern NSW planning, surveying and engineering consultancy: urban development and subdivision, road design, stormwater, civil drafting and design documentation and technical reporting, which match Marc's Advanced Diploma road, earthworks, pavement and stormwater design in Civil 3D and AutoCAD.",
   "The advert accepts relevant qualifications and/or industry experience and welcomes someone taking the next step; Marc has a BSCE (2019) and the Advanced Diploma (Feb 2026), plus subdivision finishing site work in the Philippines.",
   "Direct employer; apply through SEEK (two screening questions); the cover letter must answer the advert's project experience question, which the draft does."],
  caution="Role is in Lismore or Casuarina NSW, so relocation must be confirmed by Marc before applying. The advert leans toward people with experience delivering urban development or civil projects; Marc's design work is academic and his site work is from the Philippines. No salary listed.",
  gaps=["Relocation to Northern NSW not confirmed","No commercial consultancy design experience (study only)","No Australian work experience yet; 12d not on record"],
  how_src="SEEK 7 day widened sweep (1424 seen, 308 past the prefilter, 80 details) on tick "+RUN+". Advert 95487722 listed 26 Oct 2026, closes 9am 25 Nov 2026. Contact named in the advert: Aaron Hoffman, (02) 6622 1011, office@ndc.com.au, for enquiries; the route is SEEK.",
  call=["Why NDC? \u2192 Subdivision, road and stormwater design delivered next to planners and surveyors is the mix I want to learn in.",
   "What design software have you used? \u2192 AutoCAD, Civil 3D and Revit in my Advanced Diploma coursework, not in a consultancy.",
   "Most relevant project experience? \u2192 Road geometry, earthworks, pavement and stormwater design in the Advanced Diploma, and subdivision finishing works on site in the Philippines.",
   "Will you move to the Northern Rivers? \u2192 Marc to answer; applications only say open to discussing relocation.",
   "Work rights? \u2192 Subclass 485, full working rights until December 2027.",
   "Start date and salary? \u2192 Marc to answer; nothing on record."]),
]
recs=[]
for s in specs:
    d=json.load(open(f"drafts/{s['n']}.json")); a=C[d['seek_id']]
    cover=os.path.abspath(s['cover']); tmp='/tmp/'+s['res']; shutil.copy(RES,tmp)
    how=s['how_src']+" Dedupe: not blocked by tracker.py check, not in /workspace/job-finds; Gmail in:anywhere search for the employer name and domain on 31 Oct 2026 found nothing, and no SEEK receipts in the last 14 days. Email body and cover letter drafted from facts.json only and passed checks.py tone and facts; cover letter rendered with compact_pdf.py (one page, read back). Nothing was sent. Saved locally only (tracker full, Marc 20 Oct 2026)."
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
