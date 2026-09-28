export const meta = {
  name: 'job-search-tick',
  description: 'Screen SEEK candidates and web sweeps for Marc, research hiring contacts, draft and adversarially verify applications',
  phases: [
    { title: 'Sweep', detail: 'employer careers pages and web angles for adverts SEEK does not carry' },
    { title: 'Screen', detail: 'fit score against facts.json, mandatory checks, open advert' },
    { title: 'Contact', detail: 'employer-published hiring contact with evidence' },
    { title: 'Draft', detail: 'email, cover letter, screening answers' },
    { title: 'Verify', detail: 'refute every claim; tone; fix once' },
  ],
}

const RUN = args.run_dir
const REPO = args.repo
const COMMON = `
Repo: ${REPO}. Run folder: ${RUN}. Today is ${args.today} (${args.today_iso}).
Read ${REPO}/automation/facts.json (the ONLY allowed facts about Marc), ${REPO}/automation/config.json (rules), and ${REPO}/AGENTS.md rules apply.
Never invent anything about Marc. Never guess an email address. Do not edit files outside ${RUN} except ${REPO}/automation/employers.json where told.
Return only the structured output; no prose to a human.`

const SCREEN_SCHEMA = {
  type: 'object',
  properties: {
    seek_id: { type: 'string' }, source: { type: 'string' }, company: { type: 'string' }, title: { type: 'string' }, location: { type: 'string' }, url: { type: 'string' },
    percent: { type: 'number' }, rationale: { type: 'string' }, caution: { type: 'string' },
    gaps: { type: 'array', items: { type: 'string' } }, mandatory_unmet: { type: 'array', items: { type: 'string' } },
    route: { type: 'string', enum: ['SEEK', 'EMPLOYER_PORTAL', 'EMPLOYER_FORM', 'EMAIL', 'UNKNOWN'] },
    apply_instructions: { type: 'string' }, apply_email: { type: 'string' }, open: { type: 'boolean' }, employer_is_agency: { type: 'boolean' },
    listed_at: { type: 'string' }, expires_at: { type: 'string' }, screening_questions: { type: 'array', items: { type: 'string' } }, notes: { type: 'string' },
  },
  required: ['seek_id', 'company', 'title', 'percent', 'rationale', 'caution', 'gaps', 'mandatory_unmet', 'route', 'open', 'employer_is_agency'],
}
const SWEEP_SCHEMA = {
  type: 'object',
  properties: {
    found: { type: 'array', items: { type: 'object', properties: {
      id: { type: 'string' }, source: { type: 'string' }, company: { type: 'string' }, title: { type: 'string' }, location: { type: 'string' }, url: { type: 'string' },
      listed_at: { type: 'string' }, content_text: { type: 'string' }, apply_instructions: { type: 'string' }, file: { type: 'string' } },
      required: ['id', 'source', 'company', 'title', 'url', 'content_text', 'file'] } },
    checked: { type: 'array', items: { type: 'string' } }, notes: { type: 'string' },
  },
  required: ['found', 'checked'],
}
const CONTACT_SCHEMA = {
  type: 'object',
  properties: {
    seek_id: { type: 'string' }, company_url: { type: 'string' }, careers_url: { type: 'string' },
    recipient_name: { type: 'string' }, recipient_role: { type: 'string' }, recipient_email: { type: 'string' },
    contact_evidence_url: { type: 'string' }, evidence_quote: { type: 'string' },
    contact_confidence: { type: 'string', enum: ['published_direct', 'published_inbox', 'none'] },
    named_people: { type: 'array', items: { type: 'object', properties: { name: { type: 'string' }, role: { type: 'string' }, email: { type: 'string' }, evidence_url: { type: 'string' } }, required: ['name', 'role', 'evidence_url'] } },
    employer_line: { type: 'string' }, notes: { type: 'string' },
  },
  required: ['seek_id', 'contact_confidence', 'named_people', 'employer_line'],
}
const DRAFT_SCHEMA = {
  type: 'object',
  properties: { seek_id: { type: 'string' }, draft_file: { type: 'string' }, subject: { type: 'string' }, email_words: { type: 'number' }, letter_words: { type: 'number' }, checks_output: { type: 'string' }, notes: { type: 'string' } },
  required: ['seek_id', 'draft_file', 'subject', 'email_words', 'letter_words', 'checks_output'],
}
const VERIFY_SCHEMA = {
  type: 'object',
  properties: { seek_id: { type: 'string' }, pass: { type: 'boolean' }, false_claims: { type: 'array', items: { type: 'string' } }, weak_lines: { type: 'array', items: { type: 'string' } }, tone_issues: { type: 'array', items: { type: 'string' } }, human_tone: { type: 'number' }, specific_to_advert: { type: 'boolean' }, notes: { type: 'string' } },
  required: ['seek_id', 'pass', 'false_claims', 'weak_lines', 'tone_issues', 'human_tone', 'specific_to_advert'],
}

function screenPrompt(id, extraFile) {
  const where = extraFile ? `Read the candidate JSON at ${extraFile}.` : `Read ${RUN}/candidates.json and find the candidate whose seek_id is "${id}" (fields: title, company, location, content_text, listed_at, expires_at, is_expired, is_link_out, work_type, salary, screening_questions, bullets).`
  return `${COMMON}
Task: screen one job advert for Marc. ${where}
Score with config.json → fit.rubric against facts.json ONLY (start 50; role level up to +25; discipline overlap up to +15; location up to +10; -40 for a mandatory requirement Marc cannot meet such as citizenship/PR only, a licence he lacks, a degree or trade he lacks, or a hard "N+ years commercial experience" requirement; -15 for "must have Australian experience"; -10 if the advertiser is a recruitment agency with no named employer). Unknown details are gaps, not fails.
Set open=true only if is_expired is false (or the advert says nothing about closing) and expires_at, if present, is after ${args.today_iso}. Set route from the advert: EMAIL if the advert says to email an address (put it in apply_email), EMPLOYER_PORTAL/EMPLOYER_FORM if it says apply on the company site (is_link_out true usually means this), else SEEK. Quote apply_instructions from the advert text. Copy screening_questions, listed_at, expires_at, location, url. employer_is_agency=true for recruiters (WorkPac, Randstad, Chandler Macleod, NES Fircroft, Fetch, Roach, Lindores, Public Sector People, Airswift, Focus Executive, Constructability, Employment Matters, Aptus etc.).
rationale: three short lines. caution: one line ("rough fit, not an interview forecast" plus the main unknown). gaps: honest things to check (visa acceptance, relocation, experience level, licences).`
}

phase('Sweep')
const sweepJobs = [
  { key: 'employers', prompt: `${COMMON}
Task: check these employers' own careers pages for OPEN junior civil roles (graduate, junior, cadet, trainee, drafter, draftsperson, civil designer, site engineer, estimator, project coordinator): ${args.employers.join('; ')}.
Use WebSearch to find each careers page, then WebFetch it. For each open, relevant advert found: WebFetch the advert page, and save its full text and details to ${RUN}/extra/<slug>.json with fields id (a slug like "beveridgewilliams-graduate-civil-engineer"), source ("employer"), company, title, location, url, listed_at (if shown, else ""), expires_at (if shown), content_text (full advert text), apply_instructions, screening_questions [] , is_expired false, is_link_out true. Skip anything that is senior, management, other disciplines, or an expression-of-interest with no open role.
Also update ${REPO}/automation/employers.json: under "employers", add one object per employer you checked keyed by employer name with careers_url (verified), checked_at "${args.today_iso}", open_junior_roles (list of titles or empty), and notes. Read the file first and keep existing entries.
Return found (one per saved file, file = absolute path) and checked (employer names).` },
  { key: 'councils-gov', prompt: `${COMMON}
Task: find OPEN council and state-government adverts in Australia for graduate, cadet, trainee or junior civil engineering, civil design or drafting roles, listed in the last 14 days, that are NOT on SEEK (or that SEEK might miss). Use WebSearch (queries such as "graduate civil engineer" council applynow, "cadet civil engineer" council 2026, "trainee civil designer" council, "engineering officer" council graduate, "civil drafter" council, VicRoads / Major Road Projects Victoria / Level Crossing Removal graduate 2027, TMR graduate program 2027, Transport for NSW graduate program 2027) and WebFetch each promising advert. Verify each is open today (${args.today_iso}) with a closing date in the future or none stated.
Save each verified advert to ${RUN}/extra/<slug>.json with the fields: id (slug), source ("council" or "government"), company, title, location, url, listed_at, expires_at, content_text (full advert text), apply_instructions, screening_questions [], is_expired false, is_link_out true. At most 6. Return found (file = absolute path) and checked (the URLs you looked at).` },
  { key: 'victoria', prompt: `${COMMON}
Task: find OPEN adverts for junior civil roles in Victoria (Melbourne west and north-west first: Melton, Caroline Springs, Sunshine, Werribee, Laverton, Tullamarine, Derrimut; then Ballarat, Geelong, Bendigo, Shepparton) that are NOT on SEEK: company careers pages, EthicalJobs, Engineers Australia jobs, Jora-listed employer sites, LinkedIn public job pages, Workforce Australia. Roles: graduate or junior civil engineer, civil drafter or draftsperson, cadet or trainee, junior site engineer, junior estimator, civil designer, project coordinator (civil). Use WebSearch with several phrasings and WebFetch each promising advert. Verify each is open today (${args.today_iso}).
Save each verified advert to ${RUN}/extra/<slug>.json with the fields: id (slug), source (site name), company, title, location, url, listed_at, expires_at, content_text (full advert text), apply_instructions, screening_questions [], is_expired false, is_link_out true. At most 6. Return found (file = absolute path) and checked (URLs looked at).` },
]

const CONTACT_PROMPT = (c) => `${COMMON}
Task: find the hiring person for this advert, following config.json → contact exactly.
Advert: ${c.title} at ${c.company} (${c.location}); url ${c.url}; route ${c.route}; apply_email from the advert: "${c.apply_email || ''}". Candidate JSON: ${c.file || RUN + '/candidates.json (seek_id ' + c.seek_id + ')'}.
Steps: (1) find the employer's real website (WebSearch the company name; for an agency advert, identify the end employer only if the advert names it, otherwise return contact_confidence "none"). (2) WebFetch the site's home, about, team/people/our-team/leadership, contact, projects, news/careers pages; open capability statements or PDFs if linked. (3) WebSearch: "<employer>" engineering manager OR director OR "civil engineer" email; "<employer>" "@<domain>"; site:<domain> contact. (4) Employer-authored public documents (tenders, council minutes, press releases) that print a name, role and business address.
A direct contact is a NAMED person in an engineering, drafting, design, operations, project or owner/director role at the employer whose BUSINESS email is published by the employer itself. Record recipient_name, recipient_role, recipient_email, contact_evidence_url (the exact page), evidence_quote (the text on that page showing the name, role and address), contact_confidence "published_direct". If only a careers/HR/application inbox is published and it explicitly accepts applications (or the advert itself gives it in apply_email): "published_inbox" with the evidence. Otherwise "none". NEVER guess or pattern-build an address, never use gmail/hotmail/outlook addresses, never use email-finder or data-broker sites (RocketReach, Hunter, Lusha, ZoomInfo, ContactOut, SignalHire, Apollo etc.), never use recruiters or unrelated project parties. A generic info@/admin@ inbox counts only if the site says it accepts job applications.
Also list named_people (name, role, email if published, evidence_url) so the cover letter can be addressed properly even when the email goes to an inbox, and employer_line: one specific, true line about the employer or the role drawn from their site or the advert (a project, a service line, a location), for the letter. company_url, careers_url. Save your findings to ${RUN}/contacts/${c.seek_id}.json as well.`

const DRAFT_PROMPT = (c) => `${COMMON}
Task: write Marc's application pack for this advert and save it as ${RUN}/drafts/${c.seek_id}.json. Inputs: the advert (${c.file || RUN + '/candidates.json, seek_id ' + c.seek_id}), the screening result at ${RUN}/screen/${c.seek_id}.json, the contact research at ${RUN}/contacts/${c.seek_id}.json, facts.json, config.json → tone (banned phrases, no em or en dashes anywhere, email under 220 words, letter under 340 words) and the Portfolio's voice (short sentences, Australian English, first person, no hype, no exclamation marks).
Email rules: greet the named contact by first name if one exists ("Hi Sam,"), otherwise "Hello," or "Hi <team name>,". Line 1 says which advert and where you saw it (SEEK, or their site) and, when writing to a named person, that you wanted to reach them directly rather than only through the portal. Then one short paragraph with the three scan facts: Advanced Diploma of Civil Construction Design finished February 2026 (road geometry, earthworks, pavement and stormwater design and documentation in Civil 3D and AutoCAD, Australian Standards); site experience in the Philippines in 2019 to 2020 as a field engineer and project-in-charge (inspections, drawings, records, coordinating crews); Melton based, White Card, driver's licence and own transport, full working rights to December 2027 on a Subclass 485 visa, available for site, regional and FIFO work. Include ONE specific line that shows you read the advert or their site (the employer_line or a requirement from the advert) and say plainly how Marc meets it or what he would bring; if the advert asks for something Marc does not have (for example 2 years experience), say the honest position in one clause rather than hiding it. End with a clear ask (a short call, or that the application is attached and lodged) and "I've attached my resume and cover letter." Sign off "Thanks," or "Kind regards," then "Marc Darenz Masarate", phone, and the portfolio address macdarenz-droid.github.io/Portfolio on its own line. Never write "tailored", never list software he only studied as commercial experience, never mention migration or residency goals.
Subject: "<Role title> application, Marc Masarate" (or "<Role title>, Marc Masarate").
Cover letter JSON "letter": {recipient_name, recipient_role, company, company_line (city or office if known), subject, greeting, paragraphs (4 or 5 short paragraphs, under 340 words total: why this role and this employer; the diploma and what he designed and documented; the site experience and what he did; eligibility and availability and the honest limit if any; a closing ask), closing}. Same facts, no dashes, no banned phrases, no bullet points.
If route is SEEK/EMPLOYER_PORTAL/EMPLOYER_FORM also write "screening_answers": for each question in screening_questions a truthful short answer from facts.json (work rights: "Subclass 485 visa, full working rights until December 2027"; years as a civil engineer: count only the Philippines site roles, about one year (Apr 2019 to Feb 2020); notice: "available immediately" unless facts say otherwise; salary expectations: "open to the advertised range"), and "checklist": five short steps for Marc or Jeremie (open the listing, attach the two PDFs from the tracker, paste the answers, submit, press Applied on the tracker with date and route).
Output JSON file fields: seek_id, company, role, location, job_url, route, recipient_name, recipient_role, recipient_email, contact_evidence_url, subject, email_body, letter, screening_answers, checklist, application_type ("ADVERTISED_VACANCY"), notes.
After saving, run: cd ${REPO}/automation/scripts && python3 - <<'EOF'
import json,checks,sys
d=json.load(open('${RUN}/drafts/${c.seek_id}.json'))
e=checks.tone_issues(d['email_body'],'email')+checks.fact_issues(d['email_body'])
lt='\\n'.join(d['letter']['paragraphs']); l=checks.tone_issues(lt,'letter')+checks.fact_issues(lt)
print('EMAIL', e); print('LETTER', l)
EOF
Fix every issue printed and re-run until both lists are empty. Report the final checks output, email_words and letter_words.`

const VERIFY_PROMPT = (c, round) => `${COMMON}
Task (round ${round}): you are a sceptical reviewer. Try to REFUTE every sentence of the email and the cover letter at ${RUN}/drafts/${c.seek_id}.json against ${REPO}/automation/facts.json and the advert (${c.file || RUN + '/candidates.json, seek_id ' + c.seek_id}). Any claim about Marc's experience, education, skills, software, dates, amounts, licences, work rights or availability that is not stated in facts.json is a false claim (list the exact sentence). Claims about the employer must match the advert or the contact research file ${RUN}/contacts/${c.seek_id}.json; anything else is a false claim. Then judge tone: would a busy engineering manager read this as a real person writing briefly, or as a template? Score human_tone 1 to 5 (5 = clearly a person). Flag weak_lines (vague, generic, salesy, repetitive, or a dash character). Flag tone_issues for any phrase in config.json → tone.banned_phrases, any em or en dash, more than one exclamation mark, or over 220 email words / 340 letter words. specific_to_advert = true only if at least one line could only have been written for this advert or employer. pass = no false claims AND no tone_issues AND human_tone >= 4 AND specific_to_advert. Default to failing when uncertain.`

const FIX_PROMPT = (c, verdict) => `${COMMON}
Task: fix the application pack at ${RUN}/drafts/${c.seek_id}.json in place. A reviewer found: false_claims ${JSON.stringify(verdict.false_claims)}; weak_lines ${JSON.stringify(verdict.weak_lines)}; tone_issues ${JSON.stringify(verdict.tone_issues)}; human_tone ${verdict.human_tone}; specific_to_advert ${verdict.specific_to_advert}; notes: ${verdict.notes || ''}.
Remove or correct every false claim using facts.json only, rewrite weak lines plainly, remove every banned phrase and every dash, keep the email under 220 words and the letter under 340, keep one line that is specific to this advert or employer, keep the honest limit if there is one. Then run the same checks.py tone/facts snippet as the drafter (cd ${REPO}/automation/scripts; python3 with checks.tone_issues and checks.fact_issues on the email and the letter paragraphs) until both lists are empty. Report the final checks output.`

// Sweep agents run alongside screening; they produce extra candidates that go through the same pipeline.
const sweepPromise = parallel(sweepJobs.map(j => () => agent(j.prompt, { label: `sweep:${j.key}`, phase: 'Sweep', schema: SWEEP_SCHEMA })))

phase('Screen')
const seekScreens = await parallel(args.candidate_ids.map(id => () =>
  agent(screenPrompt(id) + `\nAlso save your result as ${RUN}/screen/${id}.json (same fields).`, { label: `screen:${id}`, phase: 'Screen', schema: SCREEN_SCHEMA, effort: 'low' })
    .then(r => r && ({ ...r, seek_id: id, file: null }))))

const sweeps = (await sweepPromise).filter(Boolean)
const extras = sweeps.flatMap(s => s.found || [])
log(`sweeps found ${extras.length} extra adverts (${sweeps.map(s => (s.found || []).length).join('/')})`)
// Dedupe the extras against the live tracker before spending on them.
let extraScreens = []
if (extras.length) {
  const dedupe = await agent(`${COMMON}
Task: for each of these advert files, run the tracker duplicate check and report which are NEW. Files: ${JSON.stringify(extras.map(e => e.file))}.
Steps: cd ${REPO}/automation/scripts; build a JSON list where each item has company, title, url, seek_id (empty) from the files; write it to ${RUN}/extra/_check.json; run python3 tracker.py check ${RUN}/extra/_check.json --out ${RUN}/extra/_checked.json; read the output. Return the list of files whose verdict is new (not blocked) and, for the blocked ones, the reason.`,
    { label: 'dedupe:extras', phase: 'Screen', effort: 'low', schema: { type: 'object', properties: { new_files: { type: 'array', items: { type: 'string' } }, blocked: { type: 'array', items: { type: 'string' } } }, required: ['new_files', 'blocked'] } })
  const newExtras = extras.filter(e => dedupe && dedupe.new_files.includes(e.file))
  log(`extras after dedupe: ${newExtras.length}`)
  extraScreens = await parallel(newExtras.map(e => () =>
    agent(screenPrompt(e.id, e.file) + `\nAlso save your result as ${RUN}/screen/${e.id}.json (same fields, seek_id = "${e.id}", source = "${e.source}", url = "${e.url}").`, { label: `screen:${e.id}`, phase: 'Screen', schema: SCREEN_SCHEMA, effort: 'low' })
      .then(r => r && ({ ...r, seek_id: e.id, file: e.file, url: e.url, source: e.source }))))
}

const screened = [...seekScreens, ...extraScreens].filter(Boolean)
const eligible = screened.filter(s => s.percent >= 60 && s.open && (!s.mandatory_unmet || s.mandatory_unmet.length === 0))
const held = screened.filter(s => s.percent >= 60 && (!s.open || (s.mandatory_unmet && s.mandatory_unmet.length)))
eligible.sort((a, b) => (b.percent - a.percent) || String(b.listed_at || '').localeCompare(String(a.listed_at || '')))
// Prefer direct employers over agencies at equal fit; agencies rarely have a hiring contact.
const ranked = [...eligible.filter(s => !s.employer_is_agency), ...eligible.filter(s => s.employer_is_agency)]
const top = ranked.slice(0, args.top_n)
log(`screened ${screened.length} · eligible ${eligible.length} · held ${held.length} · taking ${top.length}: ${top.map(t => `${t.company} (${t.percent})`).join(', ')}`)

const packs = await pipeline(
  top,
  c => agent(CONTACT_PROMPT(c), { label: `contact:${c.seek_id}`, phase: 'Contact', schema: CONTACT_SCHEMA }).then(r => ({ ...c, contact: r })),
  c => agent(DRAFT_PROMPT(c), { label: `draft:${c.seek_id}`, phase: 'Draft', schema: DRAFT_SCHEMA }).then(r => ({ ...c, draft: r })),
  async c => {
    let verdict = await agent(VERIFY_PROMPT(c, 1), { label: `verify:${c.seek_id}`, phase: 'Verify', schema: VERIFY_SCHEMA, effort: 'high' })
    let fixed = false
    if (verdict && !verdict.pass) {
      await agent(FIX_PROMPT(c, verdict), { label: `fix:${c.seek_id}`, phase: 'Verify' })
      fixed = true
      verdict = await agent(VERIFY_PROMPT(c, 2), { label: `reverify:${c.seek_id}`, phase: 'Verify', schema: VERIFY_SCHEMA, effort: 'high' })
    }
    return { ...c, verdict, fixed }
  },
)

return {
  run_id: args.run_id,
  sweeps: sweeps.map(s => ({ found: (s.found || []).map(f => f.file), checked: s.checked, notes: s.notes })),
  screened: screened.map(s => ({ seek_id: s.seek_id, company: s.company, title: s.title, percent: s.percent, open: s.open, mandatory_unmet: s.mandatory_unmet, route: s.route, agency: s.employer_is_agency, source: s.source || 'seek' })),
  held: held.map(s => ({ seek_id: s.seek_id, company: s.company, title: s.title, percent: s.percent, open: s.open, mandatory_unmet: s.mandatory_unmet })),
  packs: packs.filter(Boolean).map(p => ({ seek_id: p.seek_id, company: p.company, title: p.title, percent: p.percent, route: p.route, contact: p.contact, draft_file: p.draft && p.draft.draft_file, verdict: p.verdict, fixed: p.fixed })),
}