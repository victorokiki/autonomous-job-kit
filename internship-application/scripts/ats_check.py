#!/usr/bin/env python3
"""Check that applicant tracking systems can read a resume PDF, and how well it covers a posting's keywords.

Usage:
  python ats_check.py RESUME.pdf --name "Full Name" [--tex TAILORED.tex] [--posting job-posting.md] [--master MASTER]

Parse checks (checks{}):
  name_near_top        the name is in the first lines of the PDF text
  ligatures            no ligature characters (ﬁ ﬂ ﬀ ﬃ ﬄ) that turn "find" into an unreadable word
  run_together         no words glued together (missing spaces in the text layer)
  two_column           false when the layout reads as one column (wide gaps on most lines suggest two columns)
  fonts_embedded       every font embedded (pdffonts; true when pdffonts isn't installed)
  digits_ok            digits survive into the text (compared with --tex when given)
  nonstandard_headings section titles outside a broad standard list (Summary, Skills, Experience, Projects,
                       Education, Certifications, Awards, Volunteer Experience, Languages, ...)

Keyword coverage (keywords{}, with --posting): the posting's skills and tools (rank_jobs.terms_in vocabulary) split into
  in_resume, in_master_not_resume (could be added: they are true), not_in_master (gaps: never add them), and
  in_resume_not_in_master (in the resume but not the master: check it is true).
Without --master the last two lists can't be told apart and the leftover terms are listed as not_in_resume.

Prints one JSON object: ok, checks{}, problems[], keywords{}, headings[].
Exit codes: 0 no problems, 2 problems found, 1 bad input.
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(HERE, '..', '..', 'lib')):
    if os.path.isdir(os.path.join(_p, 'jobkit')):
        sys.path.insert(0, os.path.abspath(_p))
        break
from jobkit import bullets, cli, latex, text  # noqa: E402

STANDARD = '''summary; professional summary; profile; professional profile; career summary; summary of qualifications;
qualifications; objective; career objective; skills; core skills; technical skills; key skills; skills summary;
core competencies; competencies; skills and tools; tools; experience; work experience; professional experience;
relevant experience; employment; employment history; work history; research experience; teaching experience;
internship experience; internships; projects; selected projects; technical projects; personal projects;
academic projects; key projects; education; education and training; training; certifications; certificates;
licences and certifications; licenses and certifications; licences; licenses; awards; honours; honors;
awards and honours; awards and honors; achievements; publications; presentations; volunteer experience;
volunteering; volunteer work; community involvement; leadership; leadership experience; activities;
extracurricular activities; languages; interests; hobbies and interests; coursework; relevant coursework;
professional development; affiliations; memberships; professional memberships; references; contact'''
STANDARD_SET = {text.norm(s) for s in STANDARD.split(';')}


def is_standard(heading):
    n = text.norm(heading.replace('&', ' and '))
    if n in STANDARD_SET:
        return True
    parts = [p for p in re.split(r'\band\b|,', n) if p.strip()]
    return len(parts) > 1 and all(p.strip() in STANDARD_SET for p in parts)


def tex_headings(src):
    s = bullets._drop_definitions(text.strip_tex_comments(src))
    m = re.search(r'\\begin\{document\}', s)
    s = s[m.end():] if m else s
    out = []
    for m in re.finditer(r'\\((?:sub)?section|[A-Za-z]*[Ss]ection[A-Za-z]*)\*?\s*(?=\{)', s):
        if m.group(1).lower().startswith('subsub'):
            continue
        arg, _ = bullets._braced(s, m.end())
        t = text.collapse(text.tex_to_text(arg))
        if t and m.group(1) != 'subsection':
            out.append(t)
    return out


def pdf_headings(pdf_txt, name):
    out = []
    lines = [l.strip() for l in pdf_txt.splitlines() if l.strip()]
    for i, l in enumerate(lines):
        words = l.split()
        if not (1 <= len(words) <= 5) or text.norm(l) == text.norm(name):
            continue
        letters = re.sub(r'[^A-Za-z]', '', l)
        if len(letters) < 4 or re.search(r'[\d@|•]', l):
            continue
        if (l.isupper() and i > 0) or is_standard(l):
            out.append(l)
    return out


def run_together(pdf_txt, src=''):
    found = []
    for tok in re.findall(r'[A-Za-z]{18,}', pdf_txt):
        if (src and tok.lower() not in src.lower()) or (not src and len(tok) >= 20):
            found.append(tok)
    if src:
        words = re.findall(r'[A-Za-z]{2,}', text.tex_to_text(src))
        pairs = {(a + b).lower() for a, b in zip(words, words[1:])}
        single = {w.lower() for w in words}
        for tok in re.findall(r'[A-Za-z]{6,}', pdf_txt):
            low = tok.lower()
            if low in pairs and low not in single and tok not in found:
                found.append(tok)
    return found[:10]


def two_column(layout_txt):
    lines = [l for l in (layout_txt or '').splitlines() if l.strip()]
    if len(lines) < 10:
        return False
    gapped = sum(1 for l in lines if re.search(r'\S\s{5,}\S', l.strip()))
    return gapped / len(lines) > 0.5


def keywords(posting, resume_txt, master=None):
    try:
        if HERE not in sys.path:
            sys.path.insert(0, HERE)
        import rank_jobs
    except Exception as e:
        return {'error': f'rank_jobs.py not available: {e}'}
    post = rank_jobs.terms_in(rank_jobs.text_of(text.read_text(posting)))
    res = rank_jobs.terms_in(rank_jobs.text_of(resume_txt))
    out = {'in_resume': sorted(post & res)}
    if master:
        mas = rank_jobs.terms_in(rank_jobs.text_of(text.read_text(master)))
        out['in_master_not_resume'] = sorted((post & mas) - res)
        out['not_in_master'] = sorted(post - mas - res)
        # posting terms the resume shows but the master never mentions: possibly invented
        out['in_resume_not_in_master'] = sorted((post & res) - mas)
    else:
        out['in_master_not_resume'] = []
        out['not_in_resume'] = sorted(post - res)
    out['posting_terms'] = len(post)
    return out


def run(pdf, name, tex=None, posting=None, master=None, include_keywords=True):
    """Returns (result dict, exit code)."""
    for p in (pdf, tex, posting, master):
        if p and not os.path.isfile(p):
            return {'ok': False, 'error': f'File not found: {p}'}, cli.BAD_INPUT
    pdf_txt = text.pdf_text(pdf)
    if pdf_txt is None:
        return {'ok': False, 'error': 'Cannot read PDF text: install poppler (pdftotext) or pypdf'}, cli.MISSING_DEP
    layout_txt = text.pdf_text(pdf, layout=True) or ''
    src = text.tex_project_text(tex) if tex else ''
    checks, problems = {}, []

    first = [l for l in pdf_txt.splitlines() if l.strip()][:5]
    checks['name_near_top'] = not latex.missing_strings('\n'.join(first), [name]) if name else None
    if checks['name_near_top'] is False:
        problems.append(f'The name "{name}" is not in the first lines of the PDF text.')

    ligs = sorted({c for c in pdf_txt if c in latex.LIGATURES})
    checks['ligatures'] = ligs
    if ligs:
        problems.append('Ligature characters in the text (' + ' '.join(ligs) + '): add \\usepackage[T1]{fontenc} '
                        'or turn ligatures off (\\defaultfontfeatures{Ligatures=NoCommon}).')

    glued = run_together(pdf_txt, src)
    checks['run_together'] = glued
    if glued:
        problems.append('Words run together in the text layer: ' + ', '.join(glued[:5]))

    checks['two_column'] = two_column(layout_txt)
    if checks['two_column']:
        problems.append('The layout reads as two columns: tracking systems may mix lines from both columns.')

    fonts = latex.pdf_fonts(pdf)
    checks['fonts_embedded'] = fonts['all_embedded']
    if not fonts['all_embedded']:
        problems.append('Fonts not embedded: ' + ', '.join(fonts['not_embedded']))

    if src:
        dig = latex.digit_check(latex.visible_source_text(src), pdf_txt, src)
        checks['digits_ok'] = dig['ok']
        if dig['warning']:
            problems.append(dig['warning'])
    else:
        checks['digits_ok'] = bool(re.search(r'\d', pdf_txt))
        if not checks['digits_ok']:
            problems.append('No digits in the PDF text: dates and numbers are unreadable to tracking systems.')

    heads = tex_headings(src) if src else pdf_headings(pdf_txt, name or '')
    odd = [h for h in heads if not is_standard(h)]
    checks['nonstandard_headings'] = odd
    if odd:
        problems.append('Section titles tracking systems may not recognise: ' + ', '.join(odd))

    res = {'ok': not problems, 'pdf': pdf, 'checks': checks, 'problems': problems, 'headings': heads}
    if posting and include_keywords:
        res['keywords'] = keywords(posting, pdf_txt + '\n' + (latex.visible_source_text(src) if src else ''), master)
    return res, (cli.ATTENTION if problems else cli.OK)


def main(argv=None):
    p = argparse.ArgumentParser(description='Check a resume PDF the way applicant tracking systems read it.')
    p.add_argument('pdf')
    p.add_argument('--name', required=True, help='the name as printed on the resume')
    p.add_argument('--tex', help='the tailored .tex source (better digit and heading checks)')
    p.add_argument('--posting', help='job-posting.md for keyword coverage')
    p.add_argument('--master', help='master resume, to tell true-but-missing keywords from gaps')
    a = p.parse_args(argv)
    res, code = run(a.pdf, a.name, a.tex, a.posting, a.master)
    cli.emit(res, code)


if __name__ == '__main__':
    main()
