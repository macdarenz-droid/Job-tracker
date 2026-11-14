#!/usr/bin/env python3
"""The one answer gate for application form questions. queue.py (add, answer, next) and checks.py (questions, draft,
record, and publish.py through them) all call answer(); no other code decides an answer.

answer(question, options, facts, pay=None, today=None) -> {'answer', 'basis', 'status', 'why'}

The gate is strict. A question is 'answered' only when a line of facts.json -> answers clearly covers it (or, for the
free-text questions marked below, a line of identity, eligibility or education does). Every other question is
'unanswered', and why says what is missing: the owner answers it once and the line goes into facts.json. Nothing is
guessed and no option is chosen because it is the nearest one. With the form's options the answer is one of them, word
for word (several joined by '; ' for a tick list); otherwise the question is 'unanswered'. With no options the answer
is the text to type, or for a choice question a short description of the choice; the submitter then runs
`queue.py answer ID --question ... --option ...` with the options on screen.

Covered (facts.json -> answers unless another block is named):
  right to work      the option naming the temporary graduate visa or Subclass 485, else the one temporary visa option
                     with no restriction on hours or industry; never citizen, permanent resident, New Zealand or an
                     option saying sponsorship is required. No options: right_to_work.free_text
  sponsorship        "Do you require sponsorship to work in Australia (now)?": No. In the future: unanswered
  notice             2 weeks, or the option meaning 2 weeks
  start date         free text only: "Two weeks after an offer" (eligibility.availability)
  salary             with options: the option whose band holds the advertised figure (pay) when one is known, else the
                     option holding the owner's band ($65,000 to $75,000) or its midpoint ($70,000); none: unanswered.
                     No options: "65000 to 75000" (or the advertised figure). Hourly rate, minimum, package: unanswered
  driver's licence   Yes; full: Yes; manual: No; manual or automatic: Automatic; another state's licence: unanswered
  car, White Card    Yes
  police check       a check for employment, or issued within the last N months: No; a current check: Yes (the facts
                     line names the month from which that becomes No); willing to obtain one: Yes
  medical, drug and alcohol tests (willing): Yes. Currently studying: No. Relocate: Yes. Travel or FIFO: Yes
  qualifications     as answers.qualification_questions say; "What qualifications do you hold?" (free text): the
                     qualifications in education, with their years
  years              as answers.years_of_experience say: a plain engineering title or the construction industry, the
                     option holding 11 months; other roles, the lowest option
  software           AutoCAD, Civil 3D and Revit only (other known tools: No); Microsoft Office products: unanswered
  experience yes/no  only the activities answers.experience_yes_no names
  declarations       true and correct, privacy policy or collection notice, consent to reference, qualification or
                     police checks: Yes. Any other declaration or consent: unanswered
  referees           free text "Available on request", never a name. Location: free text identity.location
Unanswered: hourly rate, English self-rating, Engineers Australia, future sponsorship (until facts.json gives them a
plain answer), and every question this list does not name. Pure: no files. The clock is read only for the police
check, whose answer changes in a month that facts.json states.
"""
import re
from datetime import datetime, timedelta, timezone

# The lines of facts.json -> answers the gate reads. free_text_cover_letter is not a form answer: the letter is
# pasted from the queue entry itself.
KEYS = {'right_to_work', 'future_visa_sponsorship', 'notice_period', 'expected_salary', 'expected_hourly_rate',
        'drivers_licence', 'manual_licence', 'own_car_or_regular_access', 'white_card', 'police_check',
        'pre_employment_medical', 'drug_and_alcohol_screening', 'currently_studying', 'willing_to_relocate',
        'willing_to_travel_or_fifo', 'engineers_australia_membership_or_recognition', 'qualification_questions',
        'years_of_experience', 'software', 'experience_yes_no', 'english_self_rating', 'declarations_and_consents',
        'referees', 'identity.location', 'eligibility.availability', 'education'}
NOT_FORM_ANSWERS = {'free_text_cover_letter'}

# Software a form may name that is not his (checks.py flags a claim to any of these in written text too).
KNOWN_TOOLS = ['SIDRA', 'OpenRoads', '12d', 'MicroStation', 'HEC-RAS', 'DRAINS', 'TUFLOW', 'Navisworks', 'Bluebeam',
               'Primavera', 'P6', 'MS Project', 'Trimble', 'Leica', 'ArcGIS', 'QGIS', 'InfraWorks', 'Python', 'Procore',
               'Aconex', 'SketchUp', 'Tekla', 'SpaceGass', 'Space Gass', 'ETABS', 'SAP2000', 'RAPT', 'Inventor', 'SolidWorks',
               'MATLAB', 'Power BI', 'Excel modelling', 'Excel modeling', 'GIS', 'BIM 360', 'Civil3D', 'Dynamo', 'Grasshopper']
HIS_TOOLS = {'autocad', 'autocad 2d', 'autocad 3d', 'autocad 2d/3d', 'autocad 2d and 3d', 'civil 3d', 'civil3d',
             'autocad civil 3d', 'revit', 'cad software', 'any cad software'}
OFFICE_PRODUCTS = re.compile(r'\b(excel|word|powerpoint|outlook|access|teams|onenote|products)\b')
UNSETTLED = re.compile(r'not (on record|confirmed)|skip and report|not answered here', re.I)
MONTHS = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december']
NUMBERS = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}

# A question is a yes/no question when its last sentence starts with one of these (after an 'If ..., ' clause).
YES_NO = re.compile(r'^(?:(?:if|when|as|where|should)\b[^,]*,\s*)?(?:are|do|does|did|have|has|had|would|will|can|could|is|was|were)\b')
# Private, unknowable, or a question where a standing 'Yes' would land on the wrong thing: only the owner answers.
TRAPS = re.compile(
    r"visa (grant )?number|passport|date of birth|\bdob\b|legal name|tax file|\btfn\b|\bbank\b|\babn\b|medical condition|injur|disabilit"
    r"|gender|pronoun|aboriginal|torres strait|\breferred\b|security (clearance|licen)|linkedin|defence force|military|adjustments"
    r"|how far|commute|anything else|registration number|licen[cs]e number|\bever\b|suspend|disqualified|cancel|revoked?\b|offen[cs]e"
    r"|convict|demerit|infringement|penalt|dismiss|terminated|bankrupt|conflict of interest|any reason|\bobject\b|\brefus|\bunable\b"
    r"|\bprevent|\bfail|criminal (record|history\b(?! (check|screen)))|illicit|\b(use|take|taking|using) (of )?(any )?drugs|addict")
# Words of each subject the gate answers. A question that names two of them asks two things at once: the owner's.
TOPICS = {
    'work rights': r'rights? to work|work(ing)? rights?|\bwork right|\bvisa\b|citizen|permanent resid|sponsor',
    'licence': r'licen[cs]',
    'White Card': r'white card|construction induction|induction card',
    'police check': r'police|criminal history',
    'car': r'access to (a )?(car|vehicle|transport)|own (a |reliable |your own )?(car|vehicle|transport)|reliable transport'
           r'|\band (have )?(a |own )?car\b|have (a |your own )?car\b',
    'medical tests': r'medical|drug|alcohol',
    'relocation': r'relocat',
    'travel': r'\bfifo\b|\bdido\b|(willing|available|able) to travel|\btravel (for|to|interstate|regionally|as required|when required)|\broster',
    'notice or start': r'\bnotice\b|\bstart\b|commence',
    'salary': r'salary|remuneration|hourly|(pay|day|daily|current|charge) rate|rate expectation',
    'location': r'\bwhere\b[^?]*\b(live|living|based|located|reside|residing)\b|\blocation\b|\bsuburb\b|\breside\b|\bresiding\b',
    'qualification': r'qualification|\bdegree\b|\bdiploma\b|\bbachelor',
    'studying': r'\bstudying\b|currently enrolled',
    'English': r'\benglish\b',
    'referees': r'\breferees?\b',
}


# ---------- small helpers ----------

def norm(text):
    """Lower case, plain quotes, single spaces."""
    t = str(text or '').replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"').replace('–', '-').replace('—', '-')
    return ' '.join(t.lower().split())


def _ok(answer, basis):
    return {'answer': answer, 'basis': basis, 'status': 'answered', 'why': ''}


def _no(why, basis=''):
    return {'answer': '', 'basis': basis, 'status': 'unanswered', 'why': why}


def _last(q):
    """The last sentence of a question ('incl.', 'e.g.' and the like do not end one)."""
    q = re.sub(r'\b(incl|e\.g|eg|i\.e|ie|etc|approx|no|vs|min|max)\.', r'\1', q)
    parts = [p for p in re.split(r'(?<=[.?!])\s+', q) if p.strip()]
    return parts[-1].rstrip(' ?.!:') if parts else ''


def yes_no_question(q):
    return bool(YES_NO.match(_last(q)))


def _settled(value, asked=''):
    """False when a facts line leaves this question to the owner: it says 'not on record', 'not confirmed', 'skip and
    report' or 'not answered here' outright, or in an 'If the form asks X: ...' sentence whose X is in what is asked."""
    if not isinstance(value, str) or not value.strip():
        return False
    for sentence in re.split(r'(?<=\.)\s+', value):
        if not UNSETTLED.search(sentence):
            continue
        cond = re.match(r'if (.+?):', sentence, re.I)
        if not cond:
            return False
        words = [w for w in re.findall(r'[a-z]{4,}', cond.group(1).lower()) if w not in ('form', 'asks', 'must', 'that', 'whether', 'ticked')]
        if any(re.search(r'\b' + w, asked) for w in words):
            return False
    return True


def _head(value):
    """'Yes' or 'No' when a facts line starts with it, else ''."""
    m = re.match(r'\W*(yes|no)\b', str(value or ''), re.I)
    return m.group(1).capitalize() if m else ''


def _choose(head, opts):
    """The one option that says head ('Yes' or 'No'); '' when not exactly one. With no options: head itself."""
    if not opts:
        return head
    hits = [o for o in opts if re.match(head.lower() + r'\b', norm(o))]
    return hits[0] if len(hits) == 1 else ''


def _plain_line(a, key, q, opts):
    """A line of facts.json -> answers given as it stands: the option equal to it, or the line itself."""
    value = a.get(key)
    if not _settled(value, q):
        return _no(f'facts.json -> answers -> {key} has no answer for this' if value else f'facts.json -> answers has no {key}', 'answers.' + key)
    if opts:
        hits = [o for o in opts if norm(o) == norm(value)]
        return _ok(hits[0], 'answers.' + key) if len(hits) == 1 else _no(f'no option is the answer in facts.json -> answers -> {key} ({value})', 'answers.' + key)
    return _ok(value, 'answers.' + key)


def _yes_no_line(a, key, q, opts, free=None):
    """A yes/no line of facts.json -> answers: the matching option, or with no options the line (or free)."""
    value = a.get(key)
    head = _head(value)
    if not head or not _settled(value, q):
        return _no(f'facts.json -> answers -> {key} gives no plain Yes or No', 'answers.' + key)
    if not yes_no_question(q):
        return _no('not a yes/no question, and facts.json gives only a yes or no for it', 'answers.' + key)
    pick = _choose(head, opts)
    if not pick:
        return _no(f'no single option says {head} (facts.json -> answers -> {key})', 'answers.' + key)
    return _ok(pick if opts else (free or head), 'answers.' + key)


def _melbourne_today():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo('Australia/Melbourne')).date()
    except Exception:  # pragma: no cover - no time zone data on this machine
        return (datetime.now(timezone.utc) + timedelta(hours=10)).date()


# ---------- numbers in options ----------

def _number(s):
    s = s.strip()
    return float(NUMBERS[s]) if s in NUMBERS else float(s)


def months_range(option):
    """(low, high) in months for a years-of-experience option, or None when it cannot be read."""
    o = norm(option).replace(' - ', '-')
    n = r'(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten)'
    unit = lambda u: 1 if u.startswith('month') else 12
    if re.fullmatch(r"(no( experience)?|none|nil|0|0 years?|0 months?|not applicable|n/?a)", o):
        return (0, 0)
    m = re.fullmatch(rf'(?:less than|under|below|fewer than|<)\s*{n}\s*(years?|yrs?|months?)', o)
    if m:
        return (0, _number(m.group(1)) * unit(m.group(2)) - 1)
    m = re.fullmatch(rf'(?:more than|over|above|greater than|>)\s*{n}\s*(years?|yrs?|months?)', o)
    if m:
        return (_number(m.group(1)) * unit(m.group(2)) + 1, float('inf'))
    m = re.fullmatch(rf'{n}\s*(?:\+|or more|plus|and above|and over)\s*(years?|yrs?|months?)|{n}\s*(years?|yrs?|months?)\s*(?:\+|or more|plus|and above)', o)
    if m:
        num, u = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        return (_number(num) * unit(u), float('inf'))
    m = re.fullmatch(rf'{n}\s*(?:-|to)\s*{n}\s*(years?|yrs?|months?)', o)
    if m:
        u = unit(m.group(3))
        return (_number(m.group(1)) * u, _number(m.group(2)) * u)
    m = re.fullmatch(rf'{n}\s*(years?|yrs?|months?)', o)
    if m:
        u = unit(m.group(2))
        return (_number(m.group(1)) * u, _number(m.group(1)) * u + (11 if u == 12 else 0))
    return None


def money(text):
    """The money figures in a text, in dollars: '$95k', '$70,000', '70000', '$60-65k'. A bare small number is not money."""
    t = re.sub(r'(\d+)\s*(-|to)\s*(\d+)\s*k\b', r'\1k \2 \3k', norm(text))
    out = []
    for dollar, digits, k in re.findall(r'(\$)?\s?(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(k\b)?', t):
        amount = float(digits.replace(',', '')) * (1000 if k else 1)
        if dollar or k or ',' in digits or amount >= 20000:
            out.append(amount)
    return out


def salary_range(option):
    """(low, high) in dollars a year for a salary option, or None when it holds no annual figure."""
    o = norm(option)
    found = [x for x in money(o) if x >= 1000]
    if not found or re.search(r'hour|day|week|month|super|package', o):   # '$70k + super' is not a base salary band
        return None
    if re.search(r'less than|under|below|up to|<', o):
        return (0, found[0])
    if re.search(r'\+|more than|over|above|or more|and above|plus\b', o) and len(found) == 1:
        return (found[0], float('inf'))
    if len(found) >= 2:
        return (found[0], found[1])
    return (found[0], found[0])


# ---------- the subjects ----------

def _declaration(q, opts, a):
    """True and correct, privacy, consent to reference, qualification or police checks: Yes. Any other: unanswered.
    None when the question is not a declaration of an approved kind."""
    declares = re.match(r'i (acknowledge|consent|agree|declare|confirm|certify|understand|accept|authori[sz]e)\b', q) or \
        re.search(r'\b(do|will|would) you (agree|consent|acknowledge|declare|confirm|accept)\b|\bplease (acknowledge|confirm your consent|consent)\b', q)
    if not declares:
        return None
    subjects = {'true and correct': r'\btrue and correct\b|\btrue, correct\b|\bcorrect and true\b',
                'privacy policy': r'privacy (policy|statement|notice|collection)|collection (notice|statement)',
                'reference': r'reference (check|checking)|referee check',
                'qualification': r'qualification (check|verification)|verify (my |your )?qualifications',
                'police': r'police (check|certificate)|criminal history (check|screen)|national police'}
    named = [s for s, pattern in subjects.items() if re.search(pattern, q)]
    if not named:
        return None
    other = re.search(r'medical|health|drug|alcohol|disab|injur|criminal (record|history\b(?! (check|screen)))|convict|offen[cs]e'
                      r'|marketing|third.part|\bshar(e|ing)\b|disclos|overseas|outside australia|agency|represent|enlist|military'
                      r'|background check|credit|social media|\bever\b|suspend', q)
    if other:
        return _no(f'a declaration or consent facts.json does not approve ("{other.group(0)}")', 'answers.declarations_and_consents')
    approved = re.split(r'any other', str(a.get('declarations_and_consents') or ''), flags=re.I)[0].lower()
    if not approved.startswith('yes') or not all(s.split()[0] in approved for s in named):
        return _no('facts.json -> answers -> declarations_and_consents does not approve this', 'answers.declarations_and_consents')
    if not opts:
        return _ok('Yes', 'answers.declarations_and_consents')
    hits = [o for o in opts if re.match(r'(yes|i agree|agree|i acknowledge|acknowledged?|i consent|consent|i accept|accept|i confirm|confirm(ed)?|true)\b', norm(o))
            and not re.match(r'(i )?(do not|don\'t|disagree|no)\b', norm(o))]
    return _ok(hits[0], 'answers.declarations_and_consents') if len(hits) == 1 else _no('no single option agrees', 'answers.declarations_and_consents')


def _sponsorship(q, opts, a):
    line = str(a.get('future_visa_sponsorship') or '')
    if re.search(r'future|later|at any (time|stage|point)|will you|would you|going forward|ongoing|eventually|down the track|coming years|next \d', q):
        return _plain_line(a, 'future_visa_sponsorship', q, opts) if _settled(line, q) and not re.search(r'sponsorship to work now', line) else \
            _no('future sponsorship: facts.json -> answers -> future_visa_sponsorship leaves it to the owner', 'answers.future_visa_sponsorship')
    now = re.search(r"sponsorship to work now\?'?\s*:\s*(no|yes)\b", line, re.I)
    asks_now = re.search(r'\b(do|are) you (currently |now )?(require|need|in need of)\b[^?]*\bsponsor|\brequire (visa )?sponsorship\b', q)
    if not now or not asks_now or not yes_no_question(q):
        return _no('a sponsorship question facts.json does not answer', 'answers.future_visa_sponsorship')
    pick = _choose(now.group(1).capitalize(), opts)
    return _ok(pick, 'answers.future_visa_sponsorship') if pick else _no('no single option says No', 'answers.future_visa_sponsorship')


def _right_to_work(q, opts, a):
    rule = a.get('right_to_work') or {}
    if not opts:
        free = rule.get('free_text')
        return _ok(free, 'answers.right_to_work.free_text') if free else _no('facts.json -> answers -> right_to_work has no free_text', 'answers.right_to_work')
    if not rule.get('choose'):
        return _no('facts.json -> answers -> right_to_work has no rule for choosing', 'answers.right_to_work')
    sponsor_needed = lambda o: re.search(r'sponsor', o) and not re.search(r"\b(no|not|without|don't|do not|never)\b[^,;.]{0,25}sponsor", o)
    allowed = [o for o in opts if not re.search(r'citizen|permanent resident|\bpr\b|new zealand|\bnz\b', norm(o)) and not sponsor_needed(norm(o))]
    graduate = [o for o in allowed if re.search(r'graduate|\b485\b', norm(o))]
    free = [o for o in allowed if re.search(r'temporary', norm(o)) and re.search(r'no restrictions?|without restrictions?|unrestricted|full work(ing)? rights', norm(o))
            and not re.search(r'restrictions? on|restricted (to|by|on)|limited|holiday|partner|family|bridging', norm(o))]
    pick = graduate if graduate else free
    if len(pick) != 1:
        return _no('no single option names the temporary graduate visa (Subclass 485) or a temporary visa with no restriction', 'answers.right_to_work.choose')
    return _ok(pick[0], 'answers.right_to_work.choose')


def _weeks_option(n, opts):
    """The one option meaning n weeks: '2 weeks', 'Two weeks', '2 weeks notice', 'Within 2 weeks', '14 days'."""
    word = {v: k for k, v in NUMBERS.items()}.get(n, str(n))
    w = rf'(?:{n}|{word})(?: \({n}\))? weeks?'
    pattern = rf"{w}(?:'?s?)?(?: notice)?|in {w}|within {w}|up to {w}|{w} or less|{n * 7} days"
    hits = [o for o in opts if re.fullmatch(pattern, norm(o).rstrip('.'))]
    return hits[0] if len(hits) == 1 else ''


def _weeks(text):
    m = re.search(r'\b(\d+|one|two|three|four|five|six)\s+weeks?\b', norm(text))
    return int(_number(m.group(1))) if m else None


def _notice(q, opts, a):
    value = a.get('notice_period')
    if not _settled(value, q) or _weeks(value) is None:
        return _no('facts.json -> answers -> notice_period gives no number of weeks', 'answers.notice_period')
    if opts:
        pick = _weeks_option(_weeks(value), opts)
        return _ok(pick, 'answers.notice_period') if pick else _no(f'no single option means {value}', 'answers.notice_period')
    return _ok(value, 'answers.notice_period')


def _start(q, opts, facts):
    line = next((x for x in (facts.get('eligibility') or {}).get('availability') or [] if re.search(r'\bstart\b', str(x), re.I)), '')
    m = re.search(r'\bstart (.+?)\.?$', str(line), re.I)
    if not m:
        return _no('facts.json -> eligibility -> availability has no start line', 'eligibility.availability')
    if opts:
        weeks = _weeks(m.group(1))
        pick = _weeks_option(weeks, opts) if weeks else ''
        return _ok(pick, 'eligibility.availability') if pick else _no('no single option means two weeks after an offer', 'eligibility.availability')
    text = m.group(1).strip()
    return _ok(text[:1].upper() + text[1:], 'eligibility.availability')


def _salary(q, opts, a, pay):
    if re.search(r'minimum|upper end|lower end|current (salary|remuneration|package)|includ\w* (of )?super|incl\.? super|inclusive of super|package'
                 r'|payment basis|confirm|in ?line with|range you entered|per hour|daily', q):
        return _no('a salary question facts.json does not answer (only the expected base salary is on record)', 'answers.expected_salary.rule')
    rule = str((a.get('expected_salary') or {}).get('rule') or '')
    band = re.search(r'\$([\d,]+) to \$([\d,]+)', rule)
    if not band:
        return _no('facts.json -> answers -> expected_salary.rule has no band written as "$65,000 to $75,000"', 'answers.expected_salary.rule')
    low, high = (float(x.replace(',', '')) for x in band.groups())
    figure = None
    if pay:
        annual = [x for x in money(pay) if x >= 20000]
        if not annual or re.search(r'hour|per day|daily', norm(pay)):
            return _no(f'the advertised pay ({pay}) is not an annual figure', 'answers.expected_salary.rule')
        figure = min(annual[:2])   # the lower end of a stated range
    if not opts:
        return _ok(f'{int(figure)}' if figure else f'{int(low)} to {int(high)}', 'answers.expected_salary.rule')
    ranges = [(o, salary_range(o)) for o in opts]
    if figure:
        hits = [o for o, r in ranges if r and r[0] <= figure <= r[1]]
    else:
        hits = [o for o, r in ranges if r and r[0] <= low and high <= r[1]] or \
               [o for o, r in ranges if r and r[0] <= (low + high) / 2 <= r[1]]
    if len(hits) != 1:
        held = f'${int(figure):,}' if figure else f'${int(low):,} to ${int(high):,} or ${int((low + high) / 2):,}'
        return _no(f'no single option holds {held}', 'answers.expected_salary.rule')
    return _ok(hits[0], 'answers.expected_salary.rule')


STATES = r"\b(wa|nsw|qld|sa|nt|act|tas)\b|queensland|western australia|new south wales|south australia|tasmania|northern territory|capital territory"


def _licence(q, opts, a):
    value = str(a.get('drivers_licence') or '')
    asked = q + ' ' + ' '.join(norm(o) for o in opts)
    if re.search(r'\b(open|unrestricted)\b', asked):
        asked += ' full'   # an open or unrestricted licence is a full one: a line that leaves 'full' open leaves this open too
    if not _settled(value, asked) or _head(value) != 'Yes':
        return _no("facts.json -> answers -> drivers_licence does not settle this", 'answers.drivers_licence')
    if re.search(STATES, q):
        return _no("asks for another state's licence; his licence is Victorian", 'answers.drivers_licence')
    if re.search(r'heavy|truck|forklift|motor ?cycle|\b(hr|mr|hc|lr|mc)\b|rigid|combination|\bbus\b|driving record|history', q):
        return _no('asks about a licence class or record facts.json does not cover', 'answers.drivers_licence')
    if 'manual' in q:
        manual = str(a.get('manual_licence') or '')
        auto = (_head(manual) == 'No' and 'automatic' in manual.lower()) or re.search(r'manual or automatic: automatic', value, re.I)
        basis = 'answers.manual_licence' if manual else 'answers.drivers_licence'
        if not auto:
            return _no('facts.json does not say manual or automatic', basis)
        if re.search(r'\bauto(matic)?\b', q):   # "manual or automatic?": a choice
            if not opts:
                return _ok('Automatic', basis)
            hits = [o for o in opts if re.match(r'auto', norm(o)) or re.fullmatch(r'yes,? (an )?auto\w*( only)?', norm(o))]
            return _ok(hits[0], basis) if len(hits) == 1 else _no('no single option says automatic', basis)
        if not yes_no_question(q):
            return _no('not a yes/no question', basis)
        pick = _choose('No', opts)
        return _ok(pick, basis) if pick else _no('no single option says No', basis)
    if re.search(r'provisional|probationary|learner|p ?plates?|\bp[12]\b', q):
        return _no('asks about a licence stage facts.json does not answer', 'answers.drivers_licence')
    if re.search(r'\bfull\b|\bopen\b|unrestricted', q) and not re.search(r'\bfull\b', value.split('.')[0], re.I):   # the line itself says full
        return _no('facts.json does not say the licence is full', 'answers.drivers_licence')
    if not yes_no_question(q):
        return _no('not a yes/no question', 'answers.drivers_licence')
    if not opts:
        return _ok('Yes', 'answers.drivers_licence')
    hits = [o for o in opts if re.match(r'(yes|full|open|car|class c|automatic|unrestricted)\b', norm(o))
            and not re.search(r'manual|provisional|probationary|learner|p ?plate|\bp[12]\b|heavy|\bhr\b|\bmr\b|truck|motor ?cycle|forklift|^no\b', norm(o))]
    return _ok(hits[0], 'answers.drivers_licence') if len(hits) == 1 else _no('no single option is his full licence', 'answers.drivers_licence')


def _police(q, opts, a, today):
    value = str(a.get('police_check') or '')
    if not _settled(value, q) or not _head(value):
        return _no('facts.json -> answers -> police_check does not settle this', 'answers.police_check')
    if not yes_no_question(q):
        return _no('not a yes/no question about the police check', 'answers.police_check')
    sentences = re.split(r'(?<=\.)\s+', value)
    if re.search(r'willing|prepared|happy to|consent|agree to|able to obtain|undergo|undertake|complete|obtain|participate', q):
        if not re.search(r'willing to (obtain|get)', value, re.I):
            return _no('facts.json -> answers -> police_check does not say he is willing to obtain one', 'answers.police_check')
        head, free = 'Yes', 'Yes'
    elif re.search(r'for employment|employment purposes|within the (last|past)|in the (last|past)|issued (in|within)|last \d+ months|\d+ months|recent', q):
        said = next((s for s in sentences if re.search(r'for employment|within the last', s, re.I)), '')
        m = re.search(r'\((no)\)|:\s*(no)\b', said, re.I)
        if not m:
            return _no('facts.json -> answers -> police_check says nothing about a check for employment or a recent one', 'answers.police_check')
        extra = re.search(r"'([^']+)'", said)
        head, free = 'No', 'No.' + (f' {extra.group(1)}' if extra else '')
    elif re.search(r'\b(have|hold|possess)\b[^?]*\b(current|valid)\b', q):
        head, free = _head(value), sentences[0].rstrip('.')
        change = re.search(r'from (' + '|'.join(MONTHS) + r') (\d{4}) the answer becomes: ([^.]+)', value, re.I)
        when = today or _melbourne_today()
        if change and (when.year, when.month) >= (int(change.group(2)), MONTHS.index(change.group(1).lower()) + 1):
            head, free = _head(change.group(3)) or 'No', change.group(3).strip()
    else:
        return _no('a police check question facts.json does not answer', 'answers.police_check')
    pick = _choose(head, opts)
    return _ok(pick if opts else free, 'answers.police_check') if pick else _no(f'no single option says {head}', 'answers.police_check')


def _tests(q, opts, a):
    if not re.search(r'willing|prepared|happy to|consent|agree to|undergo|undertake|participate|complete|attend|able to (pass|complete|undergo)', q):
        return _no('a medical or drug test question that is not about willingness to take the test', 'answers.pre_employment_medical')
    keys = (['pre_employment_medical'] if 'medical' in q else []) + (['drug_and_alcohol_screening'] if re.search(r'drug|alcohol', q) else [])
    results = [_yes_no_line(a, key, q, opts) for key in keys]
    bad = next((r for r in results if r['status'] != 'answered'), None)
    return bad or _ok(results[0]['answer'], results[0]['basis'])


def _years_subject(q):
    """('role', X) or ('field', X) for a how-many-years question, or (None, None)."""
    shapes = [(r"how many years'? (?:of )?experience do you have (?:working )?as (?:an? |the )?(?P<x>.+)", 'role'),
              (r"how many years'? (?:of )?experience do you have (?:in|with) (?:an? |the )?(?P<x>.+)", 'field'),
              (r"how many years'? (?:of )?experience in (?:an? |the )?(?P<x>.+?) do you have", 'field'),
              (r"how many years (?:of )?(?:the )?(?P<x>.+?) experience do you have", 'field')]
    for pattern, kind in shapes:
        m = re.fullmatch(pattern, q)
        if m:
            return kind, ' '.join(re.sub(r'[^a-z0-9/+&\' ]', ' ', m.group('x')).split())
    return None, None


ROLE_PREFIXES = {'civil', 'junior', 'graduate', 'assistant', 'construction', 'site', 'project'}  # 'Assistant Civil Engineer' is a civil engineer


def _years(q, opts, a, facts):
    kind, x = _years_subject(q)
    if not kind:
        return _no('a years-of-experience question in a shape facts.json does not answer', 'answers.years_of_experience')
    rows = {k: str(v) for k, v in (a.get('years_of_experience') or {}).items() if k not in ('rule', '_about')}
    parts = {p.strip().lower(): row for row in rows for p in row.split(',') if p.strip()}
    worked = next((row for row in rows if '11 months' in rows[row]), None)
    words = x.replace('/', ' / ').split()
    hits = []
    if kind == 'role' and 'engineer' in words:
        # Months as an engineer are claimed only for a plain engineering title: 'Civil Site Engineer', 'Graduate Engineer'.
        # 'Rail Project Engineer', 'Senior Site Engineer' or 'Site Engineer / Estimator' asks about work he has not done.
        if words.count('engineer') == 1 and all(w in ROLE_PREFIXES or w == 'engineer' for w in words) and worked:
            hits = [worked]
        else:
            return _no('an engineering title facts.json does not cover (only a plain graduate, junior, site, project or civil engineer title)', 'answers.years_of_experience')
    elif kind == 'field':
        if x in parts and x not in ('cad', 'any other role') and not x.endswith('engineer'):
            hits = [parts[x]]
    else:
        lowest = {p: row for p, row in parts.items() if 'lowest option' in rows[row].lower() and p != 'any other role'}
        hits = sorted({row for p, row in lowest.items() if re.search(r'\b' + re.escape(p) + r'\b', x)})
        held = {w for job in facts.get('experience') or [] for w in re.findall(r'[a-z]{5,}', str(job.get('role') or '').lower())}
        # 'any other role' is the lowest option too, but not for a title near work he has done: one that shares a word
        # with a job he has held, or names construction, site, engineering or leading people.
        near = held | {'construction', 'site', 'engineering', 'lead', 'leader', 'supervisor', 'foreman', 'manager'}
        if not hits and 'any other role' in parts and not near & set(re.findall(r'[a-z]{4,}', x)):
            hits = [parts['any other role']]
    kinds = {'worked' if '11 months' in rows[row] else 'lowest' if 'lowest option' in rows[row].lower() else 'other' for row in hits}
    if len(kinds) != 1 or kinds == {'other'}:
        return _no(f'no line of facts.json -> answers -> years_of_experience names "{x}"', 'answers.years_of_experience')
    row = hits[0]
    basis = 'answers.years_of_experience.' + row
    if opts:
        ranges = [(o, months_range(o)) for o in opts]
        if any(r is None for _, r in ranges):
            return _no('an option could not be read as a length of time', basis)
        if kinds == {'worked'}:
            pick = [o for o, r in ranges if r[0] <= 11 <= r[1]]
        else:
            least = min(r for _, r in ranges)   # the lowest start, then the narrowest: 'No experience' before 'Less than 1 year'
            # The lowest option must claim no time at all: '1 year' as the lowest would still overstate 'no paid role'.
            pick = [o for o, r in ranges if r == least] if least[0] == 0 else []
        return _ok(pick[0], basis) if len(pick) == 1 else _no('no single option ' + ('holds 11 months' if kinds == {'worked'} else 'is the lowest'), basis)
    if kinds == {'worked'}:
        period = re.search(r'(\w+ \d{4} to \w+ \d{4})', rows[row])
        return _ok('Less than 1 year (11 months' + (f', {period.group(1)})' if period else ')'), basis)
    free = re.search(r"free text if offered: '([^']+)'", rows[row], re.I)
    return _ok(free.group(1) if free else 'None: no paid role of this kind', basis)


def _qualification(q, opts, a, facts):
    known = {k.lower(): v for k, v in (a.get('qualification_questions') or {}).items() if not k.startswith('_')}
    other = 'any other named qualification'
    m = re.fullmatch(r"(?:have you (?:successfully )?completed|do you (?:currently )?(?:hold|have|possess)) (?:a |an |any )?(?:relevant )?"
                     r"(?P<kind>qualifications?|bachelor'?s? degree|bachelor'?s?|degree|university degree|tertiary degree) (?:in|of) (?P<x>.+)", q)
    if not m or not known:
        return None
    degree = 'qualification' not in m.group('kind')
    names = {}
    for key in known:
        if key == other:
            continue
        names[key] = key
        pair = re.fullmatch(r'(.+) (\w+) or (\w+)', key)   # 'engineering drafting or design'
        if pair:
            names[f'{pair.group(1)} {pair.group(2)}'] = names[f'{pair.group(1)} {pair.group(3)}'] = key
    held = [str(e.get('qualification') or '').lower() for e in facts.get('education') or []]
    words = lambda text: set(re.findall(r'[a-z]{4,}', text))
    found = []   # (head, basis) of each alternative the question names
    # 'X / Y' is one field (SEEK's 'engineering drafting / engineering design'): every part must say the same.
    # 'X, Y or Z' offers alternatives: one Yes is enough.
    every = '/' in m.group('x')
    for part in (p.strip() for p in re.split(r'\s*/\s*' if every else r'\s*(?:,|\band/or\b|\bor\b)\s*', m.group('x')) if p.strip()):
        part = re.sub(r'^(an?|the) ', '', part)
        if re.search(r'equivalent|related|similar|^other\b', part):
            found.append(('', ''))
        elif part in names and not (degree and not re.search(r'bachelor|degree', str(known[names[part]]), re.I) and names[part] not in ('engineering', 'civil engineering')):
            found.append((_head(known[names[part]]), 'answers.qualification_questions.' + names[part]))
        elif other not in known:
            found.append(('', ''))
        elif len(part.split()) > 1 and any(re.search(r'\b' + re.escape(part) + r'\b', h) for h in held) and not degree:
            found.append(('Yes', 'answers.qualification_questions.' + other))   # named, whole, in the title of one he holds
        elif words(part) and not words(part) & words(' '.join(held)):
            found.append(('No', 'answers.qualification_questions.' + other))    # nothing he holds shares a word with it
        else:
            found.append(('', ''))   # shares a word with his own ('science', 'construction management'): not guessed
    yes = [b for h, b in found if h == 'Yes']
    if every and not all(h == 'Yes' for h, _ in found):
        yes = []
    if yes:
        head, basis = 'Yes', yes[0]
    elif found and all(h == 'No' for h, _ in found):
        head, basis = 'No', found[0][1]
    else:
        return _no('a qualification facts.json -> answers -> qualification_questions does not name', 'answers.qualification_questions')
    if not yes_no_question(q):
        return _no('not a yes/no question', basis)
    pick = _choose(head, opts)
    if not pick:
        return _no(f'no single option says {head}', basis)
    value = str(known.get(basis.rsplit('.', 1)[1], '')) if basis.endswith(tuple(known)) else ''
    return _ok(pick if opts else (value if _head(value) == head and value.startswith(head + ':') else head), basis)


def _qualifications_held(q, opts, facts):
    if opts:
        return _no('a choice of qualification levels: facts.json does not say which option', 'education')
    held = []
    for e in facts.get('education') or []:
        years = re.findall(r'\b(?:19|20)\d\d\b', str(e.get('completed') or e.get('dates') or ''))
        if e.get('qualification') and years:
            held.append(f"{e['qualification']}, {years[-1]}")
    return _ok('; '.join(held), 'education') if held else _no('facts.json -> education is empty', 'education')


def _tool(part):
    """'his', 'office', 'office product', 'other' (a known tool he has not used) or None for a name nobody listed."""
    p = re.sub(r'^(autodesk|the|using|use of) ', '', part.strip())
    p = re.sub(r' (software|program|programs|package|packages)$', '', p) if p not in ('cad software', 'any cad software') else p
    if p in HIS_TOOLS or p + ' software' in HIS_TOOLS:
        return 'his'
    if re.fullmatch(r'(microsoft|ms) office( suite)?', p):
        return 'office'
    if OFFICE_PRODUCTS.search(p) and re.search(r'microsoft|ms\b|^(excel|word|powerpoint|outlook)', p):
        return 'office product'
    if any(re.match(re.escape(t.lower()) + r'\b', p) for t in KNOWN_TOOLS):
        return 'other'
    return None


def _software(q, opts, a):
    software = a.get('software') or {}
    cad = str(software.get('CAD') or '')
    names = [n.strip() for n in re.split(r',|\band\b', cad.split(' only')[0]) if n.strip()] if ' only' in cad else []
    which = re.fullmatch(r"which of the following (?P<x>.+?) (?:do you have experience (?:with|using|in)|are you experienced (?:with|in)(?: using)?|have you used|have you worked with)", q)
    if which:
        x = which.group('x')
        if 'office' in x or OFFICE_PRODUCTS.search(x):
            return _no('Microsoft Office products are not named in facts.json -> answers -> software', 'answers.software.Microsoft Office')
        if not re.fullmatch(r'(cad|drafting|cad drafting|cad and drafting)( software| programs?| packages?| software packages| tools)?'
                            r'|(design|civil design|design and drafting|civil drafting) (software|programs?|packages?|software packages|tools)', x):
            return _no(f'facts.json -> answers -> software names CAD software only, not "{x}"', 'answers.software.CAD')
        if not names:
            return _no('facts.json -> answers -> software -> CAD gives no list', 'answers.software.CAD')
        if not opts:
            return _ok(', '.join(names), 'answers.software.CAD')
        ticked = [o for o in opts if _tool(norm(o)) == 'his']
        return _ok('; '.join(ticked), 'answers.software.CAD') if ticked else _no('none of the options is AutoCAD, Civil 3D or Revit', 'answers.software.CAD')
    m = re.fullmatch(r'do you have (?:any )?(?:previous )?experience (?:using|with|in using) (?P<x>.+)|do you have (?:any )?(?P<y>.+?) experience|have you used (?P<z>.+)', q)
    if not m:
        return None
    x = (m.group('x') or m.group('y') or m.group('z')).replace('"', '')
    whole = _tool(x)   # 'AutoCAD 2D/3D' is one tool
    kinds = [whole] if whole else [_tool(p) for p in re.split(r'\s*(?:,|/|\band\b|\bor\b)\s*', x) if p.strip()]
    if not any(kinds):
        return None   # not software: an activity, for the experience lines
    if all(k == 'his' for k in kinds) and names:
        head, basis = 'Yes', 'answers.software.CAD'
    elif all(k == 'office' for k in kinds) and _head(software.get('Microsoft Office')) == 'Yes' and _settled(software.get('Microsoft Office'), q):
        head, basis = 'Yes', 'answers.software.Microsoft Office'
    elif all(k == 'other' for k in kinds) and names:
        head, basis = 'No', 'answers.software.other' if software.get('other') else 'answers.software.CAD'
    elif 'office product' in kinds:
        return _no('Microsoft Office products are not named in facts.json -> answers -> software', 'answers.software.Microsoft Office')
    else:
        return _no('names software facts.json does not list, or his tools together with others', 'answers.software')
    pick = _choose(head, opts)
    return _ok(pick, basis) if pick else _no(f'no single option says {head}', basis)


LEAD_INS = ('working on ', 'carrying out ', 'in ', 'with ')


def _experience(q, opts, a):
    m = re.fullmatch(r'do you have (?:any )?experience (?P<x>.+)|do you have (?:any )?(?P<y>.+?) experience', q)
    if not m:
        return None
    x = (m.group('x') or m.group('y')).strip()
    asked = {x.rstrip('s')} | {x[len(lead):].rstrip('s') for lead in LEAD_INS if x.startswith(lead)}
    for key, value in (a.get('experience_yes_no') or {}).items():
        if key != 'anything else' and asked & {p.strip().lower().rstrip('s') for p in key.split(',') if p.strip()}:
            return _yes_no_line(a['experience_yes_no'], key, q, opts) | {'basis': 'answers.experience_yes_no.' + key}
    return _no('an activity facts.json -> answers -> experience_yes_no does not name', 'answers.experience_yes_no')


def _location(q, opts, facts):
    if opts:
        return _no('a choice of places: facts.json does not say which option', 'identity.location')
    if re.search(r'city only|postcode|\bstate\b|where in ', q):
        return _no('asks for a part of the address facts.json does not give on its own', 'identity.location')
    place = (facts.get('identity') or {}).get('location')
    return _ok(place, 'identity.location') if place else _no('facts.json -> identity has no location', 'identity.location')


def _referees(q, opts, a):
    line = str(a.get('referees') or '')
    first = line.split('.')[0].strip()
    if opts or not first or not re.match(r'available on request', first, re.I):
        return _no('referees are given on request only, and the form wants something else', 'answers.referees')
    return _ok(first, 'answers.referees')


# ---------- the gate ----------

def answer(question, options=None, facts=None, pay=None, today=None):
    """The standing answer to one form question. See the module notes for what is covered.

    options: the choices on screen (none for a free-text question). pay: the advert's own pay text, when the entry
    or the caller knows it (salary only). today: the date to judge the police check by (default: today in Melbourne).
    """
    facts = facts or {}
    a = facts.get('answers') or {}
    q = norm(question).rstrip(' ?.:!')
    opts = [' '.join(str(o).split()) for o in options or [] if str(o).strip()]
    if not q:
        return _no('no question text')
    declared = _declaration(q, opts, a)
    if declared:
        return declared
    trap = TRAPS.search(q)
    if trap:
        return _no(f'only the owner can answer this ("{trap.group(0)}": a private detail, or a question a standing answer could get wrong)')
    topics = [name for name, pattern in TOPICS.items() if re.search(pattern, q)]
    if str(question).count('?') > 1 or len(topics) > 1:
        return _no('asks several things at once' + (f" ({', '.join(topics)})" if len(topics) > 1 else ''))
    if re.search(r"how many years|years'? (of )?experience|number of years", q):
        return _years(q, opts, a, facts)
    if 'sponsor' in q:
        return _sponsorship(q, opts, a)
    if re.search(r'engineers australia|washington accord|\bner\b|national engineering register|rpeq|registered professional engineer|cpeng|chartered|mieaust', q):
        if re.search(r'engineers australia|washington accord|mieaust', q):
            return _plain_line(a, 'engineers_australia_membership_or_recognition', q, opts) if _settled(a.get('engineers_australia_membership_or_recognition'), q) \
                else _no('Engineers Australia: not on record (facts.json -> answers -> engineers_australia_membership_or_recognition)', 'answers.engineers_australia_membership_or_recognition')
        return _no('a professional registration facts.json does not record')
    if re.search(TOPICS['work rights'], q) or re.search(r'(entitled|eligib\w*|authori[sz]ed|allowed|permitted|legal right|legally able) to (live and )?work|residency status|work permit', q):
        return _right_to_work(q, opts, a)
    if re.search(r'hourly|per hour|rate expectation|(pay|day|daily|current|charge) rate|\brate\b[^?]*\b(looking for|expect)', q):
        return _plain_line(a, 'expected_hourly_rate', q, opts) if _settled(a.get('expected_hourly_rate'), q) \
            else _no('hourly rate: not on record (facts.json -> answers -> expected_hourly_rate)', 'answers.expected_hourly_rate')
    if re.search(r'salary|remuneration', q):
        return _salary(q, opts, a, pay)
    if re.search(r'\bnotice\b', q):
        return _notice(q, opts, a)
    if re.search(r"start date|availab\w* to (start|commence)|when (can|could|would) you (start|commence)|earliest (available )?start|"
                 r"(able|available) to start|when are you available|commence (work|in|a)", q):
        if re.search(r'\d{4}|\b(' + '|'.join(m[:3] for m in MONTHS) + r')[a-z]*\b|immediately|tomorrow|next week', q):
            return _no('asks about a particular start date; facts.json gives only two weeks after an offer', 'eligibility.availability')
        return _start(q, opts, facts)
    if re.search(r"driv\w*'?s? licen[cs]e|driving licen[cs]e|licen[cs]ed? to drive|car licen[cs]e|class c\b|(provisional|probationary|p ?plate|learner)\b[^?]*licen[cs]e", q):
        return _licence(q, opts, a)
    if re.search(TOPICS['car'], q):
        return _yes_no_line(a, 'own_car_or_regular_access', q, opts)
    if re.search(TOPICS['White Card'], q):
        return _yes_no_line(a, 'white_card', q, opts)
    if re.search(r'police (check|certificate|clearance)|national police|criminal history (check|screen)', q):
        return _police(q, opts, a, today)
    if re.search(r'medical|drug|alcohol', q):
        return _tests(q, opts, a)
    if re.search(r'\bcurrently (studying|enrolled)\b|are you (currently )?(a )?student\b', q):
        if re.search(r'\bor\b|/|prepared|recent graduate|completed|washington', q):
            return _no('asks about study together with something else', 'answers.currently_studying')
        return _yes_no_line(a, 'currently_studying', q, opts)
    if re.search(r'relocat', q):
        if re.search(r'overseas|international|new zealand|abroad|another country', q):
            return _no('relocation outside Australia is not on record', 'answers.willing_to_relocate')
        return _yes_no_line(a, 'willing_to_relocate', q, opts, free=a.get('willing_to_relocate'))
    if re.search(r'\bfifo\b|\bdido\b|\btravel|\broster', q):
        if 'experience' in q or not re.search(r'willing|available|open to|able to|prepared|happy|consider|comfortable', q):
            return _no('not a question about willingness to travel or work FIFO', 'answers.willing_to_travel_or_fifo')
        return _yes_no_line(a, 'willing_to_travel_or_fifo', q, opts)
    qualification = _qualification(q, opts, a, facts)
    if qualification:
        return qualification
    if re.fullmatch(r"what (relevant )?qualifications? do you (currently )?(hold|have)|what qualifications have you (completed|obtained)"
                    r"|please (list|provide|indicate) your (relevant )?qualifications?", q):
        return _qualifications_held(q, opts, facts)
    software = _software(q, opts, a)
    if software:
        return software
    experience = _experience(q, opts, a)
    if experience:
        return experience
    if re.search(r'\benglish\b', q):
        return _plain_line(a, 'english_self_rating', q, opts)
    if re.search(r'\breferees?\b', q):
        return _referees(q, opts, a)
    if re.fullmatch(r"where (are|do) you (currently )?(live|living|located|based|reside|residing)|where are you located|where are you currently (living|based|located)"
                    r"|(what is |what's )?your (current )?location|location|current location|(please confirm )?which suburb (do )?you (currently )?(live|reside) in"
                    r"|(please confirm )?which suburb do you (currently )?(live|reside) in|which suburb do you live in", q):
        return _location(q, opts, facts)
    return _no('no line of facts.json -> answers covers this question')
