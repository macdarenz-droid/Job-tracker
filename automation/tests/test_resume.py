"""Tests for scripts/resume.py, documents/resume/ and SEEK_PROFILE.md. They run offline."""
import copy
import html
import re
import sys
import tempfile
import unittest
from pathlib import Path

import pymupdf

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'scripts'))

import resume  # noqa: E402
from common import CONFIG, FACTS, ROOT  # noqa: E402

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

BUILT = {lane: resume.build(lane) for lane in resume.LANES}


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
                    self.assertEqual(text, resume.tidy(resume.pick(FACTS, paths[0])))
            self.assertIs(resume.verify(lines), lines)

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

    def test_more_than_two_pages_is_refused(self):
        facts = copy.deepcopy(FACTS)
        facts['experience'][1]['points'] = facts['experience'][1]['points'] * 12
        with tempfile.TemporaryDirectory() as out, self.assertRaises(ValueError):
            resume.write('engineer', out, facts)

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


NOTES = {'basis', 'use', 'dates_note', 'work_rights_rule', 'drivers_licence_detail', 'honest_limits',
         'never_mention', 'honest_limits_rule', 'strengths'}
FIELD = r'^(Job title|Company|Started|Ended|Course|Institution|Finished|Locations|Notice period|Salary): '


def claims(node):
    """The strings of facts.json that may be said about him: no notes, no limits, no rules."""
    if isinstance(node, dict):
        return ' '.join(claims(v) for k, v in node.items() if k not in NOTES and not k.startswith('_'))
    return ' '.join(claims(v) for v in node) if isinstance(node, list) else resume.tidy(node)


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


class SeekProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.md = (ROOT / 'SEEK_PROFILE.md').read_text(encoding='utf-8')
        cls.blocks = text_blocks(cls.md)
        cls.held = ' '.join([claims(FACTS), CONFIG['seek']['where']] + [CONFIG['lanes'][k]['what'] for k in resume.LANES])

    def entries(self, section, first):
        """The text blocks of a section, split where a line starts with `first`."""
        found = []
        for row in self.blocks[section]:
            if row.startswith(first):
                found.append([])
            found[-1].append(row)
        return found

    def test_sections(self):
        self.assertEqual(list(self.blocks), ['Headline', 'Personal summary', 'Career history', 'Education',
                                             'Licences and certifications', 'Skills', 'Preferred roles and locations',
                                             'Right to work'])
        for heading in ['Resumes to store', 'Settings to check once']:
            self.assertIn('\n## ' + heading + '\n', self.md)

    def test_every_line_to_type_is_held_by_facts_or_lanes(self):
        known = resume.words(self.held + ' or ' + ' '.join(resume.GLUE))
        for rows in self.blocks.values():
            for row in rows:
                said = re.sub(FIELD, '', row.removeprefix('- '))
                self.assertLessEqual(numbers(said), numbers(self.held), row)
                self.assertFalse(resume.words(said) - known, row)

    def test_headline_and_summary(self):
        self.assertEqual(self.blocks['Headline'], [FACTS['identity']['titles']['drafter']])
        summary, = self.blocks['Personal summary']
        self.assertTrue(70 <= len(summary.split()) <= 90, len(summary.split()))
        self.assertTrue(summary.startswith('Civil design graduate with an Advanced Diploma'))

    def test_career_history_is_the_facts_newest_first(self):
        jobs = self.entries('Career history', 'Job title: ')
        self.assertEqual(len(jobs), len(FACTS['experience']))
        starts = [resume.started(row.split(': ')[1]) for job in jobs for row in job if row.startswith('Started: ')]
        self.assertEqual(starts, sorted(starts, reverse=True))
        by_role = {resume.tidy(j['role']): j for j in FACTS['experience']}
        for job in jobs:
            fact = by_role[job[0].split(': ', 1)[1]]
            started, ended = resume.tidy(fact['dates']).split(' to ')
            self.assertEqual(job[1:4], ['Company: ' + fact['employer'], 'Started: ' + started, 'Ended: ' + ended])
            points = [resume.tidy(p) for p in fact['points']]
            self.assertEqual(len(job[4:]), min(3, len(points)), job[0])
            for row in job[4:]:
                self.assertIn(row.removeprefix('- '), points)

    def test_education_is_the_facts(self):
        courses = self.entries('Education', 'Course: ')
        self.assertEqual(len(courses), len(FACTS['education']))
        for course, fact in zip(courses, FACTS['education']):
            self.assertTrue(course[0].startswith('Course: ' + fact['qualification']))
            self.assertIn(fact.get('code', ''), course[0])
            started, ended = resume.tidy(fact['dates']).split(' to ')
            self.assertEqual(course[1:3], ['Institution: ' + fact['provider'], 'Started: ' + started])
            self.assertIn(course[3], ['Finished: ' + fact.get('completed', ended), 'Finished: ' + ended])
            self.assertEqual([row.removeprefix('- ') for row in course[4:]], fact['points'])

    def test_skills_hold_the_software_in_facts_and_no_other_tool(self):
        skills = self.blocks['Skills']
        self.assertEqual(skills[:len(FACTS['capabilities']['software'])], FACTS['capabilities']['software'])
        self.assertEqual(len(skills), len(set(skills)))
        for tool in NOT_HIS:
            self.assertNotRegex(self.md, r'(?i)\b' + re.escape(tool) + r'\b')

    def test_visa_end_date_only_in_the_right_to_work_text(self):
        self.assertEqual(self.blocks['Right to work'], [FACTS['answers']['right_to_work']['free_text']])
        self.assertEqual(self.md.count('2027'), 1)

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
