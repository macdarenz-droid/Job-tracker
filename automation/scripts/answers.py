#!/usr/bin/env python3
"""The one answer gate for application form questions. queue.py (add, answer, next) and checks.py (questions, draft,
record, and publish.py through them) all call answer(); no other code decides an answer.

answer(question, options, facts, pay=None, today=None) -> {'answer', 'basis', 'status', 'why'}

The gate is strict. A question is 'answered' only when a line of facts.json -> answers clearly covers it (or, for the
free-text questions marked below, a line of identity, eligibility or education does). Every other question is
'unanswered', and why says what is missing: the owner answers it once and his answer goes into facts.json -> answers
-> owner_answers (below). Nothing is guessed and no option is chosen because it is the nearest one. With the form's
options the answer is one of them, word for word (several joined by '; ' for a tick list); otherwise the question is
'unanswered'. A Yes or No is chosen only from an option that says Yes or No and nothing more ('Yes.' is one; 'Yes, and
I hold a forklift licence' or 'No - but willing' is not), and the same holds for 'I agree' and his licence (plain_option).
With no options the answer
is the text to type, or for a choice question a short description of the choice; the submitter then runs
`queue.py answer ID --question ... --option ...` with the options on screen.

Covered (facts.json -> answers unless another block is named):
  owner_answers      first, before every rule below: a list of {"question": text, "options": [text, ...] (optional),
                     "answer": text, "date": "YYYY-MM-DD", "entry": queue id (optional)}. A question whose text is the
                     same (owner_key: case, spacing, double quotation marks and a closing ?.:! aside) gets that answer;
                     with options on screen only when it is one of them (norm), else unanswered. A row with "entry"
                     answers that queue entry only (answer(..., entry=ID)), and goes before a row without one; a
                     question about one job or its pay (JOB_SPECIFIC: 'this role', 'similar role', 'salary') needs
                     "entry". A question asking for a private detail (PRIVATE_ASK: date of birth, tax file number,
                     address, health) is never taken from a row: the owner types it himself. A malformed row answers
                     nothing (owner_answer_problems). A row with no options whose answer is a plain length of time
                     ("2 years", "18 months"), for a how-many-years question: the one option whose range holds that
                     number ("1 - 5 Years"), when every option reads as a length of time; a number on the edge of two
                     options ("1 year" with "0 - 1 years" and "1 - 5 Years") is unanswered (_owner_length_option)
  right to work      Yes/No 'Do you have the right to work in Australia?' (the legal right, currently, hold) and 'Do
                     you have full working rights in Australia?': Yes. 'Are you an Australian citizen or permanent
                     resident?' (or PR, either order): No. 'Unrestricted' and anything more stay unanswered. Otherwise
                     the option naming the temporary graduate visa or Subclass 485 and nothing more (RTW_GRADUATE_WORDS:
                     not 'with more than 2 years remaining', 'no sponsorship now or in the future', 'and have applied
                     for permanent residency'); only when no option names that visa, the one temporary visa option with
                     no restriction on hours or industry and nothing more; only when there is none of those either, the
                     one option that says temporary and nothing more ("I have temporary working rights", "Temporary
                     visa": RTW_TEMPORARY_WORDS), when no other option says temporary or names a restriction or limit;
                     never citizen, permanent resident, New Zealand or an option saying sponsorship is required, nor a
                     graduate option that says restrictions apply. No options: right_to_work.free_text. Work rights
                     somewhere other than Australia ('in New Zealand', 'overseas', 'in Australia and New Zealand') or
                     someone else's ('your partner'): unanswered (RTW_ELSEWHERE)
  sponsorship        owner, 15 Nov 2026 (future_visa_sponsorship, sponsorship_free_text): needs it now, currently, to start
                     or to work for the employer ("Do you require sponsorship to work in Australia?", "Will you need
                     sponsorship to start?"): No. Now or in the future, at any time, long term, during employment, going
                     to, expect or anticipate, to remain or stay in Australia, to continue working, "Will you require
                     sponsorship?": Yes; with options the one that says Yes, or Yes in the future, and nothing more ('Yes,
                     in the future', 'Not now, but in the future'), never one that says he needs it now; a plain Yes
                     beside another Yes option or one that names now or the future is unanswered. A question about now
                     whose options offer the future ('Yes, in the future') is answered as a future question, never with
                     a No that would say never. Free text ("Please outline your visa sponsorship requirements"):
                     sponsorship_free_text -> text, after its future_prefix ("Yes, in the future.") for a future
                     question. Unanswered: someone else's sponsorship or another country's (H-1B, green card), his work
                     rights in the same question, a question about seeking or being eligible for it, one with a negation
                     ('without sponsorship'), one not about his own need ('Does this role require sponsorship?'), one
                     that names now and a time to come less plainly ('currently ... to remain'), a free-text question
                     that also asks about the visa he holds
  notice             2 weeks, or the option meaning 2 weeks
  start date         free text only: "Two weeks after an offer" (eligibility.availability)
  salary             only when pay, the advert's own pay text, is known: an annual figure (the lower end of a range;
                     a figure written with $, k or a comma goes before a bare number, and a number after ref, no.,
                     id, job, position or the like is not pay) picks the option whose band holds it; pay "not stated"
                     (or "none") picks the option holding the owner's band ($65,000 to $75,000) or its midpoint
                     ($70,000). No options: the figure, or "65000 to 75000". pay not given (None or ''): unanswered,
                     because "the advert states no pay" and "the pay was not recorded" are not the same. Hourly rate,
                     minimum, package: unanswered
  driver's licence   Yes; full: Yes; manual: No; manual or automatic: Automatic; another state's licence: unanswered
  car, White Card    Yes
  police check       a check for employment: No. A window ("within the last 12 months", "less than 6 months old",
                     "issued in 2026") is compared with the month of issue in the facts line: inside it Yes, outside
                     it No, on its edge or unreadable ("recent") unanswered. A current check: Yes (the facts line
                     names the month from which that becomes No); willing to obtain one: Yes
  medical, drug and alcohol tests (willing): Yes. Currently studying: No. Relocate: Yes. Travel or FIFO: Yes
  Not for any of these: a question that joins the subject to another requirement ("a White Card and a First Aid
  certificate", "your own car with comprehensive insurance", "relocate and work night shift"); one about something
  already done ("Have you completed a medical?", "Have you relocated before?": facts.json records willingness only;
  a police check question in the past tense is judged as above); relocation at his own cost or without assistance;
  travel overseas; FIFO or rosters with night shifts. Sponsorship "long term", "permanently" or after the visa is a
  future-sponsorship question; "to start" in a sponsorship question is now, not a start date.
  qualifications     as answers.qualification_questions say; "What qualifications do you hold?" (free text): the
                     qualifications in education, with their years. A Yes whose options are qualification levels and no
                     plain Yes ('Yes, Certificate I' ... 'Yes, Bachelor Degree' ... 'Yes, Doctoral Degree'): the one
                     option naming the level of his highest qualification behind that Yes (education; for engineering
                     the Bachelor of Science in Civil Engineering: 'Yes, Bachelor Degree'), never Honours, Master or
                     higher; that level not offered once: unanswered (_level_option)
  credentials        'Do you have / hold <a formal credential>?' (17 Nov 2026): No, when qualification_questions ->
                     'any other named qualification' says otherwise No and every alternative is either '<level> in/of
                     <field>' whose field shares no word with what he holds ('a Certificate III in Laboratory Skills'), a
                     Masters or doctoral degree (none in education), or a licence or ticket TICKETS names ('a forklift
                     licence', 'a First Aid certificate') that facts.json does not mention. Not: a credential described
                     rather than named ('an overseas degree', 'a site safety ticket'), an abbreviation or unit code (BSc,
                     CIC, CPCWHS1001, WWCC), a document that is no qualification (an English test, a vaccination
                     certificate), a level with no field, Honours, a driving licence of any class, 'or equivalent',
                     experience, skills or software, or anything a rule above answers (White Card, driver's licence)
  years              as answers.years_of_experience say: a plain engineering title or the construction industry, the
                     option holding 11 months; other roles, the lowest option
  software           AutoCAD, Civil 3D and Revit only (other known tools: No); Microsoft Office products: unanswered
  experience yes/no  only the activities answers.experience_yes_no names
  declarations       true and correct, privacy policy or collection notice, consent to reference, qualification or
                     police checks: Yes, the one option that agrees and nothing more ('I agree', 'checked', or an option
                     that repeats the declaration word for word: 'I accept the Privacy Statement'). Only a declaration whose
                     every word is one DECLARATION_WORDS lists. Any other declaration or consent: unanswered, among them
                     terms or conditions of anything, marketing in other words (job alerts, a talent pool, being contacted
                     about other roles), details passed to partners, clients or related companies, a cost to him, a
                     further test or agreement (DECLARATION_MORE), a further clause or object ('... and agree to work
                     weekends'), an employer's name
  referees           free text "Available on request", never a name. Location: free text identity.location
  contact fields     free text, a form's own label for his details and nothing more (CONTACT_FIELDS): "First" or "First
                     name" (the first word of identity.name, when it is identity.short_name), "Last" or "Surname" (the
                     last word), "Full name" or "Name" (identity.name), "Email" or "Personal Email" (identity.email),
                     "Phone" or "Mobile number" (identity.phone). Never a label naming anyone else (referee, manager,
                     emergency contact, employer), another part of the name (middle, preferred, legal) or another
                     subject ("First aid", "First Nations", "Last day"); with options on screen: unanswered
Unanswered: hourly rate, English self-rating, Engineers Australia (until facts.json gives them a plain answer), and
every question this list does not name. Pure: no files. The clock is read only for the police
check, whose answer changes in a month that facts.json states.
"""
import re
from datetime import date, datetime, timedelta, tzinfo

# The lines of facts.json -> answers the gate reads. free_text_cover_letter is not a form answer: the letter is
# pasted from the queue entry itself.
KEYS = {'owner_answers', 'right_to_work', 'future_visa_sponsorship', 'sponsorship_free_text', 'notice_period', 'expected_salary',
        'expected_hourly_rate', 'drivers_licence', 'manual_licence', 'own_car_or_regular_access', 'white_card', 'police_check',
        'pre_employment_medical', 'drug_and_alcohol_screening', 'currently_studying', 'willing_to_relocate',
        'willing_to_travel_or_fifo', 'engineers_australia_membership_or_recognition', 'qualification_questions',
        'years_of_experience', 'software', 'experience_yes_no', 'english_self_rating', 'declarations_and_consents',
        'referees', 'identity.location', 'identity.name', 'identity.short_name', 'identity.email', 'identity.phone',
        'eligibility.availability', 'education'}
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
# A yes/no question that joins its subject to something else: 'and a current First Aid certificate', 'with comprehensive
# insurance', 'including night shifts'. Matched on the question with the subject's own words replaced by 'qq'.
JOIN = re.compile(r'(?:\b(?:and|plus|as well as|along with|together with|including|incl|with (?:a|an|comprehensive|current|valid|full|your|own|no))\b|[/&])'
                  r'\s*(?:(?:a|an|the|your|own|current|valid|full)\s+)*+(?!qq\b)[a-z]')
# The same join with the other requirement first: 'a First Aid certificate and a qq' (17 Nov 2026: 'Do you have a First Aid
# certificate and a White Card?' had been answered Yes from the White Card alone).
JOIN_BEFORE = re.compile(r'\b(?!(?:have|hold|possess|own|a|an|the|your|current|valid|full|you|do|are|is|and|or)\b)[a-z]+\s*'
                         r'(?:\b(?:and|plus|as well as)\b|[/&])\s*(?:(?:a|an|the|your|own|current|valid|full)\s+)*+qq\b')
# Something already done: facts.json records only willingness for medicals, tests, relocation and travel.
PAST = re.compile(r'^(?:have|has|had|did) you\b|\b(?:obtained|completed|undergone|undertaken|passed|relocated|travel+ed)\b')
OWN_COST = re.compile(r'own (?:cost|expense)|at (?:your|my|their) (?:own )?(?:cost|expense)|without (?:any )?(?:relocation )?(?:assistance|support|package|allowance)'
                      r'|self.?fund|(?:pay|paying) for|cover (?:the |your )?(?:cost|costs|expenses?)|no relocation (?:assistance|support|package|allowance)')
ABROAD = re.compile(r'overseas|international|abroad|outside (?:of )?australia|another country|new zealand')
NIGHT_SHIFT = re.compile(r'\bnight|\bshifts?\b')
NUMBER_WORD = r'(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|eighteen|twenty-four)'
MORE_NUMBERS = {'eleven': 11, 'twelve': 12, 'eighteen': 18, 'twenty-four': 24}

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


def plain_option(option, *heads):
    """True when an option says one of heads and nothing more: after norm, the head itself with nothing but punctuation
    after it ('Yes', 'Yes.', 'YES!'). An option that carries further words ('Yes, and I hold a forklift licence', 'No -
    but willing', 'Yes - 5+ years') says something facts.json may not hold, so it is never chosen."""
    o = norm(option)
    return any(re.fullmatch(re.escape(norm(h)) + r'[^\w]*', o) for h in heads)


def _choose(head, opts):
    """The one option that says head ('Yes' or 'No') and nothing more (plain_option); '' when not exactly one. With no
    options: head itself."""
    if not opts:
        return head
    hits = [o for o in opts if plain_option(o, head)]
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


def _first_sunday(year, month):
    day = date(year, month, 1)
    return day + timedelta(days=(6 - day.weekday()) % 7)


class MelbourneRule(tzinfo):
    """Australia/Melbourne by its rule, for a machine with no time zone data (Windows without the tzdata package):
    AEST, UTC+10, and AEDT, UTC+11, from 2 am on the first Sunday in October to 3 am on the first Sunday in April."""

    def _summer_utc(self, utc):
        """True when a UTC time (naive) falls in daylight saving: the changes are at 16:00 UTC the day before."""
        starts = datetime.combine(_first_sunday(utc.year, 10), datetime.min.time()) - timedelta(hours=8)
        ends = datetime.combine(_first_sunday(utc.year, 4), datetime.min.time()) - timedelta(hours=8)
        return utc >= starts or utc < ends

    def utcoffset(self, dt):
        if dt is None:
            return timedelta(hours=10)
        local = dt.replace(tzinfo=None)
        starts = datetime.combine(_first_sunday(local.year, 10), datetime.min.time()) + timedelta(hours=2)
        ends = datetime.combine(_first_sunday(local.year, 4), datetime.min.time()) + timedelta(hours=3)
        return timedelta(hours=11 if local >= starts or local < ends else 10)

    def dst(self, dt):
        return self.utcoffset(dt) - timedelta(hours=10)

    def tzname(self, dt):
        return 'AEDT' if self.dst(dt) else 'AEST'

    def fromutc(self, dt):
        utc = dt.replace(tzinfo=None)
        return (utc + timedelta(hours=11 if self._summer_utc(utc) else 10)).replace(tzinfo=self)


MELBOURNE_RULE = MelbourneRule()


def melbourne():
    """The Australia/Melbourne time zone: the tz database's, or MELBOURNE_RULE where this machine has none."""
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo('Australia/Melbourne')
    except Exception:  # no time zone data on this machine: the rule, never a fixed UTC+10
        return MELBOURNE_RULE


def _melbourne_today():
    return datetime.now(melbourne()).date()


def _also(q, pattern):
    """What a yes/no question asks for besides its subject ('and a current first' in 'do you hold a white card and a
    current first aid certificate'), or ''. pattern matches the subject's own words; several of them joined by 'and',
    '&', '/' or 'or' are one subject ('medical and drug and alcohol')."""
    rest = re.sub(r'\b(willing|able|prepared|happy|available)\s+and\s+(?:willing|able|prepared|happy|available)\b', r'\1', q)   # 'willing and able'
    rest = re.sub(r'\band\s*/\s*or\b', 'or', rest)   # 'and/or' offers a choice, it adds nothing
    rest = re.sub(r'(?:' + pattern + r')[\w-]*', ' qq ', rest)
    rest = re.sub(r'\bqq\b(?:\s*(?:and|&|/|or|,)\s*(?:(?:a|an|the|your)\s+)?qq\b)+', 'qq', rest)
    m = JOIN.search(rest) or JOIN_BEFORE.search(rest)
    return ' '.join(rest[m.start():].replace('qq', '...').split()[:6]) if m else ''


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


# A number right after one of these words is an identifier (a position, job or reference number), never pay.
ID_BEFORE = re.compile(r'(?:\bref(?:erence)?|\bno|\bnumber|\bnum|\bid|#|\bjob|\bposition|\bvacancy|\brequisition|\breq|\bcode|\bband'
                       r'|\blevel|\bgrade|\bclassification|\bpostcode)\W{0,3}$')


def money(text, marked_only=False):
    """The money figures in a text, in dollars: '$95k', '$70,000', '70000', '$60-65k'. A bare small number is not money,
    nor a bare number after ref, no., id, job, position and the like ('Position number 51234'), nor one of 7 or more
    digits. marked_only: only the figures written with $, k or a comma."""
    t = re.sub(r'(\d+)\s*(-|to)\s*(\d+)\s*k\b', r'\1k \2 \3k', norm(text))
    out = []
    for m in re.finditer(r'(\$)?\s?(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(k\b)?', t):
        dollar, digits, k = m.groups()
        amount = float(digits.replace(',', '')) * (1000 if k else 1)
        if dollar or k or ',' in digits:
            out.append(amount)
        elif not marked_only and 20000 <= amount < 1000000 and not ID_BEFORE.search(t[:m.start()]):
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

AGREE = ('yes', 'i agree', 'agree', 'i acknowledge', 'acknowledge', 'acknowledged', 'i consent', 'consent', 'i accept', 'accept',
         'i confirm', 'confirm', 'confirmed', 'true')
# Terms and conditions, of use or of anything else, are not among the declarations facts.json -> answers ->
# declarations_and_consents approves ('the terms of the Privacy Statement' are the privacy statement's own).
TERMS = re.compile(r'\bterms (?:and|&) conditions\b|\bterms of (?:use|service)\b|\bt ?& ?cs?\b|\bterms\b(?! of (?:the |this |our |your )?privacy)'
                   r'|\bconditions\b|\beula\b|user agreement')
# What else a declaration may ask that facts.json does not approve, besides the subjects _declaration names (17 Nov 2026):
# marketing in other words, passing his details on, a cost to him, a further assessment or agreement.
DECLARATION_MORE = re.compile(r'newsletter|subscri|promot|job alert|\balerts?\b|\bupdates?\b|talent (?:pool|community|network|bank|database)'
                              r'|mailing list|\bsms\b|text messages?|future (?:roles?|opportunit|positions?|vacanc|jobs?|employment)'
                              r'|other (?:roles?|opportunit|positions?|vacanc|jobs?|employers?)|contact(?:ed)? (?:me|you)\b|partners?\b|affiliat'
                              r'|related (?:bodies|body|entit|compan)|subsidiar|\bclients?\b|transferr?|\bsold\b|\bsell|passed (?:on )?to|\bgroup\b'
                              r'|\bcosts?\b|expense|\bfees?\b|\bpay\b|\bpaid\b|deduct|psychometric|aptitude|\bvideo|recording|biometric|\bai\b'
                              r'|artificial intelligence|automated|code of conduct|agreement|contract|non.?compete|restraint|probation'
                              r'|working with children|\bwwcc\b|vulnerable|job description|selection criteria')
# 'and (I) agree to', 'and to', 'and consent to' ...: the start of a further clause of a declaration.
DECLARATION_CLAUSE = re.compile(r'\band\s+(?:i\s+)?(?:also\s+)?(?=(?:agree|consent|accept|acknowledge|confirm|declare|certify|authori[sz]e'
                                r'|understand|undertake|will|to)\b)')
# A clause of these words only declares; it says nothing of its own.
DECLARING = {'i', 'we', 'also', 'hereby', 'have', 'read', 'and', 'understood', 'understand', 'accept', 'agree', 'acknowledge', 'consent',
             'confirm', 'declare', 'certify', 'authorise', 'authorize'}
# The words an approved declaration may hold (17 Nov 2026): the approved subjects, the words that declare them, the usual
# consequence of a false declaration ('... to the best of my knowledge, and that any incorrect or misleading information
# may lead to disqualification, or if appointed, to termination of employment') and the usual lead-in to a check ('Certain
# roles require a criminal history check to be performed as part of the recruitment process ... willing to participate').
# Any other word is something more ('I accept the Privacy Statement and agree to work weekends', '... of <employer>'):
# the owner's, whatever the options. A tick box ('checked') and an option repeating the declaration agree like 'I agree'.
DECLARATION_WORDS = {'i', 'we', 'you', 'us', 'do', 'please', 'a', 'an', 'have', 'read', 'and', 'understood', 'understand', 'accept', 'agree',
                     'to', 'with', 'acknowledge', 'consent', 'confirm', 'declare', 'certify', 'that', 'the', 'this', 'our', 'your', 'my', 'all',
                     'information', 'details', 'provided', 'given', 'supplied', 'submitted', 'in', 'application', 'is', 'true', 'correct',
                     'complete', 'accurate', 'privacy', 'policy', 'statement', 'notice', 'collection', 'reference', 'references', 'referee',
                     'check', 'checks', 'checking', 'qualification', 'qualifications', 'verification', 'police', 'national', 'conducting',
                     # the consequence of a false declaration
                     'best', 'of', 'knowledge', 'any', 'incorrect', 'false', 'inaccurate', 'misleading', 'may', 'lead', 'result', 'or', 'if',
                     'disqualification', 'appointed', 'termination', 'dismissal', 'employment',
                     # the lead-in to a check
                     'certain', 'role', 'roles', 'require', 'required', 'criminal', 'history', 'be', 'performed', 'as', 'part', 'recruitment',
                     'process', 'for', 'shortlisted', 'candidate', 'candidates', 'are', 'aware', 'willing', 'participate', 'needed'}
# The options that name his licence and nothing more: 'Full licence' and "Full driver's licence" say only what facts.json
# holds; 'Yes - full licence with own car and trailer licence' says more.
LICENCE_OPTIONS = ('yes', 'full', 'open', 'unrestricted', 'car', 'class c', 'automatic', 'full licence', 'full license',
                   "full driver's licence", "full driver's license", 'full drivers licence', 'full drivers license', 'open licence',
                   'open license', 'unrestricted licence', 'unrestricted license', 'car licence', 'car license', 'class c licence',
                   'class c license')
AUTOMATIC_OPTIONS = ('auto', 'automatic', 'automatic only', 'yes, automatic', 'yes automatic', 'yes, an automatic', 'yes, auto',
                     'yes, automatic only', 'automatic licence', 'automatic license')


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
    if not named and not TERMS.search(q):
        return None
    other = re.search(r'medical|health|drug|alcohol|disab|injur|criminal (record|history\b(?! (check|screen)))|convict|offen[cs]e'
                      r'|marketing|third.part|\bshar(e|ing)\b|disclos|overseas|outside australia|agency|represent|enlist|military'
                      r'|background check|credit|social media|\bever\b|suspend', q) or TERMS.search(q) or DECLARATION_MORE.search(q)
    if other:
        return _no(f'a declaration or consent facts.json does not approve ("{other.group(0)}")', 'answers.declarations_and_consents')
    # A further promise joined to an approved one ('I accept the Privacy Statement and agree to work weekends', '... and to
    # being contacted by recruiters'): every clause must name an approved subject (17 Nov 2026).
    clauses = [c for c in DECLARATION_CLAUSE.split(q) if not set(re.findall(r'[a-z]+', c)) <= DECLARING]   # 'I acknowledge and agree to ...'
    if not all(any(re.search(pattern, c) for pattern in subjects.values()) for c in clauses):
        return _no('a further declaration or consent is joined to an approved one: facts.json approves only the subjects it names',
                   'answers.declarations_and_consents')
    extra = sorted(set(re.findall(r'[a-z]+', q)) - DECLARATION_WORDS)
    if extra:
        return _no(f'the declaration holds more than the subjects facts.json approves ("{" ".join(extra[:4])}")',
                   'answers.declarations_and_consents')
    approved = re.split(r'any other', str(a.get('declarations_and_consents') or ''), flags=re.I)[0].lower()
    if not approved.startswith('yes') or not all(s.split()[0] in approved for s in named):
        return _no('facts.json -> answers -> declarations_and_consents does not approve this', 'answers.declarations_and_consents')
    if not opts:
        return _ok('Yes', 'answers.declarations_and_consents')
    # 'Yes, and I agree to receive marketing emails' is not one. A tick box ('checked') agrees, and so does an option whose
    # label is the declaration itself ('I accept the Privacy Statement': question and option the same words, in his own voice).
    own = re.match(r'i (acknowledge|consent|agree|declare|confirm|certify|understand|accept|authori[sz]e)\b', q)
    hits = [o for o in opts if plain_option(o, *AGREE, 'checked') or (own and norm(o).rstrip(' ?.:!') == q)]
    return _ok(hits[0], 'answers.declarations_and_consents') if len(hits) == 1 else _no('no single option agrees', 'answers.declarations_and_consents')


# Sponsorship (owner, 15 Nov 2026). facts.json -> answers -> future_visa_sponsorship holds the two answers as
# "'Do you need sponsorship to work now?': No" and "'Will you now or in the future require sponsorship?': Yes";
# sponsorship_free_text holds the free-text answer ("text") and what goes before it for a future question
# ("future_prefix"). A question asks about the future when it names a time to come (SPONSOR_FUTURE: 'now or in the
# future', 'at any time', 'long term', 'during your employment'), a time to come less plainly (SPONSOR_LATER: 'going
# to', 'anticipate', 'expect to', 'to remain in Australia', 'to continue working'; with now as well, two things at once:
# the owner's), or, naming no time and not now (SPONSOR_NOW: 'now', 'currently', 'to start'), when it asks 'will you' or
# 'would you'; a question that names now ('Will you need sponsorship to start?'), or a 'do you' or 'are you' question
# naming no time to come, asks about now. Options that name the future ('Yes, in the future') make a question about now
# one about both: it is answered as a future question. Only a question about his needing or requiring it (SPONSOR_NEED,
# SPONSOR_HIS) is his: 'Are you seeking sponsorship?' (he is) is not the same question, 'Does this role require
# sponsorship?' is not about him, and one with a negation ('able to work without sponsorship') reads the other way
# round: all go to the owner.
NOW_LINE = re.compile(r"sponsorship to work now\?'?\s*:\s*(no|yes)\b", re.I)
FUTURE_LINE = re.compile(r"in the future require sponsorship\?'?\s*:\s*(no|yes)\b", re.I)
SPONSOR_FUTURE = re.compile(r'future|later|at any (time|stage|point)|at some (point|stage)|going forward|ongoing|eventually|down the track|coming years'
                            r'|next \d|long.?term|permanent(ly)?|beyond|after (your|the|my) (current )?visa|end of|expir'
                            r'|during (your|the|my) (employment|engagement|time with us|contract)')
SPONSOR_LATER = re.compile(r'\bgoing to\b|\banticipat\w*|\bexpect\w*|\bforesee\w*|\benvisag\w*|\blikely\b|\bintend\w*|\bplan(?:s|ning)? to\b'
                           r'|\b(?:remain|stay|continu\w*|extend\w*|extension|renew\w*)\b')
SPONSOR_NOW = re.compile(r'\b(now|currently|at present|presently|right now|today|immediately|at (this|the) (time|moment))\b|\bto (start|commence)\b')
SPONSOR_NEED = re.compile(r'\b(require[sd]?|requiring|need(s|ed|ing)?|in need of)\b')
# His own need: 'you' in the question, or sponsorship 'required' or 'needed' ('Is sponsorship required?'), or his visa.
SPONSOR_HIS = re.compile(r'\byou\b|\bsponsor\w*\b[^?]*\b(?:required|needed|necessary)\b|\b(?:required|needed|necessary)\b[^?]*\bsponsor'
                         r'|\byour (?:current )?visa\b')
SPONSOR_NEGATED = re.compile(r"\b(not|without|no|never|nor|don't|doesn't|won't|isn't|aren't)\b")
SPONSOR_MODAL = re.compile(r'^(?:(?:if|when|as|where|should)\b[^,]*,\s*)?(will|would)\b|\b(will|would) you\b')
# His work rights in the same question ('Are you a citizen, PR, or do you require sponsorship?'): two things at once.
SPONSOR_WITH_RIGHTS = re.compile(r'citizen|permanent resid|\bpr\b|rights? to work|work(ing)? rights?|residency|entitled|eligib')
# Phrases of time or of the role that RTW_ELSEWHERE would read as another place ('in the future', 'in order to').
SPONSOR_NOT_A_PLACE = re.compile(r'\bin (?:the )?(?:near |foreseeable |coming |longer |long )?(?:future|term)\b|\bin (?:the )?(?:next|coming) (?:few |\d+ )?\w+'
                                 r'|\b(?:in|within) (?:the next )?(?:\d+|one|two|three|four|five|a few|a couple of) (?:years?|months?)(?: time)?\b'
                                 r'|\bin order to\b|\bin need of\b|\bin (?:this|that|the|your|our|a|any) (?:role|position|job|company|organisation|organization|team|business|capacity)\b')
# Someone else's sponsorship, or another country's: facts.json holds only his own, for Australia.
SPONSOR_SOMEONE_ELSE = re.compile(r'\b(?:partner|spouse|husband|wife|dependants?|dependents?|children|child|family|relatives?|someone else|anyone else|another person)\b'
                                  r'|\b(?:usa|u\.s\.a?|united states|america|uk|united kingdom|britain|new zealand|nz|canada|singapore|europe|eu|philippines)\b'
                                  r'|\bus (?:visa|work|employer|citizen)'   # 'US visa sponsorship', not 'for us' or 'sponsor us'
                                  r'|\bh-?1b\b|\bgreen card\b')   # United States visa words
# Free text: a question that also asks about the visa he holds, or a second question, is not answered by the free-text line.
SPONSOR_VISA_DETAIL = re.compile(r'visa (status|type|subclass|class|number|expir\w*|details?|conditions?|held)|(what|which) (type of )?visa|current visa|your visa\b(?! sponsor)')
SPONSOR_SECOND = re.compile(r'\b(?:and|or)\s+(?:do|does|are|is|will|would|can|could|have|has|what|which|when|how)\s+(?:you|your)\b')
# Options for a future question: one that says Yes, or Yes in the future, and nothing more (_future_yes); never one that
# says he needs it now.
FUTURE_MARK = re.compile(r'\b(future|later|eventually|after|beyond|long(er)?[ -]?term|down the track|at some (point|stage)|at a later (date|stage|time))\b')
NOT_NOW = re.compile(r"\b(?:but )?(?:i )?(?:do not|don't|dont|not|no)(?: need| require)?(?: it| sponsorship)?(?: right)? "
                     r"(?:now|currently|immediately|yet|at (?:the moment|present|this (?:time|stage)))\b")
FUTURE_OK_WORDS = {'in', 'the', 'near', 'future', 'later', 'at', 'a', 'some', 'point', 'stage', 'date', 'time', 'eventually', 'down', 'track',
                   'longer', 'long', 'term', 'after', 'my', 'current', 'visa', 'expires', 'expiry', 'ends', 'beyond', 'but', 'and', 'i', 'will',
                   'would', 'may', 'require', 'need', 'sponsorship', 'be', 'required', 'needed'}


def _future_yes(option):
    """True when an option says Yes, or Yes in the future, and nothing more: 'Yes', 'Yes, in the future', 'Yes, but not
    now', 'Not now, but in the future', 'In the future', 'Yes, after my current visa expires'. Never an option that says
    he needs it now ('Yes, now', 'Yes, now and in the future', 'Yes, I require sponsorship to start') or adds anything
    else ('Yes, 482 visa')."""
    t = ' '.join(re.sub(r"[^\w\s']", ' ', norm(option)).split())
    yes = bool(re.match(r'yes\b', t))
    rest = NOT_NOW.sub(' ', t[3:] if yes else t)
    if SPONSOR_NOW.search(rest) or (not yes and not FUTURE_MARK.search(rest)):
        return False
    return set(re.findall(r"[a-z0-9']+", rest)) <= FUTURE_OK_WORDS


def _says_now(option):
    """True when an option starts with Yes or says he needs it now (after 'not now' and the like are taken out)."""
    t = ' '.join(re.sub(r"[^\w\s']", ' ', norm(option)).split())
    return bool(re.match(r'yes\b', t) or SPONSOR_NOW.search(NOT_NOW.sub(' ', t)))


def _names_time(option):
    """True when an option names now, not now, or a time to come ('Not now, but maybe later', 'I don't require it now'):
    beside it a plain 'Yes' could mean now."""
    t = ' '.join(re.sub(r"[^\w\s']", ' ', norm(option)).split())
    return bool(SPONSOR_NOW.search(t) or FUTURE_MARK.search(t) or NOT_NOW.search(t))


def _sponsorship(q, opts, a):
    """See the notes above NOW_LINE. Present: the plain No option ('Do you need sponsorship to work now?' in facts). Future:
    the one option _future_yes reads as Yes, or Yes in the future ('Will you now or in the future require sponsorship?');
    a plain 'Yes' beside another Yes option (except one 'Yes, in the future' style option, which is then his), or beside
    one that says now or names a time, is the owner's. A question about now with an option that names the future is
    answered as a future question. Free text: the owner's own words (sponsorship_free_text), after future_prefix for a
    future question. Someone else's sponsorship, another country's, or his work rights in the same question:
    unanswered. A facts line that is a plain answer of its own (no NOW_LINE, no FUTURE_LINE) answers a future question
    as it stands, as before 15 Nov 2026."""
    basis = 'answers.future_visa_sponsorship'
    line = str(a.get('future_visa_sponsorship') or '')
    place = SPONSOR_NOT_A_PLACE.sub(' ', q)
    if RTW_ELSEWHERE.search(place) or SPONSOR_SOMEONE_ELSE.search(place):
        return _no("someone else's sponsorship, or sponsorship somewhere other than Australia: facts.json -> answers -> "
                   'future_visa_sponsorship holds only his own, for Australia', basis)
    if SPONSOR_WITH_RIGHTS.search(q):
        return _no('asks about his work rights together with sponsorship: two things at once', basis)
    names_now = bool(SPONSOR_NOW.search(q))
    if not SPONSOR_FUTURE.search(q) and SPONSOR_LATER.search(q) and names_now:
        return _no(f'names now and a time to come ("{SPONSOR_LATER.search(q).group(0)}") without saying which it asks about: the owner\'s', basis)
    future = bool(SPONSOR_FUTURE.search(q) or SPONSOR_LATER.search(q)) or (not names_now and bool(SPONSOR_MODAL.search(q)))
    if not yes_no_question(q):
        return _sponsorship_free_text(q, opts, a, future, line)
    if SPONSOR_NEGATED.search(q) or not SPONSOR_NEED.search(q):
        return _no('a sponsorship question that does not plainly ask whether he needs or requires it (a negation, seeking, eligible): '
                   "the owner's", basis)
    if not SPONSOR_HIS.search(q):
        return _no("a sponsorship question that is not about his own need ('Does this role require sponsorship?'): the owner's", basis)
    if not future and any(FUTURE_MARK.search(norm(o)) for o in opts):
        future = True   # 'Yes, in the future' on screen: a plain No would say never, so the options decide (as a future question)
    now, later = NOW_LINE.search(line), FUTURE_LINE.search(line)
    if future:
        if not now and not later and _settled(line, q) and line.strip():
            return _plain_line(a, 'future_visa_sponsorship', q, opts)   # a plain line of its own, as before 15 Nov 2026
        if not later or not _settled(line, q):
            return _no('future sponsorship: facts.json -> answers -> future_visa_sponsorship leaves it to the owner', basis)
        head = later.group(1).capitalize()
        if head != 'Yes':
            pick = _choose(head, opts)
            return _ok(pick, basis) if pick else _no(f'no single option says {head}', basis)
        if not opts:
            return _ok('Yes', basis)
        hits = [o for o in opts if _future_yes(o)]
        marked = [o for o in hits if not plain_option(o, 'Yes')]
        if len(hits) == 2 and len(marked) == 1:
            hits = marked   # 'Yes' beside 'Yes, in the future': the plain Yes then means now, the other is his
        if len(hits) != 1:
            return _no('no single option says Yes, or Yes in the future, and nothing more (never one that says he needs it now)', basis)
        others = [o for o in opts if o is not hits[0] and (_says_now(o) or _names_time(o))]
        if others and plain_option(hits[0], 'Yes'):
            return _no(f'a plain Yes beside another option that differs on now or the future ("{others[0]}"): the owner\'s', basis)
        return _ok(hits[0], basis)
    lead = re.search(r'^(?:(?:if|when|as|where|should)\b[^,]*,\s*)?(do|does|are|is|will|would)\b', _last(q))
    if not now or not lead or (lead.group(1) in ('will', 'would') and not names_now):
        return _no('a sponsorship question facts.json does not answer', basis)
    pick = _choose(now.group(1).capitalize(), opts)
    return _ok(pick, basis) if pick else _no(f'no single option says {now.group(1).capitalize()}', basis)


def _sponsorship_free_text(q, opts, a, future, line):
    """A free-text sponsorship question ('Please outline your visa sponsorship requirements'): the owner's own words in
    facts.json -> answers -> sponsorship_free_text -> text; for a future question future_prefix goes first, and only
    while future_visa_sponsorship says Yes for the future. With options on screen, a question about the visa he holds or a
    second question in it: unanswered."""
    basis = 'answers.sponsorship_free_text'
    rule = a.get('sponsorship_free_text') if isinstance(a.get('sponsorship_free_text'), dict) else {}
    text = str(rule.get('text') or '').strip()
    if opts:
        return _no('a sponsorship question with options that is not a yes or no question: the owner\'s', basis)
    if SPONSOR_VISA_DETAIL.search(q) or SPONSOR_SECOND.search(q):
        return _no('asks about the visa he holds, or a second question, besides sponsorship', basis)
    if not text or not _settled(text, q):
        return _no('facts.json -> answers -> sponsorship_free_text has no text', basis)
    if not future:
        return _ok(text, basis)
    later = FUTURE_LINE.search(line)
    prefix = str(rule.get('future_prefix') or '')
    if not later or later.group(1).lower() != 'yes' or not prefix.strip() or not _settled(line, q):
        return _no('future sponsorship: facts.json -> answers -> future_visa_sponsorship and sponsorship_free_text -> future_prefix '
                   'do not give it', basis)
    return _ok(prefix.rstrip() + ' ' + text, basis)


# The plain yes/no work-rights questions, as the whole question (q, without its closing ?.:!). Anything more ('unrestricted',
# 'without restriction', 'for the next 5 years', a citizen or permanent resident question that does not name Australia)
# is not one of them and goes on to the rule below.
RTW_YES = re.compile(r"(?:do|does) you (?:currently )?(?:have|hold) (?:the |a )?(?:legal )?right to work in australia"
                     r"|do you (?:currently )?(?:have|hold) (?:full )?work(?:ing)? rights in australia")
_CITIZEN = r"(?:an? )?(?:australian )?citizen(?: of australia)?"
_RESIDENT = r"(?:an? )?(?:australian )?(?:permanent resident|pr)(?: of australia)?"
RTW_CITIZEN_OR_PR = re.compile(rf"are you {_CITIZEN} or {_RESIDENT}|are you {_RESIDENT} or {_CITIZEN}")


def _right_to_work_yes_no(q, opts, rule):
    """'Do you have the right to work in Australia?' (and 'the legal right', 'full working rights'): Yes, as
    right_to_work.free_text says full working rights. 'Are you an Australian citizen or permanent resident?' (or PR, in
    either order): No, as right_to_work.never_choose names both. Only with the options on screen and only a plain Yes
    or No option; None when the question is not one of these, or no such option is there (the rule below then reads
    the options)."""
    if not opts:
        return None
    if RTW_YES.fullmatch(q) and re.search(r'full working rights', str(rule.get('free_text') or ''), re.I):
        pick = _choose('Yes', opts)
    elif RTW_CITIZEN_OR_PR.fullmatch(q) and 'australia' in q:
        never = ' '.join(str(x) for x in rule.get('never_choose') or []).lower()
        pick = _choose('No', opts) if 'citizen' in never and 'permanent resident' in never else ''
    else:
        return None
    return _ok(pick, 'answers.right_to_work') if pick else None


# The words a right-to-work option may hold to be chosen: the visa itself and nothing more (as plain_option for Yes/No).
# 'Temporary Graduate visa (485)', 'I have a graduate temporary work visa' and 'Temporary visa with full working rights'
# say only what facts.json holds. An option that adds anything (how long it has left, 'no sponsorship now or in the
# future', 'and have applied for permanent residency', a stream, a Yes) is never chosen: the question is unanswered.
_RTW_COMMON = {'i', 'im', 'am', 'have', 'hold', 'a', 'an', 'the', 'on', 'currently', 'holder', 'my', 'of', 'visa', 'temporary',
               'work', 'working', 'with', 'full', 'rights', 'right', 'to', 'in', 'australia', 'no', 'restriction', 'restrictions',
               'without', 'unrestricted'}
RTW_GRADUATE_WORDS = _RTW_COMMON | {'graduate', 'subclass', 'sc', '485', 'tgv'}
RTW_FREE_WORDS = _RTW_COMMON | {'e', 'g', 'eg', 'doctoral', 'student'}   # SEEK's 'I have a temporary visa with no restrictions (e.g. doctoral student)'
# The words of an option that says only that he holds a temporary visa or temporary working rights ('I have temporary
# working rights', 'Temporary visa'): no Yes or No, no restriction, time, stream or sponsorship. Chosen only when no option
# names the graduate visa or an unrestricted temporary visa, it is the one option that says temporary, and no other
# option names a restriction or limit (the form would then split temporary rights, and this one does not say which).
RTW_TEMPORARY_WORDS = {'i', 'im', 'am', 'have', 'hold', 'a', 'an', 'the', 'on', 'currently', 'holder', 'my', 'of', 'visa',
                       'temporary', 'work', 'working', 'with', 'rights', 'right', 'to', 'in', 'australia'}
RTW_RESTRICTION = re.compile(r'restrict|limit|condition|\bhours?\b|part.?time|\bcap(ped)?\b')
# A work-rights question about somewhere other than Australia ('in New Zealand', 'in the UK', 'overseas', 'in Australia
# and New Zealand') or about someone else ('your partner'): facts.json -> answers -> right_to_work holds only his own
# Australian work rights. 'In Australia' and 'in the country you are applying to' are his.
RTW_ELSEWHERE = re.compile(r"\b(?:in|within) (?!australia\b(?!\s*(?:and|or|&|/|,)\s*\w))(?!(?:the|this|that|your) country\b)"
                           r"|\b(?:overseas|abroad|outside|elsewhere|another country|other countries)\b"
                           r"|\b(?:your|his|her|their) (?:partner|spouse|husband|wife|dependants?|dependents?|children|child|family)\b")


def _rtw_words(option):
    return set(re.findall(r'[a-z0-9]+', norm(option).replace("'", '')))


def _says_restricted(option):
    """True when an option says restrictions apply ('485 visa with restrictions'); 'no restrictions', 'without
    restrictions' and 'unrestricted' do not."""
    return bool(re.search(r'\brestrict', re.sub(r'\b(?:no|without)(?: \w+)? restrictions?\b', ' ', norm(option))))


def _plain_temporary(opts):
    """[the option] when exactly one option says temporary, it holds only RTW_TEMPORARY_WORDS, and no other option names a
    restriction or limit; [] otherwise."""
    temporary = [o for o in opts if re.search(r'\btemporary\b', norm(o))]
    if len(temporary) != 1 or any(RTW_RESTRICTION.search(norm(o)) for o in opts if o is not temporary[0]):
        return []
    return temporary if _rtw_words(temporary[0]) <= RTW_TEMPORARY_WORDS else []


def _right_to_work(q, opts, a):
    rule = a.get('right_to_work') or {}
    if RTW_ELSEWHERE.search(q):
        return _no("work rights somewhere other than Australia, or someone else's: facts.json -> answers -> right_to_work holds only his "
                   'own Australian work rights', 'answers.right_to_work')
    if not opts:
        free = rule.get('free_text')
        return _ok(free, 'answers.right_to_work.free_text') if free else _no('facts.json -> answers -> right_to_work has no free_text', 'answers.right_to_work')
    plain = _right_to_work_yes_no(q, opts, rule)
    if plain:
        return plain
    if not rule.get('choose'):
        return _no('facts.json -> answers -> right_to_work has no rule for choosing', 'answers.right_to_work')
    named = [o for o in opts if re.search(r'graduate|\b485\b', norm(o))]
    if named:   # the form offers the graduate visa: only an option that says that and nothing more, never another one instead
        pick = [o for o in named if _rtw_words(o) <= RTW_GRADUATE_WORDS and not _says_restricted(o)]
        if len(pick) != 1:
            return _no('no single option names the temporary graduate visa (Subclass 485) and nothing more (an option that adds a '
                       'time left, sponsorship, residency or anything else is not chosen)', 'answers.right_to_work.choose')
        return _ok(pick[0], 'answers.right_to_work.choose')
    free = [o for o in opts if re.search(r'temporary', norm(o)) and re.search(r'no restrictions?|without restrictions?|unrestricted|full work(ing)? rights', norm(o))
            and not re.search(r'restrictions? on|restricted (to|by|on)|limited|holiday|partner|family|bridging', norm(o)) and _rtw_words(o) <= RTW_FREE_WORDS]
    if not free:   # 15 Nov 2026 (TTW): 'I have temporary working rights', the one temporary option, naming no restriction
        free = _plain_temporary(opts)
    if len(free) != 1:
        return _no('no single option names the temporary graduate visa (Subclass 485) or a temporary visa with no restriction, and '
                   'nothing more', 'answers.right_to_work.choose')
    return _ok(free[0], 'answers.right_to_work.choose')


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


# pay as an entry or a caller gives it when the advert states no pay at all.
NO_PAY = re.compile(r"(?:pay |salary )?(?:not stated|none( stated)?|no pay( stated)?|no salary( stated)?|not given|not shown|not advertised)\.?")
PAY_UNKNOWN = ("the advert's pay is not recorded (advert_pay): give the advert's own pay text, or \"not stated\" when the "
               "advert gives none, as advert_pay (queue.py answer --from-file, the file written with <<'EOF', quoted)")


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
    if pay is None or not str(pay).strip():
        return _no(PAY_UNKNOWN, 'answers.expected_salary.rule')
    if not NO_PAY.fullmatch(norm(pay)):
        annual = [x for x in money(pay, marked_only=True) if x >= 20000] or [x for x in money(pay) if x >= 20000]
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
        # Owner, 14 Nov 2026: when the options split the band, choose the option that starts at the figure the rule
        # names ("choose the option that starts at $70,000"); with an advertised range, the option that starts at
        # its lower end. Only an option that starts exactly there counts.
        starts = re.search(r'starts at \$([\d,]+)', rule)
        point = figure if figure else (float(starts.group(1).replace(',', '')) if starts else None)
        split = [o for o, r in ranges if r and point is not None and r[0] == point]
        if starts and len(split) == 1 and len([o for o, r in ranges if r and r[0] <= point <= r[1]]) >= 2:
            return _ok(split[0], 'answers.expected_salary.rule')
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
            hits = [o for o in opts if plain_option(o, *AUTOMATIC_OPTIONS)]
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
    hits = [o for o in opts if plain_option(o, *LICENCE_OPTIONS)]   # only his licence, nothing more
    return _ok(hits[0], 'answers.drivers_licence') if len(hits) == 1 else _no('no single option is his full licence', 'answers.drivers_licence')


def _months_back(day, months):
    """The date months calendar months before day (the last day of the month when that day does not exist)."""
    y, m = divmod(day.year * 12 + day.month - 1 - months, 12)
    m += 1
    last = (date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)).day
    return date(y, m, min(day.day, last))


def _police_window(q):
    """The time a police check question asks about: ('months', [N, ...]), ('year', YYYY), ('unread', '') for a window that
    cannot be read ('recent', 'or later'), or None when it names none."""
    if re.search(r'\b(?:or (?:later|after|newer|earlier)|since|after|before|prior to)\b', q):
        return ('unread', '')
    months = []
    for n, unit in re.findall(NUMBER_WORD + r'[\s-]*(months?|years?|yrs?)\b', q):
        count = int(n) if n.isdigit() else NUMBERS.get(n) or MORE_NUMBERS.get(n)
        months.append(count * (1 if unit.startswith('month') else 12))
    if re.search(r'\b(?:last|past|previous) (?:calendar )?year\b|\bwithin (?:a|one|the) year\b|\bless than (?:a|one) year\b|\byear old\b', q):
        months.append(12)
    if months:
        return ('months', months)
    year = re.search(r'\b(?:issued|dated|obtained|completed|done|from|in)\s+(?:in\s+)?((?:19|20)\d\d)\b', q)
    if year:
        return ('year', int(year.group(1)))
    if re.search(r'\brecent|\bwithin\b|\bin the (?:last|past)\b|\bless than\b|\bold\b|\bup to date\b|\bup-to-date\b', q):
        return ('unread', '')
    return None


def _police_by_date(window, issued, today):
    """'Yes' when the check issued in the month issued (year, month) falls inside the window for certain, 'No' when it
    falls outside it for certain, '' on the edge or for an unread window."""
    first = date(issued[0], issued[1], 1)
    last = _months_back(date(issued[0] + (issued[1] == 12), issued[1] % 12 + 1, 1), 0) - timedelta(days=1)
    kind, value = window
    if kind == 'year':
        return 'Yes' if value == issued[0] else 'No'
    if kind != 'months':
        return ''
    found = set()
    for n in value:
        cutoff = _months_back(today, n)
        found.add('Yes' if first >= cutoff else 'No' if last < cutoff else '')
    return found.pop() if len(found) == 1 else ''


def _police(q, opts, a, today):
    value = str(a.get('police_check') or '')
    if not _settled(value, q) or not _head(value):
        return _no('facts.json -> answers -> police_check does not settle this', 'answers.police_check')
    if not yes_no_question(q):
        return _no('not a yes/no question about the police check', 'answers.police_check')
    sentences = re.split(r'(?<=\.)\s+', value)
    said = next((s for s in sentences if re.search(r'for employment|within the last', s, re.I)), '')
    extra = re.search(r"'([^']+)'", said)
    no_free = 'No.' + (f' {extra.group(1)}' if extra else '')
    window = _police_window(q)
    when = today or _melbourne_today()
    if re.search(r'willing|prepared|happy to|consent|agree to|able to obtain|undergo|undertake|complete|obtain|participate', q) and not PAST.search(q):
        if not re.search(r'willing to (obtain|get)', value, re.I):
            return _no('facts.json -> answers -> police_check does not say he is willing to obtain one', 'answers.police_check')
        head, free = 'Yes', 'Yes'
    elif re.search(r'for employment|employment purposes|for (?:a|an|this|the) (?:job|role|position|employer)', q):
        if not re.search(r'\((no)\)|:\s*(no)\b', said, re.I):
            return _no('facts.json -> answers -> police_check says nothing about a check for employment', 'answers.police_check')
        head, free = 'No', no_free
    elif window:
        issued = re.search(r'\b(' + '|'.join(MONTHS) + r') ((?:19|20)\d\d)\b', sentences[0], re.I)
        if not issued:
            return _no('facts.json -> answers -> police_check does not give the month the check was issued', 'answers.police_check')
        head = _police_by_date(window, (int(issued.group(2)), MONTHS.index(issued.group(1).lower()) + 1), when)
        if not head:
            return _no('asks about a time window facts.json cannot settle (unreadable, or on the edge of the month of issue)', 'answers.police_check')
        free = sentences[0].rstrip('.') if head == 'Yes' else no_free
    elif PAST.search(q) and not re.search(r'\b(current|valid)\b', q):
        return _no('asks about a check already done, with no time or purpose facts.json can settle', 'answers.police_check')
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
    if PAST.search(q):
        return _no('asks whether he has done a medical or test; facts.json records only that he is willing', 'answers.pre_employment_medical')
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
    found = []   # (head, basis, part) of each alternative the question names
    # 'X / Y' is one field (SEEK's 'engineering drafting / engineering design'): every part must say the same.
    # 'X, Y or Z' offers alternatives: one Yes is enough.
    every = '/' in m.group('x')
    for part in (p.strip() for p in re.split(r'\s*/\s*' if every else r'\s*(?:,|\band/or\b|\bor\b)\s*', m.group('x')) if p.strip()):
        part = re.sub(r'^(an?|the) ', '', part)
        if re.search(r'equivalent|related|similar|^other\b', part):
            found.append(('', '', part))
        elif part in names and not (degree and not re.search(r'bachelor|degree', str(known[names[part]]), re.I) and names[part] not in ('engineering', 'civil engineering')):
            found.append((_head(known[names[part]]), 'answers.qualification_questions.' + names[part], part))
        elif other not in known:
            found.append(('', '', part))
        elif len(part.split()) > 1 and any(re.search(r'\b' + re.escape(part) + r'\b', h) for h in held) and not degree:
            found.append(('Yes', 'answers.qualification_questions.' + other, part))   # named, whole, in the title of one he holds
        elif words(part) and not words(part) & words(' '.join(held + [k for k in known if k != other])):
            found.append(('No', 'answers.qualification_questions.' + other, part))    # nothing he holds shares a word with it
            # (17 Nov 2026: nor a field qualification_questions answers: 'a qualification in drafting' is not No)
        else:
            found.append(('', '', part))   # shares a word with his own ('science', 'construction management'): not guessed
    yes = [(b, p) for h, b, p in found if h == 'Yes']
    if every and not all(h == 'Yes' for h, _, _ in found):
        yes = []
    if yes:
        head, basis = 'Yes', yes[0][0]
    elif found and all(h == 'No' for h, _, _ in found):
        head, basis = 'No', found[0][1]
    else:
        return _no('a qualification facts.json -> answers -> qualification_questions does not name', 'answers.qualification_questions')
    if not yes_no_question(q):
        return _no('not a yes/no question', basis)
    pick = _choose(head, opts)
    if not pick and head == 'Yes' and opts:   # 'Yes, Certificate I' ... 'Yes, Bachelor Degree': the level of the one he holds
        pick = _level_option(yes, known, facts, opts)
        if not pick and any(_option_level(o) for o in opts):
            return _no('the options are qualification levels, and no single one is the level of the qualification he holds '
                       '(facts.json -> education): never a higher or a lower one', basis)
    if not pick:
        return _no(f'no single option says {head}', basis)
    value = str(known.get(basis.rsplit('.', 1)[1], '')) if basis.endswith(tuple(known)) else ''
    return _ok(pick if opts else (value if _head(value) == head and value.startswith(head + ':') else head), basis)


# Qualification levels as a form lists them after 'Yes, ' (SEEK: 'Yes, Certificate I' ... 'Yes, Doctoral Degree'), lowest
# first. An option is a level only when its words, after a leading Yes, are one of these and nothing more.
LEVELS = [('certificate i', r'certificate (?:i|1)'), ('certificate ii', r'certificate (?:ii|2)'),
          ('certificate iii', r'certificate (?:iii|3)'), ('certificate iv', r'certificate (?:iv|4)'), ('diploma', r'diploma'),
          ('advanced diploma', r'advanced diploma'), ('associate degree', r'associate degree'),
          ('bachelor', r"bachelor(?:'?s)?(?: degree)?"),
          ('honours', r"bachelor(?:'?s)?(?: degree)? ?\(?(?:with )?honou?rs\)?|honou?rs(?: degree)?"),
          ('graduate certificate', r'graduate certificate'), ('graduate diploma', r'graduate diploma'),
          ('master', r"master(?:'?s)?(?: degree)?"), ('doctoral', r'doctoral(?: degree)?|doctorate|ph\.? ?d')]


def _option_level(option):
    """The level an option names and nothing more ('Yes, Bachelor Degree' -> 'bachelor'), or None."""
    o = re.sub(r'^yes\b[\s,.:;-]*', '', norm(option)).rstrip(' .')
    return next((name for name, pattern in LEVELS if re.fullmatch(pattern, o)), None)


def _title_level(title):
    """The level of a qualification he holds, from its title in facts.json -> education ('Bachelor of Science in Civil
    Engineering (BSCE)' -> 'bachelor'), or None."""
    t = norm(title)
    for name, pattern in reversed(LEVELS):
        if re.match(r'(?:' + pattern + r')\b', t):
            return 'honours' if name == 'bachelor' and re.search(r'honou?rs', t) else name
    return None


def _level_option(yes, known, facts, opts):
    """The one option naming the level of his highest qualification behind a Yes, or ''. yes: (basis, part) of each Yes the
    question got; a qualification in facts.json -> education is behind it when its title holds the field asked
    ('engineering' in 'Bachelor of Science in Civil Engineering') or the qualification_questions line names it. Only the
    level he holds: a lower one ('Yes, Diploma') is not what he has, a higher one ('Masters Degree') is not true."""
    ranks = [name for name, _ in LEVELS]
    held = []
    for basis, part in yes:
        line = norm(known.get(basis.rsplit('.', 1)[1], ''))
        for e in facts.get('education') or []:
            title = norm(e.get('qualification'))
            bare = re.sub(r'\s*\([^)]*\)', '', title)
            if title and (re.search(r'\b' + re.escape(part) + r'\b', title) or (bare and bare in line)):
                held.append(_title_level(title))
    if not held or None in held:
        return ''
    top = max(held, key=ranks.index)
    hits = [o for o in opts if _option_level(o) == top]
    return hits[0] if len(hits) == 1 else ''


# 'Do you have a Certificate III in Laboratory Skills?' (17 Nov 2026). No only to a formal credential the question names in
# one of two shapes, every alternative ('X or Y') on its own:
#  - a qualification with a field of its own, '<level> in/of <field>' ('a Certificate III in Laboratory Skills', 'a Diploma
#    of Surveying'), the field sharing no word with what he holds (_held_words); or a Masters or doctoral degree when
#    facts.json -> education holds nothing at that level;
#  - a licence or ticket TICKETS names ('a forklift licence', 'a First Aid certificate') that facts.json does not mention.
# Never this rule's (the owner's): a credential described rather than named ('an overseas degree', 'a STEM degree', 'a 4
# year degree', 'a site safety ticket', 'an AQF certificate'), an abbreviation or unit code (BSc, Adv Dip, CIC,
# CPCWHS1001, WWCC, NPC), a document that is no qualification (an English test, a vaccination, birth or insurance
# certificate), a level with no field ('a Diploma', 'a Bachelor degree'), Honours, a driving licence of any class (HR, MR,
# truck: facts.json does not record his licence class), an alternative left open, experience, skills or software.
CREDENTIAL_ASK = re.compile(r'do you (?:currently )?(?:have|hold|possess) (?P<x>.+)')
CREDENTIAL_PREFIX = r'(?:(?:a|an|the|current|valid|completed)\s+)*'
QUALIFICATION_NAMED = re.compile(
    CREDENTIAL_PREFIX + r"(?P<level>cert(?:ificate)?\.? ?(?:iv|i{1,3}|[1-4])|advanced diploma|diploma|associate degree"
    r"|graduate (?:certificate|diploma)|bachelor(?:'?s)?(?: degree)?|master(?:'?s)?(?: degree)?|doctoral degree|doctorate|ph\.? ?d)"
    r"(?: (?:in|of) (?P<field>[a-z]+(?: (?:[a-z]+|&)){0,6}))?(?: \((?P<code>[a-z]{2,6}\d{3,6})\))?")
# Licences and tickets a form may name that are formal credentials and none of his (a site, plant or laboratory ticket).
TICKETS = (r'(?:provide |senior |basic )?first aid(?: and cpr)?|cpr|forklift|confined spaces?(?: entry)?|(?:working|work) (?:safely )?at heights?'
           r'|heights|elevated work(?:ing)? platform|ewp|boom lift|scissor lift|dogging|rigging|scaffolding|crane|asbestos(?: removal| awareness)?'
           r'|gas test(?:ing)?(?: of)? atmospheres|nuclear (?:gauge|densometer|(?:moisture )?density gauge)|radiation(?: safety| use| user)?'
           r'|traffic (?:control|management)(?: implementation)?|excavator|skid steer|backhoe|front end loader|roller|grader|dozer|high risk work')
TICKET_NAMED = re.compile(CREDENTIAL_PREFIX + r'(?P<ticket>' + TICKETS + r') (?:licen[cs]e|ticket|certificate|certification|card|accreditation)'
                          r'(?: \((?P<code>[a-z]{2,6}\d{0,6})\))?')
# Words a field may not hold: an open or described field ('a related field', 'an accredited ...'), a second item, a place.
FIELD_STOP = {'a', 'an', 'the', 'or', 'any', 'other', 'related', 'relevant', 'similar', 'equivalent', 'field', 'fields', 'discipline',
              'disciplines', 'area', 'areas', 'appropriate', 'suitable', 'recognised', 'recognized', 'accredited', 'australian', 'australia',
              'overseas', 'international', 'foreign', 'higher', 'above', 'etc', 'from', 'with', 'at', 'by', 'for', 'like', 'such', 'as',
              'eg', 'ie', 'including', 'plus', 'minimum', 'least', 'licence', 'license', 'ticket', 'certificate', 'card', 'degree', 'diploma',
              'software', 'computer', 'autodesk', 'microsoft', 'cad'}
# Fields next to his own (Bachelor of Science in Civil Engineering; Advanced Diploma of Civil Construction Design): a
# qualification in one of them is never answered No here.
HELD_FIELD_KIN = {'engineering', 'engineer', 'civil', 'construction', 'design', 'drafting', 'science', 'infrastructure', 'cad'}
# The unit code of the White Card (Construction Induction).
WHITE_CARD_CODE = re.compile(r'cpcc?whs1001')
CREDENTIAL_NOT_THIS = re.compile(r'equivalent|related|similar|\bor (?:higher|above|other|more)\b|\bhigher\b|\babove\b|experience|knowledge'
                                 r'|understanding|familiar|abilit|skills? (?:in|with|to)\b|software|\bcad\b|autodesk|microsoft|\boffice\b'
                                 r'|\b(?:or|and) (?:are|do|would|will|can|could|have|has|is|if)\b|willing|prepared|happy to|able to|obtain'
                                 r'|toward|studying|enrol|progress|intend|plan(?:ning)? to|\bget\b|\bif not\b')
# A driving licence in other words ('a manual licence', 'a full licence', 'a C class licence', 'a NSW licence', 'an HR
# licence'): the licence rule's subject, never this one's.
DRIVING = re.compile(r'driv|\bcar\b|vehicle|\bclass\b|\bmanual\b|\bauto(?:matic)?\b|\bfull\b|\bopen\b|unrestricted|provisional|probationary'
                     r'|learner|\bp ?plates?\b|\bp[12]\b|motor|victorian|\bvic\b|australian|heavy|truck|rigid|combination|\bbus\b'
                     r'|\b(?:hr|mr|hc|lr|mc)\b|' + STATES)


def _held_text(facts, a):
    """Everything facts.json says he holds or has done, as one lower-case text: education (titles, codes, points),
    eligibility, and the names of the answers and of the fields answers -> qualification_questions answers."""
    parts = []
    for e in facts.get('education') or []:
        parts += [str(e.get('qualification') or ''), str(e.get('code') or ''), ' '.join(str(p) for p in e.get('points') or [])]
    for value in (facts.get('eligibility') or {}).values():
        parts += [str(v) for v in value] if isinstance(value, list) else [str(value)]
    parts += [k.replace('_', ' ') for k in a if not k.startswith('_')]
    parts += [k for k in (a.get('qualification_questions') or {}) if not k.startswith('_')]
    return norm(' '.join(parts))


def _stems(text):
    return {w[:-1] if len(w) > 4 and w.endswith('s') else w for w in re.findall(r'[a-z0-9]+', text)}


def _held_words(facts, a):
    """The words of what he holds, for a field: his qualification titles and codes, his licence, White Card, Working with
    Children Check and police check in eligibility, the fields answers -> qualification_questions answers, and the fields
    next to his own (HELD_FIELD_KIN)."""
    e = facts.get('eligibility') or {}
    texts = [str(x.get('qualification') or '') + ' ' + str(x.get('code') or '') for x in facts.get('education') or []]
    texts += [str(e.get(k) or '') for k in ('drivers_licence', 'drivers_licence_detail', 'white_card', 'wwcc', 'police_check')]
    texts += [k for k in (a.get('qualification_questions') or {}) if not k.startswith('_') and k != 'any other named qualification']
    return _stems(norm(' '.join(texts))) | HELD_FIELD_KIN


def _not_held(part, facts, a):
    """True when part names one formal credential he clearly does not hold (see above), else False."""
    ranks = [name for name, _ in LEVELS]
    m = QUALIFICATION_NAMED.fullmatch(part)
    if m:
        level = re.sub(r'^cert(?:ificate)?\.? ?', 'certificate ', m.group('level'))
        level = next((name for name, pattern in LEVELS if re.fullmatch(pattern, level)), None)
        code, field = m.group('code'), m.group('field') or ''
        if not level or (code and (code in _held_text(facts, a) or WHITE_CARD_CODE.fullmatch(code))):
            return False
        held = [_title_level(str(e.get('qualification') or '')) for e in facts.get('education') or []]
        if level in ('master', 'doctoral'):   # a level above every one he holds: whatever its field
            return not any(h is None or ranks.index(h) >= ranks.index(level) for h in held) and \
                not any(re.search(r'master|doctor|ph\.? ?d', norm(e.get('qualification'))) for e in facts.get('education') or [])
        words = field.split()
        if not words or set(words) & FIELD_STOP or OFFICE_PRODUCTS.search(field) or (_stems(field) - {'and'}) & _held_words(facts, a):
            return False
        return not any(re.search(r'(?<![a-z0-9])' + re.escape(t.lower()) + r'(?![a-z0-9])', field) for t in KNOWN_TOOLS + sorted(HIS_TOOLS))
    m = TICKET_NAMED.fullmatch(part)
    if m:
        text, code = _held_text(facts, a), m.group('code')
        if re.search(r'\b(?:' + TICKETS + r')\b', text) or (code and (code in text or WHITE_CARD_CODE.fullmatch(code))):
            return False
        return True
    return False


def _credential_not_held(q, opts, a, facts):
    """No to 'Do you have / hold <a formal credential he clearly does not hold>?' (see above) when facts.json lists his
    credentials completely (answers -> qualification_questions -> 'any other named qualification': only one in education
    or eligibility; otherwise No). None for anything else: the rules above answer what he holds, the rest is the owner's."""
    m = CREDENTIAL_ASK.fullmatch(q)
    if not m or CREDENTIAL_NOT_THIS.search(m.group('x')) or not yes_no_question(q):
        return None
    x = re.sub(r'\band\s*/\s*or\b', 'or', m.group('x'))
    if re.search(r'licen[cs]', x) and DRIVING.search(x):
        return None
    key = 'any other named qualification'
    rule = str((a.get('qualification_questions') or {}).get(key) or '')
    if not _settled(rule, q) or not re.search(r'\botherwise no\b', rule, re.I):
        return None
    parts = [p.strip() for p in re.split(r'\s*,\s*(?:or\s+)?|\s+or\s+|\s*/\s*', x)]
    if not all(p and _not_held(p, facts, a) for p in parts):
        return None
    basis = 'answers.qualification_questions.' + key
    pick = _choose('No', opts)
    return _ok(pick, basis) if pick else _no('no single option says No', basis)


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


# His own contact details asked as a form's plain field label (15 Nov 2026, Coffey Testing: 'First', 'Last', 'Personal
# Email'). The whole label must be one of these, after an optional your, my, personal, applicant or candidate: anything
# more names someone else ('Referee first name', 'Manager email', 'Emergency contact phone', 'Employer name'), another
# part of the name ('Middle name', 'Preferred name', 'Legal first name', 'Given names': all of them) or another subject
# ('First aid', 'First Nations', 'Last day', 'Work email').
CONTACT_OWN = r"(?:(?:your|my|personal|applicant'?s?|candidate'?s?) )?"
CONTACT_FIELDS = {
    'first': r'first(?: name)?|given name|forename',
    'last': r'last(?: name)?|surname|family name',
    'full': r'(?:full )?name',
    'email': r'e-?mail(?: address)?',
    'phone': r'(?:mobile|phone|telephone)(?: phone)?(?: number| no)?|contact (?:phone )?number',
}
# A word before the last that makes the family name two words ('de la Cruz', 'van Dijk'): the last word alone is then not it.
NAME_PARTICLES = {'de', 'da', 'del', 'dela', 'della', 'di', 'do', 'dos', 'das', 'du', 'la', 'le', 'van', 'von', 'der', 'den',
                  'ter', 'ten', 'st', 'bin', 'binti', 'al', 'el', 'mac', 'mc', 'o'}


def _contact(q, opts, facts):
    """His first, last or full name, email or phone (facts.json -> identity) for a plain contact field (CONTACT_FIELDS),
    as text to type; None when the question is not one. First is the first word of identity.name, and only when it is
    identity.short_name (where the facts give one); last is the last word, and not after a particle. With options on
    screen: unanswered (facts.json gives only the text)."""
    label = re.sub(r'\s*\*+$', '', q)   # 'First name *': the form's required mark
    kind = next((k for k, p in CONTACT_FIELDS.items() if re.fullmatch(CONTACT_OWN + '(?:' + p + ')', label)), None)
    if not kind:
        return None
    ident = facts.get('identity') or {}
    key = kind if kind in ('email', 'phone') else 'name'
    basis = 'identity.' + key
    if opts:
        return _no('a contact field with options: facts.json -> identity gives only the text to type', basis)
    value = ' '.join(str(ident.get(key) or '').split())
    if key == 'email':
        return _ok(value, basis) if re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', value) else _no('facts.json -> identity has no email', basis)
    if key == 'phone':
        return _ok(value, basis) if len(re.sub(r'\D', '', value)) >= 8 else _no('facts.json -> identity has no phone', basis)
    words = value.split()
    if len(words) < 2:
        return _no('facts.json -> identity -> name is not a first and a last name', basis)
    if kind == 'full':
        return _ok(value, basis)
    if kind == 'first':
        short = str(ident.get('short_name') or '').strip()
        if short and short != words[0]:
            return _no('facts.json -> identity: the first word of name is not short_name, so the first name is not settled', basis)
        return _ok(words[0], basis)
    if words[-2].lower() in NAME_PARTICLES:
        return _no('facts.json -> identity -> name: the family name may be more than its last word', basis)
    return _ok(words[-1], basis)


# ---------- the owner's own answers ----------

OWNER_KEYS = ('question', 'options', 'answer', 'date', 'entry')
OWNER_BASIS = 'answers.owner_answers'
ENTRY_ID = re.compile(r'[a-z0-9][a-z0-9-]{2,90}')   # a queue id, as queue.py validate allows it
# A question that asks for a private detail: the owner types it on the form himself, and it is never stored in facts.json
# (public). An owner row for it is refused, and the gate never takes one (the traps then leave it with the owner).
PRIVATE_ASK = re.compile(r"visa (grant )?number|passport|date of birth|birth ?date|\bdob\b|\bborn\b|legal name|tax file|\btfn\b"
                         r"|\bbank\b|\bbsb\b|\babn\b|superannuation|medical|injur|disabilit|health|gender|pronoun|aboriginal"
                         r"|torres strait|licen[cs]e number|registration number|\baddress\b|post ?code|\bstreet\b|next of kin"
                         r"|emergency contact|\bage\b|how old|marital|religio|ethnic|nationality|country of birth")
# A question about one job or its pay: the owner's answer holds for the entry he gave it for, not for every form whose
# question has the same words. A row for such a question needs "entry".
JOB_SPECIFIC = re.compile(r"\b(?:this|the|our) (?:role|position|job|opportunity|vacancy|company|team|organi[sz]ation|business|employer)\b"
                          r"|similar role|relevant to the (?:role|position)|job (?:ad|advert)|for the role|\bour\b|salary|remuneration"
                          r"|\bpay\b|\b(?:hourly|day|daily|pay|charge) rate\b|rate expectation")


def owner_key(text):
    """A question as owner_answers compares it: norm (case, spacing, curly quotes), without double quotation marks and
    without a closing ?, ., : or !."""
    return ' '.join(norm(text).replace('"', ' ').split()).rstrip(' ?.:!')


def _real_date(text):
    try:
        return bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}', text)) and bool(date.fromisoformat(text))
    except ValueError:
        return False


def owner_row_problems(row):
    """Why one row of facts.json -> answers -> owner_answers cannot be used ([] when it can). A row is {"question":
    text, "options": [text, ...] (optional: the options he saw), "answer": text, "date": "YYYY-MM-DD", "entry": queue id
    (optional: the entry he answered it for)}; with options the answer is one of them. A question about one job or its
    pay needs "entry"; a question asking for a private detail is refused."""
    if not isinstance(row, dict):
        return ['not an object {question, options, answer, date, entry}']
    p = [f'unknown key {k} (the keys are question, options, answer, date and entry)' for k in sorted(set(row) - set(OWNER_KEYS))]
    question, given, options, day = row.get('question'), row.get('answer'), row.get('options'), row.get('date')
    if not isinstance(question, str) or not owner_key(question):
        p.append('question: the exact text of the form question')
    elif PRIVATE_ASK.search(owner_key(question)):
        p.append('question: asks for a private detail; the owner types it himself on the form, and it is never stored in '
                 'facts.json (public)')
    elif 'entry' not in row and JOB_SPECIFIC.search(owner_key(question)):
        p.append('question: is about one job or its pay: add "entry": "<queue id>" so the answer is used on that entry only')
    if 'entry' in row and not (isinstance(row['entry'], str) and ENTRY_ID.fullmatch(row['entry'])):
        p.append('entry: the queue id the answer is for (for example seek-95506594), or leave it out')
    if not isinstance(given, str) or not given.strip():
        p.append("answer: the owner's answer, as text")
    if options is not None and (not isinstance(options, list) or not all(isinstance(o, str) and o.strip() for o in options)):
        p.append('options: a list of the options he saw, each as text')
    elif options and isinstance(given, str) and given.strip() and not any(norm(o) == norm(given) for o in options):
        p.append(f'the answer {given!r} is not one of its options')
    if not (isinstance(day, str) and _real_date(day)):
        p.append('date: YYYY-MM-DD, the day he gave the answer')
    return p


def owner_answer_problems(facts):
    """Every shape problem of facts.json -> answers -> owner_answers ([] when it is absent or sound): a list of rows
    (owner_row_problems), each question once for each entry (and once without one)."""
    rows = ((facts or {}).get('answers') or {}).get('owner_answers')
    if rows is None:
        return []
    if not isinstance(rows, list):
        return ['answers -> owner_answers: a list of {question, options, answer, date, entry}']
    out, seen = [], {}
    for n, row in enumerate(rows, 1):
        out += [f'answers -> owner_answers row {n}: {x}' for x in owner_row_problems(row)]
        key = (owner_key(row.get('question')), str(row.get('entry') or '')) if isinstance(row, dict) and isinstance(row.get('question'), str) else ''
        if key and key[0] and key in seen:
            out.append(f'answers -> owner_answers row {n}: the question is there twice (also row {seen[key]}): keep one answer')
        elif key and key[0]:
            seen[key] = n
    return out


def _owner_answer(question, opts, a, entry=None):
    """The owner's own answer to this question (facts.json -> answers -> owner_answers), or None when he gave none. A
    row with "entry" is used only for that entry, and before a row without one. With options on screen the answer is
    the one option equal to his (norm), else the question is unanswered. A question asking for a private detail is
    never answered from a row (None: the rules below, and the traps, decide it)."""
    rows = a.get('owner_answers')
    key = owner_key(question)
    if not key or not isinstance(rows, list) or PRIVATE_ASK.search(key):
        return None
    hits = [r for r in rows if isinstance(r, dict) and isinstance(r.get('question'), str) and owner_key(r['question']) == key]
    scoped = [r for r in hits if 'entry' in r and entry and r.get('entry') == entry]
    hits = scoped or [r for r in hits if 'entry' not in r]
    if not hits:
        return None
    if len(hits) > 1 or owner_row_problems(hits[0]):
        return _no('facts.json -> answers -> owner_answers: the row for this question is not sound (queue.py check names the fault)', OWNER_BASIS)
    row = hits[0]
    if not opts:
        return _ok(row['answer'], OWNER_BASIS)
    pick = [o for o in opts if norm(o) == norm(row['answer'])]
    if not pick and not row.get('options'):   # he answered in his own words: a length of time picks the option holding it
        pick = _owner_length_option(question, row['answer'], opts)
    if len(pick) != 1:
        edge = len(pick) > 1 and not any(norm(o) == norm(row['answer']) for o in opts)
        return _no(f"the owner's answer of {row['date']} is not one of the options on screen" + (' (it falls in more than one of them)' if edge else '')
                   + ' (facts.json -> answers -> owner_answers)', OWNER_BASIS)
    return _ok(pick[0], OWNER_BASIS)


OWNER_LENGTH = re.compile(r'(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten)\s*(years?|yrs?|months?)')


def _owner_length_option(question, given, opts):
    """15 Nov 2026 (TTW): the options holding the length of time the owner gave in his own words ('2 years', '18 months')
    for a how-many-years question: every option must read as a length of time (months_range), and the number must fall
    inside an option's range ('2 years' is 24 months: '1 - 5 Years', 12 to 60). [] when his answer is not a plain length,
    the question asks something else or an option cannot be read. A number on the edge of two options ('1 year' with
    '0 - 1 years' and '1 - 5 Years') is in both: the caller then leaves the question unanswered."""
    if not re.search(r"how many years|years'? (of )?experience|number of years", norm(question)):
        return []
    m = OWNER_LENGTH.fullmatch(norm(given).rstrip(' .'))
    ranges = [(o, months_range(o)) for o in opts]
    if not m or any(r is None for _, r in ranges):
        return []
    months = _number(m.group(1)) * (1 if m.group(2).startswith('month') else 12)
    return [o for o, r in ranges if r[0] <= months <= r[1]]


# ---------- the gate ----------

def answer(question, options=None, facts=None, pay=None, today=None, entry=None):
    """The standing answer to one form question. See the module notes for what is covered.

    options: the choices on screen (none for a free-text question). pay: the advert's own pay text, when the entry
    or the caller knows it (salary only). today: the date to judge the police check by (default: today in Melbourne).
    entry: the queue id the form belongs to (an owner answer given for one entry is used only there; None, at
    screening, uses only the rows without "entry"). The owner's own answers (facts.json -> answers -> owner_answers)
    go before every other rule, except for a question asking for a private detail.
    """
    facts = facts or {}
    a = facts.get('answers') or {}
    q = norm(question).rstrip(' ?.:!')
    opts = [' '.join(str(o).split()) for o in options or [] if str(o).strip()]
    if not q:
        return _no('no question text')
    owner = _owner_answer(question, opts, a, entry)
    if owner:
        return owner
    declared = _declaration(q, opts, a)
    if declared:
        return declared
    trap = TRAPS.search(q)
    if trap:
        return _no(f'only the owner can answer this ("{trap.group(0)}": a private detail, or a question a standing answer could get wrong)')
    # 'Do you require sponsorship to start?' asks about sponsorship, not a start date (the sponsorship rule reads 'to start' as now).
    topical = re.sub(r'\bto (?:start|commence)\b', ' ', q) if 'sponsor' in q else q
    topics = [name for name, pattern in TOPICS.items() if re.search(pattern, topical)]
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
    licence = r"driv\w*'?s? licen[cs]e|driving licen[cs]e|licen[cs]ed? to drive|car licen[cs]e|class c\b|(provisional|probationary|p ?plate|learner)\b[^?]*licen[cs]e"
    police = r'police (check|certificate|clearance)|national police|criminal history (check|screen)'
    studying = r'\bcurrently (studying|enrolled)\b|are you (currently )?(a )?student\b'
    travel = r'\bfifo\b|\bdido\b|\btravel|\broster'
    white_card = r'(?:general )?(?:white card|construction induction(?: training)?(?: card)?|induction (?:training )?card)'
    for pattern, words in ((licence, r'driv\w*|licen[cs]e|class c'), (TOPICS['car'], TOPICS['car']), (TOPICS['White Card'], white_card),
                           (police, police + r'|police'), (r'medical|drug|alcohol', r'(pre-?employment )?(medical|drug|alcohol)'),
                           (studying, studying), (r'relocat', r'relocat'), (travel, travel)):
        if re.search(pattern, q):
            also = _also(q, words)
            if also:
                return _no(f'asks for something else as well ("{also}"): facts.json answers only the one subject')
            break
    if re.search(licence, q):
        return _licence(q, opts, a)
    if re.search(TOPICS['car'], q):
        return _yes_no_line(a, 'own_car_or_regular_access', q, opts)
    if re.search(TOPICS['White Card'], q):
        return _yes_no_line(a, 'white_card', q, opts)
    if re.search(police, q):
        return _police(q, opts, a, today)
    if re.search(r'medical|drug|alcohol', q):
        return _tests(q, opts, a)
    if re.search(studying, q):
        if re.search(r'\bor\b|/|prepared|recent graduate|completed|washington', q):
            return _no('asks about study together with something else', 'answers.currently_studying')
        return _yes_no_line(a, 'currently_studying', q, opts)
    if re.search(r'relocat', q):
        if ABROAD.search(q):
            return _no('relocation outside Australia is not on record', 'answers.willing_to_relocate')
        if OWN_COST.search(q):
            return _no('relocation at his own cost or without assistance: facts.json says only that he will relocate (do not promise who pays '
                       'for the move)', 'answers.willing_to_relocate')
        if PAST.search(q):
            return _no('asks about a move already made; facts.json records only that he is willing to relocate', 'answers.willing_to_relocate')
        return _yes_no_line(a, 'willing_to_relocate', q, opts, free=a.get('willing_to_relocate'))
    if re.search(travel, q):
        if 'experience' in q or PAST.search(q) or not re.search(r'willing|available|open to|able to|prepared|happy|consider|comfortable', q):
            return _no('not a question about willingness to travel or work FIFO', 'answers.willing_to_travel_or_fifo')
        if ABROAD.search(q):
            return _no('travel outside Australia is not on record', 'answers.willing_to_travel_or_fifo')
        if NIGHT_SHIFT.search(q):
            return _no('night or shift work is not on record', 'answers.willing_to_travel_or_fifo')
        return _yes_no_line(a, 'willing_to_travel_or_fifo', q, opts)
    qualification = _qualification(q, opts, a, facts)
    if qualification:
        return qualification
    if re.fullmatch(r"what (relevant )?qualifications? do you (currently )?(hold|have)|what qualifications have you (completed|obtained)"
                    r"|please (list|provide|indicate) your (relevant )?qualifications?", q):
        return _qualifications_held(q, opts, facts)
    credential = _credential_not_held(q, opts, a, facts)
    if credential:
        return credential
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
    contact = _contact(q, opts, facts)
    if contact:
        return contact
    if re.fullmatch(r"where (are|do) you (currently )?(live|living|located|based|reside|residing)|where are you located|where are you currently (living|based|located)"
                    r"|(what is |what's )?your (current )?location|location|current location|(please confirm )?which suburb (do )?you (currently )?(live|reside) in"
                    r"|(please confirm )?which suburb do you (currently )?(live|reside) in|which suburb do you live in", q):
        return _location(q, opts, facts)
    return _no('no line of facts.json -> answers covers this question')
