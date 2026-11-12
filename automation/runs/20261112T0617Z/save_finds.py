import json, uuid, hashlib, os, sys
from datetime import datetime, timezone
sys.path.insert(0,'/workspace/job-finds'); from _save_find import save
RUN='20261112T0617Z'
now=datetime.now(timezone.utc); iso=now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
local=datetime.now().astimezone(); found=local.strftime('%Y-%m-%dT%H:%M+11:00 AEDT')
def sha(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
SW="Tick "+RUN+": open web first (web search across jobau, Jobstralia, JobsNext, SimplyHired, Prosple, College Recruiter, TheJobsMap, Jora council pages, LiveHire, Hobsons Bay and Stonnington council adverts, and Ferrycarrig's own job board) plus SEEK 3 days/60 details (1190 seen, 262 prefilter, nothing new worth keeping) widened to 14 days/80 details (1443 seen, 401 prefilter, nothing new worth keeping)."
GM="Gmail could not be checked on this tick (no Gmail connector attached), so search macdarenz@gmail.com in:anywhere for the employer before applying. Dedupe: tracker.py check new; not in /workspace/job-finds or prior_outreach.json."
P={
'nassima':dict(cover='Marc_Masarate_Nassima_Civil_Engineering_Draftsperson_Cover_Letter.pdf',res='Marc_Masarate_Nassima_Resume.pdf',status='READY_JEREMIE_JOBSNEXT',method='JobsNext (Apply now)',pct=70,
 rat=["Civil Engineering Draftsperson at Nassima Design Group (VIC 3094, north east Melbourne), permanent full time, AUD 80,000 to 90,000: civil drawings, layouts, cross sections, profiles and details for roads, drainage, subdivisions, earthworks and utilities in CAD.",
 "The advert names a Diploma or Advanced Diploma in Civil Construction Design and AutoCAD/Civil 3D, which is exactly Marc's February 2026 Advanced Diploma; his drawing review and site records from 2019 to 2020 add practical context.",
 "Melbourne based, direct employer, drafting experience only highly regarded rather than required."],
 caution="Nassima is a small building design practice (about six people on LinkedIn, residential focus); the advert is only on JobsNext (posted 30 Oct 2026, no closing date) and the director's old sole trader ABN was cancelled in July 2026 (the company itself is registered), so confirm the role is genuine before sharing more than a resume. Earlier tick skipped it because the advert was thin; the full advert is now visible. No paid drafting experience; Montmorency is a long commute from Melton.",
 gaps=["No paid drafting experience (study only)","Residential and building work may be a larger share than the advert suggests"],
 listed='2026-10-30',expires='',apply="Apply on JobsNext with the Apply now button (JobsNext jobseeker account needed). No email published.",
 call=["CAD? \u2192 AutoCAD 2D/3D and Civil 3D through the Advanced Diploma of Civil Construction Design (Feb 2026).","Roads and drainage? \u2192 Designed road geometry, earthworks, pavements and stormwater drainage in the diploma.","Drafting experience? \u2192 From study; on site in 2019 to 2020 reviewed drawings and kept site records.","Work rights? \u2192 Subclass 485, full working rights until December 2027.","Salary and start? \u2192 Advert says 80 to 90k; Marc to answer himself."],
 how_extra="Found on JobsNext through an open web search for junior civil drafter roles in Victoria (posted 30 Oct 2026). Not on the tracker, prior_outreach.json or /workspace/job-finds; skipped once on an earlier tick as too thin, now kept with the full advert."),
'ferrycarrig':dict(cover='Marc_Masarate_Ferrycarrig_Graduate_Civil_Engineer_Cover_Letter.pdf',res='Marc_Masarate_Ferrycarrig_Resume.pdf',status='READY_JEREMIE_INDEED',method='Company website / Indeed (confirm live)',pct=70,
 rat=["Graduate Civil Engineer with Ferrycarrig, a Sydney utilities and civil infrastructure contractor, on a major civil project: day to day coordination with site supervisors, subcontractor and material coordination, drawing review, ITPs and quality records, site inspections, daily reports, procurement and programme tracking.",
 "Almost every duty matches Marc's 2019 to 2020 site work (crew coordination, drawing review, inspections, site and progress reports, procurement and materials) plus his civil degree and Australian Advanced Diploma.",
 "Direct employer, true graduate role, site based."],
 caution="Sydney, so relocation (Marc has not confirmed; letter says open to discussing). Advert seen on SimplyHired, jobau and other mirrors (posted about 3 Nov 2026), not on SEEK, and Ferrycarrig's own Adlogic board showed no listings, so confirm the advert is live before applying. Wants a recent graduate; Marc's degree is 2019 and site experience overseas.",
 gaps=["No Australian site or ITP experience","Relocation to Sydney not confirmed","Degree 2019, not a recent graduate"],
 listed='2026-11-03',expires='',apply="Apply through the original advert (Indeed/SimplyHired mirror) or Ferrycarrig's careers page; if not listed, use Register your interest at https://jobboards.adlogic.com.au/ferrycarrig/. No email published.",
 call=["Site experience? \u2192 About ten months on site in the Philippines (2019 to 2020): crew coordination, drawing review, inspections, site and progress reports, procurement.","ITPs? \u2192 Quality checks and inspections on site; Australian ITP format still to learn.","Move to Sydney? \u2192 Marc to decide; open to discussing.","Work rights? \u2192 Subclass 485, full working rights until December 2027.","Salary and start? \u2192 Marc to answer himself."],
 how_extra="Found through an open web search of jobau November graduate listings, then the full advert on SimplyHired (9 days old on 12 Nov 2026). Not on the tracker, prior_outreach.json or /workspace/job-finds; never screened before."),
}
recs=[]
for k,p in P.items():
    d=json.load(open(f'drafts/{k}.json'))
    cover=os.path.abspath(p['cover']); res=os.path.abspath(p['res'])
    how=SW+" "+p['how_extra']+" "+GM+" Cover letter drafted from facts.json only; checks.py facts OK and tone OK (letter under 340 words); cover letter and one page resume rendered and read back (1 page each). Status "+p['status']+": nothing was submitted or sent. Saved locally only (tracker full, Marc 20 Oct 2026)."
    notes="HOW GROK AI FOUND THIS\n"+how+"\n\nIF THEY CALL, LIKELY QUESTIONS\n"+"\n".join('\u2022 '+c for c in p['call'])
    d['notes']=notes; rid=str(uuid.uuid4())
    rec={"id":rid,"key":"manual:"+rid,"contributor_name":"Grok AI","created_by":"grok-job-search","record_kind":"AUTOMATED_LEAD","run_id":RUN,"created_at":iso,"updated_at":iso,"version":1,
     "attachments":[{"kind":"cover","filename":p['cover'],"sha256":sha(cover),"stored_in":"local:/workspace/job-finds"},{"kind":"resume","filename":p['res'],"sha256":sha(res),"stored_in":"local:/workspace/job-finds","note":"one page resume built from facts.json"}],
     "company":d['company'],"role":d['role'],"location":d['location'],"job_url":d['job_url'],"company_url":d['company_url'],"status":p['status'],"application_type":"ADVERTISED_VACANCY","vacancy_status":d['vacancy_status'],
     "application_route":d['route'],"application_method":p['method'],"recipient_name":d['recipient_name'],"recipient_role":d['recipient_role'],"recipient_email":"","contact_email":"",
     "contact_evidence_url":d['contact_evidence_url'],"contact_verified_at":iso,"contact_confidence":"none","subject":d['subject'],"email_body":"","fit":p['rat'],"gaps":p['gaps'],
     "match_score":{"percent":p['pct'],"method":"resume-fit-v2","rationale":p['rat'],"caution":p['caution']},
     "advert":{"source":"web","listed_at":p['listed'],"expires_at":p['expires'],"verified_at":iso,"apply_instructions":p['apply'],"screening_questions":[]},
     "screening_answers":[],"checklist":d['checklist'],"notes":notes,"how_found":how,"call_prep":p['call'],"checked_at":iso,"seek_id":d.get('seek_id'),"duplicate_key":(d['company']+'|'+d['role']).lower(),"preparation_only":True,"found_at":found}
    readme=(f"# {d['company']}, {d['role']}, {d['location']}\n\n- Status: {p['status']}, fit {p['pct']}%, route {p['method']}\n- Link: {d['job_url']}\n- Apply: {p['apply']}\n- Closes: {p['expires'] or 'not stated'}\n- Why: {' '.join(p['rat'])}\n- Caution: {p['caution']}\n- Gaps: {'; '.join(p['gaps'])}\n- Files: record.json, draft.json, cover letter PDF and one page resume PDF (both read back).\n\n## Checklist\n"
     +"\n".join(f"{i+1}. {c}" for i,c in enumerate(d['checklist']))+"\n\n"+notes+"\n")
    json.dump(d,open('/tmp/draft.json','w'),indent=1,ensure_ascii=False)
    if save(rec,[cover,res,'/tmp/draft.json'],readme,local.strftime('%Y-%m-%d')): recs.append(rec)
json.dump(recs,open('local_records.json','w'),indent=1,ensure_ascii=False)
print(len(recs))
