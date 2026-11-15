#!/usr/bin/env python3
"""Build a LaTeX resume into a PDF and check the result.

Usage:
  python build_resume.py MAIN.tex --out OUT.pdf [--max-pages N] [--expect TEXT ...]
                         [--engine tectonic|xelatex|lualatex|pdflatex]

MAIN.tex is the file with \\documentclass; files it \\input's are found beside it. The build runs in a temporary copy
of MAIN.tex's folder, so nothing is written into the user's folder except OUT.pdf (an older OUT.pdf is moved into
_old/ first). The PDF is written even when it is too long, so it can be looked at; the exit code says it is too long.

--max-pages  page limit (default 1; 0 = no limit, for the master).
--expect     text that must appear in the PDF text (pass the person's name here; repeatable).
--engine     LaTeX engine; default: tectonic if installed, else xelatex/lualatex when the source uses fontspec,
             else pdflatex.

Checks: page count, a readable text layer, each --expect string, digits surviving into the PDF text (Carlito without
"lining" loses them), estimated empty lines at the bottom of the last page, margins and smallest text size.

Prints one JSON object: ok, pdf, engine, pages, max_pages, free_lines, page_fill (0-1), margins_in{left,right,top,
bottom}, smallest_text_pt, missing_text[], digits{source,pdf}, warnings[], previous_version_moved_to; on errors
errors[{line, message}] and hints[]; when too long, lines_over (about how many lines to cut).

Exit codes: 0 ok, 1 compile failed or bad input, 2 longer than the page limit (or a check needs attention),
3 no LaTeX engine.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(HERE, '..', '..', 'lib')):
    if os.path.isdir(os.path.join(_p, 'jobkit')):
        sys.path.insert(0, os.path.abspath(_p))
        break
from jobkit import cli, latex, text  # noqa: E402


def run(main_tex, out_pdf, max_pages=1, expect=(), engine=None):
    """Build and check. Returns (result dict, exit code)."""
    if not os.path.isfile(main_tex):
        return {'ok': False, 'error': f'File not found: {main_tex}'}, cli.BAD_INPUT
    src = text.tex_project_text(main_tex)
    if '\\documentclass' not in src:
        return {'ok': False, 'error': f'{main_tex} has no \\documentclass: pass the main .tex file'}, cli.BAD_INPUT
    built = latex.compile_tex(main_tex, engine=engine)
    res = {'ok': False, 'pdf': None, 'engine': built['engine'], 'pages': None, 'max_pages': max_pages,
           'free_lines': None, 'page_fill': None, 'margins_in': None, 'smallest_text_pt': None, 'missing_text': [],
           'digits': None, 'warnings': [], 'previous_version_moved_to': None}
    if built['no_latex']:
        res.update(error='No LaTeX engine available', hints=built['hints'])
        return res, cli.NO_LATEX
    if not built['ok']:
        res.update(error='The LaTeX build failed', errors=[{'line': e['line'], 'message': e['message']}
                                                           for e in built['errors']], hints=built['hints'])
        latex.cleanup(built)
        return res, cli.BAD_INPUT
    try:
        res['previous_version_moved_to'] = latex.save_pdf(built['pdf'], out_pdf)
    except OSError as e:
        latex.cleanup(built)
        return {'ok': False, 'error': f'Could not write {out_pdf}: {e}'}, cli.FILE_BUSY
    latex.cleanup(built)
    res['pdf'] = os.path.abspath(out_pdf)
    code = cli.OK

    lay = latex.layout(out_pdf, src)
    res.update(pages=lay['pages'], free_lines=lay['free_lines'], page_fill=lay['page_fill'],
               margins_in=lay['margins_in'], smallest_text_pt=lay['smallest_text_pt'])
    pdf_txt = text.pdf_text(out_pdf) or ''
    if not text.norm(pdf_txt):
        res['warnings'].append('The PDF has no readable text layer: applicant tracking systems will see nothing.')
        code = cli.ATTENTION
    res['missing_text'] = latex.missing_strings(pdf_txt, expect)
    if res['missing_text']:
        res['warnings'].append('Not found in the PDF text: ' + '; '.join(res['missing_text']))
        code = cli.ATTENTION
    dig = latex.digit_check(latex.visible_source_text(src), pdf_txt, src)
    res['digits'] = {'source': dig['source'], 'pdf': dig['pdf']}
    if dig['warning']:
        res['warnings'].append(dig['warning'])
        code = cli.ATTENTION
    if lay['smallest_text_pt'] is not None and lay['smallest_text_pt'] < 8.5:
        res['warnings'].append(f'Some text is about {lay["smallest_text_pt"]} pt: keep body text at 10 pt or more.')
    m = lay['margins_in'] or {}
    if m.get('left') is not None and min(m['left'], m['right']) < 0.4:
        res['warnings'].append('Side margins are under 0.4 in: printers and some readers may cut text.')
    if max_pages and lay['pages'] and lay['pages'] > max_pages:
        over = latex.lines_beyond(out_pdf, max_pages)
        res['lines_over'] = over
        res['warnings'].append(f'{lay["pages"]} pages, limit {max_pages}: cut about {over} lines'
                               if over is not None else f'{lay["pages"]} pages, limit {max_pages}')
        return res, cli.ATTENTION
    res['ok'] = code == cli.OK
    return res, code


def main(argv=None):
    p = argparse.ArgumentParser(description='Build a LaTeX resume into a PDF and check it.')
    p.add_argument('main', help='main .tex file (the one with \\documentclass)')
    p.add_argument('--out', required=True, help='PDF to write')
    p.add_argument('--max-pages', type=int, default=1, help='page limit (0 = no limit)')
    p.add_argument('--expect', nargs='*', default=[], help='text that must appear in the PDF (e.g. the name)')
    p.add_argument('--engine', choices=latex.ENGINES)
    a = p.parse_args(argv)
    res, code = run(a.main, a.out, a.max_pages, a.expect, a.engine)
    cli.emit(res, code)


if __name__ == '__main__':
    main()
