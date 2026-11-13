"""Tests for scripts/resume.py, documents/resume/ and SEEK_PROFILE.md. They run offline."""
import contextlib
import copy
import html
import io
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pymupdf

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'scripts'))

import resume  # noqa: E402
from common import CONFIG, FACTS  # noqa: E402

HEADINGS = {
    'drafter': ['Profile', 'Design and drafting', 'Work history', 'Additional experience', 'Education',
                'Eligibility and licences'],
    'technician': ['Profile', 'Site inspection and quality-check experience',
                   'Standards and methods used in Advanced Diploma coursework', 'Tickets, licence and site readiness',
                   'Other work history', 'Education', 'Eligibility and licences'],
    'engineer': ['Profile', 'Site experience', 'Other work history', 'Education', 'Eligibility and licences'],
}
# Order of the roles on the page. Every variant's work-history section starts with the current job.
ROLES = {
    'drafter': ['Console Operator', 'Field Engineer', 'Project-in-Charge Engineer', 'Technical Support Representative'],
    'technician': ['Field Engineer', 'Project-in-Charge Engineer', 'Console Operator', 'Technical Support Representative'],
    'engineer': ['Field Engineer', 'Project-in-Charge Engineer', 'Console Operator', 'Technical Support Representative'],
}
# Tools and instruments that facts.json says he has not used, or does not list.
NOT_HIS = ['12d', 'SIDRA', 'OpenRoads', 'MicroStation', 'Tekla', 'Bluebeam', 'Excel', 'Microsoft Project',
           'Total Station', 'GNSS', 'Pryda', 'GIS', 'Benchmark']
# Capitalised words that the builder writes itself and that claim nothing.
OWN_WORDS = {'completed', 'referees'}

# The words written in resume.py, as they print today. A change of wording has to be made here too.
PROFILES = {
    'drafter':
        'Civil design graduate with an Advanced Diploma of Civil Construction Design, completed in Australia in '
        'February 2026, and a Bachelor of Science in Civil Engineering. Designed and documented road geometry, '
        'earthworks, pavement systems and stormwater drainage, and prepared and reviewed technical drawings in '
        'AutoCAD and Civil 3D, applying Australian Standards. Site experience reviewing structural and architectural '
        'drawings and checking work against project requirements.',
    'technician':
        'Civil construction design graduate (Advanced Diploma, February 2026) with site experience in inspections, '
        'quality checks and safety checks. Prepared site reports, material records and progress reports, and in '
        'technical support resolved 40 to 60 cases a day while keeping accurate case notes. Advanced Diploma '
        'coursework used AS 1289, AS 1726 and Austroads road and pavement guides. Available for site, regional '
        'and FIFO work.',
    'engineer':
        'Civil engineering graduate with site experience as a project-in-charge and field engineer in the '
        'Philippines (Apr 2019 to Feb 2020): coordinating 10 to 15 workers a day, site inspections, safety checks, '
        'quality checks, reviewing drawings, tracking procurement and preparing progress reports. Completed an '
        'Advanced Diploma of Civil Construction Design in Australia in February 2026, covering road geometry, '
        'earthworks, pavement systems and stormwater drainage.',
}
SUMMARY = ('Civil design graduate with an Advanced Diploma of Civil Construction Design (RII60520), completed in '
           'Australia in February 2026, and a Bachelor of Science in Civil Engineering. Designed and documented road '
           'geometry, earthworks, pavement systems and stormwater drainage, and prepared and reviewed technical '
           'drawings in AutoCAD and Civil 3D, applying Australian Standards. Site experience in inspections, quality '
           'checks, material records and progress reports. White Card and {licence}. Will relocate anywhere in '
           'Australia and can start two weeks after an offer.')
# eligibility.police_check as a fact with notes after its first sentence (its wording of 13 Nov 2026, evening).
POLICE_NOTE = ('Holds an AFP National Police Check certificate issued in March 2026 (application received 19 March '
               '2026; certificate forwarded 23 March 2026). It was obtained for his visa. Treat it as current until '
               "March 2027; after that the answer is 'willing to obtain one'.")

BUILT = {lane: resume.build(lane) for lane in resume.LANES}


def with_checks(licence, police):
    facts = copy.deepcopy(FACTS)
    facts['eligibility'].update(drivers_licence=licence, police_check=police)
    return facts


def earlier():
    """The licence and the police check as the owner first gave them on 13 Nov 2026."""
    return with_checks("Current Victorian driver's licence and own reliable transport",
                       'Holds a current National Police Certificate (owner, 13 Nov 2026)')


def later():
    """The same two facts after they were looked up: a full licence, a dated certificate with notes."""
    return with_checks("Full Victorian driver's licence and own reliable transport", POLICE_NOTE)


def lower_first(s):
    return s[:1].lower() + s[1:]


def files(folder):
    return {p.name: p.read_bytes() for p in Path(folder).iterdir()}


def text_of(lines):
    return '\n'.join(text for _, text, _ in lines)


def squash(s):
    """Text without bullets, separators and line breaks, for comparing a PDF with its lines."""
    return re.sub(r'\s+', ' ', re.sub('[|•\x95]', ' ', s)).strip()


def numbers(s):
    return set(re.findall(r'\d+(?:[.,]\d+)*', s))


def names(s):
    return {w.lower() for w in re.findall(r'\b[A-Z][A-Za-z0-9]*', s)}


def lowered(s):
    return set(re.findall(r'[a-z0-9]+', s.lower()))


def sources(lines, paths):
    return ' '.join(resume.tidy(resume.flat(resume.pick(lines.facts, p))) for p in paths)


class TidyTests(unittest.TestCase):
    def test_ranges_are_written_with_to(self):
        self.assertEqual(resume.tidy('Feb 2024 – Feb 2026'), 'Feb 2024 to Feb 2026')
        self.assertEqual(resume.tidy('2014–2019'), '2014 to 2019')
        self.assertEqual(resume.tidy('May 2024 – present'), 'May 2024 to present')
        self.assertEqual(resume.tidy('Coordinated 10–15 workers each day'), 'Coordinated 10 to 15 workers each day')

    def test_a_dash_in_a_job_title_becomes_a_comma(self):
        self.assertEqual(resume.tidy('Technical Support Representative – Microsoft Software'),
                         'Technical Support Representative, Microsoft Software')

    def test_project_values_and_source_notes_are_left_out(self):
        point = next(p for job in FACTS['experience'] for p in job['points'] if 'community hall' in p)
        self.assertIn('PHP', point)
        self.assertEqual(resume.tidy(point),
                         'Helped deliver a community hall renovation, finished within the six-month construction program')
        self.assertEqual(resume.tidy('Holds a current National Police Certificate (owner, 13 Nov 2026)'),
                         'Holds a current National Police Certificate')

    def test_lead_is_the_first_sentence_without_its_notes(self):
        self.assertEqual(resume.lead(POLICE_NOTE), 'AFP National Police Check certificate issued in March 2026')
        self.assertEqual(resume.lead('Holds a current National Police Certificate (owner, 13 Nov 2026)'),
                         'Current National Police Certificate')
        self.assertEqual(resume.lead('White Card (Construction Induction)'), 'White Card')
        with self.assertRaises(ValueError):
            resume.lead('Paid AUD 50 for it. Kept the receipt.')

    def test_phrases_must_be_in_the_text_letter_for_letter(self):
        text = 'site inspections, progress monitoring, quality checks and safety observations'
        self.assertEqual(resume.phrases(['Site inspections', 'Quality checks'], text, 'x'),
                         ['Site inspections', 'Quality checks'])
        for bad in ['Safety inspections', 'Quality monitoring', 'Materials testing']:
            with self.assertRaises(ValueError, msg=bad):
                resume.phrases(['Site inspections', bad], text, 'x')

    def test_refuses_what_it_cannot_clean(self):
        for bad in ['A job costing PHP 3 million', 'Budget of AUD 5,000', 'Roads — and drains', 'Roads–drains']:
            with self.assertRaises(ValueError, msg=bad):
                resume.tidy(bad)


class ContentTests(unittest.TestCase):
    def test_one_variant_for_each_lane_in_config(self):
        lanes = {k: v['resume'] for k, v in CONFIG['lanes'].items() if isinstance(v, dict) and 'resume' in v}
        self.assertEqual(sorted(resume.LANES), sorted(lanes.values()))

    def test_name_first_then_the_lane_headline(self):
        for lane, lines in BUILT.items():
            self.assertEqual(lines[0][:2], ('name', FACTS['identity']['name']))
            self.assertEqual(lines[1][:2], ('headline', FACTS['identity']['titles'][lane]))
            self.assertNotIn('graduate civil engineer', text_of(lines).lower())

    def test_contact_line_and_eligibility_line(self):
        ident, elig = FACTS['identity'], FACTS['eligibility']
        for lines in BUILT.values():
            self.assertEqual(lines[2][1], f"Melton VIC | {ident['phone']} | {ident['email']} | {ident['portfolio_url']}")
            self.assertEqual(lines[3][1], ' | '.join([elig['work_rights_short'], elig['drivers_licence'], elig['white_card']]))
            self.assertTrue(ident['portfolio_url'].startswith('https://'))

    def test_sections_of_each_variant(self):
        for lane, lines in BUILT.items():
            self.assertEqual([t for k, t, _ in lines if k == 'h'], HEADINGS[lane], lane)
            self.assertEqual([t for k, t, _ in lines if k == 'label'],
                             ['Drawings in the online portfolio'] if lane == 'drafter' else [], lane)
            self.assertEqual(lines[-1][1], 'Referees available on request.')

    def test_profile_is_50_to_65_words(self):
        for lane, lines in BUILT.items():
            profile = lines[[t for _, t, _ in lines].index('Profile') + 1]
            self.assertEqual(profile[0], 'p')
            self.assertTrue(50 <= len(profile[1].split()) <= 65, (lane, len(profile[1].split())))

    def test_every_line_traces_to_the_facts_it_names(self):
        """No number and no capitalised word (tool, employer, place, standard) that its facts do not hold;
        a line that names one fact is that fact, word for word."""
        for lane, lines in BUILT.items():
            for kind, text, paths in lines:
                if kind in ('h', 'label'):
                    continue
                self.assertTrue(paths, text)
                held = sources(lines, paths)
                said = text.split(': ', 1)[1] if kind == 'kv' else text
                self.assertLessEqual(numbers(said), numbers(held), (lane, text))
                self.assertLessEqual(names(said) - OWN_WORDS, lowered(held), (lane, text))
                if kind == 'li' and len(paths) == 1:
                    fact = resume.pick(FACTS, paths[0])
                    self.assertEqual(text, resume.lead(fact) if paths[0].endswith('.police_check') else resume.tidy(fact))
            self.assertIs(resume.verify(lines), lines)

    def test_written_sentences_are_these_words(self):
        """verify() checks words, not meaning ('field engineer in Australia' would pass it), so the sentences
        written in resume.py are pinned here word for word."""
        for lane, lines in BUILT.items():
            texts = [t for _, t, _ in lines]
            self.assertEqual(texts[texts.index('Profile') + 1], PROFILES[lane], lane)
            written = [t for k, t, paths in lines if k in ('p', 'li') and len(paths) > 1]
            self.assertEqual(written, [PROFILES[lane], 'Will relocate anywhere in Australia'], lane)
        self.assertEqual(resume.seek(earlier())['Personal summary'],
                         [SUMMARY.format(licence="current Victorian driver's licence")])
        self.assertEqual(resume.seek(later())['Personal summary'],
                         [SUMMARY.format(licence="full Victorian driver's licence")])

    def test_police_check_is_the_first_sentence_of_its_fact_and_no_more(self):
        for lane, lines in BUILT.items():
            police = ('li', resume.lead(FACTS['eligibility']['police_check']), ('eligibility.police_check',))
            self.assertEqual(lines[lines.index(police) + 1], ('li', FACTS['eligibility']['wwcc'], ('eligibility.wwcc',)))
        for lane in resume.LANES:
            self.assertIn('\nCurrent National Police Certificate\n', text_of(resume.build(lane, earlier())), lane)
            text = text_of(resume.build(lane, later()))
            self.assertIn('\nAFP National Police Check certificate issued in March 2026\n', text, lane)
            self.assertIn("Full Victorian driver's licence and own reliable transport", text, lane)
            for gone in ['current', 'Current', 'his visa', 'willing to obtain', '19 March', 'Holds']:
                self.assertNotIn(gone, text, (lane, gone))
            self.assertEqual(text.count('2027'), 1, lane)      # the work-rights line; not the note on the check

    def test_every_course_and_every_availability_line_is_printed(self):
        facts = copy.deepcopy(FACTS)
        facts['education'].insert(1, {'qualification': 'Certificate IV in Laboratory Techniques',
                                      'provider': 'Example Institute, Australia', 'dates': '2026–2027',
                                      'points': ['Sampled and tested soils and concrete']})
        facts['eligibility']['availability'].append('Available for night and weekend shifts')
        for lane in resume.LANES:
            lines = resume.build(lane, facts)
            texts = [t for _, t, _ in lines]
            for course in facts['education']:
                self.assertTrue(any(t.startswith(course['qualification']) for k, t, _ in lines if k == 'role'), lane)
                self.assertIn(f"{course['provider']} | {resume.tidy(course['dates'])}", texts, lane)
            self.assertIn('Sampled and tested soils and concrete', texts, lane)
            self.assertEqual(texts.count('Available for night and weekend shifts'), 1, lane)
            for line in FACTS['eligibility']['availability']:
                self.assertEqual(texts.count(line), 1, (lane, line))
            self.assertEqual(texts[texts.index('Profile') + 1], PROFILES[lane], lane)   # the degree is still the Bachelor
        study = resume.seek(facts)['Education']
        self.assertEqual([row for row in study if row.startswith('Course: ')],
                         ['Course: Advanced Diploma of Civil Construction Design (RII60520)',
                          'Course: Certificate IV in Laboratory Techniques',
                          'Course: Bachelor of Science in Civil Engineering (BSCE)'])
        self.assertEqual(study[study.index('Course: Certificate IV in Laboratory Techniques') + 2:][:2],
                         ['Started: 2026', 'Finished: 2027'])

    def test_verify_refuses_words_and_numbers_the_facts_do_not_hold(self):
        for text in ['Drafted road designs in 12d and SIDRA', 'Coordinated 25 workers each day',
                     'Carried out compaction testing on site']:
            lines = resume.Lines(FACTS)
            lines.say('li', text, 'experience.1.points', 'experience.2.points', 'capabilities.software')
            with self.assertRaises(ValueError, msg=text):
                resume.verify(lines)

    def test_build_stops_when_a_fact_under_a_written_sentence_changes(self):
        facts = copy.deepcopy(FACTS)
        point = next(p for job in facts['experience'] for p in job['points'] if '10–15 workers' in p)
        for job in facts['experience']:
            job['points'] = [p.replace('10–15 workers', '25 workers') for p in job['points']]
        self.assertNotIn(point, resume.flat(facts['experience']))
        with self.assertRaises(ValueError):
            resume.build('engineer', facts)       # its profile says 10 to 15 workers
        facts = copy.deepcopy(FACTS)
        facts['capabilities']['standards_coursework'].remove('AS 1289')
        with self.assertRaises(ValueError):
            resume.build('technician', facts)     # its profile names AS 1289
        self.assertNotIn('AS 1289', text_of(resume.build('drafter', facts)))

    def test_tools_and_employers_are_only_those_in_facts(self):
        employers = {resume.tidy(j['employer']) for j in FACTS['experience']}
        providers = {resume.tidy(e['provider']) for e in FACTS['education']}
        for lane, lines in BUILT.items():
            text = text_of(lines)
            for tool in NOT_HIS:
                self.assertNotRegex(text, r'(?i)\b' + re.escape(tool) + r'\b', lane)
            orgs = {t.rsplit(' | ', 1)[0] for k, t, _ in lines if k == 'org'}
            self.assertEqual(orgs, employers | providers, lane)
            software = [t for k, t, _ in lines if k == 'kv' and t.startswith('Software: ')]
            self.assertEqual(software, ['Software: ' + ', '.join(FACTS['capabilities']['software'])], lane)

    def test_no_project_values_no_dashes_nothing_he_lacks(self):
        flags = [p for p in CONFIG['tone']['no_volunteered_limits']['flag_patterns'] if 'december 2027' not in p]
        for lane, lines in BUILT.items():
            text = text_of(lines)
            for banned in ['PHP', 'AUD', '22,000', '27,000', 'million', '–', '—', 'Sheet', 'Updated', '(owner']:
                self.assertNotIn(banned, text, (lane, banned))
            for phrase in flags + [s.lower() for s in FACTS['strengths']] + ['residency', 'migration', 'referee:']:
                self.assertNotIn(phrase, text.lower(), (lane, phrase))
            for kind, t, _ in lines:
                if kind == 'org':
                    self.assertRegex(t, r' \| (\w{3} )?\d{4} to ((\w{3} )?\d{4}|present)$')

    def test_work_history_starts_with_the_current_australian_job(self):
        current = next(j for j in FACTS['experience'] if 'present' in j['dates'])
        self.assertIn('VIC', current['employer'])
        self.assertEqual(len(current['points']), 1)
        for lane, lines in BUILT.items():
            at = next(n for n, (k, t, _) in enumerate(lines) if k == 'h' and t.lower().endswith('work history'))
            self.assertEqual([t for _, t, _ in lines[at + 1:at + 4]],
                             [current['role'], f"{current['employer']} | May 2024 to present", current['points'][0]], lane)
            self.assertNotEqual(lines[at + 4][0], 'li', lane)   # one line, nothing added to it
            roles = [t for k, t, _ in lines if k == 'role' and 'Diploma' not in t and 'Bachelor' not in t]
            self.assertEqual(len(roles), len(ROLES[lane]))
            for role, start in zip(roles, ROLES[lane]):
                self.assertTrue(role.startswith(start), (lane, roles))

    def test_roles_are_newest_first_in_each_group(self):
        facts = copy.deepcopy(FACTS)
        facts['experience'].insert(1, {'role': 'Site Engineer', 'employer': 'Example Civil, Philippines',
                                       'dates': 'Mar 2018 – Jan 2019', 'points': ['Carried out site inspections']})
        current, site, other = resume.jobs(facts)
        starts = [resume.started(resume.pick(facts, p + '.dates')) for p in site]
        self.assertEqual(starts, [(2019, 9), (2019, 4), (2018, 3)])
        self.assertEqual([resume.pick(facts, p + '.dates') for p in current], ['May 2024 – present'])
        self.assertEqual([resume.pick(facts, p + '.role')[:17] for p in other], ['Technical Support'])

    def test_every_bullet_sits_under_its_own_job_or_course(self):
        for lane, lines in BUILT.items():
            owner = None
            for kind, _, paths in lines:
                if kind == 'role':
                    owner = paths[0].rsplit('.', 1)[0]            # 'experience.2' or 'education.0'
                elif kind in ('h', 'label'):
                    owner = None
                elif kind == 'li' and paths[0].startswith(('experience.', 'education.')):
                    self.assertTrue(paths[0].startswith(owner + '.points.'), (lane, paths))

    def test_full_work_rights_line_only_in_the_last_section(self):
        full = FACTS['eligibility']['work_rights']
        self.assertIn('December 2027', full)
        for lane, lines in BUILT.items():
            texts = [t for _, t, _ in lines]
            self.assertEqual(texts[texts.index('Eligibility and licences') + 1], full, lane)
            self.assertEqual(text_of(lines).count('2027'), 1, lane)


class PdfTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.pdf = {lane: resume.write(lane, cls.tmp.name)[0] for lane in resume.LANES}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def pages(self, lane):
        with pymupdf.open(self.pdf[lane]) as doc:
            return [page.get_text() for page in doc]

    def test_file_names(self):
        self.assertEqual(sorted(p.name for p in self.pdf.values()),
                         ['Marc_Masarate_Resume_Drafter.pdf', 'Marc_Masarate_Resume_Engineer.pdf',
                          'Marc_Masarate_Resume_Technician.pdf'])

    def test_two_pages_at_most_and_small(self):
        for lane, pdf in self.pdf.items():
            with pymupdf.open(pdf) as doc:
                self.assertLessEqual(len(doc), 2, lane)
                self.assertEqual(doc[0].rect, pymupdf.paper_rect('a4'))
            self.assertLess(pdf.stat().st_size, 80_000, lane)

    def test_text_layer_reads_in_the_order_of_the_lines(self):
        """pymupdf returns the text as it lies in the file: the name first, each job followed by its own
        bullets, nothing but the lines of the resume."""
        for lane, lines in BUILT.items():
            pages = self.pages(lane)
            self.assertEqual(pages[0].splitlines()[0], FACTS['identity']['name'])
            self.assertEqual(squash(' '.join(pages)), squash(text_of(lines)), lane)
            whole = squash(' '.join(pages))
            for n, (kind, text, _) in enumerate(lines):
                if kind == 'role' and lines[n + 2][0] == 'li':
                    job = squash(' '.join(t for _, t, _ in lines[n:n + 3]))   # role, employer and dates, first bullet
                    self.assertIn(job, whole, (lane, text))

    def test_no_visa_end_date_in_the_top_third(self):
        short = FACTS['eligibility']['work_rights_short']
        for lane, pdf in self.pdf.items():
            with pymupdf.open(pdf) as doc:
                page = doc[0]
                top = ' '.join(w[4] for w in page.get_text('words') if w[3] < page.rect.height / 3)
            self.assertIn(short, top, lane)
            self.assertNotRegex(top, r'(?i)2027|until|expir|december', lane)
            whole = ' '.join(self.pages(lane))
            self.assertLess(whole.index('Eligibility and licences'), whole.index('2027'), lane)

    def test_no_page_ends_with_a_heading_and_no_role_is_split(self):
        for lane, lines in BUILT.items():
            pages = self.pages(lane)
            headings = {t for k, t, _ in lines if k in ('h', 'role', 'org', 'label')}
            for page in pages[:-1]:
                self.assertNotIn(page.strip().splitlines()[-1], headings, lane)
            on_page, page, at = [], 0, 0          # the page each line is on, found by reading the pages in order
            for _, text, _ in lines:
                found = squash(pages[page]).find(squash(text), at)
                if found < 0:
                    page, found = page + 1, squash(pages[page + 1]).find(squash(text))
                    self.assertGreaterEqual(found, 0, (lane, text))
                on_page.append(page)
                at = found + len(squash(text))
            for n, (kind, text, _) in enumerate(lines):
                if kind == 'role':
                    end = next((m for m in range(n + 1, len(lines)) if lines[m][0] not in ('org', 'li')), len(lines))
                    self.assertEqual(len(set(on_page[n:end])), 1, (lane, text))

    def test_text_stays_inside_the_margins(self):
        for lane, pdf in self.pdf.items():
            with pymupdf.open(pdf) as doc:
                for page in doc:
                    for x0, y0, x1, y1, word, *_ in page.get_text('words'):
                        self.assertGreaterEqual(x0, resume.LEFT, (lane, word))
                        self.assertLessEqual(x1, page.rect.width - resume.LEFT + 0.5, (lane, word))
                        self.assertLessEqual(y1, page.rect.height - resume.BOTTOM + 4, (lane, word))

    def test_standard_fonts_nothing_embedded_links_work(self):
        ident = FACTS['identity']
        for lane, pdf in self.pdf.items():
            with pymupdf.open(pdf) as doc:
                fonts = {f[3] for page in doc for f in page.get_fonts()}
                self.assertEqual(fonts, {'Helvetica', 'Helvetica-Bold'}, lane)
                self.assertEqual({link['uri'] for link in doc[0].get_links()},
                                 {ident['portfolio_url'], 'mailto:' + ident['email']}, lane)
                self.assertEqual(doc.metadata['author'], ident['name'])

    def test_same_facts_give_the_same_file(self):
        with tempfile.TemporaryDirectory() as again:
            for lane, pdf in self.pdf.items():
                self.assertEqual(resume.write(lane, again)[0].read_bytes(), pdf.read_bytes(), lane)

    def test_html_next_to_the_pdf_holds_the_same_lines(self):
        for lane, lines in BUILT.items():
            page = self.pdf[lane].with_suffix('.html').read_text(encoding='utf-8')
            self.assertNotIn('{{', page)
            body = page.split('<body>')[1]
            got = [html.unescape(re.sub(r'<[^>]+>', '', row)).strip() for row in body.splitlines()]
            self.assertEqual([g for g in got if g], [t for _, t, _ in lines], lane)
            self.assertIn(f'<a href="{FACTS["identity"]["portfolio_url"]}">', page)
            self.assertIn('<meta name="robots" content="noindex,nofollow">', page.split('</head>')[0])

    def test_more_than_two_pages_is_refused_and_nothing_is_written(self):
        facts = copy.deepcopy(FACTS)
        facts['experience'][0]['points'] = facts['experience'][0]['points'] * 15
        for lane in resume.LANES:
            with tempfile.TemporaryDirectory() as out:
                with self.assertRaisesRegex(ValueError, '3 pages'):
                    resume.write(lane, out, facts)
                self.assertEqual(files(out), {}, lane)

    def test_build_writes_the_three_variants_and_the_seek_page(self):
        with tempfile.TemporaryDirectory() as out:
            done = resume.write_all(out, seek_md=Path(out) / 'SEEK_PROFILE.md')
            self.assertEqual([(pdf.name, pages) for pdf, pages in done], [(self.pdf[lane].name, 2) for lane in resume.LANES])
            made = files(out)
            self.assertEqual(sorted(made), sorted([p.name for p in self.pdf.values()] + ['SEEK_PROFILE.md']
                                                  + [p.with_suffix('.html').name for p in self.pdf.values()]))
            for pdf in self.pdf.values():
                self.assertEqual(made[pdf.name], pdf.read_bytes())
                self.assertEqual(made[pdf.with_suffix('.html').name], pdf.with_suffix('.html').read_bytes())
            self.assertEqual(made['SEEK_PROFILE.md'].decode('utf-8'),
                             resume.fill(resume.SEEK_MD.read_text(encoding='utf-8'), resume.seek()))

    def test_a_refused_build_leaves_every_file_as_it_was(self):
        """The drafter variant builds in each case; it is the technician variant, a third page or the SEEK
        text that is refused, and then nothing at all may be written."""
        no_standard, long_job = copy.deepcopy(FACTS), copy.deepcopy(FACTS)
        no_standard['capabilities']['standards_coursework'].remove('AS 1289')     # the technician profile names it
        long_job['experience'][0]['points'] = long_job['experience'][0]['points'] * 15
        self.assertTrue(resume.build('drafter', no_standard))
        with tempfile.TemporaryDirectory() as out, tempfile.TemporaryDirectory() as empty:
            page = Path(out) / 'SEEK_PROFILE.md'
            resume.write_all(out, seek_md=page)
            before = files(out)
            for facts in (no_standard, long_job):
                for folder in (out, empty):
                    with self.assertRaises(ValueError):
                        resume.write_all(folder, facts, seek_md=Path(folder) / 'SEEK_PROFILE.md')
            with mock.patch.object(resume, 'SKILLS', resume.SKILLS + ['Compaction testing']):
                for folder in (out, empty):
                    with self.assertRaises(ValueError):
                        resume.write_all(folder, later(), seek_md=Path(folder) / 'SEEK_PROFILE.md')
            self.assertEqual(files(out), before)
            self.assertEqual(files(empty), {})

    def test_build_command_with_out_leaves_the_repository_alone(self):
        before = files(resume.OUT_DIR), resume.SEEK_MD.read_bytes()
        with tempfile.TemporaryDirectory() as out, contextlib.redirect_stdout(io.StringIO()) as said:
            resume.main(['build', '--out', out, '--png', str(Path(out) / 'png')])
            self.assertEqual(len(list((Path(out) / 'png').glob('*.png'))), 6)
            self.assertEqual((Path(out) / 'SEEK_PROFILE.md').read_text(encoding='utf-8'),
                             resume.fill(before[1].decode('utf-8'), resume.seek()))
            self.assertEqual(said.getvalue().count(' 2 pages'), 3)
            self.assertIn(str(Path(out) / 'SEEK_PROFILE.md'), said.getvalue())
        self.assertEqual((files(resume.OUT_DIR), resume.SEEK_MD.read_bytes()), before)

    def test_committed_files_say_what_the_facts_say_now(self):
        """Fails after facts.json changes until 'resume.py build' is run and documents/resume/ is committed."""
        for lane, lines in BUILT.items():
            committed = resume.OUT_DIR / self.pdf[lane].name
            self.assertTrue(committed.exists(), f'{committed} is missing: run scripts/resume.py build')
            with pymupdf.open(committed) as doc:
                self.assertLessEqual(len(doc), 2)
                self.assertEqual(squash(' '.join(page.get_text() for page in doc)), squash(text_of(lines)), lane)
            self.assertEqual(committed.with_suffix('.html').read_text(encoding='utf-8'),
                             self.pdf[lane].with_suffix('.html').read_text(encoding='utf-8'), lane)


class LayoutTests(unittest.TestCase):
    def test_parts_between_bars_stay_whole_where_they_fit(self):
        text = FACTS['identity']['titles']['engineer']
        rows = resume.lay(text, 'hebo', 10.5, resume.WIDTH, ' | ')
        self.assertGreater(len(rows), 1)
        self.assertEqual(' | '.join(rows), text)
        for part in text.split(' | '):
            self.assertTrue(any(part in row for row in rows), part)

    def test_no_line_is_wider_than_the_page(self):
        for lines in BUILT.values():
            for kind, text, _ in lines:
                font, size, _, _, indent = resume.STYLE[kind]
                label, rows, _ = resume.shape(kind, text)
                for i, row in enumerate(rows):
                    used = pymupdf.get_text_length(label, 'hebo', size) if i == 0 else 0
                    self.assertLessEqual(used + pymupdf.get_text_length(row, font, size), resume.WIDTH - indent, row)


def text_blocks(md):
    """{section heading: the lines of its text blocks}"""
    found, section, inside = {}, None, False
    for line in md.splitlines():
        if line.startswith('```'):
            inside = line.strip() == '```text'
        elif inside:
            found.setdefault(section, []).append(line)
        elif line.startswith('## '):
            section = line[3:]
    return found


def outside(md):
    """The lines of the page that are in no text block."""
    rows, inside = [], False
    for line in md.splitlines():
        if line.startswith('```'):
            inside = line.strip() == '```text'
        elif not inside:
            rows.append(line)
    return rows


def entries(rows):
    """The entries of a block: lists of lines, split at the empty lines."""
    found = [[]]
    for row in rows:
        found.append([]) if row == '' else found[-1].append(row)
    return found


class SeekProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.md = resume.SEEK_MD.read_text(encoding='utf-8')
        cls.built = resume.seek()
        cls.fresh = resume.fill(cls.md, cls.built)       # the page as a build would write it now

    def test_sections(self):
        self.assertEqual(list(self.built), ['Headline', 'Personal summary', 'Career history', 'Education',
                                            'Licences and certifications', 'Skills', 'Preferred roles and locations',
                                            'Right to work'])
        for heading in ['Resumes to store', 'Settings to check once']:
            self.assertIn('\n## ' + heading + '\n', self.md)

    def test_every_block_in_the_file_is_the_block_built_from_the_facts(self):
        """Fails after facts.json changes until 'resume.py build' is run and SEEK_PROFILE.md is committed."""
        self.assertEqual(text_blocks(self.md), self.built)
        self.assertEqual(self.md, self.fresh)

    def test_a_line_added_to_a_block_by_hand_is_found_and_a_rebuild_removes_it(self):
        added = {'Licences and certifications': ['Australian citizen', 'Permanent resident'],
                 'Skills': ['Construction materials testing', 'Soil, concrete, asphalt and aggregates testing',
                            'Structural drafter'],
                 'Career history': ['- 11 years of paid experience as a civil engineer and site engineer in Australia'],
                 'Personal summary': ['Two years of paid drafting in AutoCAD and Civil 3D']}
        for section, lines in added.items():
            for line in lines:
                last = self.built[section][-1]
                page = self.fresh.replace(last + '\n```', last + '\n' + line + '\n```')
                self.assertNotEqual(page, self.fresh, line)
                self.assertNotEqual(text_blocks(page), self.built, line)
                self.assertEqual(resume.fill(page, self.built), self.fresh, line)

    def test_fill_refuses_a_block_it_has_no_text_for_and_text_it_has_no_block_for(self):
        with self.assertRaisesRegex(ValueError, 'Skills'):
            resume.fill(self.md.replace('## Skills', '## Skills\n\n```text\nExcel\n```'), self.built)
        with self.assertRaisesRegex(ValueError, 'Other tickets'):
            resume.fill(self.md + '\n## Other tickets\n\n```text\nForklift\n```\n', self.built)
        with self.assertRaisesRegex(ValueError, 'Right to work'):
            resume.fill(self.md.split('## Right to work')[0], self.built)
        other = '```json\n{"left": "alone"}\n```\n'
        self.assertTrue(resume.fill(self.md + other, self.built).endswith(other))

    def test_headline_and_summary(self):
        self.assertEqual(self.built['Headline'], [FACTS['identity']['titles']['drafter']])
        summary, = self.built['Personal summary']
        self.assertTrue(70 <= len(summary.split()) <= 90, len(summary.split()))
        self.assertEqual(summary, SUMMARY.format(licence=lower_first(FACTS['eligibility']['drivers_licence'].split(' and ')[0])))

    def test_summary_is_refused_when_a_fact_under_it_goes(self):
        facts = copy.deepcopy(FACTS)
        facts['education'][0]['points'] = [p.replace('Civil 3D', 'Revit') for p in facts['education'][0]['points']]
        with self.assertRaisesRegex(ValueError, '3d'):
            resume.seek(facts)

    def test_career_history_is_the_facts_newest_first(self):
        jobs = entries(self.built['Career history'])
        self.assertEqual(len(jobs), len(FACTS['experience']))
        starts = [resume.started(row.split(': ')[1]) for job in jobs for row in job if row.startswith('Started: ')]
        self.assertEqual(starts, sorted(starts, reverse=True))
        by_role = {resume.tidy(j['role']): j for j in FACTS['experience']}
        for job in jobs:
            fact = by_role[job[0].removeprefix('Job title: ')]
            started, ended = resume.tidy(fact['dates']).split(' to ')
            self.assertEqual(job[1:4], ['Company: ' + fact['employer'], 'Started: ' + started, 'Ended: ' + ended])
            points = [resume.tidy(p) for p in fact['points']]
            self.assertEqual(len(job[4:]), min(3, len(points)), job[0])
            at = [points.index(row.removeprefix('- ')) for row in job[4:]]      # each is a point of this job
            self.assertEqual(at, sorted(set(at)), job[0])
        first = entries(self.built['Career history'])[-1]
        self.assertTrue(first[0].startswith('Job title: Project-in-Charge'))
        self.assertTrue(first[-1].startswith('- Carried out site inspections, safety checks and quality monitoring'))

    def test_education_is_the_facts(self):
        courses = entries(self.built['Education'])
        self.assertEqual(len(courses), len(FACTS['education']))
        for course, fact in zip(courses, FACTS['education']):
            code = f" ({fact['code']})" if 'code' in fact else ''
            started, ended = resume.tidy(fact['dates']).split(' to ')
            self.assertEqual(course[:4], ['Course: ' + fact['qualification'] + code, 'Institution: ' + fact['provider'],
                                          'Started: ' + started, 'Finished: ' + fact.get('completed', ended)])
            self.assertEqual([row.removeprefix('- ') for row in course[4:]], fact['points'])

    def test_each_licence_line_is_one_eligibility_field(self):
        elig = FACTS['eligibility']
        self.assertEqual(self.built['Licences and certifications'],
                         [elig['white_card'], elig['drivers_licence'].split(' and ')[0], resume.lead(elig['police_check']),
                          elig['wwcc']])
        self.assertEqual(resume.seek(earlier())['Licences and certifications'],
                         ['White Card (Construction Induction)', "Current Victorian driver's licence",
                          'Current National Police Certificate', 'Working with Children Check'])

    def test_later_facts_change_the_blocks_and_nothing_else_needs_changing(self):
        """The licence and police-check wording comes from the facts, in the blocks and nowhere else."""
        built = resume.seek(later())
        self.assertEqual(built['Licences and certifications'],
                         ['White Card (Construction Induction)', "Full Victorian driver's licence",
                          'AFP National Police Check certificate issued in March 2026', 'Working with Children Check'])
        self.assertEqual(built['Personal summary'], [SUMMARY.format(licence="full Victorian driver's licence")])
        page = resume.fill(resume.fill(self.md, resume.seek(earlier())), built)
        self.assertEqual(outside(page), outside(self.md))
        self.assertEqual(text_blocks(page), built)
        self.assertNotRegex(page, r'(?i)current victorian|current national|probationary|SEEK Pass')
        self.assertEqual(page.count('2027'), 1)

    def test_words_outside_the_blocks_state_no_fact(self):
        prose = '\n'.join(re.sub(r'^\d+\. |`[^`]*`', '', row) for row in outside(self.md))   # no list numbers, no file names
        self.assertNotRegex(prose, r'\d')            # no date, year, subclass, postcode, salary or count
        self.assertNotRegex(prose, r'(?i)victorian|police certificate|probationary|SEEK Pass|citizen|resident|not on record')
        for rows in self.built.values():
            for row in rows:
                self.assertNotIn(row or 'no empty line is looked for', prose)

    def test_skills_are_the_software_then_phrases_of_what_he_has_done(self):
        skills, software = self.built['Skills'], FACTS['capabilities']['software']
        self.assertEqual(skills[:len(software)], software)
        self.assertEqual(skills[len(software):], resume.SKILLS)
        self.assertEqual(len(skills), len(set(skills)))
        done = ' | '.join([resume.tidy(v) for v in FACTS['capabilities'].values() if isinstance(v, str)]
                          + FACTS['capabilities']['methods_coursework']
                          + [resume.tidy(p) for x in FACTS['experience'] + FACTS['education'] for p in x['points']]).lower()
        for skill in resume.SKILLS:
            self.assertIn(skill.lower(), done)
        for tool in NOT_HIS:
            self.assertNotRegex(self.md, r'(?i)\b' + re.escape(tool) + r'\b')

    def test_a_skill_that_is_only_in_a_lane_description_or_an_answer_is_refused(self):
        for bad in ['Construction materials testing', 'Soil, concrete, asphalt and aggregates testing',
                    'Structural drafter', 'Estimating', 'Preparing and submitting tenders', 'Excel']:
            with mock.patch.object(resume, 'SKILLS', resume.SKILLS + [bad]), self.assertRaises(ValueError, msg=bad):
                resume.seek()

    def test_wanted_roles_are_phrases_of_the_lanes_in_queue_order(self):
        block = self.built['Preferred roles and locations']
        lanes = sorted(resume.LANES, key=lambda lane: CONFIG['lanes'][lane]['rank'])
        self.assertEqual(lanes, ['drafter', 'technician', 'engineer'])
        self.assertEqual(block[:3], ['- ' + ', '.join(resume.WANTED[lane]) for lane in lanes])
        for lane in lanes:
            for title in resume.WANTED[lane]:
                self.assertIn(title.lower(), CONFIG['lanes'][lane]['what'].lower())
        self.assertEqual(block[3:], ['Locations: ' + CONFIG['seek']['where'],
                                     'Notice period: ' + FACTS['answers']['notice_period'], 'Salary: $65,000 to $75,000'])
        self.assertIn('$65,000 to $75,000', FACTS['answers']['expected_salary']['rule'])
        for bad in ['Estimator', 'Site engineer', 'Traffic controller']:     # excluded, or the engineer lane's
            wanted = dict(resume.WANTED, drafter=resume.WANTED['drafter'] + [bad])
            with mock.patch.object(resume, 'WANTED', wanted), self.assertRaises(ValueError, msg=bad):
                resume.seek()
        facts = copy.deepcopy(FACTS)
        facts['answers']['expected_salary']['rule'] = 'Ask the owner.'
        with self.assertRaisesRegex(ValueError, 'expected_salary'):
            resume.seek(facts)

    def test_visa_end_date_only_in_the_right_to_work_text(self):
        self.assertEqual(self.built['Right to work'], [FACTS['answers']['right_to_work']['free_text']])
        self.assertEqual(self.md.count('2027'), 1)

    def test_seek_command_prints_the_blocks(self):
        with contextlib.redirect_stdout(io.StringIO()) as said:
            resume.main(['seek'])
        printed = said.getvalue()
        for section, rows in self.built.items():
            self.assertIn(f'## {section}\n' + '\n'.join(rows) + '\n', printed)

    def test_names_the_three_resume_files_and_the_default(self):
        for lane in resume.LANES:
            name = resume.file_stem(lane) + '.pdf'
            self.assertIn(f'| {lane} | `{name}` |', self.md)
            self.assertTrue((resume.OUT_DIR / name).exists(), name)
        self.assertIn('| drafter | `Marc_Masarate_Resume_Drafter.pdf` | default', self.md)

    def test_nothing_that_must_stay_out(self):
        for banned in ['PHP', 'AUD', '–', '—', 'Graduate Civil Engineer', 'Jeremie', 'referee']:
            self.assertNotIn(banned, self.md, banned)
        self.assertNotRegex(self.md, r'\d{6,}')     # no card, licence or access numbers


if __name__ == '__main__':
    unittest.main()
