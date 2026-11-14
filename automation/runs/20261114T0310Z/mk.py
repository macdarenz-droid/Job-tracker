import json
# ---- vTCE speculative (email) ----
email="""Dear Andrew,

Your careers page says vT Consulting Engineers is always looking for people from cadet level up, with Civil Designer and Civil Engineer listed for the civil team, so I'm writing to ask about a junior civil design role.

In February 2026 I finished an Advanced Diploma of Civil Construction Design, where I designed and documented road geometry, earthworks, pavement and stormwater drainage in Civil 3D and AutoCAD. I also hold a Bachelor of Science in Civil Engineering (Philippines, 2019). From 2019 to 2020 I worked on site in the Philippines as a project-in-charge engineer and then a field engineer, reviewing drawings and carrying out inspections and quality checks. I live in Melton VIC, hold a White Card and a driver's licence, and have full working rights to December 2027 on a Subclass 485 visa. I'm open to discussing relocation to Brisbane.

Your Augustine Heights State School work, with bulk earthworks, stormwater networks, council road design and modified pavements, is the kind of civil documentation I trained in. My design work so far is from coursework rather than commercial projects. Would you be open to a short call? I've attached my resume and cover letter.

Kind regards,
Marc Darenz Masarate
0478 764 077
macdarenz@gmail.com
https://macdarenz-droid.github.io/Portfolio
"""
letter={"recipient_name":"Andrew van Tonder","recipient_role":"Director","company":"vT Consulting Engineers","company_line":"vT Consulting Engineers, founded by Andrew van Tonder in 2013, provides civil and structural engineering from Carina in Brisbane, from development approval through detailed design to construction inspections.",
"subject":"Expression of interest: junior civil designer","greeting":"Dear Andrew,",
"paragraphs":["I am writing to ask whether vT Consulting Engineers has room for a junior civil designer or graduate civil engineer. Your careers page says you are always looking for people from cadet level up, and it lists Civil Designer and Civil Engineer for the civil team.",
"In February 2026 I finished an Advanced Diploma of Civil Construction Design in Australia. I designed and documented road geometry, earthworks, pavement systems and stormwater drainage, and prepared and reviewed technical drawings in AutoCAD and Civil 3D, applying Australian Standards. I also hold a Bachelor of Science in Civil Engineering (Philippines, 2019).",
"From 2019 to 2020 I worked on site in the Philippines, first as a project-in-charge engineer on a community hall renovation and then as a field engineer on residential subdivision finishing works. I reviewed structural and architectural drawings, carried out site inspections and quality checks, and prepared site and progress reports.",
"Your Augustine Heights State School project, with bulk earthworks, stormwater networks, council road design and modified pavements, is the kind of documentation I trained in. My design work so far is from coursework rather than commercial projects. I live in Melton VIC, hold a White Card and a driver's licence, have full working rights to December 2027 on a Subclass 485 visa, and am open to discussing relocation to Brisbane.",
"My resume is attached, and I would welcome a short conversation."],"closing":"Kind regards,"}
d={"seek_id":None,"company":"vT Consulting Engineers","role":"Speculative enquiry: junior civil designer / graduate civil engineer","location":"Carina, Brisbane QLD",
"job_url":"https://vtce.com.au/careers-with-vtce/","company_url":"https://vtce.com.au/","route":"EMAIL","application_type":"SPECULATIVE_ENQUIRY","vacancy_status":"OPEN_CAREERS_EOI_NO_SPECIFIC_ADVERT",
"recipient_name":"Andrew van Tonder","recipient_role":"Director","recipient_email":"admin@vtce.com.au","contact_evidence_url":"https://vtce.com.au/careers-with-vtce/",
"subject":"Junior civil designer enquiry, Marc Masarate","email_body":email,"letter":letter,
"checklist":["Search Gmail in:anywhere for vT Consulting Engineers, vTCE and vtce.com.au before sending (Gmail was not reachable on this tick)","Confirm Marc is open to relocating to Brisbane (South East Queensland) for a junior civil design role","Send the email in this folder from macdarenz@gmail.com to admin@vtce.com.au (the careers page address) with the cover letter and one page resume attached","Alternatively use the upload form on https://vtce.com.au/careers-with-vtce/ with the same files","Record the send date in /workspace/job-finds"],
"screening_answers":[]}
json.dump(d,open('drafts/vtce.json','w'),indent=1,ensure_ascii=False)
json.dump(letter,open('drafts/vtce_L.json','w'),indent=1,ensure_ascii=False)
open('drafts/vtce_letter.txt','w').write('\n\n'.join(letter['paragraphs']))
open('drafts/vtce_email.txt','w').write(email)
print('vtce letter',sum(len(p.split()) for p in letter['paragraphs']),'email',len(email.split()))
# ---- Residential Engineering (portal) ----
L2={"recipient_name":"","recipient_role":"Hiring Team","company":"Residential Engineering","company_line":"Residential Engineering has delivered structural, geotechnical, inspection and survey services to residential builders across New South Wales for more than 40 years, backed by Five Group.",
"subject":"Application: Structural Site Engineer, Canberra or Goulburn","greeting":"Dear Hiring Team,",
"paragraphs":["I am applying for the Structural Site Engineer role covering Canberra and Goulburn, advertised on LinkedIn. A field based role built around site inspections on residential projects, with structural design during quieter periods, is the kind of work I want to grow in.",
"I hold a Bachelor of Science in Civil Engineering (Philippines, 2019), where I studied structural principles, construction methods and surveying, and in February 2026 I finished an Advanced Diploma of Civil Construction Design in Australia, preparing and reviewing technical drawings in AutoCAD and Civil 3D and applying Australian Standards.",
"From 2019 to 2020 I worked on site in the Philippines, first as a project-in-charge engineer on a community hall renovation and then as a field engineer on residential subdivision finishing works. I reviewed structural and architectural drawings, carried out site inspections, safety checks and quality monitoring, prepared site and progress reports, and kept clients and stakeholders up to date.",
"Your advert asks for site inspection experience in the Australian construction industry; my inspection work so far was in the Philippines, and I would learn local residential practice from your team. I hold a White Card and a driver's licence with my own transport, have full working rights to December 2027 on a Subclass 485 visa, and am open to discussing relocation to Canberra or Goulburn.",
"My resume is attached, and I would welcome a conversation about the role."],"closing":"Kind regards,"}
d2={"seek_id":None,"company":"Residential Engineering","role":"Structural Site Engineer","location":"Canberra ACT or Goulburn NSW (field based)",
"job_url":"https://au.linkedin.com/jobs/view/4487422784","company_url":"https://residentialengineering.com.au/","route":"EMPLOYER_PORTAL","application_type":"ADVERTISED_VACANCY","vacancy_status":"OPEN_LINKEDIN_AND_SEEK",
"recipient_name":"","recipient_role":"","recipient_email":"","contact_evidence_url":"https://au.linkedin.com/jobs/view/4487422784",
"subject":"Structural Site Engineer, Canberra or Goulburn (LinkedIn 4487422784)","email_body":"","letter":L2,
"checklist":["Search Gmail in:anywhere for Residential Engineering, reseng.com.au and Five Group before applying (Gmail was not reachable on this tick)","Confirm Marc is willing to relocate to Canberra or Goulburn for a field based role with extensive regional travel","Open LinkedIn job 4487422784 (also listed on SEEK as Structural Site Engineer, Residential Engineering, Canberra ACT) and apply with the cover letter and resume from this folder","Answer work rights as Subclass 485, full working rights to December 2027; licence yes; asbestos and silica awareness training: none on record (Marc to confirm)","Record the apply date in /workspace/job-finds"],
"screening_answers":[{"q":"Right to work in Australia","a":"Temporary graduate visa (Subclass 485) with full working rights until December 2027"},{"q":"Current driver's licence?","a":"Yes, Australian driver's licence and own transport"},{"q":"Tertiary qualification in Civil or Structural Engineering?","a":"Yes, Bachelor of Science in Civil Engineering (Philippines, 2019); Advanced Diploma of Civil Construction Design (Australia, Feb 2026)"},{"q":"Australian site inspection experience?","a":"No; site inspections and quality checks in the Philippines 2019 to 2020"},{"q":"Salary expectation","a":"Marc to answer"}]}
json.dump(d2,open('drafts/reseng.json','w'),indent=1,ensure_ascii=False)
json.dump(L2,open('drafts/reseng_L.json','w'),indent=1,ensure_ascii=False)
open('drafts/reseng_letter.txt','w').write('\n\n'.join(L2['paragraphs']))
print('reseng letter',sum(len(p.split()) for p in L2['paragraphs']))
