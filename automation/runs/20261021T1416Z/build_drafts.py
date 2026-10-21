import json
RUN=open('/tmp/run_id').read().strip()
D={}
D['95393367']=dict(
 seek_id=95393367, company="Coffey Testing Pty Ltd", role="Construction Materials Testing Technician, Entry-Level",
 location="Werribee, Melbourne VIC", job_url="https://www.seek.com.au/job/95393367", company_url="https://www.coffeytesting.com.au/",
 route="EMPLOYER_PORTAL", application_type="ADVERTISED_VACANCY", recipient_name="", recipient_role="", recipient_email="",
 contact_evidence_url="https://www.seek.com.au/job/95393367",
 subject="Construction Materials Testing Technician, Werribee (SEEK 95393367), Marc Masarate", email_body="",
 letter=dict(recipient_name="", recipient_role="Recruitment Team", company="Coffey Testing Pty Ltd",
  company_line="Coffey Testing provides NATA accredited construction materials testing for transport infrastructure, mining and resources projects, with field and laboratory work on soils, concrete and aggregates.",
  subject="Construction Materials Testing Technician, Entry-Level, Werribee (SEEK 95393367)",
  greeting="Dear Coffey Testing Recruitment Team,",
  paragraphs=[
   "I saw your entry-level Construction Materials Testing Technician advert for Werribee on SEEK and would like to apply. I am based in Melton, close to Werribee, and I am looking for a site-based start in civil infrastructure where quality and accurate records matter.",
   "I completed an Advanced Diploma of Civil Construction Design at Albright Institute in February 2026, where I designed and documented road geometry, earthworks, pavement and stormwater drainage. My coursework covered AS 1289 and AS 1726, so I have studied how soils are tested and described, and I hold a Bachelor of Science in Civil Engineering from the Philippines (2019).",
   "From 2019 to 2020 I worked on site in the Philippines, first as project-in-charge on a community hall renovation and then as a field engineer on residential subdivision finishing works. I carried out site inspections and quality checks, kept material records and wrote site and progress reports, and worked closely with engineers, subcontractors and suppliers.",
   "I have not worked in a testing laboratory yet, so I would value the Training Academy and the Certificate III pathway you describe. I hold an Australian driver's licence with my own reliable transport, a White Card, and full working rights to December 2027 on a Subclass 485 visa. I am available for site and regional project work.",
   "I have attached my resume and would welcome the chance to talk about the role."],
  closing="Kind regards,"),
 screening_answers=[],
 checklist=[
  "Check Gmail again for any Coffey Testing receipt, then open https://www.seek.com.au/job/95393367 and confirm it is still open (SEEK listing expires 20 Nov 2026, about 23:59 AEDT)",
  "Confirm with Marc whether his driver's licence is manual or automatic (the advert says a manual licence is advantageous, not required) and that he is comfortable with the physical side of the role (repeatedly lifting 15 kg and over)",
  "Apply through Coffey Testing's own application page via the SEEK link out with the master resume and the saved cover letter PDF",
  "Answer any portal questions from facts only; do not claim laboratory or NATA testing experience (AS 1289 and AS 1726 are coursework only)",
  "Note the receipt date in /workspace/job-finds (tracker recording is paused)"],
 notes="Direct employer advert on SEEK with a link out to Coffey Testing's own application page. Entry level with a first-week Training Academy and a funded Certificate III or IV in laboratory skills. Werribee is close to Melton, so no relocation.")
D['95409467']=dict(
 seek_id=95409467, company="McConnell Dowell Australia", role="Site Engineer (Marine, Mid West WA, FIFO 2:1)",
 location="Perth WA (FIFO to the Mid West)", job_url="https://www.seek.com.au/job/95409467", company_url="https://www.mcconnelldowell.com/",
 route="EMPLOYER_PORTAL", application_type="ADVERTISED_VACANCY", recipient_name="", recipient_role="", recipient_email="",
 contact_evidence_url="https://www.seek.com.au/job/95409467",
 subject="Site Engineer, Mid West WA FIFO (SEEK 95409467), Marc Masarate", email_body="",
 letter=dict(recipient_name="", recipient_role="Recruitment Team", company="McConnell Dowell Australia",
  company_line="McConnell Dowell is delivering a marine infrastructure project in Western Australia's Mid West, with site engineers working on a FIFO 2:1 roster alongside the Construction Manager, supervisors and subcontractors.",
  subject="Site Engineer, Marine Infrastructure, Mid West WA (SEEK 95409467)",
  greeting="Dear McConnell Dowell Recruitment Team,",
  paragraphs=[
   "I saw your Site Engineer advert on SEEK for the marine infrastructure project in WA's Mid West and would like to apply. The role centres on interpreting drawings, inspections, quality documentation and coordinating site activities, which is the work I want to build my career on, and I am available for FIFO work.",
   "I hold a Bachelor of Science in Civil Engineering from the Philippines (2019) and completed an Advanced Diploma of Civil Construction Design at Albright Institute in February 2026, where I designed and documented road geometry, earthworks, pavement and stormwater drainage in AutoCAD and Civil 3D.",
   "From 2019 to 2020 I worked on site in the Philippines. As project-in-charge on a community hall renovation I coordinated 10 to 15 workers each day, reviewed structural and architectural drawings against project requirements, and carried out site inspections, safety checks and quality monitoring. As a field engineer on residential subdivision finishing works I prepared site reports, material records and progress reports and coordinated with engineers, subcontractors and suppliers.",
   "My site experience is about a year rather than the two years you mention, and I have not worked on a marine project, but you welcome applicants with transferable skills. I hold an Australian driver's licence and a White Card, and full working rights to December 2027 on a Subclass 485 visa.",
   "I have attached my resume and would welcome the chance to discuss the role."],
  closing="Kind regards,"),
 screening_answers=[],
 checklist=[
  "Confirm with Marc that he is happy with a FIFO 2:1 roster to WA's Mid West from Perth (FIFO availability is on record; check whether flights are from Perth only and whether he would need to be Perth based)",
  "Check Gmail again for any McConnell Dowell receipt, then open https://www.seek.com.au/job/95409467 and confirm it is still open (SEEK listing expires 20 Nov 2026, about 18:58 AEDT)",
  "Apply through McConnell Dowell's own careers page via the SEEK link out with the master resume and the saved cover letter PDF",
  "Answer portal questions from facts only: site experience is about a year (Apr 2019 to Feb 2020, Philippines); no marine or Australian site experience; do not claim ITP authoring beyond inspections and quality checks",
  "Note the receipt date in /workspace/job-finds (tracker recording is paused)"],
 notes="Direct employer advert (McConnell Dowell, SEEK link out). 'Ideally at least two years' experience' is a preference, not a mandatory requirement; the advert explicitly invites applicants who do not tick every box. Pre-employment medical including drug and alcohol testing.")
for k,v in D.items(): json.dump(v,open(f'drafts/{k}.json','w'),indent=1,ensure_ascii=False)
