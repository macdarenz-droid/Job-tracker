import json
D={}
D['cardinia']={"seek_id":"95866809","company":"Cardinia Shire Council","role":"Development Engineer","location":"Officer VIC",
"job_url":"https://www.seek.com.au/job/95866809","company_url":"https://www.cardinia.vic.gov.au","route":"SEEK link-out to the council online application form","application_type":"ADVERTISED_VACANCY","vacancy_status":"OPEN_SEEK",
"letter":{"recipient_name":"Team Leader Development","recipient_role":"","company":"Cardinia Shire Council","company_line":"Cardinia Shire Council has created a new Development Engineer role in Officer to assess drainage, traffic and construction plans for new developments, working alongside senior engineers.",
"subject":"Development Engineer, Officer (SEEK 95866809)","greeting":"Dear Team Leader Development,",
"paragraphs":["Please accept my application for the new Development Engineer role. Your advert asks for a civil engineering background as a recent graduate, an understanding of drainage principles and a genuine eagerness to learn development engineering, and that describes where I am.",
"I hold a Bachelor of Science in Civil Engineering (Philippines, 2019), and in February 2026 I finished an Advanced Diploma of Civil Construction Design in Australia. In that course I designed and documented road geometry, earthworks, pavement and stormwater drainage, and prepared and reviewed drawings in AutoCAD and Civil 3D against Australian Standards.",
"From 2019 to 2020 I worked on site in the Philippines as a field engineer and project-in-charge. I reviewed drawings, carried out site inspections and quality checks, and prepared site and progress reports while working with engineers, subcontractors and suppliers to sort out site issues.",
"Assessing development applications and Legal Point of Discharge requests would be new to me, and I would learn them from your senior engineers. I live in Melton, hold a White Card and an Australian driver's licence, and have full working rights to December 2027 on a Subclass 485 visa.",
"My resume is attached, and I would welcome the chance to talk about the role."],"closing":"Kind regards,"},
"checklist":["Search Gmail in:anywhere for Cardinia before applying (Gmail was not reachable on this tick)","Read the Position Description linked in the SEEK advert","Open SEEK job 95866809 (closes 26 Nov 2026) and follow Apply to the council online form","Upload the resume and the brief cover letter from this folder","Record the apply date in /workspace/job-finds"],
"screening_answers":[]}
D['bsbrothers']={"seek_id":"95870684","company":"B & S Brothers Enterprises Pty Ltd","role":"Civil Engineering Draftsperson","location":"Melton VIC",
"job_url":"https://www.seek.com.au/job/95870684","company_url":"","route":"SEEK quick apply","application_type":"ADVERTISED_VACANCY","vacancy_status":"OPEN_SEEK",
"letter":{"recipient_name":"Hiring Team","recipient_role":"","company":"B & S Brothers Enterprises Pty Ltd","company_line":"B & S Brothers Enterprises in Melton is hiring a Civil Engineering Draftsperson to draft drainage, sewerage, subdivision and road plans and to support its engineers on site.",
"subject":"Civil Engineering Draftsperson, Melton (SEEK 95870684)","greeting":"Dear Hiring Team,",
"paragraphs":["Please accept my application for the Civil Engineering Draftsperson role in Melton. I live in Melton, and your advert asks for an Advanced Diploma of Civil Construction Design, which I finished in February 2026.",
"In that course I designed and documented road geometry, earthworks, pavement and stormwater drainage, and prepared and reviewed drawings in AutoCAD and Civil 3D against Australian Standards. I also hold a Bachelor of Science in Civil Engineering (Philippines, 2019).",
"From 2019 to 2020 I worked on site in the Philippines as a field engineer and project-in-charge. I reviewed drawings, carried out site inspections and quality checks, prepared site, material and progress reports, and worked with subcontractors and suppliers to sort out site issues.",
"I do not yet have the three years of drafting experience your advert lists, so I am applying on the strength of the qualification and my site background. I hold a White Card and an Australian driver's licence, and have full working rights to December 2027 on a Subclass 485 visa.",
"My resume is attached, and I would welcome a chat."],"closing":"Kind regards,"},
"checklist":["Decide whether to apply despite the stated minimum of 3 years experience (Marc has about one year of site work plus the Feb 2026 Advanced Diploma)","Search Gmail in:anywhere for B & S Brothers before applying (Gmail was not reachable on this tick)","Open SEEK job 95870684 (closes 13 Dec 2026) and apply; answer the six SEEK questions honestly (485 visa, Advanced Diploma yes, drafting experience under 1 year)","Attach the resume and cover letter from this folder","Record the apply date in /workspace/job-finds"],
"screening_answers":[]}
for k,d in D.items():
    d.update({"recipient_name":"","recipient_role":"","recipient_email":"","contact_evidence_url":d['job_url'],"subject":d['letter']['subject'],"email_body":"","notes":""})
    json.dump(d,open(f'drafts/{k}.json','w'),indent=1,ensure_ascii=False)
    json.dump(d['letter'],open(f'drafts/{k}_L.json','w'),indent=1,ensure_ascii=False)
    open(f'drafts/{k}_letter.txt','w').write('\n\n'.join(d['letter']['paragraphs']))
    print(k, sum(len(p.split()) for p in d['letter']['paragraphs']))
