import json, uuid, hashlib, os, sys
from datetime import datetime, timezone
sys.path.insert(0,'/workspace/job-finds'); from _save_find import save
RUN=open('/tmp/RUN').read().strip()
now=datetime.now(timezone.utc); iso=now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
local=datetime.now().astimezone(); found=local.strftime('%Y-%m-%dT%H:%M+11:00 AEDT')
def sha(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
SW="Open-web sweep on tick "+RUN+" (jobau, ZipRecruiter, Prosple, GradConnection, Employment Hero, LinkedIn, Melton City Council applynow board, employer careers pages) plus a SEEK 3 day sweep (60 details, nothing unscreened at fit 60) widened to a 7 day SEEK sweep (80 details)."
GM="Gmail could not be checked on this tick (no Gmail connector attached), so search macdarenz@gmail.com in:anywhere for the employer before applying. Dedupe: tracker.py check new; not in /workspace/job-finds or prior_outreach.json."
CALLW=["Work rights? \u2192 Subclass 485, full working rights until December 2027.","Start date and salary? \u2192 Marc to answer; nothing on record."]
specs=[
 dict(n='cpb',cover='Marc_Masarate_CPB_Document_Controller_Cover_Letter.pdf',res='Marc_Masarate_CPB_Resume.pdf',pct=63,status='READY_JEREMIE_EMPLOYER_PORTAL',source='open_web_cpb_pageup',listed='2026-11-06',expires=None,
  apply="Apply on CPB Contractors' PageUp careers page (job 1005896). Agency applications not accepted; no application email published.",
  rationale=["Permanent full time Document Controller on CPB's 80 MW Truganina data centre (with UGL and EIC): managing drawings and design updates, registers, issuing/tracking/archiving documents, review workflows, revisions, reports and records.",
   "Lines up with Marc's site record keeping (site reports, material records, progress reports), drawing review on the community hall job and his AutoCAD/Civil 3D drawing work; advert only says candidates will likely bring document control or project administration experience.",
   "Tier 1 direct employer about 20 minutes from Melton; no citizenship or PR requirement stated."],
  caution="No formal document control role or document management system (Aconex or similar) on record; the advert expects such experience as likely, not mandatory. Data centre project, so the civil content is limited to inground services and finishing works. No closing date shown.",
  gaps=["No formal document control experience","No document management system experience on record","No Australian construction experience"],
  how="Found on the open web (ZipRecruiter, posted 6 Nov 2026) and read in full on CPB's own PageUp careers page (job 1005896) on 11 Nov 2026. No application email is published, so no email is prepared.",
  call=["Document control experience? \u2192 Not a formal role yet; on site I kept site reports, material records and progress reports and reviewed drawings against project requirements.","Systems? \u2192 Microsoft Office and Google Workspace; I have not used Aconex or a similar system yet.","Accuracy under volume? \u2192 In technical support I handled 40 to 60 cases a day with accurate case notes."]),
 dict(n='bmd',cover='Marc_Masarate_BMD_Site_Engineer_Cover_Letter.pdf',res='Marc_Masarate_BMD_Resume.pdf',pct=64,status='HELD_MANDATORY_UNRESOLVED',source='seek',listed='2026-11-06',expires='2026-12-07T23:59+10:30',
  apply="SEEK apply (advert 95755286) with resume and cover letter; no screening questions listed.",
  rationale=["Full time Site Engineer in BMD Constructions' Adelaide major infrastructure team: planning and coordinating civil works, subcontractors, suppliers and materials, ITPs and quality records, drawing and specification review.",
   "Matches Marc's 2019 to 2020 field engineer work (inspections, quality checks, procurement and materials tracking, progress reports, coordinating subcontractors and suppliers) plus his BSCE and civil design diploma; advert accepts experience or exposure.",
   "Direct employer; held only because one stated requirement is unresolved."],
  caution="HELD: the advert asks for a civil engineering qualification recognised by Engineers Australia; Marc's BSCE (Philippines, 2019) has no EA assessment on record. Adelaide means relocation, which Marc has not confirmed. Tier 1/Tier 2 experience highly regarded; Marc has none in Australia. SEEK expiry 7 Dec 2026.",
  gaps=["Engineers Australia recognition of BSCE unresolved","Relocation to Adelaide not confirmed","No Australian or Tier 1/2 construction experience","No Australian ITP system experience"],
  how="Found on the 7 day SEEK sweep (advert 95755286, listed 6 Nov 2026, expires 7 Dec 2026) and read in full on 11 Nov 2026. Held as HELD_MANDATORY_UNRESOLVED because of the Engineers Australia recognition line. Nothing sent.",
  call=["Engineers Australia? \u2192 BSCE from the Philippines (2019); no EA assessment on record (Marc to answer).","ITPs and quality records? \u2192 I did quality checks and site reports; I have not used Australian ITP systems yet.","Relocation? \u2192 Open to discussing a move to Adelaide for the right role (Marc to confirm)."]),
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
     "application_route":d['route'],"application_method":{'EMPLOYER_PORTAL':'Company website','SEEK':'SEEK'}[d['route']],"recipient_name":"","recipient_role":d['recipient_role'],"recipient_email":"","contact_email":"",
     "contact_evidence_url":d['contact_evidence_url'],"contact_verified_at":iso,"contact_confidence":"none","subject":d['subject'],"email_body":d['email_body'],"fit":s['rationale'],"gaps":s['gaps'],
     "match_score":{"percent":s['pct'],"method":"resume-fit-v2","rationale":s['rationale'],"caution":s['caution']},
     "advert":{"source":s['source'],"listed_at":s['listed'],"expires_at":s['expires'],"verified_at":iso,"apply_instructions":s['apply'],"screening_questions":[x['q'] for x in d['screening_answers']] if False else []},
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
