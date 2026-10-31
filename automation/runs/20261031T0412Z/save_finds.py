import json, uuid, hashlib, shutil, sys, os
from datetime import datetime, timezone
sys.path.insert(0,'/workspace/job-finds'); from _save_find import save
RUN='20261031T0412Z'
now=datetime.now(timezone.utc); iso=now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
local=datetime.now().astimezone(); found=local.strftime('%Y-%m-%dT%H:%M+11:00 AEDT')
RES='/workspace/repos/Portfolio/assets/Marc-Darenz-Masarate-Resume.pdf'
def sha(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
C={x['seek_id']:x for x in json.load(open('candidates.json'))['candidates']}
C.update({x['seek_id']:x for x in json.load(open('cand7.json'))['candidates']})
specs=[
 dict(n='walgett',cover='Marc_Masarate_Walgett_Shire_Council_Roads_Engineer_Cover_Letter.pdf',res='Marc_Masarate_Walgett_Shire_Council_Resume.pdf',pct=62,status='READY_JEREMIE_EMPLOYER_PORTAL',conf='none',
  rationale=["Roads Engineer at a regional NSW council: road investigations, scoping and estimates, design, construction monitoring, maintenance and flood restoration, with no minimum years stated and relocation assistance plus shared housing offered.",
   "Matches Marc's BSCE (2019), Advanced Diploma road geometry, earthworks, pavement and stormwater design to Austroads, cost estimates and bills of quantities, and Philippines site inspections, quality checks and progress reporting; Class C licence and Construction Induction Card (White Card) held.",
   "Direct employer (council); SEEK links out to Council's online application form, closes 9.00am Monday 16 November 2026."],
  caution="Advert wants experience delivering road, pavement or drainage works plus contract administration and financial monitoring; Marc's is coursework and about 1 year of Philippines site work, no Australian road projects or TfNSW specifications. Walgett is remote north western NSW; relocation is Marc's call. Salary $78,000 to $95,411.",
  gaps=["No Australian road construction or maintenance experience","Contract administration and TfNSW standards not on record","Relocation to Walgett not confirmed"],
  how_src="SEEK 3 day sweep on tick "+RUN+" (1179 seen, 232 past the prefilter, 60 details). Advert 95577489 listed 29 Oct 2026, closes 9.00am 16 Nov 2026 AEDT (SEEK expiry 28 Nov). No named hiring contact; the advert gives jobs@walgett.nsw.gov.au for questions only and asks for applications through Council's online form, so the route is the employer portal.",
  call=["Why Walgett? \u2192 Practical roads work from investigation to construction on a regional network is the career I want, and the Council supports relocation.",
   "Road design experience? \u2192 Road geometry, earthworks, pavement and stormwater drainage in Civil 3D and AutoCAD to Austroads in my Advanced Diploma.",
   "Site experience? \u2192 Field engineer and project-in-charge in the Philippines 2019 to 2020: inspections, quality checks, materials tracking, progress reports, 10 to 15 workers a day.",
   "Would you move to Walgett? \u2192 Marc to answer; applications only say open to discussing relocation.",
   "Work rights? \u2192 Subclass 485, full working rights until December 2027.",
   "Start date and salary? \u2192 Marc to answer; nothing on record."]),
 dict(n='lgc',cover='Marc_Masarate_LGC_Traffic_Management_Civil_Engineering_Technician_Cover_Letter.pdf',res='Marc_Masarate_LGC_Traffic_Management_Resume.pdf',pct=60,status='READY_JEREMIE_SEEK',conf='none',
  rationale=["Civil Engineering Technician at a Perth traffic management business: TMPs and traffic guidance schemes in AutoCAD and GIS, site inspections and data collection, risk assessments and SWMS, equipment quantities, permits and drawing registers.",
   "Qualification route met by the Advanced Diploma of Civil Construction Design (diploma or 3 years experience); AutoCAD, Civil 3D, Austroads and AS 1742.14 coursework, site inspections, safety checks and record keeping from the Philippines; White Card held.",
   "Direct employer; apply on SEEK with seven screening questions."],
  caution="Traffic management focus: GIS, AS 1742.3, AGTTM and Main Roads WA standards are not on record, no traffic control experience and no High Risk Work licence on record; AWTM accreditation would need to be obtained. Perth relocation for Marc to confirm. No salary shown.",
  gaps=["No traffic management or traffic control experience","GIS software and Main Roads WA standards not used on a job","AWTM accreditation and Perth relocation not confirmed"],
  how_src="SEEK widened 7 day sweep on tick "+RUN+" (80 details). Advert 95510637 listed 27 Oct 2026, expires 26 Nov 2026 AEDT. No application email or named contact in the advert, so the route is SEEK.",
  call=["Why traffic management? \u2192 Preparing traffic guidance schemes and supporting site and permit work is a practical start to my civil career in Australia.",
   "AutoCAD and standards? \u2192 AutoCAD and Civil 3D drawings to Australian Standards including AS 1742.14 in my Advanced Diploma; no traffic management job yet.",
   "Site safety experience? \u2192 Site inspections, safety checks and quality monitoring in the Philippines 2019 to 2020.",
   "Will you get AWTM and move to Perth? \u2192 Marc to answer.",
   "Work rights? \u2192 Subclass 485, full working rights until December 2027.",
   "Start date and salary? \u2192 Marc to answer; nothing on record."]),
]
recs=[]
for s in specs:
    d=json.load(open(f"drafts/{s['n']}.json")); a=C[d['seek_id']]
    cover=os.path.abspath(s['cover']); tmp='/tmp/'+s['res']; shutil.copy(RES,tmp)
    how=s['how_src']+" Dedupe: not blocked by tracker.py check, not in /workspace/job-finds; Gmail in:anywhere search for the employer name and domain on 31 Oct 2026 found nothing, and no SEEK receipts in the last 14 days (no hits for Walgett, LGC Traffic or City of Ryde). Email body and cover letter drafted from facts.json only and passed checks.py tone and facts; cover letter rendered with compact_pdf.py (one page, read back). Nothing was sent. Saved locally only (tracker full, Marc 20 Oct 2026)."
    notes="HOW GROK AI FOUND THIS\n"+how+"\n\nIF THEY CALL, LIKELY QUESTIONS\n"+"\n".join('\u2022 '+c for c in s['call'])
    d['notes']=notes
    rid=str(uuid.uuid4())
    rec={"id":rid,"key":"manual:"+rid,"contributor_name":"Grok AI","created_by":"grok-job-search","record_kind":"AUTOMATED_LEAD","run_id":RUN,"created_at":iso,"updated_at":iso,"version":1,
     "attachments":[{"kind":"cover","filename":s['cover'],"sha256":sha(cover),"stored_in":"local:/workspace/job-finds"},{"kind":"resume","filename":s['res'],"sha256":sha(tmp),"stored_in":"local:/workspace/job-finds"}],
     "company":d['company'],"role":d['role'],"location":d['location'],"job_url":d['job_url'],"company_url":d['company_url'],"status":s['status'],"application_type":"ADVERTISED_VACANCY","vacancy_status":"OPEN_SEEK",
     "application_route":d['route'],"application_method":"Email" if d['route']=='EMAIL' else ("Company website" if d['route']=='EMPLOYER_PORTAL' else "SEEK"),"recipient_name":"","recipient_role":d['recipient_role'],"recipient_email":d['recipient_email'],"contact_email":d['recipient_email'],
     "contact_evidence_url":d['contact_evidence_url'],"contact_verified_at":iso,"contact_confidence":s['conf'],"subject":d['subject'],"email_body":d['email_body'],"fit":s['rationale'],"gaps":s['gaps'],
     "match_score":{"percent":s['pct'],"method":"resume-fit-v2","rationale":s['rationale'],"caution":s['caution']},
     "advert":{"source":"seek","listed_at":a['listed_at'],"expires_at":a['expires_at'],"verified_at":iso,"apply_instructions":("Apply on SEEK" if d['route']=='SEEK' else "SEEK links out to Council online application form; resume required, cover letter highly regarded" if d['route']=='EMPLOYER_PORTAL' else "Apply Now on SEEK or email resume and cover letter to "+d['recipient_email']),"screening_questions":a['screening_questions']},
     "screening_answers":d['screening_answers'],"checklist":d['checklist'],"notes":notes,"how_found":how,"call_prep":s['call'],"checked_at":iso,"seek_id":d['seek_id'],
     "duplicate_key":d['company'].lower().split()[0]+"|"+d['seek_id'],"preparation_only":True,"found_at":found}
    route="Council online form via SEEK" if d['route']=='EMPLOYER_PORTAL' else f"EMAIL to {d['recipient_email']} (or SEEK)" if d['route']=='EMAIL' else "SEEK"
    readme=(f"# {d['company']}, {d['role']}, {d['location']}\n\n- Status: {s['status']}, fit {s['pct']}%, route {route}\n- Link: {d['job_url']}\n- Why: {' '.join(s['rationale'])}\n- Caution: {s['caution']}\n- Gaps: {'; '.join(s['gaps'])}\n"
      "- Files: record.json, draft.json (email body and letter), cover letter PDF (1 page, read back), resume PDF.\n\n## Checklist\n"+"\n".join(f"{i+1}. {c}" for i,c in enumerate(d['checklist']))+
      "\n\n## Screening answers\n"+"\n".join(f"- {x['q']}: {x['a']}" for x in d['screening_answers'])+"\n\n## Email draft\n\nSubject: "+d['subject']+"\n\n"+d['email_body']+"\n\n"+notes+"\n")
    dp=f"/tmp/draft.json"; json.dump(d,open(dp,'w'),indent=1,ensure_ascii=False)
    save(rec,[cover,tmp,dp],readme,local.strftime('%Y-%m-%d'))
    json.dump({"percent":s['pct'],"rationale":s['rationale'],"caution":s['caution'],"gaps":s['gaps'],"mandatory_unmet":[],"mandatory_unresolved":[],"route":d['route'],"apply_email":d['recipient_email'],"open":True,"employer_is_agency":False,"company":d['company'],"title":d['role']},open(f"screen/{s['n']}.json",'w'),indent=1)
    recs.append(rec)
json.dump(recs,open('local_records.json','w'),indent=1,ensure_ascii=False)
