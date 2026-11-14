import json
email="""Dear Matt,

I'm writing to ask whether Halex Group has room for a junior civil draftsperson. I saw your earlier advert for a Civil Engineering Draftsperson in Cheltenham, and I understand it has now closed, so I wanted to reach you directly in case drafting support is still needed on your residential projects.

In February 2026 I finished an Advanced Diploma of Civil Construction Design in Australia, where I designed and documented road geometry, earthworks, pavement and stormwater drainage in Civil 3D and AutoCAD. I also hold a Bachelor of Science in Civil Engineering (Philippines, 2019). From 2019 to 2020 I worked on site in the Philippines as a project-in-charge engineer and then a field engineer, reviewing structural and architectural drawings and carrying out inspections and quality checks. I live in Melton, hold a White Card and a driver's licence with my own transport, and have full working rights to December 2027 on a Subclass 485 visa.

My drafting so far is from coursework rather than commercial production, so I would be learning your residential standards from your team. Would you be open to a short chat? I've attached my resume and cover letter.

Kind regards,
Marc Darenz Masarate
0478 764 077
macdarenz@gmail.com
https://macdarenz-droid.github.io/Portfolio
"""
letter={"recipient_name":"Matt Haymes","recipient_role":"Co-founder","company":"Halex Group Pty Ltd","company_line":"Halex Group, founded in 2018 by Matt and Jesse, designs, manages and builds high-end residential projects across metro Melbourne from Cheltenham.",
"subject":"Expression of interest: junior civil draftsperson","greeting":"Dear Matt,",
"paragraphs":["I am writing to ask whether Halex Group has room for a junior civil draftsperson. Your earlier Civil Engineering Draftsperson advert, which has now closed, described site plans, civil drawings and documentation for residential building and site works, and that is the kind of work I want to build my career on.",
"In February 2026 I finished an Advanced Diploma of Civil Construction Design in Australia. I designed and documented road geometry, earthworks, pavement and stormwater drainage, and prepared and reviewed technical drawings in AutoCAD and Civil 3D, applying Australian Standards. I also hold a Bachelor of Science in Civil Engineering (Philippines, 2019) and have modelled in Revit.",
"From 2019 to 2020 I worked on site in the Philippines, first as a project-in-charge engineer on a community hall renovation and then as a field engineer on residential subdivision finishing works. I reviewed structural and architectural drawings, carried out site inspections and quality checks, prepared site and progress reports, and coordinated with subcontractors and suppliers.",
"My drafting so far is from coursework rather than commercial production, and I would learn your residential standards from your team. I live in Melton, hold a White Card and a driver's licence with my own transport, and have full working rights to December 2027 on a Subclass 485 visa.",
"My resume is attached, and I would welcome a short conversation about any drafting or site support role."],"closing":"Kind regards,"}
d={"seek_id":None,"company":"Halex Group Pty Ltd","role":"Speculative enquiry: junior civil draftsperson","location":"Cheltenham, Melbourne VIC",
"job_url":"https://halexgroup.com.au/contact-us/","company_url":"https://halexgroup.com.au/","route":"EMAIL","application_type":"SPECULATIVE_ENQUIRY","vacancy_status":"NO_OPEN_ADVERT_PRIOR_ROLE_EXPIRED",
"recipient_name":"Matt Haymes","recipient_role":"Co-founder","recipient_email":"matt@halexgroup.com.au","contact_evidence_url":"https://halexgroup.com.au/contact-us/",
"subject":"Expression of interest: junior civil draftsperson, Marc Masarate","email_body":email,"letter":letter,
"checklist":["Search Gmail in:anywhere for Halex Group and halexgroup.com.au before sending (Gmail was not reachable on this tick)","Confirm Marc is happy to commute from Melton to Cheltenham (south east Melbourne) for a residential drafting role","Send the email in this folder from macdarenz@gmail.com to matt@halexgroup.com.au with the cover letter and one page resume attached","Optionally call Matt Haymes on 0425 005 549 (number on the Halex contact page) to ask whether a drafting role is still needed","Record the send date in /workspace/job-finds"],
"screening_answers":[]}
json.dump(d,open('drafts/halex.json','w'),indent=1,ensure_ascii=False)
json.dump(letter,open('drafts/halex_L.json','w'),indent=1,ensure_ascii=False)
open('drafts/halex_letter.txt','w').write('\n\n'.join(letter['paragraphs']))
open('drafts/halex_email.txt','w').write(email)
print('letter',sum(len(p.split()) for p in letter['paragraphs']),'email',len(email.split()))
