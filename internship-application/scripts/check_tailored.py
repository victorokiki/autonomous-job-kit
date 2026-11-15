#!/usr/bin/env python3
"""Run every check on a tailored resume in one go, and start its changes.md.

Usage:
  python check_tailored.py TAILORED --master MASTER --name NAME (--out OUT.pdf | --pdf EXISTING.pdf)
                           [--posting job-posting.md] [--profile profile.json] [--expect TEXT ...]
                           [--max-pages N] [--check-template]

TAILORED is the tailored .tex (built into --out) or a .docx whose PDF the user exported (--pdf).
Steps, in order:
  1. build (.tex with --out) with build_resume.py; when the PDF is over the page limit the run stops here and reports
     only how many lines to cut. Page limit: --max-pages, else profile resumeMaxPages, else 1.
  2. compare_bullets.py MASTER TAILORED
  3. check_resume.py MASTER TAILORED --resume (profile as --known, the posting's company and role as --allow)
  4. ats_check.py on the PDF (keyword coverage when --posting is given)
  5. page 1 rendered to <PDF base>-page1.png at 80 dpi (when pdftoppm is installed)
  6. <PDF base>-changes.md written beside the PDF: a changes.md skeleton (Angle, Page, Reworded before -> after,
     Kept as is, Dropped from the master, Gaps) with <...> slots for Claude to fill. An older one goes to _old/.
--check-template also builds the master (no page limit, in the temp folder) and runs the ATS parse checks on it.

Prints one JSON object: ok, fix[] (must change before saving), review[] (change, or justify in changes.md), page{},
bullets{counts, unchanged_share}, facts{counts, ...}, ats{problems}, keywords{in_resume, in_master_not_resume,
not_in_master}, pdf, png, changes.

Exit codes: 0 nothing to fix or review, 2 something to fix/review or too long, 1 bad input or compile error,
3 no LaTeX engine (the source checks still ran).
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
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from jobkit import bullets, cli, files, latex, text  # noqa: E402
import ats_check  # noqa: E402
import build_resume  # noqa: E402
import compare_bullets  # noqa: E402


def posting_fields(path):
    out = {'company': '', 'role': ''}
    if not path:
        return out
    try:
        with open(path, encoding='utf-8-sig', errors='replace') as f:
            raw = f.read()
    except OSError:
        return out
    for key in out:
        m = re.search(r'^\s*-\s*' + key + r':\s*(.+)$', raw, re.I | re.M)
        if m:
            out[key] = m.group(1).strip()
    if not out['company'] or not out['role']:
        m = re.search(r'^#\s+(.+?)\s+at\s+(.+?)\s*$', raw, re.M)
        if m:
            out['role'] = out['role'] or m.group(1)
            out['company'] = out['company'] or m.group(2)
    return out


def changes_skeleton(tailored, pdf, page, cmp_res, kw, posting):
    lines = [f'# Changes: {os.path.basename(pdf or tailored)}', '']
    if posting.get('company') or posting.get('role'):
        lines += [f'Posting: {posting.get("role") or "<role>"} at {posting.get("company") or "<company>"}', '']
    lines += ['## Angle', '<one or two sentences: what this version leads with for this posting, and why>', '']
    lines += ['## Page']
    if page.get('pages') is not None:
        lines.append(f'- {page["pages"]} page(s), limit {page.get("max_pages") or "none"}; about '
                     f'{page.get("free_lines")} empty line(s) at the bottom')
    lines += ['<what was cut, shortened or added to fit the page>', '']
    lines += ['## Reworded']
    items = (cmp_res or {}).get('bullets', [])
    changed = [b for b in items if b['kind'] in ('reworded', 'merged')]
    for b in changed:
        before = ' + '.join(b['source'])
        lines += [f'- Before{" (merged)" if b["kind"] == "merged" else ""}: {before}', f'  After: {b["text"]}',
                  '  Why: <the posting need this answers>']
    for b in items:
        if b['kind'] == 'no_source':
            lines += [f'- New wording with no clear master source: {b["text"]}',
                      '  Source: <the master or profile fact it states, or remove it>']
    if not changed and not any(b['kind'] == 'no_source' for b in items):
        lines.append('- (none)')
    lines += ['', '## Kept as is']
    kept = [b['text'] for b in items if b['kind'] == 'unchanged']
    lines += [f'- {t}' for t in kept] or ['- (none)']
    lines += ['', '## Dropped from the master']
    lines += [f'- {t}' for t in (cmp_res or {}).get('master_unused', [])] or ['- (none)']
    lines += ['<why these were left out>', '', '## Gaps']
    gaps = (kw or {}).get('not_in_master') or []
    if gaps:
        lines.append('Posting asks for these; the master has no evidence of them, so they were NOT added:')
        lines += [f'- {g}' for g in gaps]
    else:
        lines.append('- (none found)' if kw else '- <posting keywords missing from the master (no posting given)>')
    lines += ['<how to address the gaps honestly, e.g. in the cover letter or an interview>', '']
    return '\n'.join(lines)


def template_check(master, name):
    built = latex.compile_tex(master)
    if built['no_latex']:
        return {'ok': None, 'problems': ['no LaTeX engine: master not built']}
    if not built['ok']:
        latex.cleanup(built)
        return {'ok': False, 'problems': ['the master does not build: ' + '; '.join(
            f'line {e["line"]}: {e["message"]}' for e in built['errors'])]}
    res, _ = ats_check.run(built['pdf'], name, tex=master, include_keywords=False)
    latex.cleanup(built)
    return {'ok': res.get('ok'), 'problems': res.get('problems', []), 'checks': res.get('checks', {})}


def run(a):
    """Returns (result dict, exit code). `a` has the argparse fields."""
    for pth in (a.tailored, a.master, a.posting, a.profile, a.pdf):
        if pth and not os.path.isfile(pth):
            return {'ok': False, 'error': f'File not found: {pth}'}, cli.BAD_INPUT
    ext = os.path.splitext(a.tailored)[1].lower()
    if ext not in ('.tex', '.docx'):
        return {'ok': False, 'error': 'TAILORED must be a .tex or .docx file'}, cli.BAD_INPUT
    if ext == '.docx' and not a.pdf:
        return {'ok': False, 'error': 'Only .tex sources can be built: export the .docx to PDF and pass --pdf'}, \
            cli.BAD_INPUT
    profile = cli.load_json(a.profile, {}) or {}
    limit = a.max_pages if a.max_pages is not None else profile.get('resumeMaxPages') or 1
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 1
    post = posting_fields(a.posting)
    fix, review = [], []
    no_latex = False
    page = {'pages': None, 'max_pages': limit, 'free_lines': None, 'page_fill': None}
    pdf = None
    src = text.tex_project_text(a.tailored) if ext == '.tex' else ''

    # 1. build or measure
    if a.out and ext == '.tex' and not a.pdf:
        b, code = build_resume.run(a.tailored, a.out, limit, [a.name] + list(a.expect or []))
        if code == cli.NO_LATEX:
            no_latex = True
            review.append('No LaTeX engine here: the PDF was not built (compile in Overleaf and re-run with --pdf).')
        elif code in (cli.BAD_INPUT, cli.FILE_BUSY):
            return {'ok': False, 'error': b.get('error'), 'errors': b.get('errors', []), 'hints': b.get('hints', [])}, \
                cli.BAD_INPUT
        else:
            pdf = b['pdf']
            page.update(pages=b['pages'], free_lines=b['free_lines'], page_fill=b['page_fill'],
                        margins_in=b['margins_in'], smallest_text_pt=b['smallest_text_pt'], engine=b['engine'])
            if 'lines_over' in b:
                page['lines_over'] = b['lines_over']
                return {'ok': False, 'fix': [f'Too long: {b["pages"]} pages, limit {limit}. Cut about '
                                             f'{b["lines_over"]} lines (shorten or drop the bullets least relevant to '
                                             'the posting), then run this again.'],
                        'review': [], 'page': page, 'pdf': pdf}, cli.ATTENTION
            for w in b['warnings']:
                (fix if ('Not found' in w or 'digits' in w or 'text layer' in w) else review).append(w)
    else:
        pdf = a.pdf or a.out
        if not pdf or not os.path.isfile(pdf):
            return {'ok': False, 'error': 'Pass --out (to build the .tex) or --pdf (an existing PDF)'}, cli.BAD_INPUT
        lay = latex.layout(pdf, src)
        page.update(pages=lay['pages'], free_lines=lay['free_lines'], page_fill=lay['page_fill'],
                    margins_in=lay['margins_in'], smallest_text_pt=lay['smallest_text_pt'])
        if limit and lay['pages'] and lay['pages'] > limit:
            page['lines_over'] = latex.lines_beyond(pdf, limit)
            return {'ok': False, 'fix': [f'Too long: {lay["pages"]} pages, limit {limit}. Cut about '
                                         f'{page["lines_over"]} lines, then run this again.'],
                    'review': [], 'page': page, 'pdf': pdf}, cli.ATTENTION
        missing = latex.missing_strings(text.pdf_text(pdf) or '', [a.name] + list(a.expect or []))
        if missing:
            fix.append('Not found in the PDF text: ' + '; '.join(missing))
    if page.get('free_lines') is not None and page['free_lines'] >= 2 and (not limit or page['pages'] == limit):
        review.append(f'About {page["free_lines"]} empty lines at the bottom of the last page: fill the page with '
                      'more true detail from the master that fits the posting.')

    # 2. bullets
    cmp_res, ccode = compare_bullets.run(a.master, a.tailored)
    bul = {'counts': cmp_res.get('counts'), 'unchanged_share': cmp_res.get('unchanged_share'),
           'total': cmp_res.get('total')}
    if ccode == cli.BAD_INPUT:
        review.append('Bullet comparison not possible: ' + cmp_res.get('error', ''))
    else:
        if cmp_res['unchanged_share'] > 0.5:
            review.append(f'{round(cmp_res["unchanged_share"] * 100)}% of the bullets are unchanged from the master: '
                          'reword the ones that matter most for this posting, or say why in changes.md.')
        for it in cmp_res['bullets']:
            if it['kind'] == 'no_source':
                review.append(f'Bullet with no clear source in the master: "{it["text"]}" (name its source in '
                              'changes.md or remove it).')

    # 3. facts
    known = [a.profile] if a.profile else []
    allow = [v for v in (post['company'], post['role']) if v]
    facts, _ = bullets.fact_check(a.master, a.tailored, known, allow, resume=True)
    for n in facts.get('new_numbers', []):
        fix.append(f'Number "{n["raw"]}" is not in the master or profile ("...{n["context"]}..."): use the true '
                   'figure or remove it.')
    for c in facts.get('missing_contact', []):
        fix.append(f'Contact detail from the master is missing: {c}')
    for ph in facts.get('placeholders', []):
        fix.append(f'Placeholder left in the text: {ph}')
    for t in facts.get('new_terms', []):
        review.append(f'"{t["term"]}" does not appear in the master or profile ("...{t["context"]}..."): keep it only '
                      'if it is true and stated in the master; never add a posting keyword the user lacks.')

    # 4. ATS
    ats = {'problems': []}
    kw = None
    if pdf:
        ares, acode = ats_check.run(pdf, a.name, tex=a.tailored if ext == '.tex' else None, posting=a.posting,
                                    master=a.master)
        ats = {'problems': ares.get('problems', []), 'checks': ares.get('checks', {})}
        kw = ares.get('keywords')
        for term in (kw or {}).get('in_resume_not_in_master', []):
            fix.append(f'Posting keyword "{term}" is in the resume but not in the master: remove it unless the master '
                       'is missing a true fact (then add it to the master first).')
        for prob in ats['problems']:
            (review if prob.startswith('Section titles') else fix).append('ATS: ' + prob)
    elif a.posting:
        kw = ats_check.keywords(a.posting, latex.visible_source_text(src) if src else text.read_text(a.tailored),
                                a.master)

    # 5. preview
    png = latex.render_png(pdf, os.path.splitext(pdf)[0] + '-page1.png', 1, 80) if pdf else None

    # 6. changes.md skeleton
    base = os.path.splitext(pdf or a.tailored)[0]
    changes = base + '-changes.md'
    files.write_text(changes, changes_skeleton(a.tailored, pdf, page, cmp_res if ccode != cli.BAD_INPUT else {},
                                               kw, post))

    res = {'ok': not fix and not review and not no_latex, 'fix': fix, 'review': review, 'page': page, 'bullets': bul,
           'facts': {'counts': facts.get('counts'), 'new_numbers': facts.get('new_numbers', []),
                     'new_terms': facts.get('new_terms', []), 'missing_contact': facts.get('missing_contact', []),
                     'placeholders': facts.get('placeholders', [])},
           'ats': ats, 'keywords': {k: (kw or {}).get(k, []) for k in ('in_resume', 'in_master_not_resume',
                                                                       'not_in_master', 'in_resume_not_in_master')},
           'pdf': pdf, 'png': png, 'changes': changes}
    if a.check_template:
        if a.master.lower().endswith('.tex'):
            tpl = template_check(a.master, a.name)
            res['template'] = tpl
            for prob in tpl.get('problems', []):
                review.append('Master template: ' + prob)
        else:
            res['template'] = {'ok': None, 'problems': ['the master is not LaTeX: template check skipped']}
        res['ok'] = res['ok'] and not review
    if no_latex:
        return res, cli.NO_LATEX
    return res, (cli.ATTENTION if fix or review else cli.OK)


def main(argv=None):
    p = argparse.ArgumentParser(description='Build and check a tailored resume; start its changes.md.')
    p.add_argument('tailored', help='tailored .tex (or .docx with --pdf)')
    p.add_argument('--master', required=True)
    p.add_argument('--name', required=True, help='the name as printed on the resume')
    p.add_argument('--posting')
    p.add_argument('--profile')
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--out', help='PDF to build from the .tex')
    g.add_argument('--pdf', help='an existing PDF of TAILORED')
    p.add_argument('--expect', nargs='*', default=[])
    p.add_argument('--max-pages', type=int)
    p.add_argument('--check-template', action='store_true')
    a = p.parse_args(argv)
    res, code = run(a)
    cli.emit(res, code)


if __name__ == '__main__':
    main()
