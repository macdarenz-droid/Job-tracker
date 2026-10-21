import json, uuid, hashlib, shutil, sys, os, copy
from datetime import datetime, timezone
sys.path.insert(0,'/workspace/job-finds'); from _save_find import save
RUN=open('/tmp/run_id').read().strip()
now=datetime.now(timezone.utc); iso=now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
local=datetime.now().astimezone(); found=local.strftime('%Y-%m-%dT%H:%M+11:00 AEDT')
RES='/workspace/repos/Portfolio/assets/Marc-Darenz-Masarate-Resume.pdf'
def sha(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
COMMON_CALL=[
 "What are your work rights? \u2192 Subclass 485 visa, full working rights until December 2027.",
 "Tell me about your site experience. \u2192 About a year in the Philippines, 2019 to 2020: project-in-charge on a community hall renovation (10 to 15 workers a day, drawing reviews, inspections, quality checks), then field engineer on subdivision finishing works (site reports, material records, procurement, coordinating with engineers and suppliers).",
 "What did you study in Australia? \u2192 Advanced Diploma of Civil Construction Design, Albright Institute, February 2024 to February 2026: road geometry, earthworks, pavement and stormwater drainage, drawings in AutoCAD and Civil 3D to Australian Standards, Before You Dig Australia enquiries.",
 "Do you have a licence, White Card, transport? \u2192 Yes to all three; also a Working with Children Check.",
 "When could you start, and what salary? \u2192 Answer honestly; nothing was promised in the application."]
SPEC={
'95393367':dict(slug='Coffey', cover='Marc_Masarate_Coffey_Testing_CMT_Technician_Cover_Letter.pdf', resume='Marc_Masarate_Coffey_Testing_Resume.pdf',
 status='READY_JEREMIE_EMPLOYER_PORTAL', pct=68,
 rationale=["Entry-level technician role with a first-week Training Academy and funded Certificate III or IV: no prior testing experience required, only safety awareness, willingness to learn, computer skills and fitness for lifting.",
  "Duties overlap Marc's site record: travelling to project sites, sampling and testing soils, aggregates and concrete, recording results and working with site supervisors and engineers; his coursework covered AS 1289 and AS 1726, and his Philippines site work included inspections, quality checks and material records.",
  "Direct employer (Coffey Testing, NATA accredited CMT provider), full time, Werribee VIC near Melton; listed 21 Oct 2026, SEEK expiry 20 Nov 2026."],
 caution="Testing technician pathway rather than drafting or site engineering, so it is a step sideways into civil infrastructure quality work. Manual driver's licence is 'advantageous' (licence type not on record). Physically demanding (repeated lifts of 15 kg and over). No laboratory or NATA testing experience on record.",
 gaps=["No construction materials testing or laboratory experience (AS 1289 and AS 1726 are coursework only)","Manual licence advantageous; licence type not on record","No Australian site experience; site work was in the Philippines 2019 to 2020"],
 listed='2026-10-21T00:31:42.739Z', expires='2026-11-20T12:59:59.999Z',
 apply="SEEK link out to Coffey Testing's own application page. No email or named contact in the advert.",
 how=f"Contractors and testing consultancies rotation on tick {RUN}. Not in the default SEEK sweep: found in the widened SEEK keyword sweep (daterange 14, 1767 listings seen, 397 past the prefilter) among listings that had never been detailed, then fetched with seek.py details. SEEK id 95393367, listed 21 Oct 2026 11:31 AEDT, SEEK expiry 20 Nov 2026 (about 23:59 AEDT). Direct employer: Coffey Testing Pty Ltd (also advertising the same entry-level role in Canberra and Western Sydney). Contact: the advert gives no email or named person, so no email was drafted; route is Coffey Testing's own application page via the SEEK link out. Dedupe: tracker.py check new; not in prior_outreach.json, employers.json, the journal or /workspace/job-finds; Gmail in:anywhere for Coffey: only a 4 Aug 2026 LinkedIn alert and an unrelated 2019 personal email, no application. Nothing was sent or applied. Saved locally only (tracker full).",
 call=["How did you find us? \u2192 Your entry-level CMT Technician advert for Werribee on SEEK.",
  "Have you done materials testing before? \u2192 Not in a laboratory. I studied AS 1289 and AS 1726 in my Advanced Diploma, and on site in the Philippines I did inspections, quality checks and kept material records.",
  "Is your licence manual? \u2192 Marc to answer.",
  "Are you comfortable with physical work and lifting? \u2192 Marc to answer honestly.",
  "Why testing rather than design? \u2192 It is hands-on civil infrastructure work on site and in the lab, close to home, with a training pathway.",
  "Can you travel to regional sites? \u2192 Yes, available for site and regional project work."]+COMMON_CALL),
'95409467':dict(slug='McConnell_Dowell', cover='Marc_Masarate_McConnell_Dowell_Site_Engineer_Cover_Letter.pdf', resume='Marc_Masarate_McConnell_Dowell_Resume.pdf',
 status='READY_JEREMIE_EMPLOYER_PORTAL', pct=64,
 rationale=["Site engineer role on a marine infrastructure project: coordinating site activities, interpreting drawings, inspections, ITPs and quality documentation, progress monitoring and subcontractor coordination, which match Marc's Philippines site work (drawing reviews, inspections, quality checks, site and progress reports, coordinating crews and subcontractors).",
  "Essentials met: civil engineering degree (BSCE 2019, plus Advanced Diploma 2026), driver's licence and White Card. 'Ideally at least two years' is a preference and the advert invites applicants with transferable skills.",
  "Direct employer (McConnell Dowell), full time, FIFO 2:1 from Perth to the Mid West, consistent with Marc's FIFO availability; listed 21 Oct 2026, SEEK expiry 20 Nov 2026."],
 caution="About a year of site experience (Philippines, 2019 to 2020) against a preferred two years; no marine or Australian site experience; ITP authoring, cost and claims work not on record. FIFO is from Perth, so Marc must confirm whether he would need to be Perth based. Pre-employment medical with drug and alcohol testing.",
 gaps=["Site experience about a year against a preferred two years","No marine construction experience","No Australian site experience","Progress claims, procurement packages and cost monitoring on a major project not on record","FIFO point of hire likely Perth (Marc to confirm)"],
 listed='2026-10-21T07:58:56.627Z', expires='2026-11-20T07:58:00.000Z',
 apply="SEEK link out to McConnell Dowell's own careers page. No email or named contact in the advert.",
 how=f"Contractors rotation on tick {RUN}. Found in the widened SEEK keyword sweep (daterange 14, 1767 listings seen, 397 past the prefilter) among listings never detailed before, then fetched with seek.py details. SEEK id 95409467, listed 21 Oct 2026 18:58 AEDT, SEEK expiry 20 Nov 2026 (about 18:58 AEDT). Direct employer: McConnell Dowell Australia. Contact: the advert gives no email or named person, so no email was drafted; route is McConnell Dowell's careers page via the SEEK link out. Dedupe: tracker.py check new; not in prior_outreach.json or /workspace/job-finds; employers.json notes only an earlier look at the McConnell Dowell 2027 graduate program (not applied); Gmail in:anywhere for McConnell: no application receipt or reply (matches were SEEK receipt threads for other employers). Nothing was sent or applied. Saved locally only (tracker full).",
 call=["How did you find us? \u2192 Your Site Engineer advert for the Mid West marine project on SEEK.",
  "How much site experience do you have? \u2192 About a year in the Philippines (April 2019 to February 2020), as project-in-charge then field engineer; not yet on an Australian or marine project.",
  "Have you worked with ITPs and quality documentation? \u2192 I carried out site inspections, safety checks and quality monitoring and kept site reports and material records; I have not written ITPs on an Australian project.",
  "Can you do FIFO 2:1 from Perth? \u2192 Marc to answer; FIFO availability is on record but the point of hire is Perth.",
  "Have you handled progress claims or subcontractor packages? \u2192 I tracked procurement and materials and coordinated subcontractors and suppliers; claims were not part of my role."]+COMMON_CALL),
}
recs=[]
for sid,s in SPEC.items():
    d=json.load(open(f'drafts/{sid}.json')); det=json.load(open(f'details/{sid}.json'))
    tmp=f'/tmp/{s["resume"]}'; shutil.copy(RES,tmp)
    cover=os.path.abspath(s['cover'])
    notes=("HOW GROK AI FOUND THIS\n"+s['how']+"\n\nIF THEY CALL, LIKELY QUESTIONS\n"+"\n".join('\u2022 '+c for c in s['call']))
    rec={"id":str(uuid.uuid4())}
    rec.update({"key":"manual:"+rec['id'],"contributor_name":"Grok AI","created_by":"grok-job-search","record_kind":"AUTOMATED_LEAD","run_id":RUN,
     "created_at":iso,"updated_at":iso,"version":1,
     "attachments":[{"kind":"cover","filename":s['cover'],"sha256":sha(cover),"stored_in":"local:/workspace/job-finds"},
                    {"kind":"resume","filename":s['resume'],"sha256":sha(tmp),"stored_in":"local:/workspace/job-finds"}],
     "company":d['company'],"role":d['role'],"location":d['location'],"job_url":d['job_url'],"company_url":d['company_url'],
     "status":s['status'],"application_type":"ADVERTISED_VACANCY","vacancy_status":"OPEN_ADVERT_VERIFIED","application_route":"EMPLOYER_PORTAL",
     "application_method":"Company website","recipient_name":"","recipient_role":"","recipient_email":"","contact_email":"",
     "contact_evidence_url":d['contact_evidence_url'],"contact_verified_at":"","contact_confidence":"none",
     "subject":d['subject'],"email_body":"","fit":s['rationale'],"gaps":s['gaps'],
     "match_score":{"percent":s['pct'],"method":"resume-fit-v2","rationale":s['rationale'],"caution":s['caution']},
     "advert":{"source":"seek","listed_at":s['listed'],"expires_at":s['expires'],"verified_at":iso,"apply_instructions":s['apply'],"screening_questions":det.get('screening_questions') or []},
     "screening_answers":[],"checklist":d['checklist'],"notes":notes,"how_found":s['how'],"call_prep":s['call'],"checked_at":iso,
     "seek_id":int(sid),"duplicate_key":''.join(c for c in d['company'].lower() if c.isalnum())+f"|seek:{sid}","preparation_only":True,"found_at":found})
    readme=(f"# {d['company']}, {d['role']} ({d['location']})\n\n- Status: {s['status']}, fit {s['pct']}%, route EMPLOYER_PORTAL\n- Link: {d['job_url']}\n"
            f"- Why: {' '.join(s['rationale'])}\n- Caution: {s['caution']}\n- Gaps: {'; '.join(s['gaps'])}\n"
            f"- Files: record.json, draft.json, cover letter PDF (1 page, read back: name and role correct), resume PDF.\n\n## Checklist\n"
            + "\n".join(f"{i+1}. {c}" for i,c in enumerate(d['checklist'])) + "\n\n" + notes + "\n")
    draftp=f'/tmp/draft.json'; json.dump(d,open(draftp,'w'),indent=1,ensure_ascii=False)
    folder=save(rec,[cover,tmp,draftp],readme,local.strftime('%Y-%m-%d'))
    recs.append(rec)
    json.dump(s|{'percent':s['pct']},open(f'screen/{sid}.json','w'),indent=1,ensure_ascii=False)
json.dump(recs,open('local_records.json','w'),indent=1,ensure_ascii=False)
