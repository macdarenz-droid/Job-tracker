import json, uuid, hashlib, shutil, sys, os
from datetime import datetime, timezone
sys.path.insert(0,'/workspace/job-finds'); from _save_find import save
RUN='20261021T1913Z'
now=datetime.now(timezone.utc); iso=now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
local=datetime.now().astimezone(); found=local.strftime('%Y-%m-%dT%H:%M+11:00 AEDT')
RES='/workspace/repos/Portfolio/assets/Marc-Darenz-Masarate-Resume.pdf'
def sha(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
d=json.load(open('drafts/leed-grad.json'))
cover=os.path.abspath('Marc_Masarate_Leed_Graduate_Civil_Engineer_Cover_Letter.pdf')
tmp='/tmp/Marc_Masarate_Leed_Resume.pdf'; shutil.copy(RES,tmp)
pct=68
rationale=["Graduate program for site-based civil construction (pipelines, treatment plants, pump stations, roads, earthworks) on regional VIC and NSW projects including Snowy 2.0, suited to FIFO and DIDO, which matches Marc's site background and his regional and FIFO availability.",
 "Eligibility explicitly lists Temporary Graduate visa holders, plus a C class licence and a civil engineering bachelor degree; Marc has the 485 visa, a licence and a 2019 BSCE, and his Philippines site work (inspections, quality checks, coordinating crews, site reports) fits a graduate site role.",
 "Direct employer; Leed's graduate page names careers@leed.net.au for applications and Leed's LinkedIn post (about early Oct 2026) says it is still seeking graduate applications; a December 2026 graduate intake expression of interest is circulating on job boards."]
caution="Degree rule reads 'completed or expected completion in the intake year'; Marc's BSCE was completed in 2019, so Leed may prefer recent graduates (Marc could ask). The application needs an academic transcript and two referees, neither on record. Water and pipeline work is not in Marc's history. Regional VIC and NSW FIFO or DIDO, so Marc to confirm."
gaps=["Bachelor degree completed 2019, not in the intake year","Academic transcript and two referee details needed (not on record)","No Australian site experience; site work was in the Philippines 2019 to 2020","No water, pipeline or treatment plant project experience"]
how=(f"Victoria off-SEEK rotation on tick {RUN}. The default SEEK sweep (3 days, 1140 seen) and a widened 7-day sweep with 20 new keyword sets (1521 seen, 326 past the prefilter) found only adverts already screened in earlier ticks. Leed came from an open-web search of regional Victoria graduate roles: job boards show 'Expression Of Interest - Graduate Civil Engineer Program (Dec 2026)', and Leed's own graduate page (https://www.leed.net.au/working-at-leed/graduates-and-undergraduates/) sets the eligibility (full working rights including Temporary Graduate visa holders, C class licence, civil degree) and names careers@leed.net.au for applications, asking for a resume of at most 2 pages, a cover letter, an academic transcript and two referees. Leed's LinkedIn post after Deakin's Geelong careers expo says it is still seeking graduates for regional VIC and NSW projects including Snowy 2.0, mainly FIFO and DIDO. "
 "Dedupe: not in prior_outreach.json, employers.json, the journal or /workspace/job-finds; Gmail search for leed.net.au or Leed on 22 Oct 2026 found no Leed email (only unrelated SEEK mail). Email body and cover letter drafted from facts.json only and passed checks.py tone and facts. Nothing was sent. Saved locally only (tracker full).")
call=["How did you hear about the program? \u2192 Your graduate page and your post saying you still need graduates for regional VIC and NSW projects.",
 "When did you finish your degree? \u2192 BSCE in the Philippines in 2019, and the Advanced Diploma of Civil Construction Design in Australia in February 2026.",
 "Are you happy to do FIFO or DIDO in regional Victoria and NSW? \u2192 Marc to answer; FIFO and regional availability is on record.",
 "Have you worked on water or pipeline projects? \u2192 No; my site work was a community hall renovation and residential subdivision finishing works.",
 "What are your work rights? \u2192 Subclass 485 visa, full working rights until December 2027.",
 "Tell me about your site experience. \u2192 About a year in the Philippines, 2019 to 2020: project-in-charge on a community hall renovation (10 to 15 workers a day, drawing reviews, inspections, quality checks), then field engineer on subdivision finishing works (site reports, material records, procurement).",
 "When could you start? \u2192 Marc to answer honestly; nothing was promised."]
notes="HOW GROK AI FOUND THIS\n"+how+"\n\nIF THEY CALL, LIKELY QUESTIONS\n"+"\n".join('\u2022 '+c for c in call)
rid=str(uuid.uuid4())
rec={"id":rid,"key":"manual:"+rid,"contributor_name":"Grok AI","created_by":"grok-job-search","record_kind":"AUTOMATED_LEAD","run_id":RUN,
 "created_at":iso,"updated_at":iso,"version":1,
 "attachments":[{"kind":"cover","filename":os.path.basename(cover),"sha256":sha(cover),"stored_in":"local:/workspace/job-finds"},
                {"kind":"resume","filename":os.path.basename(tmp),"sha256":sha(tmp),"stored_in":"local:/workspace/job-finds"}],
 "company":d['company'],"role":d['role'],"location":d['location'],"job_url":d['job_url'],"company_url":d['company_url'],
 "status":"PREPARED_NOT_SENT","application_type":"ADVERTISED_VACANCY","vacancy_status":"OPEN_PROGRAM_VERIFIED","application_route":"EMAIL",
 "application_method":"Email","recipient_name":"","recipient_role":d['recipient_role'],"recipient_email":d['recipient_email'],"contact_email":d['recipient_email'],
 "contact_evidence_url":d['contact_evidence_url'],"contact_verified_at":iso,"contact_confidence":"published_inbox",
 "subject":d['subject'],"email_body":d['email_body'],"fit":rationale,"gaps":gaps,
 "match_score":{"percent":pct,"method":"resume-fit-v2","rationale":rationale,"caution":caution},
 "advert":{"source":"employer_site","listed_at":"","expires_at":"","verified_at":iso,"apply_instructions":"Email careers@leed.net.au with a resume (max 2 pages), cover letter, academic transcript and two referees.","screening_questions":[]},
 "screening_answers":[],"checklist":d['checklist'],"notes":notes,"how_found":how,"call_prep":call,"checked_at":iso,
 "seek_id":None,"duplicate_key":"leedengineeringandconstruction|grad-civil-2026","preparation_only":True,"found_at":found}
readme=(f"# {d['company']}, {d['role']}\n\n- Status: PREPARED_NOT_SENT, fit {pct}%, route EMAIL to {d['recipient_email']}\n- Link: {d['job_url']}\n"
        f"- Why: {' '.join(rationale)}\n- Caution: {caution}\n- Gaps: {'; '.join(gaps)}\n"
        "- Files: record.json, draft.json (email body and letter), cover letter PDF (1 page, read back: name and program correct), resume PDF.\n\n## Checklist\n"
        + "\n".join(f"{i+1}. {c}" for i,c in enumerate(d['checklist'])) + "\n\n## Email draft\n\nSubject: "+d['subject']+"\n\n"+d['email_body']+"\n\n"+notes+"\n")
json.dump(d,open('/tmp/draft.json','w'),indent=1,ensure_ascii=False)
save(rec,[cover,tmp,'/tmp/draft.json'],readme,local.strftime('%Y-%m-%d'))
json.dump({"percent":pct,"rationale":rationale,"caution":caution,"gaps":gaps,"mandatory_unmet":[],"mandatory_unresolved":[],"route":"EMAIL","apply_email":d['recipient_email'],"open":True,"employer_is_agency":False,"company":d['company'],"title":d['role']},open('screen/leed-grad.json','w'),indent=1)
json.dump([rec],open('local_records.json','w'),indent=1,ensure_ascii=False)
