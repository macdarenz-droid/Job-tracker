import json, uuid, hashlib, os, sys
from datetime import datetime, timezone
sys.path.insert(0,'/workspace/job-finds'); from _save_find import save
RUN='20261114T0310Z'
now=datetime.now(timezone.utc); iso=now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
local=datetime.now().astimezone(); found=local.strftime('%Y-%m-%dT%H:%M+11:00 AEDT')
def sha(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
SW="Tick "+RUN+": SEEK 3 day sweep (939 seen, 186 prefilter, 80 details; only 1 never seen before: D.A. Abcede & Associates 'Civil Engineers', a Philippine firm with no Australian location, not kept); open web first: LinkedIn guest listings Australia wide (12 keywords last 3 days plus 20 keywords last 7 days, about 340 listings, filtered against tracker, job finds and run history), web searches for Victorian council graduate roles and junior civil drafting roles, employer careers pages; Jora blocked (bot check), GradConnection now redirects to SEEK."
GM="Gmail could not be checked on this tick (no Gmail connector attached), so search macdarenz@gmail.com in:anywhere before acting. Dedupe: tracker.py check new for this employer; not in /workspace/job-finds, prior_outreach.json, earlier run files or the journal."
CALL_BASE=["Work rights? \u2192 Subclass 485, full working rights until December 2027.","Software? \u2192 AutoCAD and Civil 3D from the Advanced Diploma (Feb 2026); Revit modelling; drafting is coursework, not commercial."]
P={
'vtce':dict(cover='Marc_Masarate_vT_Consulting_Engineers_Civil_Designer_Cover_Letter.pdf',res='Marc_Masarate_vT_Consulting_Engineers_Resume.pdf',status='PREPARED_NOT_SENT',method='Email',pct=66,conf='published_inbox',
 rat=["vT Consulting Engineers (Carina, Brisbane; founded 2013 by Director Andrew van Tonder, RPEQ civil and structural) is a civil and structural consultancy whose civil services cover earthworks, roadworks, pavement design, stormwater drainage, sewer and water reticulation and development approvals.",
 "Its careers page says it is always on the lookout for people from cadets to senior level and lists Civil Designer and Civil Engineer for the civil team, asking for a cover letter and resume to admin@vtce.com.au. That matches Marc's Advanced Diploma coursework (road geometry, earthworks, pavement, stormwater in Civil 3D and AutoCAD) and BSCE.",
 "No specific advert or closing date, so this is a clearly labelled speculative enquiry to the inbox the careers page names; Brisbane needs relocation (open to discussing)."],
 caution="No specific open vacancy is advertised, only a standing careers invitation. Brisbane relocation from Melton is needed (Marc to confirm). Design experience is coursework only (said honestly).",
 gaps=["No commercial civil design experience","No Australian work experience","12d Model not on record","Relocation to Brisbane unconfirmed"],
 listed='',expires='',apply="Speculative email to admin@vtce.com.au, the address the careers page (https://vtce.com.au/careers-with-vtce/) gives for cover letters and resumes; letter addressed to Director Andrew van Tonder (named on https://vtce.com.au/about/). An upload form on the careers page is the alternative. Nothing was sent.",
 call=["Civil design experience? \u2192 Advanced Diploma coursework (Feb 2026): road geometry, earthworks, pavement, stormwater drainage in Civil 3D and AutoCAD; not yet commercial.","Site experience? \u2192 Project-in-charge engineer then field engineer in the Philippines (2019 to 2020): drawing review, inspections, quality checks, site reports.","Move to Brisbane? \u2192 Open to discussing relocation; Marc to confirm timing.","12d Model? \u2192 Not used yet; trained in Civil 3D."]+CALL_BASE,
 how_extra="No advertised vacancy is open; this is a speculative enquiry. Found on the open web: a web search for junior civil drafting roles with direct email applications surfaced the vTCE careers page; never in the tracker or job finds. Careers page read for the application address (Cloudflare obfuscated email decoded to admin@vtce.com.au, also shown as the site contact); About page read for the Director's name; Civil Engineering Services page read for the Augustine Heights State School project line."),
'reseng':dict(cover='Marc_Masarate_Residential_Engineering_Structural_Site_Engineer_Cover_Letter.pdf',res='Marc_Masarate_Residential_Engineering_Resume.pdf',status='READY_JEREMIE_EMPLOYER_PORTAL',method='Company website',pct=63,conf='none',
 rat=["Residential Engineering (40+ years of structural, geotechnical, inspection and survey services for residential construction in NSW; backed by Five Group) is hiring a field based Structural Site Engineer for Canberra ACT or Goulburn NSW: structural inspections on residential projects, inspection reports with photos, liaising with builders, and structural design (concrete, steel, timber) in quieter periods.",
 "It asks for a tertiary qualification in Civil or Structural Engineering, a driver's licence and willingness to travel; Marc's BSCE (2019), Advanced Diploma (Feb 2026), 2019 to 2020 site inspection, quality check and drawing review work, and licence fit the core of the role.",
 "Listed on LinkedIn (seniority Associate) on 10 Nov 2026 and on SEEK; no years of experience stated."],
 caution="The advert asks for site inspection experience within the Australian construction industry and knowledge of Australian residential practice and Standards; Marc's inspection work was in the Philippines (scored as an Australian experience gap). Needs relocation to Canberra or Goulburn and extensive regional driving (Marc to confirm). Asbestos and silica awareness training is ideal; none on record.",
 gaps=["No Australian site inspection experience","Limited structural design (concrete, steel, timber) beyond study","Relocation to Canberra or Goulburn unconfirmed","No asbestos or silica awareness training on record"],
 listed='2026-11-10',expires='',apply="Apply through the LinkedIn advert https://au.linkedin.com/jobs/view/4487422784 (or the matching SEEK listing, Structural Site Engineer, Residential Engineering, Canberra ACT). The advert says Five Group Talent Acquisition recruits directly; no application email or named hiring manager is published (only admin@reseng.com.au, which does not say it takes applications), so no email was prepared. Nothing was submitted.",
 call=["Inspection experience? \u2192 Site inspections, safety checks and quality monitoring on Philippine projects (2019 to 2020); not yet in Australia.","Structural design? \u2192 Structural principles in the BSCE; reviewed structural and architectural drawings on site; no commercial design yet.","Move and travel? \u2192 Driver's licence and own transport; open to discussing relocation to Canberra or Goulburn; Marc to confirm."]+CALL_BASE,
 how_extra="Found on the open web: LinkedIn guest job listings (keyword site engineer, last 7 days) showed Residential Engineering's Structural Site Engineer (LinkedIn 4487422784, posted 10 Nov 2026); a web search confirmed the same advert on SEEK (Canberra ACT, listed about three days earlier). Never in the tracker, job finds or run history. Employer website and careers page read: no application email or recruiter name."),
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
     "company":d['company'],"role":d['role'],"location":d['location'],"job_url":d['job_url'],"company_url":d['company_url'],"status":p['status'],"application_type":d['application_type'],"vacancy_status":d['vacancy_status'],
     "application_route":d['route'],"application_method":p['method'],"recipient_name":d['recipient_name'],"recipient_role":d['recipient_role'],"recipient_email":d.get('recipient_email',''),"contact_email":d.get('recipient_email',''),
     "contact_evidence_url":d['contact_evidence_url'],"contact_verified_at":iso,"contact_confidence":p["conf"],"subject":d['subject'],"email_body":d.get('email_body',''),"fit":p['rat'],"gaps":p['gaps'],
     "match_score":{"percent":p['pct'],"method":"resume-fit-v2","rationale":p['rat'],"caution":p['caution']},
     "advert":{"source":("linkedin" if k=="reseng" else "open_web"),"listed_at":p['listed'],"expires_at":p['expires'],"verified_at":iso,"apply_instructions":p['apply'],"screening_questions":[]},
     "screening_answers":[],"checklist":d['checklist'],"notes":notes,"how_found":how,"call_prep":p['call'],"checked_at":iso,"seek_id":d.get('seek_id'),"duplicate_key":(d['company']+'|'+d['role']).lower(),"preparation_only":True,"found_at":found}
    readme=(f"# {d['company']}, {d['role']}, {d['location']}\n\n- Status: {p['status']}, fit {p['pct']}%, route {p['method']}\n- Link: {d['job_url']}\n- Apply: {p['apply']}\n- Closes: {p['expires'] or 'not stated'}\n- Why: {' '.join(p['rat'])}\n- Caution: {p['caution']}\n- Gaps: {'; '.join(p['gaps'])}\n- Files: record.json, draft.json, cover letter PDF and one page resume PDF (both read back).\n\n## Checklist\n"
     +"\n".join(f"{i+1}. {c}" for i,c in enumerate(d['checklist']))+"\n\n"+notes+"\n")
    json.dump(d,open('/tmp/draft.json','w'),indent=1,ensure_ascii=False)
    if p['status']=='PREPARED_NOT_SENT':
        import subprocess
        json.dump(rec,open('/tmp/rec_check.json','w'),indent=1,ensure_ascii=False)
        out=subprocess.run(['python3','../../scripts/checks.py','record','/tmp/rec_check.json'],capture_output=True,text=True)
        print('checks.py record:',out.stdout.strip(),out.stderr.strip())
        bad=[l for l in out.stdout.splitlines() if l.startswith('- ') and 'not in R2' not in l and 'dry-build' not in l]
        if bad: print('ABORT',k,bad); continue
    if save(rec,[cover,res,'/tmp/draft.json'],readme,local.strftime('%Y-%m-%d')): recs.append(rec)
json.dump(recs,open('local_records.json','w'),indent=1,ensure_ascii=False)
print(len(recs))
