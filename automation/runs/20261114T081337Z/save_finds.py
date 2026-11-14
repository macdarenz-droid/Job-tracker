import json, uuid, hashlib, os, sys, subprocess
from datetime import datetime, timezone
sys.path.insert(0,'/workspace/job-finds'); from _save_find import save
RUN='20261114T081337Z'
now=datetime.now(timezone.utc); iso=now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
local=datetime.now().astimezone(); found=local.strftime('%Y-%m-%dT%H:%M+11:00 AEDT')
def sha(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
SW=open('sweep_summary.txt').read().strip()
GM="Gmail could not be checked on this tick (no Gmail connector attached), so search macdarenz@gmail.com in:anywhere for this employer before acting. Dedupe: not in the tracker (tracker.py check), /workspace/job-finds, prior_outreach.json, the queue, earlier run files or the journal."
CALL_BASE=["Work rights? \u2192 Subclass 485, full working rights until December 2027, no sponsorship needed.","Start? \u2192 Two weeks after an offer."]
P={
'wsp':dict(cover='Marc_Masarate_WSP_Laboratory_Technician_in_Training_Cover_Letter.pdf',res='Marc_Masarate_Resume_Technician.pdf',status='READY_JEREMIE_EMPLOYER_PORTAL',method='Company website',pct=80,conf='none',
 job_url="https://emit.fa.ca3.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_2001/job/96985",company_url="https://www.wsp.com/en-au/",vacancy="OPEN_EMPLOYER_PORTAL_AND_LINKEDIN",recipient="",recipient_role="",email="",evidence="https://emit.fa.ca3.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_2001/job/96985",subject="Laboratory Technician in Training, Malaga WA (WSP job 96985)",body="",
 rat=["Technician lane (rank 2): WSP's National Technical Contracting geotechnical laboratories (NATA accredited) want Trainee, Junior and Intermediate laboratory technicians; the trainee role prepares and tests soil, rock, aggregate and concrete samples under supervision, maintains equipment, handles samples, joins site visits and keeps records.",
 "Essentials are high school mathematics, a driver's licence and the ability to obtain a White Card and first aid; Certificate III in Laboratory Techniques is advantageous, not required. Marc has a White Card, a full Victorian licence, AS 1726 and AS 1289 coursework in the Advanced Diploma, a BSCE, and 2019 to 2020 site inspection, quality check and material record work.",
 "Entry level with structured training and funded qualifications; fit scored with lane-fit-v3 (50 + entry level 25 + duty overlap 5 + lane 2 bonus 10, rounded down to 80 for the relocation to Perth)."],
 caution="Malaga WA means relocating to Perth (facts.json: will relocate anywhere in Australia). The Oracle form questions were not visible without starting an application; any work-rights option that is not the Subclass 485 or unrestricted temporary visa option, or any future sponsorship question: stop and ask Marc. Posted 19 Oct 2026 with no closing date, reposted on LinkedIn 9 Nov 2026.",
 gaps=["No paid laboratory testing experience (coursework only)","No Certificate III in Laboratory Techniques (advantageous only)","No first aid certificate on record (ability to obtain is what the advert asks)","Relocation to Perth needed"],
 listed='2026-10-19',expires='',apply="Apply on WSP's careers portal (Oracle): https://emit.fa.ca3.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_2001/job/96985 (ref 218_652203_96985; also LinkedIn https://au.linkedin.com/jobs/view/4480945366). Attach the cover letter and the technician resume in this folder. Nothing was submitted.",
 call=["Lab experience? \u2192 Coursework applying AS 1726 and AS 1289 in the Advanced Diploma (Feb 2026); site inspections and quality checks in the Philippines 2019 to 2020.","Move to Perth? \u2192 Yes, will relocate; can start two weeks after an offer.","Licence? \u2192 Full Victorian driver's licence, automatic, own transport; White Card held."]+CALL_BASE,
 how_extra="Found on the open web first: LinkedIn guest job listings (keyword 'materials testing technician', last 7 days) showed WSP 'Laboratory Technician in Training' (LinkedIn 4480945366, posted 9 Nov 2026); a web search and WSP's Oracle careers API confirmed the live requisition (job 96985, Malaga WA, posted 19 Oct 2026, no end date). Never in the tracker, job finds, queue or run history."),
'langtree':dict(cover='Marc_Masarate_Langtree_Consulting_Junior_Civil_Drafter_Cover_Letter.pdf',res='Marc_Masarate_Resume_Drafter.pdf',status='PREPARED_NOT_SENT',method='Email',pct=66,conf='published_inbox',
 job_url="https://www.langtreeconsulting.com.au/careers",company_url="https://www.langtreeconsulting.com.au/",vacancy="OPEN_CAREERS_EOI_NO_SPECIFIC_ADVERT",recipient="",recipient_role="HR",email="hr@langtreeconsulting.com.au",evidence="https://www.langtreeconsulting.com.au/careers",subject=None,body=None,
 rat=["Drafter lane (rank 1): Langtree Consulting Engineers (Townsville, established 2016) does civil design for councils, developers and contractors across North and Central Queensland. Its Civil Drafter page (junior to intermediate, under a Senior Mentor) covers property and development drainage assessment, earthworks and road design, flood assessment and site drainage.",
 "That page's essentials are a recently completed Associate Degree in Civil Engineering 'or similar relevant qualification' and practical use of 12D or Civil 3D and AutoCAD; Marc's Advanced Diploma of Civil Construction Design (Feb 2026, Civil 3D and AutoCAD, roads, earthworks, stormwater) matches.",
 "No dated advert is open (SEEK ads from 2025 expired; the careers page now lists Senior/Principal, mid-senior Civil Designer and Graduate Civil Engineer and asks for a cover letter and CV to hr@langtreeconsulting.com.au), so this is a clearly labelled speculative enquiry to the address the careers page publishes."],
 caution="Speculative: no specific open junior drafter vacancy is dated; the Civil Drafter page is undated. Townsville means relocation (facts.json: will relocate anywhere). The Civil Drafter page says 'whilst undertaking or completing study' and offers study flexibility; Marc has completed his diploma, which the page also accepts ('recently completed').",
 gaps=["No commercial drafting experience (coursework only)","12D not on record (Civil 3D accepted as the alternative)","No Australian land development project experience (desirable)","Relocation to Townsville needed"],
 listed='',expires='',apply="Speculative email to hr@langtreeconsulting.com.au, the address the careers page (https://www.langtreeconsulting.com.au/careers) gives for cover letters and CVs, with the cover letter and drafter resume attached. Nothing was sent.",
 call=["Drafting experience? \u2192 Advanced Diploma coursework (Feb 2026): road geometry, earthworks, pavement, stormwater drainage in Civil 3D and AutoCAD.","12D? \u2192 Trained in Civil 3D and AutoCAD.","Move to Townsville? \u2192 Yes, will relocate; can start two weeks after an offer."]+CALL_BASE,
 how_extra="Found on the open web: a web search for junior civil drafter roles with email applications surfaced Langtree Consulting's Civil Drafter page; careers, graduate program and About pages read; SEEK checked for the advertiser (last adverts 2025, expired). Never in the tracker, job finds, queue or run history."),
}
recs=[]
for k,p in P.items():
    d=json.load(open(f'drafts/{k}.json'))
    if k=='langtree': p['subject']=d['email']['subject']; p['body']=d['email']['body']
    cover=os.path.abspath(p['cover']); res=os.path.abspath(p['res'])
    how=SW+" "+p['how_extra']+" "+GM+" Cover letter drafted from facts.json only (three paragraphs, under 200 words); checks.py draft and facts OK; letter rendered with letter_pdf.py (1 page, read back); attached resume is the current lane resume from documents/resume (resume.py build, 2 pages), because compact_pdf.py was retired on 14 Nov 2026. Status "+p['status']+": nothing was submitted or sent. Saved locally only (tracker full, Marc 20 Oct 2026)."
    notes="HOW GROK AI FOUND THIS\n"+how+"\n\nIF THEY CALL, LIKELY QUESTIONS\n"+"\n".join('\u2022 '+c for c in p['call'])
    checklist=(["Search Gmail in:anywhere for "+d['company']+" before acting (Gmail was not reachable on this tick)"]+
      (["Apply on the WSP portal link with the cover letter and technician resume in this folder","Answer right to work with the Subclass 485 option; notice 2 weeks; relocate yes; any question not in facts.json answers: stop and ask Marc","Record the apply date in /workspace/job-finds"] if k=='wsp' else
       ["Send the email in draft.json from macdarenz@gmail.com to hr@langtreeconsulting.com.au with the cover letter and drafter resume attached","Record the send date in /workspace/job-finds"]))
    rid=str(uuid.uuid4())
    rec={"id":rid,"key":"manual:"+rid,"contributor_name":"Grok AI","created_by":"grok-job-search","record_kind":"AUTOMATED_LEAD","run_id":RUN,"created_at":iso,"updated_at":iso,"version":1,
     "attachments":[{"kind":"cover","filename":p['cover'],"sha256":sha(cover),"stored_in":"local:/workspace/job-finds"},{"kind":"resume","filename":p['res'],"sha256":sha(res),"stored_in":"local:/workspace/job-finds","note":"lane resume built by resume.py from facts.json"}],
     "company":d['company'],"role":d['role'],"location":d['location'],"job_url":p['job_url'],"company_url":p['company_url'],"status":p['status'],"application_type":d['application_type'],"vacancy_status":p['vacancy'],
     "application_route":d['route'],"application_method":p['method'],"recipient_name":p['recipient'],"recipient_role":p['recipient_role'],"recipient_email":p['email'],"contact_email":p['email'],
     "contact_evidence_url":p['evidence'],"contact_verified_at":iso,"contact_confidence":p["conf"],"subject":p['subject'],"email_body":p['body'],"fit":p['rat'],"gaps":p['gaps'],
     "match_score":{"percent":p['pct'],"method":"lane-fit-v3","rationale":p['rat'],"caution":p['caution']},
     "advert":{"source":("linkedin+employer_portal" if k=="wsp" else "open_web"),"listed_at":p['listed'],"expires_at":p['expires'],"verified_at":iso,"apply_instructions":p['apply'],"screening_questions":[]},
     "screening_answers":[],"checklist":checklist,"notes":notes,"how_found":how,"call_prep":p['call'],"checked_at":iso,"seek_id":None,"duplicate_key":(d['company']+'|'+d['role']).lower(),"preparation_only":True,"found_at":found,
     "cover_letter_text":d['cover_letter_text'],"relocation_line":d['relocation_line']}
    readme=(f"# {d['company']}, {d['role']}, {d['location']}\n\n- Status: {p['status']}, fit {p['pct']}%, route {p['method']}\n- Link: {p['job_url']}\n- Apply: {p['apply']}\n- Closes: {p['expires'] or 'not stated'}\n- Why: {' '.join(p['rat'])}\n- Caution: {p['caution']}\n- Gaps: {'; '.join(p['gaps'])}\n- Files: record.json, draft.json, cover letter PDF (1 page, read back) and lane resume PDF.\n\n## Checklist\n"
     +"\n".join(f"{i+1}. {c}" for i,c in enumerate(checklist))+"\n\n"+notes+"\n")
    json.dump(d,open('/tmp/draft.json','w'),indent=1,ensure_ascii=False)
    json.dump(rec,open('/tmp/rec_check.json','w'),indent=1,ensure_ascii=False)
    out=subprocess.run(['python3','../../scripts/checks.py','record','/tmp/rec_check.json'],capture_output=True,text=True)
    print(k,'checks.py record:',out.stdout.strip(),out.stderr.strip())
    if save(rec,[cover,res,'/tmp/draft.json'],readme,local.strftime('%Y-%m-%d')): recs.append(rec)
json.dump(recs,open('local_records.json','w'),indent=1,ensure_ascii=False)
print(len(recs))
