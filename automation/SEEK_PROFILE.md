# SEEK profile text

The text for the owner's SEEK profile, so that the profile says what the three resumes in
`documents/resume/` say. Whoever is signed in to his SEEK account types it in once, and again
whenever a text block below changes.

- The text blocks are built by `scripts/resume.py` from `automation/facts.json`; the wanted roles
  and locations come from `automation/config.json` (`lanes`, `seek.where`). Do not edit a block by
  hand: change the facts, then run `python3 scripts/resume.py build` in `automation/`, which
  rewrites every block here together with the resumes.
- `automation/tests/test_resume.py` fails while a block differs from what the facts give.
- The words outside the blocks only say where a line goes. They state nothing about him; where a
  setting depends on a fact, they name the place in `facts.json` to read.
- SEEK's own screens were not opened to write this file. The section names here are plain
  descriptions, not SEEK's labels. Where SEEK has no such field, leave that text out. Do not move it
  to another field and do not type anything that is not in a text block.

## Headline

The headline of the drafter resume (`identity.titles.drafter`).

```text
Civil Construction Design (Advanced Diploma, February 2026) | AutoCAD, Civil 3D, Revit
```

## Personal summary

About eighty words. The first two sentences serve drafter roles, the third technician roles.

```text
Civil design graduate with an Advanced Diploma of Civil Construction Design (RII60520), completed in Australia in February 2026, and a Bachelor of Science in Civil Engineering. Designed and documented road geometry, earthworks, pavement systems and stormwater drainage, and prepared and reviewed technical drawings in AutoCAD and Civil 3D, applying Australian Standards. Site experience in inspections, quality checks, material records and progress reports. White Card and full Victorian driver's licence. Will relocate anywhere in Australia and can start two weeks after an offer.
```

## Career history

One entry for each role in `experience`, newest first, entries separated by an empty line. The
points are that role's points word for word (project values left out), three at most. Add nothing
to a role: a duty that is not in `facts.json` is not typed into SEEK.

```text
Job title: Console Operator (casual)
Company: bp Rockbank Inbound (operated by Rampage Group), Rockbank VIC
Started: May 2024
Ended: present
- Customer service and console operation at a service station, held alongside full-time study in the Advanced Diploma

Job title: Technical Support Representative, Microsoft Software
Company: Concentrix, Philippines
Started: Mar 2020
Ended: Apr 2022
- Resolved 40 to 60 technical cases a day, troubleshooting step by step and keeping accurate case notes
- Explained technical issues to customers in plain terms and worked with internal teams to fix complex problems

Job title: Field Engineer
Company: Grand Travaux, Philippines
Started: Sep 2019
Ended: Feb 2020
- Worked on residential subdivision finishing works, delivered within the three-month construction schedule
- Assisted with site inspections, daily coordination and quality checks to keep work compliant and on time
- Tracked procurement and materials, and prepared site reports, material records and progress reports

Job title: Project-in-Charge Engineer (Entry Level)
Company: JustBuilt, Philippines
Started: Apr 2019
Ended: Sep 2019
- Coordinated 10 to 15 workers each day, passed on work priorities and tracked progress to help the site run safely and efficiently
- Reviewed structural and architectural drawings and checked work against project requirements to cut down on errors and rework
- Carried out site inspections, safety checks and quality monitoring, and escalated issues that needed clarification or corrective action
```

## Education

One entry for each course in `education`, with the dates `facts.json` gives.

```text
Course: Advanced Diploma of Civil Construction Design (RII60520)
Institution: Albright Institute of Business and Language, Australia
Started: Feb 2024
Finished: February 2026
- Designed and documented road geometry, earthworks, pavement systems and stormwater drainage, and studied infrastructure design principles
- Prepared and reviewed technical drawings in AutoCAD and Civil 3D, applying Australian Standards and construction requirements
- Gained a practical understanding of design coordination, constructability, technical reporting and how civil works move from concept to documentation
- Lodged Before You Dig Australia (formerly DBYD) enquiries, followed its procedures, and designed around existing services and site constraints

Course: Bachelor of Science in Civil Engineering (BSCE)
Institution: Divine Word College of Legazpi, Philippines
Started: 2014
Finished: 2019
- Studied civil engineering design, construction methods, structural principles, hydraulics, surveying and project delivery
```

## Licences and certifications

One line for each of `eligibility.white_card`, `drivers_licence`, `police_check` and `wwcc`.

```text
White Card (Construction Induction)
Full Victorian driver's licence
AFP National Police Check certificate issued in March 2026
Working with Children Check
```

- Issuing body, issue date, expiry date, licence class and transmission: fill such a field only
  with a value that `facts.json` -> `eligibility` or `answers` holds, and leave it empty otherwise.
- No card number, licence number or certificate number is ever written into this repository.

## Skills

Only these: the software in `capabilities.software`, then phrases taken from `capabilities` and
from the points under his jobs and courses. SEEK offers its own skill names: pick the SEEK name
that says the same thing, and add no skill that has no line here.

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

The three lanes of `config.json`, in queue order, then where he will work, his notice period and
the salary band `answers.expected_salary` gives for adverts that state no pay.

```text
- Civil drafter, draftsperson, civil designer, CAD or Civil 3D technician
- Construction materials testing, civil or geotechnical laboratory and field technician, civil engineering technician
- Graduate or junior civil, site or project engineer
Locations: All Australia
Notice period: 2 weeks
Salary: $65,000 to $75,000
```

- Work type (full time, contract, casual, part time): change it only to what `facts.json` names;
  while `facts.json` names none, leave the setting as it is.

## Right to work

Which option to choose, and which options never to choose, is written in `facts.json` ->
`answers.right_to_work` (`choose`, `never_choose`, `if_unsure`). Free text, if asked:

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

1. Profile visibility. Read what it is set to and write it in the run report. Change it only to a
   setting that `facts.json` or `config.json` names; while neither names one, change nothing, and if
   the profile is hidden from employers, that is one question for the owner.
2. Default resume. It is `Marc_Masarate_Resume_Drafter.pdf`. A stored resume whose headline is not
   one of `identity.titles`, that shows the visa end date in its top lines, or whose course dates
   differ from `facts.json` -> `education`, is out of date: do not attach it to an application.
   Removing it from the account is the owner's call.
3. Right-to-work details. They match the "Right to work" section above. The visa end date goes only
   where SEEK asks for it.
4. Name, phone, email and location match `facts.json` -> `identity`.
