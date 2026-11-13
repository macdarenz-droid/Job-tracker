import json, uuid, hashlib, os, sys
from datetime import datetime, timezone
sys.path.insert(0,'/workspace/job-finds'); from _save_find import save
RUN='20261113T0211Z'
now=datetime.now(timezone.utc); iso=now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
local=datetime.now().astimezone(); found=local.strftime('%Y-%m-%dT%H:%M+11:00 AEDT')
def sha(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
SW="Tick "+RUN+": open web first (web searches across jobau, Prosple, Built In, SimplyHired, Jora, College Recruiter and SEEK category pages for Victorian graduate civil and junior drafting roles), then targeted SEEK keyword searches (draftsperson 30 days; graduate civil engineer, junior civil engineer, site engineer graduate 14 days) plus the 2 day SEEK sweep."
GM="Gmail could not be checked on this tick (no Gmail connector attached), so search macdarenz@gmail.com in:anywhere for the employer before applying. Dedupe: not in /workspace/job-finds, prior_outreach.json, earlier screen or candidate files or the journal."
P={
'cardinia':dict(cover='Marc_Masarate_Cardinia_Development_Engineer_Cover_Letter.pdf',res='Marc_Masarate_Cardinia_Resume.pdf',status='READY_JEREMIE_EMPLOYER_PORTAL',method='SEEK link-out to council portal',pct=74,
 rat=["Cardinia Shire Council has a newly created Development Engineer role in Officer VIC (full time, 79,608 to 85,742 dollars plus super, hybrid, monthly day off) assessing drainage, traffic and construction plans for new developments, learning alongside senior engineers.",
 "It asks for a civil engineering background as a recent graduate or up to two years experience, drainage principles highly regarded, eagerness to learn and clear writing; Marc's BSCE, Feb 2026 Advanced Diploma stormwater and drainage design in Civil 3D and AutoCAD, and 2019 to 2020 site reporting match.",
 "Direct council employer in Victoria; only valid Australian working rights required (485 to Dec 2027 qualifies)."],
 caution="Development assessment, Legal Point of Discharge and build over easement work is new (said honestly in the letter). Officer is in the south east, a long commute from Melton. Police check and pre-employment medical required. Closes 26 Nov 2026.",
 gaps=["No development assessment experience","No Australian site or council experience","Long commute from Melton to Officer"],
 listed='2026-11-13',expires='2026-11-26',apply="SEEK job 95866809 links out to the Cardinia Shire Council online application form; upload resume and a brief cover letter addressing suitability. Role enquiries by phone 5943 4423 (contact name blank in the advert). No email sent.",
 call=["Drainage principles? \u2192 Stormwater drainage design and documentation in Civil 3D and AutoCAD in the Advanced Diploma (Feb 2026), plus road geometry, earthworks and pavement.","Development engineering experience? \u2192 New; keen to learn assessments and approvals from the senior engineers.","Written communication? \u2192 Prepared site, material and progress reports as a field engineer (2019 to 2020).","Commute to Officer? \u2192 Lives in Melton with licence and transport; Marc to confirm the travel suits.","Work rights? \u2192 Subclass 485, full working rights until December 2027."],
 how_extra="Found by a targeted SEEK keyword search (job 95866809, listed 13 Nov 2026 AEDT, closes 26 Nov 2026); never screened before (earlier Cardinia board checks showed trades only)."),
'bsbrothers':dict(cover='Marc_Masarate_BSBrothers_Civil_Engineering_Draftsperson_Cover_Letter.pdf',res='Marc_Masarate_BSBrothers_Resume.pdf',status='HELD_MANDATORY_UNMET',method='SEEK',pct=66,
 rat=["B & S Brothers Enterprises (104 Collins Street, Melton) wants a full time Civil Engineering Draftsperson (70,000 to 80,000 dollars plus super) drafting drainage, sewerage, subdivision and road plans, assisting engineers with site measurements, quantities and inspections.",
 "It asks for an Advanced Diploma of Civil Construction Design or above, which Marc finished in Feb 2026, and the duties match his Civil 3D and AutoCAD design work and 2019 to 2020 site inspection and reporting.",
 "Direct employer in Marc's home suburb, listed 13 Nov 2026 on SEEK."],
 caution="The advert states a minimum of 3 years experience, which Marc does not have (about ten months of site work plus the diploma); held for Marc to decide. The letter says the gap honestly. SEEK asks years of civil drafting experience; answer truthfully.",
 gaps=["Minimum 3 years experience stated (mandatory, unmet)","No paid drafting experience in Australia"],
 listed='2026-11-13',expires='2026-12-13',apply="Apply on SEEK job 95870684 (six screening questions: work rights, salary, years as civil drafter, notice, civil construction qualification, years of engineering drafting). The advert also says email your resume but publishes no address. No email sent.",
 call=["Three years experience? \u2192 Not yet; about ten months on site in the Philippines (2019 to 2020) plus the Advanced Diploma finished Feb 2026.","Drafting software? \u2192 AutoCAD and Civil 3D for road, earthworks, pavement and stormwater drawings.","Site support? \u2192 Site inspections, quality checks and progress reports as field engineer and project-in-charge.","Location? \u2192 Lives in Melton.","Work rights? \u2192 Subclass 485, full working rights until December 2027."],
 how_extra="Found by a targeted SEEK keyword search (job 95870684, listed about 15 minutes before the search on 13 Nov 2026); never screened before."),
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
     "advert":{"source":("seek" if d.get('seek_id') else "web"),"listed_at":p['listed'],"expires_at":p['expires'],"verified_at":iso,"apply_instructions":p['apply'],"screening_questions":[]},
     "screening_answers":[],"checklist":d['checklist'],"notes":notes,"how_found":how,"call_prep":p['call'],"checked_at":iso,"seek_id":d.get('seek_id'),"duplicate_key":(d['company']+'|'+d['role']).lower(),"preparation_only":True,"found_at":found}
    readme=(f"# {d['company']}, {d['role']}, {d['location']}\n\n- Status: {p['status']}, fit {p['pct']}%, route {p['method']}\n- Link: {d['job_url']}\n- Apply: {p['apply']}\n- Closes: {p['expires'] or 'not stated'}\n- Why: {' '.join(p['rat'])}\n- Caution: {p['caution']}\n- Gaps: {'; '.join(p['gaps'])}\n- Files: record.json, draft.json, cover letter PDF and one page resume PDF (both read back).\n\n## Checklist\n"
     +"\n".join(f"{i+1}. {c}" for i,c in enumerate(d['checklist']))+"\n\n"+notes+"\n")
    json.dump(d,open('/tmp/draft.json','w'),indent=1,ensure_ascii=False)
    if save(rec,[cover,res,'/tmp/draft.json'],readme,local.strftime('%Y-%m-%d')): recs.append(rec)
json.dump(recs,open('local_records.json','w'),indent=1,ensure_ascii=False)
print(len(recs))
