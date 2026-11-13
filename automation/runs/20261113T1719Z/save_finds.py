import json, uuid, hashlib, os, sys
from datetime import datetime, timezone
sys.path.insert(0,'/workspace/job-finds'); from _save_find import save
RUN='20261113T1719Z'
now=datetime.now(timezone.utc); iso=now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
local=datetime.now().astimezone(); found=local.strftime('%Y-%m-%dT%H:%M+11:00 AEDT')
def sha(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
SW="Tick "+RUN+": SEEK 3 day sweep (685 seen, 172 prefilter, 80 details; only 2 unseen, Sacyr Perth Site Engineer 2+ yrs and a marine engineer, both not kept) plus 22 targeted SEEK keyword searches (3 days, nothing new and relevant); open web: LinkedIn guest job listings Australia wide (12 keyword searches, last 3 days), careersatcouncil (no civil junior roles), Jora (blocked by bot check)."
GM="Gmail could not be checked on this tick (no Gmail connector attached), so search macdarenz@gmail.com in:anywhere for the employer before applying. Dedupe: not in /workspace/job-finds, prior_outreach.json, earlier run files or the journal."
P={
'edge':dict(cover='Marc_Masarate_Edge_Building_Fire_Hydraulic_Engineer_Cover_Letter.pdf',res='Marc_Masarate_Edge_Building_Resume.pdf',status='READY_JEREMIE_EMPLOYER_PORTAL',method='LinkedIn',pct=61,
 rat=["Edge Building Solutions (small Brisbane owned building services consultancy, founded 2024, about 8 staff) wants a Junior to Mid-Level Fire & Hydraulic Engineer, full time, hybrid in Brisbane: calculations, drawings and specifications for fire protection and hydraulic services on commercial, retail, industrial and education buildings, supporting senior engineers.",
 "It asks for a Bachelor's degree in Engineering (Mechanical, Civil or Building Services), a foundation in hydraulic systems and water engineering, AutoCAD or Revit, MS Office, and communication; prior building services experience is only an advantage. Marc's BSCE (hydraulics studied), stormwater drainage design, AutoCAD, Civil 3D and Revit, and 2019 to 2020 site and reporting work fit the junior end.",
 "Direct employer, posted on LinkedIn about 5 hours before this tick (13 Nov 2026 AEDT), fewer than 25 applicants; no closing date shown."],
 caution="Building services (fire and hydraulic) is a different field from Marc's road and civil focus; AS 2419, AS 2118 and AS/NZS 3500 and mechanical principles are new (said honestly). Relocation to Brisbane unconfirmed. Fit is near the 60 threshold. Apply route is the LinkedIn apply button (not confirmed whether it is Easy Apply or links out).",
 gaps=["No fire or hydraulic building services design experience","Mechanical principles for building services","No Australian work experience","Relocation to Brisbane unconfirmed"],
 listed='2026-11-13',expires='',apply="Apply via LinkedIn job 4489558729. Published contact on the employer site: Ozcar Callos, Senior Engineer, ocallos@edgebuildings.au (https://edgebuildings.au/about/); general inbox info@edgebuildings.au appears only on a third party profile, not used. Nothing submitted or emailed.",
 call=["Hydraulics background? \u2192 Hydraulics in the BSCE (Philippines, 2019) and stormwater drainage design in the Advanced Diploma (Feb 2026).","Fire or hydraulic services design? \u2192 Not yet; would learn AS 2419, AS 2118 and AS/NZS 3500 from the team.","Software? \u2192 AutoCAD, Civil 3D and Revit from coursework, not commercial production.","Move to Brisbane? \u2192 Open to relocating; Marc to confirm.","Work rights? \u2192 Subclass 485, full working rights until December 2027."],
 how_extra="Found on the open web (LinkedIn guest listing, junior civil engineer search, posted about 5 hours earlier); never screened before. Employer site read for the company line and the published senior engineer contact."),
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
     "advert":{"source":("seek" if d.get('seek_id') else "linkedin"),"listed_at":p['listed'],"expires_at":p['expires'],"verified_at":iso,"apply_instructions":p['apply'],"screening_questions":[]},
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
