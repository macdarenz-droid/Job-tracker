import json, uuid, hashlib, shutil, sys, os
from datetime import datetime, timezone
sys.path.insert(0,'/workspace/job-finds'); from _save_find import save
RUN='20261030T2318Z'
now=datetime.now(timezone.utc); iso=now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
local=datetime.now().astimezone(); found=local.strftime('%Y-%m-%dT%H:%M+11:00 AEDT')
RES='/workspace/repos/Portfolio/assets/Marc-Darenz-Masarate-Resume.pdf'
def sha(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
C={x['seek_id']:x for x in json.load(open('candidates.json'))['candidates']}
C['95372255']=json.load(open('/tmp/det2/95372255.json'))
specs=[
 dict(n='centralvic',cover='Marc_Masarate_Central_Vic_Civil_Junior_Project_Manager_Cover_Letter.pdf',res='Marc_Masarate_Central_Vic_Civil_Resume.pdf',pct=68,status='READY_JEREMIE_SEEK',conf='none',
  rationale=["Junior Project Manager at a regional Victorian civil contractor (water and sewer, roadworks, land development) aimed explicitly at a recent civil engineering graduate: planning support, cost and progress tracking, documentation, estimating and subcontractor and supplier coordination.",
   "Matches Marc's Philippines site coordination (10 to 15 workers, procurement and materials tracking, site and progress reports) and his Advanced Diploma cost estimates, bills of quantities, road, earthworks and drainage design; requires a civil degree (BSCE 2019), licence and White Card, all held.",
   "Direct employer; apply through SEEK with two screening questions (work rights, expected salary)."],
  caution="Title says Project Manager but the advert targets recent graduates; civil construction industry experience is highly regarded and Marc has none in Australia. Ballarat is a daily drive from Melton (Western Freeway); Marc to confirm. Salary band $70,000 to $100,000; Marc to pick his expected figure. Listing first seen on 20 Oct but never screened because older ticks filtered the word manager.",
  gaps=["No Australian civil construction experience","No project management title held before","Variations and contract administration not on record"],
  how_src="Open web sweep on tick "+RUN+" (Jobstralia listing, posted 22 Oct) led to SEEK advert 95372255, listed 20 Oct 2026, expires 19 Nov 2026 AEDT, full time, $70,000 to $100,000. Earlier SEEK sweeps had dropped it on the title filter (manager), so it was never screened. No application email or named contact in the advert, so the route is SEEK.",
  call=["Why Central Vic Civil? \u2192 Your mix of water, roadworks and land development for councils and developers is the civil work I want to learn to plan and deliver.",
   "Have you managed or coordinated a project? \u2192 Project-in-charge on a community hall renovation in the Philippines: 10 to 15 workers a day, priorities, progress and client updates.",
   "Cost and estimating experience? \u2192 Cost estimates, bills of quantities and risk registers in my Advanced Diploma; procurement and materials tracking on site.",
   "Can you get to Ballarat daily? \u2192 I'm in Melton with a licence and my own car; Marc to confirm.",
   "Work rights? \u2192 Subclass 485, full working rights until December 2027.",
   "Start date and salary? \u2192 Marc to answer; nothing on record."]),
 dict(n='fowlers',cover='Marc_Masarate_Fowlers_Asphalting_Project_Engineer_Cover_Letter.pdf',res='Marc_Masarate_Fowlers_Asphalting_Resume.pdf',pct=62,status='PREPARED_NOT_SENT',conf='published_inbox',
  rationale=["Project Engineer, Civil at the Fowlers Asphalting (Downer EDI Works) Trafalgar depot: material and work lot traceability, procurement and subcontractor management, QA records, quantity tracking and reporting, programs, tenders and estimates, drawing review.",
   "Matches Marc's field engineer work (procurement and materials tracking, material records, site and progress reports, subcontractor and supplier coordination) and his Advanced Diploma pavement, road and earthworks design plus cost estimates and bills of quantities.",
   "Mandatory items held: tertiary civil qualification (BSCE 2019), driver licence, White Card. Advert publishes an application inbox (admin@fowlersasphalting.com.au) as well as SEEK Apply."],
  caution="Not a graduate title; the advert wants a sound understanding of civil and pavement construction practice, and Marc's is from study and Philippines site work. Trafalgar is about two hours from Melton, so relocation or a long commute must be confirmed by Marc. Advert says Current Victorian Driver Licence: memory says Marc's licence is Victorian, facts.json only says Australian; confirm. Fowlers is part of Downer EDI Works; the tracker holds an unapplied Downer Site Engineer lead (READY, 7 Oct), no Downer application receipts found in Gmail.",
  gaps=["No Australian pavement or asphalt construction experience","MS Project, Bluebeam, MicroStation or TBC not on record","Relocation to Gippsland not confirmed"],
  how_src="SEEK 14 day widened sweep on tick "+RUN+" (1735 seen, 430 past the prefilter, 80 details). Advert 95573011 listed 29 Oct 2026, expires 28 Nov 2026 AEDT. The advert itself says to apply on SEEK or email a resume and cover letter to admin@fowlersasphalting.com.au, so that published inbox is the email route.",
  call=["Why Fowlers? \u2192 Your Gippsland council and government civil jobs, and the traceability and quantity tracking side of a project engineer role, are the site work I want to learn.",
   "Have you handled procurement and materials? \u2192 Yes, as a field engineer in the Philippines: procurement tracking, material records and site and progress reports.",
   "Pavement knowledge? \u2192 Pavement and road design in my Advanced Diploma; no Australian asphalt or pavement construction yet.",
   "Would you move to Gippsland? \u2192 Marc to answer; applications only say open to discussing relocation.",
   "Work rights? \u2192 Subclass 485, full working rights until December 2027.",
   "Start date and salary? \u2192 Marc to answer; nothing on record."]),
]
recs=[]
for s in specs:
    d=json.load(open(f"drafts/{s['n']}.json")); a=C[d['seek_id']]
    cover=os.path.abspath(s['cover']); tmp='/tmp/'+s['res']; shutil.copy(RES,tmp)
    how=s['how_src']+" Dedupe: not blocked by tracker.py check, not in /workspace/job-finds; Gmail in:anywhere search for the employer name and domain on 31 Oct 2026 found nothing, and no SEEK receipts in the last 14 days (Downer also searched for Fowlers: no application receipts). Email body and cover letter drafted from facts.json only and passed checks.py tone and facts; cover letter rendered with compact_pdf.py (one page, read back). Nothing was sent. Saved locally only (tracker full, Marc 20 Oct 2026)."
    notes="HOW GROK AI FOUND THIS\n"+how+"\n\nIF THEY CALL, LIKELY QUESTIONS\n"+"\n".join('\u2022 '+c for c in s['call'])
    d['notes']=notes
    rid=str(uuid.uuid4())
    rec={"id":rid,"key":"manual:"+rid,"contributor_name":"Grok AI","created_by":"grok-job-search","record_kind":"AUTOMATED_LEAD","run_id":RUN,"created_at":iso,"updated_at":iso,"version":1,
     "attachments":[{"kind":"cover","filename":s['cover'],"sha256":sha(cover),"stored_in":"local:/workspace/job-finds"},{"kind":"resume","filename":s['res'],"sha256":sha(tmp),"stored_in":"local:/workspace/job-finds"}],
     "company":d['company'],"role":d['role'],"location":d['location'],"job_url":d['job_url'],"company_url":d['company_url'],"status":s['status'],"application_type":"ADVERTISED_VACANCY","vacancy_status":"OPEN_SEEK",
     "application_route":d['route'],"application_method":"Email" if d['route']=='EMAIL' else "SEEK","recipient_name":"","recipient_role":d['recipient_role'],"recipient_email":d['recipient_email'],"contact_email":d['recipient_email'],
     "contact_evidence_url":d['contact_evidence_url'],"contact_verified_at":iso,"contact_confidence":s['conf'],"subject":d['subject'],"email_body":d['email_body'],"fit":s['rationale'],"gaps":s['gaps'],
     "match_score":{"percent":s['pct'],"method":"resume-fit-v2","rationale":s['rationale'],"caution":s['caution']},
     "advert":{"source":"seek","listed_at":a['listed_at'],"expires_at":a['expires_at'],"verified_at":iso,"apply_instructions":("Apply on SEEK" if d['route']=='SEEK' else "Apply Now on SEEK or email resume and cover letter to "+d['recipient_email']),"screening_questions":a['screening_questions']},
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
