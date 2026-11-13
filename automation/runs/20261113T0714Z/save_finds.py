import json, uuid, hashlib, os, sys
from datetime import datetime, timezone
sys.path.insert(0,'/workspace/job-finds'); from _save_find import save
RUN='20261113T0714Z'
now=datetime.now(timezone.utc); iso=now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
local=datetime.now().astimezone(); found=local.strftime('%Y-%m-%dT%H:%M+11:00 AEDT')
def sha(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
SW="Tick "+RUN+": open web first (jobau, careersatcouncil, Council Direct, publicroles, Prosple, Jobstralia, ZipRecruiter, TheJobsMap, Jora and job board web searches for graduate civil, junior drafting, document control and council engineering roles across all states), then the 2 day SEEK sweep (962 seen, 182 prefilter, 60 details) and 14 targeted SEEK keyword searches (2 days)."
GM="Gmail could not be checked on this tick (no Gmail connector attached), so search macdarenz@gmail.com in:anywhere for the employer before applying. Dedupe: not in /workspace/job-finds, prior_outreach.json, earlier screen or candidate files or the journal."
P={
'pcp':dict(cover='Marc_Masarate_PCP_Graduate_Civil_Engineer_Cover_Letter.pdf',res='Marc_Masarate_PCP_Resume.pdf',status='PREPARED_NOT_SENT',method='Email (or SEEK, not both)',pct=74,
 rat=["PCP Solutions (Toowoomba civil earthworks and commercial plumbing contractor, 70+ staff, Tier 1 subcontract work across SE Queensland) wants a full time Graduate Civil Engineer (65,000 to 75,000 dollars) for site inspections, ITPs and QA records, progress reporting, drawing review, take offs and document control.",
 "It asks for a civil engineering degree, recent graduates or up to 2 years experience, basic understanding of drawings and specifications, licence and White Card, and regional travel; Marc's BSCE, Feb 2026 Advanced Diploma (Civil 3D, AutoCAD, cost estimates and BOQs) and 2019 to 2020 site inspection, quality and reporting work match most duties.",
 "Direct employer, listed on SEEK 13 Nov 2026 AEDT, expires 13 Dec 2026; the advert names admin@pcpsolutions.com.au for resumes and cover letters."],
 caution="Relocation to Toowoomba QLD (or regional QLD work) unconfirmed with Marc. No water infrastructure experience (highly regarded, not essential; said honestly). Site experience is about ten months in the Philippines. Apply by email or SEEK, not both.",
 gaps=["No water infrastructure or Tier 1 project experience","No Australian site experience","Relocation to Toowoomba unconfirmed"],
 listed='2026-11-13',expires='2026-12-13',apply="Apply via SEEK job 95872340 (seven questions) or email resume and cover letter to admin@pcpsolutions.com.au (published in the advert). Draft email prepared; NOT sent (Gmail not attached on this tick, local only).",
 call=["Site engineer experience? \u2192 About ten months on site in the Philippines (2019 to 2020) as project-in-charge and field engineer: inspections, quality checks, progress and material reports.","ITPs and QA records? \u2192 Quality checks and site records on Philippine projects; keen to learn your IMS and Tier 1 reporting.","Water infrastructure? \u2192 Not yet; stormwater drainage design in the Advanced Diploma only.","Move to Toowoomba? \u2192 Open to discussing relocation; Marc to confirm.","Work rights? \u2192 Subclass 485, full working rights until December 2027."],
 how_extra="Found by targeted SEEK keyword searches after the open web sweep (job 95872340, listed about five hours before this tick); never screened before. Contact: the advert itself publishes admin@pcpsolutions.com.au for applications. Email draft 199 words, checks.py tone and facts OK; checks.py record flags only the expected local-only items (attachments not uploaded to R2, so not publishable to the tracker), no content issues."),
'cono':dict(cover='Marc_Masarate_Cono_Site_Engineer_Cover_Letter.pdf',res='Marc_Masarate_Cono_Resume.pdf',status='READY_JEREMIE_SEEK',method='SEEK',pct=61,
 rat=["Cono Services (bulk excavation, earthworks and civil contractor working with Tier 1 builders) wants a Site Engineer in Sydney (90,000 to 110,000 dollars) for set out, ITPs, inspections and quality records, drawing interpretation and daily progress monitoring.",
 "It says graduate to intermediate level, degree in civil engineering, typically 1 to 4 years site experience, set out knowledge, licence and White Card; Marc's BSCE, Advanced Diploma earthworks design and 2019 to 2020 site inspection, quality and crew coordination work cover most duties.",
 "Direct employer, listed on SEEK 13 Nov 2026 AEDT, quick apply."],
 caution="Experience is stated as typical (1 to 4 years), not a hard minimum, but Marc has about ten months; salary band suggests they may prefer someone with more site time. No survey instrument or set out experience (said honestly). Relocation to Sydney unconfirmed.",
 gaps=["Under the typical 1 to 4 years site experience","No survey set out experience","No Australian site experience","Relocation to Sydney unconfirmed"],
 listed='2026-11-13',expires='2026-12-13',apply="Apply on SEEK job 95871692 (four questions: work rights, salary, years as site engineer, notice). No email address published. Nothing submitted.",
 call=["Site engineer years? \u2192 Less than one year, Philippines 2019 to 2020.","Set out and levels? \u2192 Studied surveying in the BSCE; no instrument work on a job yet, keen to learn.","ITPs and NCRs? \u2192 Quality checks and site records on Philippine projects.","Move to Sydney? \u2192 Open to discussing relocation; Marc to confirm.","Work rights? \u2192 Subclass 485, full working rights until December 2027."],
 how_extra="Found in the 2 day SEEK sweep and targeted SEEK keyword searches (job 95871692, listed 13 Nov 2026 AEDT); never screened before."),
'griffith':dict(cover='Marc_Masarate_Griffith_Graduate_Traffic_Design_Engineer_Cover_Letter.pdf',res='Marc_Masarate_Griffith_Resume.pdf',status='HELD_MANDATORY_UNRESOLVED',method='Company website (council portal)',pct=63,
 rat=["Griffith City Council (NSW Riverina) has a permanent Graduate Traffic and Design Engineer role (Grade 13, 87,107 to 95,814 dollars plus super, relocation assistance) assisting with traffic data, road safety proposals and heavy vehicle access for the Engineering Design Section.",
 "It asks for recent engineering graduates, AutoCAD and MS Office confidence, communication and organisation, and a current Australian driver licence; Marc's Advanced Diploma road geometry and pavement design in AutoCAD and Civil 3D with Austroads and AS 1742.14 coursework fits the design side.",
 "Direct council employer, posted about 4 Nov 2026 on careersatcouncil, closes 27 Nov 2026."],
 caution="Mandatory: a degree in engineering acceptable to Engineers Australia; Marc's Philippine BSCE recognition is unconfirmed (same rule applied to earlier held council records). Traffic data analysis is new. Relocation to Griffith NSW unconfirmed.",
 gaps=["Engineers Australia acceptance of the Philippine BSCE unconfirmed (mandatory)","No traffic engineering experience","Relocation to Griffith unconfirmed"],
 listed='2026-11-04',expires='2026-11-27',apply="Apply through the Griffith City Council portal linked from the careersatcouncil advert; include copies of licences and qualifications. Enquiries: Greg Balind 1300 176 077. Nothing submitted.",
 call=["Is your degree accepted by Engineers Australia? \u2192 Not yet assessed; Marc to confirm before applying.","Traffic engineering? \u2192 Road geometry, pavement design and AS 1742.14 in the Advanced Diploma; no traffic data work yet.","AutoCAD? \u2192 AutoCAD and Civil 3D from the Advanced Diploma (academic, not commercial).","Move to Griffith? \u2192 Open to discussing relocation; Marc to confirm.","Work rights? \u2192 Subclass 485, full working rights until December 2027."],
 how_extra="Found on the open web (careersatcouncil.com.au council engineering search, NSW council graduate listings); never screened before."),
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
