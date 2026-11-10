import json
sig="Kind regards,\nMarc Darenz Masarate\n0478 764 077\nmacdarenz@gmail.com\nhttps://macdarenz-droid.github.io/Portfolio"
SITE="From 2019 to 2020 I worked on site in the Philippines. As project-in-charge on a community hall renovation I coordinated 10 to 15 workers each day, reviewed structural and architectural drawings against project requirements and kept the client up to date. As a field engineer on residential subdivision finishing works I assisted with site inspections and quality checks, tracked procurement and materials, and prepared site, material and progress reports."
DIP="In February 2026 I finished an Advanced Diploma of Civil Construction Design at Albright Institute in Australia, where I prepared and reviewed technical drawings in AutoCAD and Civil 3D and prepared cost estimates and bills of quantities. I also hold a Bachelor of Science in Civil Engineering from the Philippines (2019)."
ELIG="I hold an Australian driver's licence with my own transport and a White Card, and I have full working rights to December 2027 on a Subclass 485 visa. I live in Melton VIC."
car={"seek_id":None,"company":"Carelli Constructions Pty Ltd","role":"Graduate/Undergraduate – Project Management","location":"Notting Hill, Melbourne VIC",
"job_url":"https://employmenthero.com/jobs/position/carelli-constructions-pty-ltd-graduateundergraduate-project-management-ccup5/","company_url":"https://www.carelliconstructions.com.au","route":"EMPLOYER_PORTAL","application_type":"ADVERTISED_VACANCY","vacancy_status":"OPEN_EMPLOYER_SITE",
"recipient_name":"","recipient_role":"Hiring team (applications through the Employment Hero job page; no application email published)","recipient_email":"","contact_evidence_url":"https://employmenthero.com/jobs/position/carelli-constructions-pty-ltd-graduateundergraduate-project-management-ccup5/",
"subject":"Graduate/Undergraduate Project Management application, Marc Masarate",
"email_body":"Not for sending. Carelli takes applications through the Apply now button on its Employment Hero job page and publishes no application email.\n\n"+sig,
"letter":{"recipient_name":"","recipient_role":"Hiring Team","company":"Carelli Constructions Pty Ltd","company_line":"Carelli Constructions provides design, construction and project management services for commercial and industrial projects from Notting Hill.",
"subject":"Graduate/Undergraduate, Project Management","greeting":"Dear Carelli Hiring Team,",
"paragraphs":["Please accept my application for the Graduate/Undergraduate Project Management role. Supporting your project managers with drawing registers, revision control, RFIs, procurement and site inspections is the coordination and documentation work I want to build my career in.",
SITE,
DIP+" That study gave me a practical understanding of design coordination, constructability and how works move from concept to documentation.",
ELIG+" My site experience is from the Philippines and my coursework was civil rather than commercial building, so I would learn your systems and contracts quickly and keep accurate records from day one.",
"I have attached my resume and would welcome the chance to talk about the role."],"closing":"Kind regards,"},
"screening_answers":[{"q":"Employment Hero application questions","a":"Not visible before signing in; answer from the resume and cover letter. Work rights: Subclass 485, full working rights to December 2027. Licence: Australian driver's licence and own transport. Salary and start date: Marc to answer."}],
"checklist":["Open the Employment Hero job page and confirm Apply now still works (live on 10 Nov 2026, posted 26 Oct 2026; one aggregator, jobau, shows applications paused)","Sign in to Employment Hero as macdarenz@gmail.com (pause for Marc if an OTP is sent)","Attach the one page resume and the cover letter from this folder","Answer any questions from the resume; salary and start date are Marc's call","Record the apply date in /workspace/job-finds"],"notes":""}
tig={"seek_id":"95756453","company":"Tigerform Pty Ltd","role":"Project Coordinator","location":"Moorabbin, Melbourne VIC",
"job_url":"https://www.seek.com.au/job/95756453","company_url":"","route":"SEEK","application_type":"ADVERTISED_VACANCY","vacancy_status":"OPEN_SEEK",
"recipient_name":"","recipient_role":"Hiring team (SEEK quick apply)","recipient_email":"","contact_evidence_url":"https://www.seek.com.au/job/95756453",
"subject":"Project Coordinator application, Marc Masarate",
"email_body":"Not for sending. Apply through SEEK (advert 95756453).\n\n"+sig,
"letter":{"recipient_name":"","recipient_role":"Hiring Team","company":"Tigerform Pty Ltd","company_line":"Tigerform is a commercial concrete structure company based in Moorabbin.",
"subject":"Project Coordinator, Moorabbin","greeting":"Dear Tigerform Hiring Team,",
"paragraphs":["Please accept my application for the Project Coordinator role advertised on SEEK. Reviewing shop drawings for missing information and clashes, tracking procurement dates, keeping document registers current and following up RFIs is the kind of coordination work I enjoy.",
SITE+" On the renovation I checked work against project requirements and escalated issues early to cut down on errors and rework.",
DIP,
ELIG+" My coordination experience is from the Philippines and I have not yet worked on commercial concrete structures, so I would learn your processes quickly and make sure site works from the latest approved drawings.",
"I have attached my resume and would welcome the chance to talk about the role."],"closing":"Kind regards,"},
"screening_answers":[{"q":"Which of the following statements best describes your right to work in Australia?","a":"Temporary graduate visa (Subclass 485) with full working rights to December 2027"},
{"q":"What's your expected annual base salary?","a":"Marc to answer (earlier SEEK applications used $60k to $75k)"},
{"q":"How many years' experience do you have as a project coordinator?","a":"Less than 1 year (Project-in-Charge Apr to Sep 2019 and Field Engineer Sep 2019 to Feb 2020, Philippines)"},
{"q":"How much notice are you required to give your current employer?","a":"Marc to answer"},
{"q":"How many years' experience do you have as an Estimating Coordinator?","a":"None"}],
"checklist":["Search Gmail in:anywhere for Tigerform and SEEK 95756453 before applying (Gmail was not reachable on this tick)","Apply on SEEK 95756453 with the one page resume and the cover letter from this folder","Answer the five SEEK questions as listed; salary and notice are Marc's call","Confirm the advert is still open (expires 10 Dec 2026)","Record the apply date in /workspace/job-finds"],"notes":""}
for n,d in [('carelli',car),('tigerform',tig)]:
    json.dump(d,open(f'drafts/{n}.json','w'),indent=1,ensure_ascii=False)
    open(f'drafts/{n}_email.txt','w').write(d['email_body'])
    open(f'drafts/{n}_letter.txt','w').write('\n\n'.join(d['letter']['paragraphs']))
    print(n,sum(len(p.split()) for p in d['letter']['paragraphs']))
