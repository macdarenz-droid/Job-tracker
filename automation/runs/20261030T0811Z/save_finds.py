import json, uuid, hashlib, shutil, sys, os
from datetime import datetime, timezone
sys.path.insert(0,'/workspace/job-finds'); from _save_find import save
RUN='20261030T0811Z'
now=datetime.now(timezone.utc); iso=now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
local=datetime.now().astimezone(); found=local.strftime('%Y-%m-%dT%H:%M+11:00 AEDT')
RES='/workspace/repos/Portfolio/assets/Marc-Darenz-Masarate-Resume.pdf'
def sha(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
C={x['seek_id']:x for x in json.load(open('candidates.json'))['candidates']}
specs=[
 dict(n='lcwater',cover='Marc_Masarate_LC_Water_Junior_Civil_Draftsperson_Cover_Letter.pdf',res='Marc_Masarate_LC_Water_Resume.pdf',pct=78,status='READY_JEREMIE_SEEK',conf='none',
  rationale=["Entry-level civil drafting role (site layouts, slabs, equipment foundations, access roads, GA drawings, drawing registers and revisions) that welcomes recent graduates and TAFE students, matching Marc's Advanced Diploma drafting in AutoCAD and Civil 3D.",
   "Geelong (Norlane) is commutable from Melton; no citizenship or experience requirement in the advert, only basic AutoCAD and 3D modelling plus a drafting or civil qualification, both of which Marc has.",
   "Direct employer (LC Water, water and wastewater treatment design and construct, about 22 staff); apply through SEEK, which carries three screening questions."],
  caution="CAD experience is academic, not commercial production drafting. No water or wastewater project experience. SEEK asks Marc to self-rate English; that answer is his. A published LC Water contact (darrenpickett@lcwater.com.au on LinkedIn) exists but is not named for applications, so no email draft is addressed to it.",
  gaps=["Commercial drafting experience (study only)","No water or wastewater treatment project experience","No Australian work experience yet"],
  how_src="SEEK default sweep (3 days, 1289 seen, 268 past the prefilter, 60 details) on tick "+RUN+". Advert 95506594 listed 26 Oct 2026, expires 27 Nov 2026 AEDT. Company details from lcwater.com.au and LC Water's LinkedIn page; no application email is published, so the route is SEEK.",
  call=["Why drafting at LC Water? \u2192 Your advert says the role shows how drawings turn into real construction; I want to draft site layouts, slabs and foundations and see them built.",
   "What CAD have you used? \u2192 AutoCAD 2D/3D, Civil 3D and Revit, in my Advanced Diploma coursework, not in a commercial office.",
   "Any water or wastewater experience? \u2192 No; my site work was a community hall renovation and subdivision finishing works in the Philippines.",
   "Can you get to Norlane every day? \u2192 I'm in Melton with a licence and my own car.",
   "Work rights? \u2192 Subclass 485, full working rights until December 2027.",
   "Start date and salary? \u2192 Marc to answer; nothing on record."]),
 dict(n='agt',cover='Marc_Masarate_AGT_Junior_Civil_Engineer_Cover_Letter.pdf',res='Marc_Masarate_AGT_Resume.pdf',pct=66,status='PREPARED_NOT_SENT',conf='published_inbox',
  rationale=["Junior Civil Engineer for recent graduates or engineers with up to three years' experience, mixing retaining wall design, estimates, drawing review, site set-out, inspections and QA documentation, which suits Marc's BSCE, Advanced Diploma and Philippines site work.",
   "Requirements are a civil engineering degree, driver's licence and White Card, all of which Marc has; PLAXIS and retaining wall experience are listed as helpful, not essential.",
   "Direct employer (Australian Ground Technologies, Rouse Hill, about 10 staff); AGT's own LinkedIn post of 20 Oct 2026 invites CVs to admin@australiangroundtechnologies.com.au as well as the SEEK advert."],
  caution="Sydney (Rouse Hill) role while Marc is in Melton: relocation must be confirmed by Marc before applying. No PLAXIS, geotechnical or retaining wall design experience. Salary question on SEEK is Marc's to answer.",
  gaps=["Relocation to Sydney not confirmed","No PLAXIS or geotechnical modelling","No retaining wall design experience","No Australian work experience yet"],
  how_src="SEEK default sweep (3 days, 1289 seen, 268 past the prefilter, 60 details) on tick "+RUN+". Advert 95535388 listed 28 Oct 2026, expires 28 Nov 2026 AEDT, $70k to $85k plus bonuses. Contact: AGT's own LinkedIn hiring post (20 Oct 2026) says to apply via the link or send a CV to admin@australiangroundtechnologies.com.au; company site lists info@ for general enquiries.",
  call=["Why AGT? \u2192 The mix of retaining wall design, estimates and site time for set-out and inspections.",
   "Have you used PLAXIS? \u2192 No; I'd learn it with your team. My design tools are AutoCAD, Civil 3D and Revit from coursework.",
   "Geotechnical background? \u2192 Coursework only, including AS 1726 and AS 1289; no retaining wall design on a job.",
   "Are you moving to Sydney? \u2192 Marc to answer; applications only say open to discussing relocation.",
   "Site experience? \u2192 About a year in the Philippines, 2019 to 2020: project-in-charge on a community hall renovation (10 to 15 workers a day, drawing reviews, inspections) and field engineer on subdivision finishing works.",
   "Work rights? \u2192 Subclass 485, full working rights until December 2027.",
   "Salary and start date? \u2192 Marc to answer; nothing on record."]),
]
recs=[]
for s in specs:
    d=json.load(open(f"drafts/{s['n']}.json")); a=C[d['seek_id']]
    cover=os.path.abspath(s['cover']); tmp='/tmp/'+s['res']; shutil.copy(RES,tmp)
    how=s['how_src']+" Dedupe: not blocked by tracker.py check, not in /workspace/job-finds; Gmail in:anywhere search for the employer name and domain on 30 Oct 2026 found nothing, and no SEEK receipts in the last 10 days. Email body and cover letter drafted from facts.json only and passed checks.py tone and facts; cover letter rendered with compact_pdf.py (one page, read back). Nothing was sent. Saved locally only (tracker full, Marc 20 Oct 2026)."
    notes="HOW GROK AI FOUND THIS\n"+how+"\n\nIF THEY CALL, LIKELY QUESTIONS\n"+"\n".join('\u2022 '+c for c in s['call'])
    d['notes']=notes
    rid=str(uuid.uuid4())
    rec={"id":rid,"key":"manual:"+rid,"contributor_name":"Grok AI","created_by":"grok-job-search","record_kind":"AUTOMATED_LEAD","run_id":RUN,"created_at":iso,"updated_at":iso,"version":1,
     "attachments":[{"kind":"cover","filename":s['cover'],"sha256":sha(cover),"stored_in":"local:/workspace/job-finds"},{"kind":"resume","filename":s['res'],"sha256":sha(tmp),"stored_in":"local:/workspace/job-finds"}],
     "company":d['company'],"role":d['role'],"location":d['location'],"job_url":d['job_url'],"company_url":d['company_url'],"status":s['status'],"application_type":"ADVERTISED_VACANCY","vacancy_status":"OPEN_SEEK",
     "application_route":d['route'],"application_method":"Email" if d['route']=='EMAIL' else "SEEK","recipient_name":"","recipient_role":d['recipient_role'],"recipient_email":d['recipient_email'],"contact_email":d['recipient_email'],
     "contact_evidence_url":d['contact_evidence_url'],"contact_verified_at":iso,"contact_confidence":s['conf'],"subject":d['subject'],"email_body":d['email_body'],"fit":s['rationale'],"gaps":s['gaps'],
     "match_score":{"percent":s['pct'],"method":"resume-fit-v2","rationale":s['rationale'],"caution":s['caution']},
     "advert":{"source":"seek","listed_at":a['listed_at'],"expires_at":a['expires_at'],"verified_at":iso,"apply_instructions":"Apply on SEEK"+(" or email CV to admin@australiangroundtechnologies.com.au (AGT LinkedIn post)" if s['n']=='agt' else ""),"screening_questions":a['screening_questions']},
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
