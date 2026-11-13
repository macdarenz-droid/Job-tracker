# SEEK profile text

The text for the owner's SEEK profile, so that the profile says what the three resumes in
`documents/resume/` say. Whoever is signed in to his SEEK account types it in once.

- Every line inside a text block below is copied or joined from `automation/facts.json`. The wanted
  roles and locations come from `automation/config.json` (`lanes`, `seek.where`).
- `automation/tests/test_resume.py` checks the blocks against those two files. Change the facts
  first, then this file, then run the tests.
- SEEK's own screens were not opened to write this file. The section names here are plain
  descriptions, not SEEK's labels. Where SEEK has no such field, leave that text out. Do not move it
  to another field and do not type anything that is not in a text block.

## Headline

```text
Civil Construction Design (Advanced Diploma, February 2026) | AutoCAD, Civil 3D, Revit
```

This is `identity.titles.drafter`, the headline of the drafter resume.

## Personal summary

About 80 words. The first two sentences serve drafter roles, the third technician roles.

```text
Civil design graduate with an Advanced Diploma of Civil Construction Design (RII60520), completed in Australia in February 2026, and a Bachelor of Science in Civil Engineering. Designed and documented road geometry, earthworks, pavement systems and stormwater drainage, and prepared and reviewed technical drawings in AutoCAD and Civil 3D, applying Australian Standards. Site experience in inspections, quality checks, material records and progress reports. White Card and current Victorian driver's licence. Will relocate anywhere in Australia and can start two weeks after an offer.
```

## Career history

Newest first. Each description is points of that role from `facts.json`, word for word, three where
the facts hold three. Nothing may be added to a role until the owner supplies it and it is in
`facts.json`.

```text
Job title: Console Operator (casual)
Company: bp Rockbank Inbound (operated by Rampage Group), Rockbank VIC
Started: May 2024
Ended: present
- Customer service and console operation at a service station, held alongside full-time study in the Advanced Diploma
```

One point: `facts.json` says duties beyond this line are not on record.

```text
Job title: Technical Support Representative, Microsoft Software
Company: Concentrix, Philippines
Started: Mar 2020
Ended: Apr 2022
- Resolved 40 to 60 technical cases a day, troubleshooting step by step and keeping accurate case notes
- Explained technical issues to customers in plain terms and worked with internal teams to fix complex problems
```

Two points: `facts.json` holds two for this role.

```text
Job title: Field Engineer
Company: Grand Travaux, Philippines
Started: Sep 2019
Ended: Feb 2020
- Worked on residential subdivision finishing works, delivered within the three-month construction schedule
- Assisted with site inspections, daily coordination and quality checks to keep work compliant and on time
- Tracked procurement and materials, and prepared site reports, material records and progress reports
```

```text
Job title: Project-in-Charge Engineer (Entry Level)
Company: JustBuilt, Philippines
Started: Apr 2019
Ended: Sep 2019
- Coordinated 10 to 15 workers each day, passed on work priorities and tracked progress to help the site run safely and efficiently
- Reviewed structural and architectural drawings and checked work against project requirements to cut down on errors and rework
- Carried out site inspections, safety checks and quality monitoring, and escalated issues that needed clarification or corrective action
```

## Education

```text
Course: Advanced Diploma of Civil Construction Design (RII60520)
Institution: Albright Institute of Business and Language, Australia
Started: Feb 2024
Finished: February 2026
- Designed and documented road geometry, earthworks, pavement systems and stormwater drainage, and studied infrastructure design principles
- Prepared and reviewed technical drawings in AutoCAD and Civil 3D, applying Australian Standards and construction requirements
- Gained a practical understanding of design coordination, constructability, technical reporting and how civil works move from concept to documentation
- Lodged Before You Dig Australia (formerly DBYD) enquiries, followed its procedures, and designed around existing services and site constraints
```

```text
Course: Bachelor of Science in Civil Engineering (BSCE)
Institution: Divine Word College of Legazpi, Philippines
Started: 2014
Finished: 2019
- Studied civil engineering design, construction methods, structural principles, hydraulics, surveying and project delivery
```

Both are complete. The start of the Advanced Diploma is February 2024; `facts.json` records that
documents saying December 2024 are wrong.

## Licences and certifications

```text
White Card (Construction Induction)
Current Victorian driver's licence
Current National Police Certificate
Working with Children Check
```

- Issuing body, issue date and expiry date are not in `facts.json`. Leave those fields empty, or the
  owner fills them in on SEEK from the cards himself.
- The licence: `facts.json` does not confirm full or probationary, or manual or automatic. Enter
  neither.
- No card number, licence number or certificate number is ever written into this repository.

## Skills

Only these. SEEK offers its own skill names: pick the SEEK name that says the same thing, and add
no skill that has no line here.

```text
AutoCAD 2D/3D
Civil 3D
Revit
Microsoft Office
Google Workspace
Road geometry
Earthworks
Pavement design
Stormwater drainage
Civil documentation
Technical drawings
Cost estimates and bills of quantities
Risk registers
Options analysis
Hand calculations
Before You Dig Australia enquiries
Site inspections
Quality checks
Safety checks
Progress monitoring
Site reports
Material records
Progress reports
Tracking procurement
Coordinating crews
Reviewing drawings
Customer service
```

## Preferred roles and locations

The three lanes of `config.json`, in queue order, anywhere in Australia.

```text
- Civil drafter, draftsperson, civil designer, CAD or Civil 3D technician (junior, trainee and cadet first)
- Construction materials testing, civil or geotechnical laboratory and field technician, civil engineering technician
- Graduate or junior civil, site or project engineer
Locations: All Australia
Notice period: 2 weeks
Salary: $65,000 to $75,000
```

- The salary band is the one `facts.json` gives for adverts that state no pay.
- Work type (full time, contract, casual, part time) is not on record. Leave that setting as it is.

## Right to work

Choose the option that names a graduate temporary work visa (Subclass 485). If there is no such
option, choose the temporary visa option that has no restriction on hours or industry. Never choose
citizen, permanent resident or an option that says sponsorship is required. Free text, if asked:

```text
Subclass 485 Temporary Graduate visa with full working rights until December 2027. No sponsorship needed.
```

## Resumes to store

Store all three files from `documents/resume/`. The default is the drafter resume, because the
drafter lane is first in the queue and the headline and summary above lead with it.

| Lane | File | Use |
| --- | --- | --- |
| drafter | `Marc_Masarate_Resume_Drafter.pdf` | default; every drafter application |
| technician | `Marc_Masarate_Resume_Technician.pdf` | chosen at apply time for a technician advert |
| engineer | `Marc_Masarate_Resume_Engineer.pdf` | chosen at apply time for an engineer advert |

The apply queue entry names the lane; `config.json` -> `lanes.<lane>.resume` names the variant.

## Settings to check once

1. Profile visibility. Read what it is set to and write it in the run report. Neither
   `facts.json` nor `config.json` says which setting the owner wants, so change nothing; if the
   profile is hidden from employers, that is one question for the owner.
2. Default resume. It is `Marc_Masarate_Resume_Drafter.pdf`. A stored resume whose headline is not
   one of `identity.titles`, that shows the visa end date in its top lines, or that gives December
   2024 as the diploma start, is out of date: do not attach it to an application. Removing it from
   the account is the owner's call.
3. Right-to-work details. They match the "Right to work" section above: visa type Subclass 485,
   no sponsorship. The end date goes only where SEEK asks for it.
4. Name, phone, email and location match `facts.json` -> `identity` (location: Melton VIC 3337).
5. `facts.json` records that the driver's licence was verified in SEEK Pass in June 2026. Check the
   profile still shows it.
