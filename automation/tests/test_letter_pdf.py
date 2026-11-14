"""The cover letter PDF of a queue entry (automation/scripts/letter_pdf.py) and the retired compact_pdf.py commands."""
import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import common  # noqa: E402
import compact_pdf  # noqa: E402
import pymupdf  # noqa: E402
import resume  # noqa: E402

try:
    import letter_pdf  # noqa: E402
except ImportError:   # it did not exist before 14 Nov 2026: every test of it then fails, as it should
    letter_pdf = None

FACTS = common.FACTS
BODY = ['I am applying for the Junior Civil Drafter role advertised on SEEK. Your advert asks for subdivision drawings in Civil 3D.',
        'In the Advanced Diploma of Civil Construction Design, finished in February 2026, I designed road geometry, earthworks and '
        'stormwater drainage in AutoCAD and Civil 3D to Australian Standards.',
        'I live in Melton and can start two weeks after an offer. Full working rights in Australia (Subclass 485 visa), no '
        'sponsorship needed. Could we talk this week?']
LETTER = 'Hello,\n\n' + '\n\n'.join(BODY) + '\n\nMarc Masarate'


def flat(text):
    return ' '.join(text.split())


class LetterPdf(unittest.TestCase):
    def setUp(self):
        if letter_pdf is None:
            self.fail('automation/scripts/letter_pdf.py is missing: no command builds a cover letter PDF from a queue entry')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.qdir = self.root / 'queue'

    def put(self, entry_id='acme-junior-drafter-1', where='open', **kw):
        e = {'id': entry_id, 'lane': 'drafter', 'route': 'EMAIL', 'company': 'Acme Civil Pty Ltd', 'role': 'Junior Civil Drafter',
             'resume_variant': 'drafter', 'relocation_line': '', 'cover_letter_text': LETTER, 'tone_allow': []}
        e.update(kw)
        path = self.qdir / where / f'{entry_id}.json' if where == 'open' else self.qdir / 'done' / '2026-11' / f'{entry_id}.json'
        common.write_json(path, e)
        return e

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = letter_pdf.main(list(args) + ['--dir', str(self.qdir), '--date', '14 November 2026'])
        return code, out.getvalue(), err.getvalue()

    def text(self, path):
        with pymupdf.open(path) as doc:
            return len(doc), '\n'.join(page.get_text() for page in doc), [link.get('uri') for page in doc for link in page.get_links()]

    def test_one_page_with_the_resume_header_and_the_whole_letter(self):  # F14, S2
        self.put()
        out = self.root / 'letter.pdf'
        code, printed, err = self.run_cli('acme-junior-drafter-1', str(out))
        self.assertEqual(code, 0, err)
        data = out.read_bytes()
        self.assertEqual(printed.strip(), f'{out}  {len(data)} bytes  sha256 {hashlib.sha256(data).hexdigest()}')
        pages, text, links = self.text(out)
        self.assertEqual(pages, 1)
        self.assertLess(len(data), 20000)
        body = flat(text)
        for line in BODY + ['Hello,', 'Kind regards,', 'Marc Masarate', '14 November 2026', 'Acme Civil Pty Ltd']:
            self.assertIn(flat(line), body)
        header = resume.Lines(FACTS)
        resume.header(header, 'drafter')
        for kind, line, _ in header:   # the same lines as the top of the drafter resume (a ' | ' may break a line)
            for part in line.split(' | '):
                self.assertIn(flat(part), body, kind)
        self.assertIn(FACTS['eligibility']['work_rights_short'], body)
        self.assertNotIn('December 2027', body)
        self.assertIn(FACTS['identity']['portfolio_url'], links)

    def test_the_header_follows_the_resume_variant_and_done_entries_are_found(self):
        self.put('acme-tech-2', where='done', resume_variant='technician', lane='technician')
        out = self.root / 'tech.pdf'
        self.assertEqual(self.run_cli('acme-tech-2', str(out))[0], 0)
        text = flat(self.text(out)[1])
        for part in FACTS['identity']['titles']['technician'].split(' | '):
            self.assertIn(flat(part), text)
        self.assertNotIn(FACTS['identity']['titles']['drafter'].split(' | ')[0] + ' |', text)

    def test_the_relocation_line_is_printed_once_at_the_end_of_the_last_paragraph(self):
        line = 'I will relocate to Geelong for this role and can start two weeks after an offer.'
        self.put(relocation_line=line)
        out = self.root / 'r.pdf'
        self.assertEqual(self.run_cli('acme-junior-drafter-1', str(out))[0], 0)
        text = flat(self.text(out)[1])
        self.assertEqual(text.count(flat(line)), 1)
        self.assertLess(text.index(flat(line)), text.index('Kind regards,'))
        self.put(cover_letter_text=LETTER.replace('Could we talk', line + ' Could we talk'), relocation_line=line)
        self.assertEqual(self.run_cli('acme-junior-drafter-1', str(out))[0], 0)
        self.assertEqual(flat(self.text(out)[1]).count(flat(line)), 1)

    def test_a_letter_that_fails_the_checks_is_refused_and_nothing_is_written(self):  # S14
        out = self.root / 'bad.pdf'
        for letter, needle in (('', 'letter text missing'),
                               (LETTER.replace('Could we talk', 'Thanks.\n\nCould we talk'), 'has 4 paragraphs'),
                               (LETTER.replace('I am applying for', 'Please accept my application for'), 'banned phrase'),
                               (LETTER.replace('no sponsorship needed', 'no sponsorship needed until Dec 2027'), 'visa end date'),
                               (LETTER.replace('Civil 3D.', 'Civil 3D – fast.'), 'banned character')):
            self.put(cover_letter_text=letter)
            code, printed, err = self.run_cli('acme-junior-drafter-1', str(out))
            self.assertEqual((code, printed), (1, ''), letter)
            self.assertIn(needle, err)
            self.assertFalse(out.exists())
        self.assertEqual(self.run_cli('no-such-entry', str(out))[0], 1)

    def test_a_letter_that_does_not_fit_one_page_is_refused(self):
        lines = letter_pdf.letter_lines(self.put(), FACTS, '14 November 2026')
        long = lines + [('p', ' '.join(BODY), 9)] * 12
        with self.assertRaisesRegex(ValueError, 'does not fit on one page'):
            letter_pdf.draw(long)


class CompactPdfRetired(unittest.TestCase):
    """F14: compact_pdf.py resume printed an unchecked resume ('supervising site activities'); its letter had no body."""

    def test_both_commands_stop_and_point_to_the_real_files(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'x.pdf'
            draft = Path(d) / 'entry.json'
            draft.write_text(json.dumps({'cover_letter_text': LETTER, 'lane': 'drafter'}), encoding='utf-8')
            for args, needle in ((['resume', str(out), '--lane', 'drafter'], 'documents/resume/Marc_Masarate_Resume_<Variant>.pdf'),
                                 (['letter', str(draft), str(out)], 'letter_pdf.py ENTRY_ID OUT.pdf')):
                with self.assertRaises(SystemExit) as stop:
                    compact_pdf.main(args)
                self.assertIn(needle, str(stop.exception.code))
                self.assertFalse(out.exists())
        source = (SCRIPTS / 'compact_pdf.py').read_text(encoding='utf-8')
        self.assertNotIn('supervising site activities', source)
        self.assertFalse(hasattr(compact_pdf, 'resume_pdf'))


if __name__ == '__main__':
    unittest.main()
