#!/usr/bin/env python3
"""Check a drafted cover letter against the user's facts and turn it into a clean one-page PDF.

Usage:
  python cover_letter.py LETTER.txt --profile profile.json --master MASTER --company "Company" --role "Role"
         --out OUT.pdf [--posting job-posting.md] [--combine RESUME.pdf] [--max-words N]
         [--location CITY] [--subject TEXT] [--engine tectonic|xelatex|lualatex|pdflatex]

LETTER.txt is plain text, from the greeting ("Dear Hiring Team,") to the sign-off ("Sincerely," then the name on the
next line), with paragraphs separated by blank lines. MASTER is the master resume (.tex, .docx, .pdf, .md or .txt).

What it checks (each finding goes to "fix" = must change, or "review" = change it or be sure it's right):
  - body length over the word limit (--max-words, else profile letterMaxWords, else 250) -> fix; under 150 -> review.
    Only the body counts: the greeting, sign-off and name lines are left out.
  - missing greeting, sign-off or the name under the sign-off -> fix
  - numbers, percentages or money that appear neither in the master resume nor in profile.json -> fix (invented facts);
    a number found only in the posting -> review (fine when it describes the company, not the user)
  - tools or skills named in the posting but absent from the master, used in the letter -> review
  - placeholders ([Company], <...>, TODO, XXX, lorem ipsum ...) -> fix
  - characters the PDF can't print (emoji and other symbols) -> fix. Curly quotes, dashes and ellipses are fine.

Then it builds the PDF with LaTeX (11pt, letter paper, 1 inch margins, no page number). The layout follows the
profile's letterStyle: "" (default: name heading, contact line "City, ST | phone | email", links line, date,
"Hiring Team / Company", letter) or "carlito" (Carlito font with lining digits, capitalised bold name, one contact line
with the first link, date, address block "Hiring Team / Company / location", bold "Re: <subject>" line; the subject
defaults to the role and the location to --location, else the posting's Location line).
Existing outputs are moved into _old/ first, never deleted. Build files live in the system temp folder.

--combine RESUME.pdf: a second PDF, <Name>_Resume_and_Cover_Letter_<Company>.pdf, is saved next to OUT.pdf: resume first, or the
letter first when the profile says "combinedOrder": "letter-first".

Output: one JSON object {ok, pdf, combined, words, max_words, layout, engine, fix[], review[], digits{}, ...}.
Exit codes: 0 all good, 2 something to fix or review, 1 bad input or the PDF failed to build,
3 no LaTeX engine on this computer (the checks still run; make a .docx instead).
"""
import argparse
import datetime as dt
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(HERE, '..', '..', 'lib')):
    if os.path.isdir(os.path.join(_p, 'jobkit')):
        sys.path.insert(0, os.path.abspath(_p))
        break
from jobkit import cli, files, text  # noqa: E402
from jobkit import location as loc  # noqa: E402

try:                                  # shared LaTeX helper from the resume pipeline; optional
    from jobkit import latex as _jk_latex
except Exception:                     # pragma: no cover - depends on what is installed
    _jk_latex = None

DEFAULT_MAX_WORDS = 250
MIN_WORDS = 150

GREETING = re.compile(r'^\s*(dear|hello|hi|greetings|good (morning|afternoon)|to whom it may concern)\b', re.I)
SIGNOFF = re.compile(r'^\s*(sincerely|yours sincerely|sincerely yours|yours truly|yours faithfully|best regards|'
                     r'kind regards|warm regards|warmest regards|regards|best wishes|best|respectfully|'
                     r'with thanks|many thanks|thank you)\s*[,.!]?\s*$', re.I)

PLACEHOLDERS = [
    (re.compile(r'\[[^\]\n]{1,60}\]'), 'a [bracketed] slot'),
    (re.compile(r'<[^<>\n]{1,80}>'), 'a <...> slot'),
    (re.compile(r'\{\{[^}\n]*\}\}'), 'a {{...}} slot'),
    (re.compile(r'\b(TODO|TBD|TBC|FIXME|XXX+)\b'), 'a to-do marker'),
    (re.compile(r'lorem ipsum', re.I), 'lorem ipsum filler'),
    (re.compile(r'\b(company name|hiring manager name|job title here|your name here|insert [a-z ]{2,30})\b', re.I),
     'template wording'),
]

# Typography that is fine to type: normalised for LaTeX rather than flagged.
_TYPO = {
    '\u2018': "`", '\u2019': "'", '\u201a': ',', '\u201c': '``', '\u201d': "''", '\u201e': ',,',
    '\u2013': '--', '\u2014': '---', '\u2012': '--', '\u2015': '---', '\u2010': '-', '\u2011': '-',
    '\u2026': '\\ldots{}', '\u00a0': '~', '\u2009': ' ', '\u202f': ' ', '\u2002': ' ', '\u2003': ' ',
    '\u00b7': '\\textperiodcentered{}', '\u2022': '\\textbullet{}', '\u20ac': '\\texteuro{}', '\u00a3': '\\pounds{}',
}
_LATEX_SPECIAL = {
    '\\': '\\textbackslash{}', '&': '\\&', '%': '\\%', '$': '\\$', '#': '\\#', '_': '\\_', '{': '\\{', '}': '\\}',
    '~': '\\textasciitilde{}', '^': '\\textasciicircum{}', '<': '\\textless{}', '>': '\\textgreater{}',
    '|': '\\textbar{}',
}

# Profile keys that are settings, not facts: their numbers must not make an invented number look supported.
_SETTING_KEYS = {'automationLevel', 'resumeMaxPages', 'bulletFormula', 'coverLetterPolicy', 'letterStyle',
                 'letterMaxWords', 'alwaysCombine', 'combinedOrder', 'weeklyGoal', 'writingStyle', 'extraRules',
                 '_comment'}

NUMBER = re.compile(r'(?<![\w.])([$£€]?\s?\d[\d,]*(?:\.\d+)?)(\s?(?:%|percent\b|per cent\b|[kK]\b|[mM]\b|million\b|'
                    r'billion\b|\+))?')


# ---- reading the letter -------------------------------------------------------------------------------------------

def paragraphs(raw):
    raw = raw.replace('\r\n', '\n').replace('\r', '\n').strip()
    return [p.strip() for p in re.split(r'\n\s*\n', raw) if p.strip()]


def split_letter(paras):
    """-> (greeting or None, body paragraphs, sign-off or None, name lines [])."""
    greeting, signoff, name_lines = None, None, []
    body = list(paras)
    if body and GREETING.match(body[0].splitlines()[0]):
        lines = body[0].splitlines()
        greeting = lines[0].strip()
        rest = ' '.join(l.strip() for l in lines[1:]).strip()
        body = ([rest] if rest else []) + body[1:]
    # sign-off: look in the last three paragraphs, line by line
    for back in range(1, min(3, len(body)) + 1):
        idx = len(body) - back
        lines = body[idx].splitlines()
        for li, line in enumerate(lines):
            if SIGNOFF.match(line):
                signoff = line.strip()
                name_lines = [l.strip() for l in lines[li + 1:] if l.strip()]
                for later in body[idx + 1:]:
                    name_lines += [l.strip() for l in later.splitlines() if l.strip()]
                before = '\n'.join(lines[:li]).strip()
                body = body[:idx] + ([before] if before else [])
                break
        if signoff:
            break
    return greeting, body, signoff, name_lines


def word_count(paras):
    return sum(len(re.findall(r"[A-Za-z0-9\u00c0-\u024f]+(?:['\u2019\-][A-Za-z0-9\u00c0-\u024f]+)*", p)) for p in paras)


# ---- fact checks --------------------------------------------------------------------------------------------------

def _flatten(obj, skip=()):
    if isinstance(obj, dict):
        return ' '.join(_flatten(v) for k, v in obj.items() if k not in skip)
    if isinstance(obj, (list, tuple)):
        return ' '.join(_flatten(v) for v in obj)
    return '' if obj is None or isinstance(obj, bool) else str(obj)


def _fmt(v):
    return str(int(v)) if float(v).is_integer() else str(v)


def number_keys(s):
    """Canonical forms of the numbers in a string: '$1,200' -> {'1200'}, '18%' -> {'18'}, '120K' -> {'120', '120000'}."""
    keys = set()
    for m in NUMBER.finditer(s or ''):
        raw = re.sub(r'[$£€,\s]', '', m.group(1)).rstrip('.')
        if not raw or not re.search(r'\d', raw):
            continue
        keys.add(raw)
        if '.' in raw:
            keys.add(raw.rstrip('0').rstrip('.'))
        suffix = (m.group(2) or '').strip().lower()
        try:
            val = float(raw)
        except ValueError:
            continue
        if suffix == 'k':
            keys.add(_fmt(val * 1000))
        elif suffix in ('m', 'million'):
            keys.add(_fmt(val * 1000000))
        elif suffix == 'billion':
            keys.add(_fmt(val * 1000000000))
        if raw.isdigit() and int(raw) >= 1000 and int(raw) % 1000 == 0:
            keys.add(_fmt(val / 1000))        # "120,000" also supports "120K"
    return keys


def letter_numbers(s):
    """[(as written, canonical key)] for each number in the letter."""
    out = []
    for m in NUMBER.finditer(s or ''):
        written = (m.group(1) + (m.group(2) or '')).strip()
        raw = re.sub(r'[$£€,\s]', '', m.group(1)).rstrip('.')
        if raw and re.search(r'\d', raw):
            out.append((written, raw))
    return out


def check_numbers(body_text, facts_text, posting_text, allowed_text, today=None):
    fix, review = [], []
    known = number_keys(facts_text)
    allowed = number_keys(allowed_text)
    in_posting = number_keys(posting_text)
    year = (today or dt.date.today()).year
    seen = set()
    for written, key in letter_numbers(body_text):
        if key in seen:
            continue
        seen.add(key)
        alt = key.rstrip('0').rstrip('.') if '.' in key else key
        if key in known or alt in known or key in allowed:
            continue
        if key.isdigit() and int(key) in (year, year + 1):      # "the Summer 2027 internship"
            continue
        if key in in_posting:
            review.append(f'"{written}" appears in the posting but not in your master resume: fine if it describes the '
                          f'company or the role, not if it is presented as your own result')
        else:
            fix.append(f'"{written}" is not in your master resume or profile: remove it or use the real figure from '
                       f'the master (never invent numbers)')
    return fix, review


def _vocab():
    """A function returning the tool/skill terms in lower-case text (rank_jobs' vocabulary when available)."""
    try:
        if HERE not in sys.path:
            sys.path.insert(0, HERE)
        import rank_jobs  # same folder
        weak = getattr(rank_jobs, 'WEAK', set())
        return lambda s: {t for t in rank_jobs.terms_in(s) if t not in weak}
    except Exception:
        words = ['python', 'sql', 'excel', 'power bi', 'tableau', 'looker', 'pandas', 'java', 'javascript',
                 'typescript', 'react', 'node.js', 'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'git', 'spark',
                 'snowflake', 'dbt', 'airflow', 'salesforce', 'sap', 'jira', 'autocad', 'solidworks', 'matlab',
                 'c++', 'c#', 'machine learning', 'tensorflow', 'pytorch', 'linux', 'figma', 'hubspot']

        def find(s):
            return {w for w in words if re.search(r'(?<![a-z0-9])' + re.escape(w) + r'(?![a-z0-9+#])', s)}
        return find


def check_terms(body_text, master_text, posting_text, profile_skills):
    if not posting_text:
        return []
    terms = _vocab()

    def low(s):
        return re.sub(r'\s+', ' ', (s or '').lower())
    posting_terms = terms(low(posting_text))
    master_terms = terms(low(master_text + ' ' + profile_skills))
    used = terms(low(body_text))
    return [f'"{t}" comes from the posting but is not in your master resume: don\'t present it as your skill '
            f'(say you are keen to learn it, or remove it)' for t in sorted((used & posting_terms) - master_terms)]


def check_placeholders(s):
    out = []
    for rx, what in PLACEHOLDERS:
        for m in rx.finditer(s):
            out.append(f'Placeholder left in the letter ({what}): "{m.group(0)}"')
    return out


def printable(ch):
    """True when the PDF fonts can show this character (after typography normalisation)."""
    o = ord(ch)
    if ch in _TYPO or ch in '\n\t':
        return True
    if 0x20 <= o < 0x7f:
        return True
    if 0xa0 <= o <= 0x17f:          # Latin-1 Supplement and Latin Extended-A (accented letters)
        return o != 0xad            # a soft hyphen is invisible: flag it
    return o in (0x218, 0x219, 0x21a, 0x21b)   # Romanian comma-below letters


def check_characters(s):
    bad = []
    for ch in s:
        if not printable(ch) and ch not in bad:
            bad.append(ch)
    if not bad:
        return []
    shown = ', '.join(f'"{c}" (U+{ord(c):04X})' for c in bad[:8])
    return [f'Characters the PDF can\'t print: {shown}. Replace them with plain text']


# ---- LaTeX --------------------------------------------------------------------------------------------------------

def tex_escape(s):
    """Plain text -> LaTeX: specials escaped, typography normalised, straight double quotes paired, characters the
    fonts can't show dropped (they are reported under fix)."""
    out, open_quote = [], True
    for ch in s or '':
        if ch == '"':
            out.append('``' if open_quote else "''")
            open_quote = not open_quote
        elif ch in _LATEX_SPECIAL:
            out.append(_LATEX_SPECIAL[ch])
        elif ch in _TYPO:
            out.append(_TYPO[ch])
        elif printable(ch):
            out.append(ch)
    return ''.join(out)


def url_escape(u):
    return u.replace('\\', '').replace('%', '\\%').replace('#', '\\#').replace('{', '').replace('}', '')


def link_href(link):
    link = link.strip()
    target = link if re.match(r'[a-z]+://', link, re.I) else 'https://' + link
    label = re.sub(r'^https?://(www\.)?', '', link, flags=re.I).rstrip('/')
    return '\\href{%s}{%s}' % (url_escape(target), tex_escape(label))


def full_name(profile):
    name = (profile.get('resumeName') or '').strip()
    if not name:
        name = ' '.join(x for x in (profile.get('firstName', ''), profile.get('lastName', '')) if x).strip()
    return re.sub(r'\s+', ' ', name)


def city_line(profile):
    return ', '.join(x for x in ((profile.get('city') or '').strip(), (profile.get('state') or '').strip()) if x)


def letter_date(profile, today=None):
    today = today or dt.date.today()
    country = (profile.get('country') or '').strip().lower()
    month = today.strftime('%B')
    if country in ('united kingdom', 'uk', 'great britain', 'england', 'scotland', 'wales', 'northern ireland',
                   'ireland', 'australia', 'new zealand'):
        return f'{today.day} {month} {today.year}'
    return f'{month} {today.day}, {today.year}'


def links(profile):
    return [profile[k].strip() for k in ('linkedin', 'github', 'portfolio', 'website')
            if isinstance(profile.get(k), str) and profile[k].strip()]


def body_tex(greeting, body, signoff, name_lines, name):
    parts = []
    if greeting:
        parts.append(tex_escape(greeting))
    for p in body:
        parts.append(tex_escape(re.sub(r'\s*\n\s*', ' ', p)))
    if signoff:
        closing = tex_escape(signoff) + '\\\\[1.2em]\n' + '\\\\\n'.join(tex_escape(l) for l in (name_lines or [name]))
        parts.append('\\begin{minipage}[t]{\\linewidth}\n' + closing + '\n\\end{minipage}')
    return '\n\n'.join(parts)


PREAMBLE = r"""\documentclass[11pt,letterpaper]{article}
\usepackage[margin=1in]{geometry}
\usepackage{iftex}
\ifPDFTeX
  \usepackage[utf8]{inputenc}
  \usepackage[T1]{fontenc}
  %(pdffont)s
\else
  \usepackage{fontspec}
\fi
%(font)s
\usepackage{textcomp}
\usepackage[hidelinks]{hyperref}
\pagestyle{empty}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0.75em}
\raggedright
\begin{document}
"""


def build_tex(profile, company, role, greeting, body, signoff, name_lines, location='', subject='', today=None,
              job_location=None):
    name = full_name(profile) or (name_lines[0] if name_lines else '')
    style = (profile.get('letterStyle') or '').strip().lower()
    where = loc.location_line(profile, job_location)['line'].split(' · ') if job_location else [city_line(profile)]
    contact_bits = where + [(profile.get('phone') or '').strip(), (profile.get('email') or '').strip()]
    sep = ' \\textbar{} '
    lk = links(profile)
    date = tex_escape(letter_date(profile, today))
    if style == 'carlito':
        tex = PREAMBLE % {'pdffont': '', 'font': '\\usepackage[sfdefault,lining]{carlito}'}
        contact = [tex_escape(b) for b in contact_bits if b] + ([link_href(lk[0])] if lk else [])
        address = ['Hiring Team', tex_escape(company)] + ([tex_escape(location)] if location else [])
        tex += '{\\Large\\bfseries %s}\\par\n' % tex_escape(name.upper())
        if contact:
            tex += '\\vspace{-0.4em}' + sep.join(contact) + '\\par\n'
        tex += '\\vspace{0.6em}' + date + '\\par\n'
        tex += '\\\\\n'.join(address) + '\\par\n'
        tex += '\\textbf{Re: %s}\\par\n' % tex_escape(subject or role)
    else:
        tex = PREAMBLE % {'pdffont': '\\usepackage{lmodern}', 'font': ''}
        tex += '{\\LARGE\\bfseries %s}\\par\n' % tex_escape(name)
        contact = [tex_escape(b) for b in contact_bits if b]
        if contact:
            tex += '\\vspace{-0.5em}' + sep.join(contact) + '\\par\n'
        if lk:
            tex += '\\vspace{-0.75em}' + sep.join(link_href(x) for x in lk) + '\\par\n'
        tex += '\\vspace{0.6em}' + date + '\\par\n'
        tex += 'Hiring Team\\\\\n' + tex_escape(company) + '\\par\n'
        if subject:
            tex += '\\textbf{Re: %s}\\par\n' % tex_escape(subject)
    tex += body_tex(greeting, body, signoff, name_lines, name) + '\n\\end{document}\n'
    return tex


def pick_engine(wanted=None):
    """The given engine, else tectonic, xelatex, lualatex, pdflatex (the letter source works with all of them)."""
    for e in ([wanted] if wanted else ['tectonic', 'xelatex', 'lualatex', 'pdflatex']):
        if e and shutil.which(e):
            return e
    return None


def _log_errors(log):
    errors = []
    lines = (log or '').splitlines()
    for i, line in enumerate(lines):
        if line.startswith('!') or line.startswith('error:'):
            num = None
            for nxt in lines[i + 1:i + 8]:
                m = re.match(r'l\.(\d+)', nxt)
                if m:
                    num = int(m.group(1))
                    break
            errors.append({'line': num, 'message': line.lstrip('! ').strip()})
    return errors[:10]


def local_compile(tex_src, engine):
    """Compile in a fresh temp folder. Returns (pdf bytes or None, errors[])."""
    work = tempfile.mkdtemp(prefix='jobkit-letter-')
    try:
        with open(os.path.join(work, 'letter.tex'), 'w', encoding='utf-8') as f:
            f.write(tex_src)
        if engine == 'tectonic':
            cmds = [['tectonic', '--chatter', 'minimal', 'letter.tex']]
        else:
            cmds = [[engine, '-interaction=nonstopmode', '-halt-on-error', 'letter.tex']] * 2
        for cmd in cmds:
            try:
                r = subprocess.run(cmd, cwd=work, capture_output=True, text=True, errors='replace', timeout=600)
            except subprocess.TimeoutExpired:
                return None, [{'line': None, 'message': f'{engine} took longer than 10 minutes'}]
            if r.returncode != 0:
                log = (r.stdout or '') + '\n' + (r.stderr or '')
                logfile = os.path.join(work, 'letter.log')
                if os.path.exists(logfile):
                    log += '\n' + open(logfile, encoding='utf-8', errors='replace').read()
                return None, _log_errors(log) or [{'line': None, 'message': log.strip()[-600:]}]
        pdf = os.path.join(work, 'letter.pdf')
        if not os.path.exists(pdf):
            return None, [{'line': None, 'message': 'the engine produced no PDF'}]
        with open(pdf, 'rb') as f:
            return f.read(), []
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _shared_compile(fn, tex_src, engine):
    """Use jobkit.latex.compile_tex(main_tex, engine=None, timeout=300) -> {ok, pdf, errors, build_dir, ...}.
    Returns (pdf bytes or None, errors[])."""
    work = tempfile.mkdtemp(prefix='jobkit-letter-src-')
    res = None
    try:
        main = os.path.join(work, 'letter.tex')
        with open(main, 'w', encoding='utf-8') as f:
            f.write(tex_src)
        res = fn(main, engine=engine, timeout=600)
        if res.get('ok') and res.get('pdf') and os.path.exists(res['pdf']):
            with open(res['pdf'], 'rb') as f:
                return f.read(), []
        errors = [{'line': e.get('line'), 'message': e.get('message')} if isinstance(e, dict)
                  else {'line': None, 'message': str(e)} for e in (res.get('errors') or [])]
        return None, errors or [{'line': None, 'message': 'the LaTeX build failed'}]
    finally:
        shutil.rmtree(work, ignore_errors=True)
        cleanup = getattr(_jk_latex, 'cleanup', None)
        if cleanup and isinstance(res, dict):
            cleanup(res)


def compile_pdf(tex_src, engine):
    """Use jobkit.latex.compile_tex when the shared helper exists, else the local helper.
    Returns (pdf bytes or None, errors[], helper name)."""
    fn = getattr(_jk_latex, 'compile_tex', None) if _jk_latex else None
    if fn and not os.environ.get('JOBKIT_LETTER_LOCAL_COMPILE'):
        try:
            pdf, errors = _shared_compile(fn, tex_src, engine)
            return pdf, errors, 'jobkit.latex'
        except Exception:
            pass
    pdf, errors = local_compile(tex_src, engine)
    return pdf, errors, 'local'


def combine(first, second, dest):
    """Join two PDFs (pypdf, else pdfunite). Returns an error string or None."""
    try:
        from pypdf import PdfWriter
    except ImportError:
        PdfWriter = None
    if PdfWriter is not None:
        try:
            w = PdfWriter()
            for p in (first, second):
                w.append(p)
            with open(dest, 'wb') as f:
                w.write(f)
            return None
        except Exception as e:  # a damaged PDF
            return f'could not combine the PDFs: {e}'
    if shutil.which('pdfunite'):
        r = subprocess.run(['pdfunite', first, second, dest], capture_output=True, text=True, errors='replace')
        return None if r.returncode == 0 else f'pdfunite failed: {r.stderr.strip()[:300]}'
    return 'install pypdf (pip install pypdf) or poppler (pdfunite) to combine the PDFs'


def file_words(profile, fallback=''):
    return '_'.join((full_name(profile) or fallback or 'Applicant').split())


def posting_field(posting_text, name):
    m = re.search(r'^-\s*%s:\s*(.+)$' % re.escape(name), posting_text or '', re.M | re.I)
    return m.group(1).strip() if m else ''


def main():
    ap = argparse.ArgumentParser(description='Check a cover letter and build its PDF.')
    ap.add_argument('letter')
    ap.add_argument('--profile', required=True)
    ap.add_argument('--master', required=True)
    ap.add_argument('--company', required=True)
    ap.add_argument('--role', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--posting')
    ap.add_argument('--combine', metavar='RESUME_PDF')
    ap.add_argument('--max-words', type=int)
    ap.add_argument('--location', default='')
    ap.add_argument('--subject', default='')
    ap.add_argument('--engine', choices=['tectonic', 'xelatex', 'lualatex', 'pdflatex'])
    a = ap.parse_args()

    cli.need_files(a.letter, a.profile, a.master, a.posting, a.combine)
    if not a.out.lower().endswith('.pdf'):
        cli.fail('--out must be a .pdf file')
    profile = cli.load_json(a.profile)
    if not isinstance(profile, dict):
        cli.fail(f'Not a valid profile JSON file: {a.profile}')
    raw = text.read_text(a.letter)
    try:
        master_text = text.read_text(a.master)
    except Exception as e:
        cli.fail(f'Could not read the master resume: {e}')
    posting_text = text.read_text(a.posting) if a.posting else ''

    fix, review = [], []
    paras = paragraphs(raw)
    if not paras:
        cli.fail('The letter file is empty')
    greeting, body, signoff, name_lines = split_letter(paras)
    if not greeting:
        fix.append('No greeting: start the letter with a line like "Dear Hiring Team,"')
    if not signoff:
        fix.append('No sign-off: end the letter with "Sincerely," and your name on the next line')
    elif not name_lines:
        fix.append('Add your name on the line under the sign-off')

    words = word_count(body)
    try:
        limit = int(a.max_words or profile.get('letterMaxWords') or DEFAULT_MAX_WORDS)
    except (TypeError, ValueError):
        limit = DEFAULT_MAX_WORDS
    if words > limit:
        fix.append(f'The letter body has {words} words; the limit is {limit}. Cut {words - limit} or more')
    elif words < MIN_WORDS:
        review.append(f'The letter body has only {words} words; most good letters have {MIN_WORDS}-{limit}')

    body_text = '\n'.join(body)
    facts = master_text + '\n' + _flatten(profile, skip=_SETTING_KEYS)
    allowed = ' '.join([a.company, a.role, a.subject, a.location, posting_field(posting_text, 'Company'),
                        posting_field(posting_text, 'Role')])
    nf, nr = check_numbers(body_text, facts, posting_text, allowed)
    fix += nf
    review += nr
    review += check_terms(body_text, master_text, posting_text, str(profile.get('skills') or ''))
    fix += check_placeholders(raw)
    fix += check_characters(raw)

    location = a.location.strip()
    if not location and posting_text:
        location = re.split(r'[;(]', posting_field(posting_text, 'Location'))[0].strip()
        if location.lower() in ('not stated', 'unknown', 'remote'):
            location = ''

    result = {'ok': False, 'pdf': None, 'combined': None, 'words': words, 'max_words': limit,
              'layout': (profile.get('letterStyle') or '').strip().lower() or 'default', 'engine': None,
              'fix': fix, 'review': review}

    engine = pick_engine(a.engine)
    if not engine:
        result['hint'] = ('No LaTeX engine found (install Tectonic: https://tectonic-typesetting.github.io). '
                          'Make the letter as a .docx instead.')
        cli.emit(result, cli.NO_LATEX)
    result['engine'] = engine

    job_location = a.location.strip() or (posting_field(posting_text, 'Location') if posting_text else '')
    tex_src = build_tex(profile, a.company, a.role, greeting, body, signoff, name_lines, location=location,
                        subject=a.subject.strip(), job_location=job_location)
    pdf_bytes, errors, helper = compile_pdf(tex_src, engine)
    result['compiled_with'] = helper
    if pdf_bytes is None:
        result.update(errors=errors, hints=['The letter text is escaped automatically; if this keeps failing, '
                                            'check for unusual characters or make a .docx instead.'])
        cli.emit(result, cli.BAD_INPUT)

    out = os.path.abspath(a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    result['previous_version_moved_to'] = files.move_to_old(out)
    with open(out, 'wb') as f:
        f.write(pdf_bytes)
    result['pdf'] = out
    result['pages'] = text.pdf_pages(out)
    if result['pages'] and result['pages'] > 1:
        fix.append(f'The letter runs to {result["pages"]} pages: cut it to one page')

    pdf_txt = text.pdf_text(out)
    if pdf_txt is not None:
        compact = re.sub(r'\s+', '', pdf_txt)
        tokens = [m.group(0) for m in re.finditer(r'\d[\d,.]*\d|\d', body_text)]
        src_digits = sum(len(re.findall(r'\d', t)) for t in tokens)
        found = sum(len(re.findall(r'\d', t)) for t in tokens if t in compact)
        result['digits'] = {'letter_body': src_digits, 'pdf': found}
        if found < src_digits:
            fix.append('Digits are missing from the PDF text (tracking systems would not read them): the carlito '
                       'layout must load \\usepackage[sfdefault,lining]{carlito}')
        if name_lines and text.norm(name_lines[0]) and text.norm(name_lines[0]) not in text.norm(pdf_txt):
            review.append('Your name was not found in the PDF text')

    if a.combine:
        name_part = file_words(profile, name_lines[0] if name_lines else '')
        company_part = files.safe_name(a.company).replace(' ', '_')
        dest = os.path.join(os.path.dirname(out), f'{name_part}_Resume_and_Cover_Letter_{company_part}.pdf')
        resume = os.path.abspath(a.combine)
        letter_first = (profile.get('combinedOrder') or '').strip().lower() == 'letter-first'
        order = (out, resume) if letter_first else (resume, out)
        if os.path.abspath(dest) in (resume, out):
            review.append('Not combined: the combined file name would overwrite an input')
        else:
            moved = files.move_to_old(dest)
            err = combine(order[0], order[1], dest)
            if err:
                review.append(err)
            else:
                result['combined'] = dest
                result['combined_order'] = 'letter-first' if letter_first else 'resume-first'
                if moved:
                    result['previous_combined_moved_to'] = moved

    result['ok'] = not fix
    cli.emit(result, cli.ATTENTION if (fix or review) else cli.OK)


if __name__ == '__main__':
    main()
