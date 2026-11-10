import json, uuid, hashlib, os, sys
from datetime import datetime, timezone
sys.path.insert(0,'/workspace/job-finds'); from _save_find import save
RUN=open('/tmp/RUN').read().strip()
now=datetime.now(timezone.utc); iso=now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
local=datetime.now().astimezone(); found=local.strftime('%Y-%m-%dT%H:%M+11:00 AEDT')
def sha(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
SW="SEEK 3 day sweep on tick "+RUN+" (60 details; all fresh SEEK leads were already screened on earlier ticks or blocked by recent outreach), widened to a 7 day SEEK sweep (80 details, nothing unscreened) and an open-web sweep (jobau, Prosple, GradConnection, Jora, council boards, John Holland and Worley careers, employer pages)."
GM="Gmail could not be checked on this tick (no Gmail connector attached), so search macdarenz@gmail.com in:anywhere for the employer before applying. Dedupe: tracker.py check new; not in /workspace/job-finds or prior_outreach.json."
CALLW=["Work rights? \u2192 Subclass 485, full working rights until December 2027.","Start date and salary? \u2192 Marc to answer; nothing on record."]
specs=[
 dict(n='jaydo',cover='Marc_Masarate_Jaydo_Site_Engineer_Cover_Letter.pdf',res='Marc_Masarate_Jaydo_Resume.pdf',pct=72,status='READY_JEREMIE_SEEK',source='seek',listed='2026-10-27',expires='2026-11-26T23:59+11:00',
  apply="SEEK quick apply (advert 95514711) with resume and cover letter; three SEEK questions (work rights, White Card, licence).",
  rationale=["Full time permanent Site Engineer in Jaydo's Urban Development team (Keilor Park): coordinating civil works for subdivisions and council projects, reviewing drawings, planning materials and subcontractors, RFIs, ITPs and quality records.",
   "Matches Marc's 2019 to 2020 field engineer work on subdivision finishing works (inspections, quality checks, procurement and materials tracking, progress reports) plus his BSCE and civil design diploma; the advert says you don't need to know everything from day one.",
   "Direct Victorian civil contractor about 30 minutes from Melton; White Card and licence questions are both Yes."],
  caution="Advert ideally wants civil construction experience across drainage, sewer, water or subdivisions; Marc's is from the Philippines and he has not worked on sewer or water projects. Title says EOI 2027, so the start may be in 2027. SEEK expiry 26 Nov 2026.",
  gaps=["No Australian construction experience","No sewer or water project experience","Under one year of site engineering"],
  how="Found on the open web (jobau listing published 29 Oct 2026), then matched to SEEK advert 95514711 (listed 27 Oct 2026, expires 26 Nov 2026) and read in full on 11 Nov 2026. Jaydo's careers page directs applicants to its SEEK adverts and publishes no application email, so no email is prepared.",
  call=["Subdivision experience? \u2192 Field engineer on residential subdivision finishing works in the Philippines, Sep 2019 to Feb 2020: inspections, quality checks, materials tracking and progress reports.","ITPs and quality records? \u2192 I did quality checks and site reports; I have not used Australian ITP systems yet.","Sewer and water? \u2192 Not yet; my coursework covered stormwater drainage design."]),
 dict(n='fyfe',cover='Marc_Masarate_Fyfe_Graduate_Civil_Engineer_Cover_Letter.pdf',res='Marc_Masarate_Fyfe_Resume.pdf',pct=66,status='HELD_MANDATORY_UNRESOLVED',source='open_web_fyfe_careers',listed='2026-11-07',expires=None,
  apply="Apply on Fyfe's careers page (careers-page.com/fyfe-2). Agency applications not accepted. Enquiries: careers@fyfe.com.au (published on the advert).",
  rationale=["Graduate Civil Engineer in Fyfe's Adelaide Property and Infrastructure team: civil designs, drawings, calculations, quantity estimates and supervised site inspections, including stormwater drainage, waterway crossings and roads.",
   "Lines up with Marc's Advanced Diploma coursework (earthworks, road geometry, pavement, stormwater, cost estimates and bills of quantities in AutoCAD and Civil 3D) and his BSCE.",
   "Direct employer; held only because the work rights requirement is unclear."],
  caution="HELD: the requirements list says Australian citizenship or permanent residency, but the last line says citizens, PRs or people with full Australian working rights will be considered. Marc has full working rights on a 485 until December 2027, not PR. Adelaide means relocation, which Marc has not confirmed. Closing date not shown on Fyfe's page (one aggregator says 7 Dec 2026).",
  gaps=["Citizenship/PR wording unresolved","Relocation to Adelaide not confirmed","No Australian design office experience","BSCE completed 2019, not a recent degree"],
  how="Found on the open web (jobau, published 7 Nov 2026) and read in full on Fyfe's own careers page on 11 Nov 2026. Held as HELD_MANDATORY_UNRESOLVED because the advert's citizenship/PR requirement conflicts with its own full working rights line. Nothing sent; Marc decides whether to ask careers@fyfe.com.au.",
  call=["Work rights? \u2192 Subclass 485 with full working rights until December 2027; not PR.","Design software? \u2192 AutoCAD and Civil 3D from my Advanced Diploma; not yet in commercial production.","Relocation? \u2192 Open to discussing relocation to Adelaide for the right role (Marc to confirm)."]),
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
     "advert":{"source":s['source'],"listed_at":s['listed'],"expires_at":s['expires'],"verified_at":iso,"apply_instructions":s['apply'],"screening_questions":[x['q'] for x in d['screening_answers']] if s['n']=='jaydo' else []},
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
