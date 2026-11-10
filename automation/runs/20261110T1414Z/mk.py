import json
sig="Kind regards,\nMarc Darenz Masarate\n0478 764 077\nmacdarenz@gmail.com\nhttps://macdarenz-droid.github.io/Portfolio"
SITE="From 2019 to 2020 I worked on site in the Philippines. As a field engineer on residential subdivision finishing works I assisted with site inspections and quality checks, tracked procurement and materials, and prepared site, material and progress reports. Before that, as project-in-charge on a community hall renovation, I coordinated 10 to 15 workers each day and reviewed structural and architectural drawings against project requirements."
DIP="In February 2026 I finished an Advanced Diploma of Civil Construction Design at Albright Institute in Australia, covering earthworks, road geometry, pavement design and stormwater drainage, with drawings prepared in AutoCAD and Civil 3D and cost estimates and bills of quantities. I also hold a Bachelor of Science in Civil Engineering from the Philippines (2019)."
ELIG="I hold an Australian driver's licence with my own transport and a White Card, and I have full working rights to December 2027 on a Subclass 485 visa."
jay={"seek_id":"95514711","company":"Jaydo Construction Pty Ltd","role":"Site Engineer - Urban Development - EOI 2027","location":"Keilor Park, Melbourne VIC",
"job_url":"https://www.seek.com.au/job/95514711","company_url":"https://jaydo.com.au","route":"SEEK","application_type":"ADVERTISED_VACANCY","vacancy_status":"OPEN_SEEK",
"recipient_name":"","recipient_role":"Hiring team (SEEK quick apply; Jaydo's careers page points applicants to SEEK)","recipient_email":"","contact_evidence_url":"https://jaydo.com.au/careers/",
"subject":"Site Engineer, Urban Development application, Marc Masarate",
"email_body":"Not for sending. Apply through SEEK (advert 95514711); Jaydo's careers page sends applicants to its SEEK adverts.\n\n"+sig,
"letter":{"recipient_name":"","recipient_role":"Hiring Team","company":"Jaydo Construction Pty Ltd","company_line":"Jaydo is a Victorian civil contractor delivering water, sewerage, drainage and related infrastructure, and its Urban Development team builds civil works for subdivisions and council projects.",
"subject":"Site Engineer, Urban Development (EOI 2027)","greeting":"Dear Jaydo Hiring Team,",
"paragraphs":["Please accept my application for the Site Engineer role in your Urban Development team, advertised on SEEK. Working between the site and the project team, reviewing drawings, planning materials and subcontractors, and keeping ITPs and quality records up to date is the work I want to build my career in.",
SITE,
DIP,
ELIG+" I live in Melton, so Keilor Park is within easy reach. My site experience is from the Philippines and I have not yet worked on sewer or water projects, so I would learn your methods quickly and follow the work through carefully.",
"I have attached my resume and would welcome the chance to talk about the role."],"closing":"Kind regards,"},
"screening_answers":[{"q":"Which of the following statements best describes your right to work in Australia?","a":"Temporary graduate visa (Subclass 485) with full working rights to December 2027"},
{"q":"Do you hold a Construction Induction Safety certificate (White Card)?","a":"Yes"},
{"q":"Do you have a current Australian driver's licence?","a":"Yes"}],
"checklist":["Search Gmail in:anywhere for Jaydo and SEEK 95514711 before applying (Gmail was not reachable on this tick)","Apply on SEEK 95514711 with the one page resume and the cover letter from this folder","Answer the three SEEK questions as listed","Confirm the advert is still open (SEEK expiry 26 Nov 2026)","Record the apply date in /workspace/job-finds"],"notes":""}
fy={"seek_id":None,"company":"Fyfe","role":"Graduate Civil Engineer (Property & Infrastructure)","location":"Adelaide SA",
"job_url":"https://www.careers-page.com/fyfe-2/job/93V47WVY","company_url":"https://fyfe.com.au","route":"EMPLOYER_PORTAL","application_type":"ADVERTISED_VACANCY","vacancy_status":"OPEN_EMPLOYER_SITE",
"recipient_name":"","recipient_role":"Fyfe careers team (enquiries to careers@fyfe.com.au as published on the advert)","recipient_email":"","contact_evidence_url":"https://www.careers-page.com/fyfe-2/job/93V47WVY",
"subject":"Graduate Civil Engineer application, Marc Masarate",
"email_body":"Not for sending. Apply on Fyfe's careers page once work rights eligibility is confirmed.\n\n"+sig,
"letter":{"recipient_name":"","recipient_role":"Hiring Team","company":"Fyfe","company_line":"Fyfe is an Australian multidisciplinary consultancy in engineering, environment, planning and surveying.",
"subject":"Graduate Civil Engineer, Property and Infrastructure","greeting":"Dear Fyfe Hiring Team,",
"paragraphs":["Please accept my application for the Graduate Civil Engineer role in your Adelaide Property and Infrastructure team. Supporting civil designs, drawings and quantity estimates for stormwater drainage, roads and crossings, alongside supervised site inspections, matches the design and documentation work I trained for.",
DIP,
SITE,
ELIG+" I live in Melton VIC and am open to discussing relocation to Adelaide for the right role. My software experience is from study rather than commercial production, so I would build on it quickly under your engineers' guidance.",
"I have attached my resume and would welcome the chance to talk about the role."],"closing":"Kind regards,"},
"screening_answers":[{"q":"Fyfe careers page questions","a":"Not visible before applying; answer from the resume and cover letter. Work rights: Subclass 485, full working rights to December 2027 (not PR or citizen). Salary and start date: Marc to answer."}],
"checklist":["First confirm eligibility: the advert lists Australian citizenship or permanent residency, but its last line also accepts full Australian working rights; Marc to decide whether to ask careers@fyfe.com.au if a Subclass 485 holder is considered","Search Gmail in:anywhere for Fyfe before applying (Gmail was not reachable on this tick)","Confirm Marc is willing to relocate to Adelaide","Apply on the Fyfe careers page with the one page resume and the cover letter from this folder","Record the apply date in /workspace/job-finds"],"notes":""}
for n,d in [('jaydo',jay),('fyfe',fy)]:
    json.dump(d,open(f'drafts/{n}.json','w'),indent=1,ensure_ascii=False)
    open(f'drafts/{n}_email.txt','w').write(d['email_body'])
    open(f'drafts/{n}_letter.txt','w').write('\n\n'.join(d['letter']['paragraphs']))
    print(n,sum(len(p.split()) for p in d['letter']['paragraphs']))
