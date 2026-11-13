import json, uuid, hashlib, os, sys
from datetime import datetime, timezone
sys.path.insert(0,'/workspace/job-finds'); from _save_find import save
RUN='20261113T1212Z'
now=datetime.now(timezone.utc); iso=now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
local=datetime.now().astimezone(); found=local.strftime('%Y-%m-%dT%H:%M+11:00 AEDT')
def sha(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
SW="Tick "+RUN+": SEEK 1 day sweep (393 seen, 63 prefilter, 60 details), widened to 3 days/80 details (1101 seen, 249 prefilter) and 20 targeted SEEK keyword searches (7 days); open web first and alongside (careersatcouncil, Prosple, Jora last 24 hours, jobau, LinkedIn guest listings, council boards incl. Melton ApplyNow and Blacktown ApplyNow, web searches for graduate civil, junior drafting and council engineering roles across all states)."
GM="Gmail could not be checked on this tick (no Gmail connector attached), so search macdarenz@gmail.com in:anywhere for the employer before applying. Dedupe: not in /workspace/job-finds, prior_outreach.json, earlier screen or candidate files or the journal."
P={
'hometoolkit':dict(cover='Marc_Masarate_Home_Toolkit_Structural_Engineer_Cover_Letter.pdf',res='Marc_Masarate_Home_Toolkit_Resume.pdf',status='READY_JEREMIE_SEEK',method='SEEK',pct=64,
 rat=["Home Toolkit (small Melbourne residential structural and building engineering practice) wants a graduate Structural Engineer (45 to 55 dollars per hour) for 4 to 6 residential inspections a week: damage mapping, causation assessment and plain written reports, reviewed by a Principal Chartered engineer.",
 "It asks for a Bachelor of Engineering (Civil or Structural), graduate to 3 years experience, White Card (they can pay), client communication, a current Victorian driver licence and reliable vehicle, and working rights; Marc's BSCE, AS/NZS 1170 and AS 4100 coursework, 2019 to 2020 site inspection, drawing review and progress reporting work and client updates match most of it.",
 "Direct employer, listed on SEEK 13 Nov 2026 AEDT (about 9 pm), expires 13 Dec 2026; quick apply with six questions."],
 caution="Degree is a BSCE (Philippines) rather than a Bachelor of Engineering; advert says graduate to 3 years so likely acceptable, but not confirmed. No forensic or residential structural assessment experience (AS 2870, AS 1684 said honestly as new). Pay is hourly; hours and rate for Marc to decide. Eltham is a long drive from Melton.",
 gaps=["No forensic structural assessment experience","No Australian work experience","BSCE vs BEng wording"],
 listed='2026-11-13',expires='2026-12-13',apply="Apply on SEEK job 95883146 (six questions: work rights, notice, years as engineering professional, hourly rate, weekly hours, licence). No email address published. Nothing submitted.",
 call=["Inspection experience? \u2192 Site inspections and quality checks on a community hall renovation and residential subdivision finishing works in the Philippines, 2019 to 2020.","Structural knowledge? \u2192 BSCE structural principles plus AS/NZS 1170 and AS 4100 coursework and hand calculations in the Advanced Diploma; AS 2870 and AS 1684 not yet used.","Report writing? \u2192 Site, material and progress reports on Philippine projects; technical reporting in the Advanced Diploma.","Licence and car? \u2192 Australian driver's licence (Victorian) and own reliable transport.","Work rights? \u2192 Subclass 485, full working rights until December 2027."],
 how_extra="Found by the targeted SEEK keyword searches after the open web sweep (job 95883146, listed about two hours before this tick); never screened before. Not in /workspace/job-finds, the journal or prior_outreach.json."),
'structability':dict(cover='Marc_Masarate_Structability_Civil_Structural_Engineer_Cover_Letter.pdf',res='Marc_Masarate_Structability_Resume.pdf',status='READY_JEREMIE_SEEK',method='SEEK',pct=60,
 rat=["Structability (Rockdale, Sydney consultancy doing insurance damage reports and scopes of work plus structural, civil and stormwater design) wants a Civil/Structural Engineer (70,000 to 80,000 dollars) for fire, tree and vehicle impact damaged buildings, 50/50 site and office, with mentoring and a 30 week engineering seminar program.",
 "It asks for a completed Civil/Structural Engineering degree, strong technical report writing, attention to detail and AutoCAD; duties include site inspections, causation reports, scopes of work and timber, steel and concrete design. Marc's BSCE, AS/NZS 1170 and AS 4100 coursework, stormwater design, AutoCAD and Revit, and 2019 to 2020 site inspection and reporting work cover the entry requirements.",
 "Direct employer, listed on SEEK 13 Nov 2026 AEDT, expires 13 Dec 2026; quick apply with seven questions. Advert says visa sponsorship may be considered (not needed: 485 to Dec 2027)."],
 caution="Structural design of timber, steel and concrete members and insurance damage reporting are new (said honestly). Relocation to Sydney unconfirmed. Fit is at the 60 threshold.",
 gaps=["No structural design practice","No insurance damage reporting experience","No Australian work experience","Relocation to Sydney unconfirmed"],
 listed='2026-11-13',expires='2026-12-13',apply="Apply on SEEK job 95876045 (seven questions: CAD, English, years as civil and structural engineer, work rights, construction years, licence, Microsoft Office). No email address published. Nothing submitted.",
 call=["Structural design? \u2192 AS/NZS 1170 and AS 4100 coursework and hand calculations; no member design on a paid job yet.","Site inspections? \u2192 Inspections, safety and quality checks on Philippine projects, 2019 to 2020.","Report writing? \u2192 Site, material and progress reports; technical reporting in the Advanced Diploma.","Move to Sydney? \u2192 Open to discussing relocation; Marc to confirm.","Work rights? \u2192 Subclass 485, full working rights until December 2027."],
 how_extra="Found on the open web (Jora graduate civil engineer, last 24 hours) and confirmed on SEEK job 95876045; the SEEK sweep prefilter had dropped it on the word structural. Never screened before; not in /workspace/job-finds, the journal or prior_outreach.json."),
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
     "application_route":d['route'],"application_method":p['method'],"recipient_name":d['recipient_name'],"recipient_role":d['recipient_role'],"recipient_email":d.get('recipient_email',''),"contact_email":d.get('recipient_email',''),
     "contact_evidence_url":d['contact_evidence_url'],"contact_verified_at":iso,"contact_confidence":("published_inbox" if d.get('recipient_email') else "none"),"subject":d['subject'],"email_body":d.get('email_body',''),"fit":p['rat'],"gaps":p['gaps'],
     "match_score":{"percent":p['pct'],"method":"resume-fit-v2","rationale":p['rat'],"caution":p['caution']},
     "advert":{"source":("seek" if d.get('seek_id') else "careersatcouncil"),"listed_at":p['listed'],"expires_at":p['expires'],"verified_at":iso,"apply_instructions":p['apply'],"screening_questions":[]},
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
