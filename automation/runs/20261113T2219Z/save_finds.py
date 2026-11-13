import json, uuid, hashlib, os, sys
from datetime import datetime, timezone
sys.path.insert(0,'/workspace/job-finds'); from _save_find import save
RUN='20261113T2219Z'
now=datetime.now(timezone.utc); iso=now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
local=datetime.now().astimezone(); found=local.strftime('%Y-%m-%dT%H:%M+11:00 AEDT')
def sha(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
SW="Tick "+RUN+": SEEK 3 day sweep (821 seen, 164 prefilter, 80 details; 0 never seen) plus 22 targeted SEEK keyword searches (3 days, 0 never seen); open web: LinkedIn guest listings Australia wide (12 keywords last 24 hours, 12 keywords last 7 days entry level), careersatcouncil (no junior civil), Careers Vic (DEECA Cadet Engineer, students only), SimplyHired (blocked), web searches for direct-apply civil roles."
GM="Gmail could not be checked on this tick (no Gmail connector attached), so search macdarenz@gmail.com in:anywhere for Halex before sending. Dedupe: tracker check new for Halex Group; not in /workspace/job-finds, prior_outreach.json, earlier run files or the journal."
P={
'halex':dict(cover='Marc_Masarate_Halex_Group_Civil_Draftsperson_Cover_Letter.pdf',res='Marc_Masarate_Halex_Group_Resume.pdf',status='PREPARED_NOT_SENT',method='Email',pct=62,
 rat=["Halex Group (Cheltenham, founded 2018 by Matt Haymes and Jesse Ullbricht) designs, manages and builds high-end residential projects across metro Melbourne and recently advertised a Civil Engineering Draftsperson ($80k to $90k): civil drawings, site plans and documentation for residential building and site works, site measurements, drawing checks and coordination with engineers and architects.",
 "That advert asked for a Diploma of Building and Construction or a relevant drafting, engineering or construction qualification, CAD proficiency and drawing interpretation. Marc's Advanced Diploma of Civil Construction Design (Feb 2026), BSCE (2019), AutoCAD, Civil 3D and Revit, and 2019 to 2020 drawing review and site inspection work fit.",
 "The advert expired about 35 days before this tick, so this is a clearly labelled speculative enquiry to the co-founder's published email, not an application to an open vacancy."],
 caution="No open vacancy: the earlier advert has expired, so the need may already be filled. Residential building drafting differs from Marc's road and civil coursework; his drafting is academic, not commercial (said honestly). Cheltenham is a long commute from Melton (Marc to confirm).",
 gaps=["No commercial drafting experience","No Australian work experience","Residential building documentation standards are new","Commute from Melton to Cheltenham unconfirmed"],
 listed='',expires='',apply="Speculative email to Matt Haymes (co-founder), matt@halexgroup.com.au, published with his name and phone on https://halexgroup.com.au/contact-us/ (page heading 'Contact us / Join Our Team'). Jesse Ullbricht (jesse@halexgroup.com.au) is the other co-founder. Nothing was sent.",
 call=["Drafting experience? \u2192 Coursework in AutoCAD, Civil 3D and Revit (Advanced Diploma, Feb 2026); not yet commercial.","Residential work? \u2192 Field engineer on residential subdivision finishing works in the Philippines (2019 to 2020); reviewed structural and architectural drawings.","Site measurements? \u2192 Site inspections and quality checks on Philippine projects; no survey instrument use on a job.","Travel to Cheltenham? \u2192 Own car and licence; Marc to confirm the commute.","Work rights? \u2192 Subclass 485, full working rights until December 2027."],
 how_extra="No advertised vacancy is open; this is a speculative enquiry. Found on the open web: a web search for Melbourne civil drafting roles surfaced Halex Group's Civil Engineering Draftsperson advert on a jobs board mirror (expired 35 days earlier); never in the tracker or job finds. Halex contact page read for the co-founders' published emails and phone numbers; About page read for the company line."),
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
     "contact_evidence_url":d['contact_evidence_url'],"contact_verified_at":iso,"contact_confidence":"published_direct","subject":d['subject'],"email_body":d.get('email_body',''),"fit":p['rat'],"gaps":p['gaps'],
     "match_score":{"percent":p['pct'],"method":"resume-fit-v2","rationale":p['rat'],"caution":p['caution']},
     "advert":{"source":"open_web","listed_at":p['listed'],"expires_at":p['expires'],"verified_at":iso,"apply_instructions":p['apply'],"screening_questions":[]},
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
