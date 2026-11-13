#!/usr/bin/env python3
"""Marc's resume in three lane variants (drafter, technician, engineer), built from facts.json only.

Every printed line is either one fact, tidied (ranges written with 'to', project values left out), or
words written in this file together with the facts they rest on; verify() refuses to build when such
a line holds a word or number that its facts do not. The PDF is drawn with pymupdf in the standard
PDF fonts: text goes down in reading order, nothing is embedded, each file is a few KB. The HTML next
to each PDF carries the same lines.

Usage:
  resume.py build [--out DIR] [--png DIR]   all variants into documents/resume/ (page images if asked)
  resume.py text LANE                       the lines of one variant and the facts each rests on
"""
import argparse
import html
import re
from pathlib import Path

import pymupdf

from common import ROOT, REPO, FACTS

LANES = ('drafter', 'technician', 'engineer')
OUT_DIR = REPO / 'documents' / 'resume'
MONTHS = 'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()

# Words that join facts but claim nothing. Anything else in a written line must be in its facts.
GLUE = 'a an and the with in of to for as on at from by while used covering completed referees'.split()

# The profile of each lane, 50 to 65 words. The names in braces are filled from the facts; every other
# word has to be in the facts that profile() names, or verify() stops the build.
PROFILE = {
    'drafter':
        'Civil design graduate with an {diploma}, completed in Australia in {completed}, and a {degree}. '
        'Designed and documented road geometry, earthworks, pavement systems and stormwater drainage, and '
        'prepared and reviewed technical drawings in AutoCAD and Civil 3D, applying Australian Standards. '
        'Site experience reviewing structural and architectural drawings and checking work against project '
        'requirements.',
    'technician':
        'Civil construction design graduate (Advanced Diploma, {completed}) with site experience in inspections, '
        'quality checks and safety checks. Prepared site reports, material records and progress reports, and in '
        'technical support resolved 40 to 60 cases a day while keeping accurate case notes. Advanced Diploma '
        'coursework used AS 1289, AS 1726 and Austroads road and pavement guides. Available for site, regional '
        'and FIFO work.',
    'engineer':
        'Civil engineering graduate with site experience as a project-in-charge and field engineer in the '
        'Philippines ({span}): coordinating 10 to 15 workers a day, site inspections, safety checks, quality '
        'checks, reviewing drawings, tracking procurement and preparing progress reports. Completed an {diploma} '
        'in Australia in {completed}, covering road geometry, earthworks, pavement systems and stormwater '
        'drainage.',
}

# Layout, in points. kind: (font, size, colour, space above, indent)
A4 = pymupdf.paper_rect('a4')
LEFT, TOP, BOTTOM, LEADING = 54, 44, 44, 1.32
WIDTH = A4.width - 2 * LEFT
INK, GREY = (0.1, 0.1, 0.1), (0.27, 0.27, 0.27)
STYLE = {
    'name': ('hebo', 20, INK, 0, 0),
    'headline': ('hebo', 10.5, INK, 2, 0),
    'meta': ('helv', 9.4, GREY, 2, 0),
    'h': ('hebo', 11, INK, 11, 0),
    'role': ('hebo', 10, INK, 6, 0),
    'org': ('helv', 10, GREY, 0, 0),
    'label': ('hebo', 10, INK, 5, 0),
    'p': ('helv', 10, INK, 4, 0),
    'kv': ('helv', 10, INK, 4, 0),
    'li': ('helv', 10, INK, 1.5, 11),
}
KEEP = ('h', 'org', 'label')           # never the last line on a page (for a role see room_for)
BULLET = chr(149)                      # the bullet in the standard fonts' encoding
TAGS = {'name': 'h1', 'headline': 'p class="headline"', 'meta': 'p class="meta"', 'h': 'h2', 'role': 'h3',
        'org': 'p class="org"', 'label': 'p class="label"', 'p': 'p', 'kv': 'p', 'li': 'li'}


def pick(facts, path):
    """The fact at a dotted path, for example 'experience.1.points.2'."""
    node = facts
    for key in path.split('.'):
        node = node[int(key)] if isinstance(node, list) else node[key]
    return node


def flat(fact):
    """Every string inside a fact, as one string."""
    if isinstance(fact, dict):
        fact = list(fact.values())
    return ' '.join(flat(x) for x in fact) if isinstance(fact, list) else str(fact)


def tidy(s):
    """A fact as it is printed: no project values, no source notes, 'to' in ranges, no dashes."""
    s = re.sub(r'\s+worth about PHP[^()]*\(AUD[^)]*\)', '', str(s))
    s = re.sub(r'\s*\(owner,[^)]*\)', '', s)
    s = re.sub(r'(?<=\d)\s*–\s*', ' to ', s).replace(' – ', ', ').replace('’', "'")
    if re.search(r'[–—]|PHP|AUD', s):
        raise ValueError(f'this fact cannot be printed as it stands: {s!r}')
    return s


def stem(word):
    word = word.lower()
    for end in ('ing', 'ed', 'es', 's'):
        if word.endswith(end) and len(word) - len(end) >= 4:
            return word[:-len(end)]
    return word


def words(s):
    return {stem(w) for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9/+'-]*(?:\.\d+)?", s)}


def verify(lines):
    """Raise if a line holds a word or number that the facts it names do not hold."""
    for kind, text, paths in lines:
        if kind in ('h', 'label'):
            continue
        said = text.split(': ', 1)[1] if kind == 'kv' else text
        known = words(' '.join(GLUE + [tidy(flat(pick(lines.facts, p))) for p in paths]))
        if words(said) - known:
            raise ValueError(f'not in the facts named {paths}: {sorted(words(said) - known)} in {text!r}')
    return lines


class Lines(list):
    """One resume: (kind, text, the paths in facts.json the text rests on), in reading order."""

    def __init__(self, facts):
        super().__init__()
        self.facts = facts

    def get(self, path):
        return tidy(pick(self.facts, path))

    def fact(self, kind, path):
        """One fact, printed as it stands."""
        self.append((kind, self.get(path), (path,)))

    def say(self, kind, text, *paths):
        """Words written here; verify() checks them against the facts named."""
        self.append((kind, tidy(text), paths))

    def head(self, text):
        self.append(('h', text, ()))


def started(dates):
    """(year, month) at the start of a dates field, for newest-first order."""
    m = re.match(r'(?:([A-Z][a-z]{2}) )?(\d{4})', dates)
    return int(m.group(2)), MONTHS.index(m.group(1)) + 1 if m.group(1) else 0


def jobs(facts):
    """Paths of the current job, the engineering roles and the other roles, each newest first."""
    paths = sorted((f'experience.{i}' for i in range(len(facts['experience']))),
                   key=lambda p: started(pick(facts, p + '.dates')), reverse=True)
    current = [p for p in paths if 'present' in pick(facts, p + '.dates')]
    site = [p for p in paths if p not in current and 'Engineer' in pick(facts, p + '.role')]
    return current, site, [p for p in paths if p not in current + site]


def header(out, lane):
    out.fact('name', 'identity.name')
    out.fact('headline', f'identity.titles.{lane}')
    contact = ['identity.location', 'identity.phone', 'identity.email', 'identity.portfolio_url']
    suburb = re.sub(r'\s+\d{4}$', '', out.get(contact[0]))   # suburb and state, no postcode
    out.say('meta', ' | '.join([suburb] + [out.get(p) for p in contact[1:]]), *contact)
    top = ['eligibility.work_rights_short', 'eligibility.drivers_licence', 'eligibility.white_card']
    out.say('meta', ' | '.join(out.get(p) for p in top), *top)


def profile(out, lane, dip, degree, site, other):
    """The lane's profile. It rests on the course, the past roles, the headlines and three lists."""
    oldest, newest = out.get(site[-1] + '.dates'), out.get(site[0] + '.dates')
    text = PROFILE[lane].format(
        diploma=out.get(dip + '.qualification'), completed=out.get(dip + '.completed'),
        degree=re.sub(r' \([A-Z]+\)$', '', out.get(degree + '.qualification')),
        span=f"{oldest.split(' to ')[0]} to {newest.split(' to ')[1]}")
    paths = [dip + k for k in ('.qualification', '.completed', '.provider', '.points')] + [degree + '.qualification']
    paths += [p + k for p in site + other for k in ('.role', '.employer', '.dates', '.points')]
    paths += ['identity.titles.technician', 'identity.titles.engineer', 'capabilities.civil_design',
              'capabilities.standards_coursework', 'eligibility.availability']
    out.say('p', text, *paths)


def job(out, path, first=None):
    """One role with its own points under it. `first` moves the points that match it to the top."""
    out.fact('role', path + '.role')
    out.say('org', f"{out.get(path + '.employer')} | {out.get(path + '.dates')}", path + '.employer', path + '.dates')
    points = pick(out.facts, path + '.points')
    for i in sorted(range(len(points)), key=lambda i: not (first and re.search(first, points[i]))):
        out.fact('li', f'{path}.points.{i}')


def course(out, path, points=True):
    title, paths = out.get(path + '.qualification'), [path + '.qualification']
    if 'code' in pick(out.facts, path):
        title, paths = f"{title} ({out.get(path + '.code')})", paths + [path + '.code']
    out.say('role', title, *paths)
    out.say('org', f"{out.get(path + '.provider')} | {out.get(path + '.dates')}", path + '.provider', path + '.dates')
    for i in range(len(pick(out.facts, path + '.points')) if points else 0):
        out.fact('li', f'{path}.points.{i}')


def coursework(out, *keys, where=' used in coursework'):
    labels = {'software': 'Software', 'standards_coursework': 'Standards' + where, 'methods_coursework': 'Methods' + where}
    for key in keys:
        out.say('kv', f"{labels[key]}: {', '.join(pick(out.facts, 'capabilities.' + key))}", 'capabilities.' + key)


def eligibility(out, *keys):
    e = 'eligibility.'
    for key in keys:
        if key == 'checks':
            out.say('li', 'Current National Police Certificate; Working with Children Check', e + 'police_check', e + 'wwcc')
        elif key == 'move':
            out.say('li', 'Will relocate anywhere in Australia', e + 'relocation', 'answers.willing_to_relocate')
        else:
            out.fact('li', e + key)


def build(lane, facts=FACTS):
    """The lines of one variant, checked against the facts."""
    out = Lines(facts)
    current, site, other = jobs(facts)
    study = [f'education.{i}' for i in range(len(facts['education']))]
    dip = next(p for p in study if 'code' in pick(facts, p))   # the Advanced Diploma carries its course code
    degree = next(p for p in study if p != dip)
    ready = ['medical_and_drug_tests', 'availability.0', 'availability.1', 'availability.2', 'move']
    held = ['drivers_licence', 'white_card', 'checks']
    header(out, lane)
    out.head('Profile')
    profile(out, lane, dip, degree, site, other)
    if lane == 'drafter':
        out.head('Design and drafting')
        course(out, dip)
        coursework(out, 'software', 'standards_coursework', 'methods_coursework')
        out.append(('label', 'Drawings in the online portfolio', ()))
        for i in range(len(facts['capabilities']['drawings_public'])):
            out.fact('li', f'capabilities.drawings_public.{i}')
        out.head('Work history')
        for path in current + site:
            job(out, path)
        out.head('Additional experience')
        for path in other:
            job(out, path)
        out.head('Education')
        course(out, dip, points=False)
        course(out, degree)
    elif lane == 'technician':
        out.head('Site inspection and quality-check experience')
        for path in site:
            job(out, path, first='inspect|quality|record|checked')
        out.head('Standards and methods used in Advanced Diploma coursework')
        coursework(out, 'standards_coursework', 'methods_coursework', where='')
        out.head('Tickets, licence and site readiness')
        eligibility(out, 'white_card', 'drivers_licence', 'checks', *ready)
        out.head('Other work history')
        for path in current + other:
            job(out, path)
        out.head('Education')
        course(out, dip)
        coursework(out, 'software')
        course(out, degree)
    else:
        out.head('Site experience')
        for path in site:
            job(out, path)
        out.head('Other work history')
        for path in current + other:
            job(out, path)
        out.head('Education')
        course(out, dip)
        coursework(out, 'software', 'standards_coursework', 'methods_coursework')
        course(out, degree)
    out.head('Eligibility and licences')
    eligibility(out, 'work_rights', *(held[:2] if lane == 'technician' else held + ready))
    out.say('p', 'Referees ' + out.get('references').lower(), 'references')
    return verify(out)


def lay(text, font, size, width, sep=' ', used=0):
    """Break text into lines no wider than `width`; `used` is taken on the first line. With sep ' | '
    a part moves to the next line whole where it can."""
    rows, row, room = [], '', width - used
    for unit in text.split(sep):
        if row and pymupdf.get_text_length(row + sep + unit, font, size) > room:
            rows.append(row)
            row, room = unit, width
        else:
            row = row + sep + unit if row else unit
    rows.append(row)
    return rows if sep == ' ' else [r for part in rows for r in lay(part, font, size, width)]


def shape(kind, text):
    """(bold label, lines, height) of one line of the resume on the page."""
    font, size, _, gap, indent = STYLE[kind]
    label = text.split(': ')[0] + ': ' if kind == 'kv' else ''
    rows = lay(text[len(label):], font, size, WIDTH - indent, ' | ' if kind in ('headline', 'meta') else ' ',
               pymupdf.get_text_length(label, 'hebo', size))
    return label, rows, gap + len(rows) * size * LEADING + (4 if kind == 'h' else 0)


def room_for(lines, shapes, n):
    """Height that must be free for line n to start on a page: a heading stays with what follows it
    and a role stays with all its points."""
    kind, total = lines[n][0], shapes[n][2]
    if kind == 'role':
        for m in range(n + 1, len(lines)):
            if lines[m][0] not in ('org', 'li'):
                break
            total += shapes[m][2]
    elif kind in KEEP and n + 1 < len(lines):
        total += room_for(lines, shapes, n + 1)
    return total


def draw(lines, path):
    """Write the PDF and return its page count. Text is written in the order of `lines`."""
    doc = pymupdf.open()
    shapes = [shape(kind, text) for kind, text, _ in lines]
    page, y = None, 0
    for n, ((kind, _, _), (label, rows, height)) in enumerate(zip(lines, shapes)):
        font, size, colour, gap, indent = STYLE[kind]
        if page is None or y + room_for(lines, shapes, n) > A4.height - BOTTOM:
            page, y = doc.new_page(width=A4.width, height=A4.height), TOP - gap
        y += gap
        for i, row in enumerate(rows):
            x = LEFT + indent
            if kind == 'li' and i == 0:
                page.insert_text((LEFT + 1, y + size), BULLET, fontname=font, fontsize=size, color=colour)
            if label and i == 0:
                page.insert_text((x, y + size), label, fontname='hebo', fontsize=size, color=colour)
                x += pymupdf.get_text_length(label, 'hebo', size)
            page.insert_text((x, y + size), row, fontname=font, fontsize=size, color=colour)
            y += size * LEADING
        if kind == 'h':
            page.draw_line((LEFT, y + 1.5), (LEFT + WIDTH, y + 1.5), color=GREY, width=0.6)
            y += 4
    ident = lines.facts['identity']
    for page in doc:
        page.clean_contents()   # one content stream a page, not one for every line: 25 KB becomes 5 KB
        for needle, uri in ((ident['portfolio_url'], ident['portfolio_url']), (ident['email'], 'mailto:' + ident['email'])):
            for rect in page.search_for(needle):
                page.insert_link({'kind': pymupdf.LINK_URI, 'from': rect, 'uri': uri})
    doc.set_metadata({'title': ident['name'] + ' resume', 'author': ident['name']})
    pages = len(doc)
    doc.save(path, garbage=4, deflate=True, no_new_id=True)   # no id, no dates: the same facts give the same file
    doc.close()
    return pages


def to_html(lines):
    """The same lines as a web page (templates/resume.html)."""
    ident = lines.facts['identity']
    body = []
    for n, (kind, text, _) in enumerate(lines):
        t = html.escape(text, quote=False)
        if kind == 'kv':
            t = '<b>' + t.replace(': ', ':</b> ', 1)
        if kind == 'meta':
            t = t.replace(ident['email'], f'<a href="mailto:{ident["email"]}">{ident["email"]}</a>')
            t = t.replace(ident['portfolio_url'], f'<a href="{ident["portfolio_url"]}">{ident["portfolio_url"]}</a>')
        tag = TAGS[kind]
        opens = '<ul>\n' if kind == 'li' and lines[n - 1][0] != 'li' else ''
        closes = '\n</ul>' if kind == 'li' and (n + 1 == len(lines) or lines[n + 1][0] != 'li') else ''
        body.append(f'{opens}<{tag}>{t}</{tag.split()[0]}>{closes}')
    page = (ROOT / 'templates' / 'resume.html').read_text(encoding='utf-8')
    return page.replace('{{title}}', html.escape(ident['name'] + ' resume')).replace('{{lines}}', '\n'.join(body))


def file_stem(lane, facts=FACTS):
    name = facts['identity']['name'].split()
    return f'{name[0]}_{name[-1]}_Resume_{lane.capitalize()}'


def write(lane, out_dir=OUT_DIR, facts=FACTS, png_dir=None):
    """Build one variant: PDF and HTML into out_dir. Returns (pdf path, pages)."""
    lines = build(lane, facts)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf = out_dir / (file_stem(lane, facts) + '.pdf')
    pages = draw(lines, pdf)
    if pages > 2:
        raise ValueError(f'{lane}: {pages} pages; a resume is two pages at most')
    pdf.with_suffix('.html').write_text(to_html(lines), encoding='utf-8')
    if png_dir:
        Path(png_dir).mkdir(parents=True, exist_ok=True)
        with pymupdf.open(pdf) as doc:
            for page in doc:
                page.get_pixmap(dpi=110).save(Path(png_dir) / f'{pdf.stem}_p{page.number + 1}.png')
    return pdf, pages


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build')
    b.add_argument('--out', default=str(OUT_DIR))
    b.add_argument('--png')
    t = sub.add_parser('text')
    t.add_argument('lane', choices=LANES)
    a = ap.parse_args(argv)
    if a.cmd == 'text':
        for kind, text, paths in build(a.lane):
            print(f"{kind}\t{text}\t{', '.join(paths)}")
        return
    for lane in LANES:
        pdf, pages = write(lane, a.out, png_dir=a.png)
        print(f'{pdf}  {pdf.stat().st_size} bytes  {pages} pages')


if __name__ == '__main__':
    main()
