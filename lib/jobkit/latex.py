"""Compiling LaTeX documents and measuring the PDFs they produce (resumes and cover letters).

Nothing here writes into the user's folder except `save_pdf` (which moves an older file into _old/ first). Builds run
in a temporary copy of the project folder in the system temp folder.

Public functions
----------------
engines_available() -> list[str]
    Installed engines, in preference order: tectonic, xelatex, lualatex, pdflatex.
choose_engine(preferred=None, source='') -> str | None
    The engine to use: `preferred` if installed (None when it isn't), else tectonic, else xelatex/lualatex when the
    source loads fontspec, else pdflatex (falling back to any installed engine). None = no LaTeX on this computer.
compile_tex(main_tex, engine=None, timeout=300) -> dict
    Builds MAIN.tex in a temp copy of its folder. Returns
    {"ok": bool, "engine": str|None, "pdf": temp path|None, "build_dir": temp folder|None, "log": str,
     "errors": [{"line": int|None, "file": str|None, "message": str}], "hints": [str], "no_latex": bool}.
    The caller copies the PDF out with save_pdf() and may remove build_dir with cleanup().
save_pdf(built_pdf, out_pdf) -> str | None
    Copies a built PDF to out_pdf, moving an existing out_pdf into _old/ first. Returns where the old one went.
cleanup(result) -> None
    Removes the temp build folder of a compile_tex() result.
parse_errors(log) -> list[dict]          error_hints(errors, log) -> list[str]
page_count(pdf) -> int | None
pdf_words(pdf) -> list[{"width", "height", "words": [(x0, y0, x1, y1, text)]}] | None   (pdftotext -bbox)
layout(pdf, source='') -> dict
    {"pages", "free_lines", "page_fill", "margins_in": {left, right, top, bottom}, "smallest_text_pt",
     "line_height_pt", "lines_per_page": [n, ...]}  (values None when they can't be measured)
lines_beyond(pdf, max_pages) -> int | None
    Text lines that sit on pages after `max_pages` (how many lines to cut).
visible_source_text(src) -> str
    The text a reader would see from LaTeX source (document body only, no lengths or options).
missing_strings(pdf_text, wanted) -> list[str]
    The strings in `wanted` not found in the PDF text (loose comparison: case, spacing, punctuation ignored).
digit_check(source_text, pdf_text, src='') -> {"source": n, "pdf": n, "ok": bool, "warning": str|None}
render_png(pdf, out_png, page=1, dpi=80) -> str | None   (pdftoppm; None when unavailable)
pdf_fonts(pdf) -> {"available": bool, "all_embedded": bool, "not_embedded": [names]}
"""
import os
import re
import shutil
import subprocess
import tempfile

from . import files
from .text import norm, pdf_pages, tex_to_text, strip_tex_comments

ENGINES = ('tectonic', 'xelatex', 'lualatex', 'pdflatex')
_IGNORE_DIRS = {'_old', '.git', '__pycache__', 'Applications', 'node_modules', '.cache'}
LIGATURES = {'\ufb00': 'ff', '\ufb01': 'fi', '\ufb02': 'fl', '\ufb03': 'ffi', '\ufb04': 'ffl'}


# ---- engines and compiling ---------------------------------------------------------------------------------------

def _read(path):
    with open(path, encoding='utf-8', errors='replace') as f:
        return f.read()


def engines_available():
    return [e for e in ENGINES if shutil.which(e)]


def choose_engine(preferred=None, source=''):
    have = engines_available()
    if preferred:
        return preferred if preferred in have else None
    if not have:
        return None
    if 'tectonic' in have:
        return 'tectonic'
    if re.search(r'\\usepackage(\[[^\]]*\])?\{[^}]*\bfontspec\b', source or ''):
        for e in ('xelatex', 'lualatex'):
            if e in have:
                return e
    if 'pdflatex' in have:
        return 'pdflatex'
    return have[0]


def _copy_project(src_dir, dest_dir):
    def ignore(folder, names):
        return [n for n in names if n in _IGNORE_DIRS or n.startswith('~$')]
    shutil.copytree(src_dir, dest_dir, ignore=ignore)


def compile_tex(main_tex, engine=None, timeout=300):
    """Build MAIN.tex in a temp copy of its folder (see the module docstring for the result)."""
    result = {'ok': False, 'engine': None, 'pdf': None, 'build_dir': None, 'log': '', 'errors': [], 'hints': [],
              'no_latex': False}
    main_tex = os.path.abspath(main_tex)
    try:
        source = _read(main_tex)
    except OSError as e:
        result['errors'] = [{'line': None, 'file': main_tex, 'message': f'cannot read the file: {e}'}]
        return result
    eng = choose_engine(engine, source)
    if not eng:
        result['no_latex'] = True
        result['hints'] = [f'The LaTeX engine "{engine}" is not installed.' if engine else
                           'No LaTeX engine found. Install Tectonic (https://tectonic-typesetting.github.io) or '
                           'compile in Overleaf.']
        return result
    result['engine'] = eng
    build = tempfile.mkdtemp(prefix='jobkit-tex-')
    result['build_dir'] = build
    src_dir = os.path.join(build, 'src')
    out_dir = os.path.join(build, 'out')
    try:
        _copy_project(os.path.dirname(main_tex), src_dir)
    except (OSError, shutil.Error) as e:
        result['errors'] = [{'line': None, 'file': None, 'message': f'could not copy the project: {e}'}]
        return result
    os.makedirs(out_dir, exist_ok=True)
    name = os.path.basename(main_tex)
    if eng == 'tectonic':
        cmds = [['tectonic', '--keep-logs', '--outdir', out_dir, name]]
    else:
        one = [eng, '-interaction=nonstopmode', '-halt-on-error', '-file-line-error', f'-output-directory={out_dir}',
               name]
        cmds = [one, one]   # second run settles references; skipped below when not needed
    log = []
    code = 0
    for i, cmd in enumerate(cmds):
        try:
            r = subprocess.run(cmd, cwd=src_dir, capture_output=True, text=True, errors='replace', timeout=timeout)
        except subprocess.TimeoutExpired:
            result['errors'] = [{'line': None, 'file': None, 'message': f'{eng} took longer than {timeout} s'}]
            result['hints'] = ['The build hung: look for an endless loop or a missing file it waits for.']
            return result
        code = r.returncode
        log.append((r.stdout or '') + (r.stderr or ''))
        if code != 0:
            break
        if i == 0 and len(cmds) > 1:
            logf = os.path.join(out_dir, os.path.splitext(name)[0] + '.log')
            try:
                if 'Rerun' not in _read(logf):
                    break
            except OSError:
                break
    logf = os.path.join(out_dir, os.path.splitext(name)[0] + '.log')
    if os.path.isfile(logf):
        log.append(_read(logf))
    result['log'] = '\n'.join(log)
    pdf = os.path.join(out_dir, os.path.splitext(name)[0] + '.pdf')
    if code == 0 and os.path.isfile(pdf):
        result['ok'] = True
        result['pdf'] = pdf
    else:
        result['errors'] = parse_errors(result['log']) or [
            {'line': None, 'file': None, 'message': f'{eng} failed (exit code {code}); see the log'}]
    result['hints'] = error_hints(result['errors'], result['log']) if not result['ok'] else []
    return result


def save_pdf(built_pdf, out_pdf):
    """Copy a built PDF to out_pdf; an existing file there goes to _old/ first."""
    moved = files.move_to_old(out_pdf) if os.path.exists(out_pdf) else None
    os.makedirs(os.path.dirname(os.path.abspath(out_pdf)), exist_ok=True)
    shutil.copy2(built_pdf, out_pdf)
    return moved


def cleanup(result):
    d = (result or {}).get('build_dir')
    if d and os.path.isdir(d) and os.path.basename(d).startswith('jobkit-tex-'):
        shutil.rmtree(d, ignore_errors=True)


_FILE_LINE = re.compile(r'^(?:error:\s*)?(?:\./)?([^\s:]+\.(?:tex|sty|cls)):(\d+):\s*(.+)$', re.M)
_BANG = re.compile(r'^! (.+)$', re.M)
_LNUM = re.compile(r'^l\.(\d+)', re.M)


def parse_errors(log):
    """Errors with line numbers from a TeX log or Tectonic output: [{line, file, message}]."""
    errors, seen = [], set()
    for m in _FILE_LINE.finditer(log or ''):
        key = (int(m.group(2)), m.group(3).strip().rstrip('.'))
        if key not in seen:
            seen.add(key)
            errors.append({'line': key[0], 'file': m.group(1), 'message': m.group(3).strip()})
    for m in _BANG.finditer(log or ''):
        msg = m.group(1).strip()
        after = (log or '')[m.end():m.end() + 2000]
        ln = _LNUM.search(after)
        line = int(ln.group(1)) if ln else None
        if (line, msg.rstrip('.')) in seen or any(e['message'].rstrip('.') == msg.rstrip('.') for e in errors):
            continue
        seen.add((line, msg.rstrip('.')))
        errors.append({'line': line, 'file': None, 'message': msg})
    return errors[:10]


_HINTS = [
    (r'Undefined control sequence', 'A command is misspelled, or the package that defines it is not loaded.'),
    (r'Missing \$ inserted', 'A special character needs escaping in text: write \\_ \\& \\% \\$ \\# instead of _ & % $ #.'),
    (r'Misplaced alignment tab', 'An unescaped & in text: write \\&.'),
    (r'File `?[^\']+\.(sty|cls)\'? not found|not found.*\.sty', 'A LaTeX package is not installed. Tectonic downloads '
     'packages itself (it needs internet the first time); otherwise install the package or compile in Overleaf.'),
    (r'Runaway argument|File ended while scanning|Missing \} inserted|Extra \}', 'Unbalanced braces { }: check the line '
     'reported and the lines above it.'),
    (r'Font .* not found|fontspec error|cannot find font', 'A font is missing on this computer: use one bundled with '
     'LaTeX (for example \\usepackage[sfdefault,lining]{carlito}) or install the font.'),
    (r'Environment \S+ undefined', 'An environment is misspelled or its package is not loaded.'),
    (r'\\begin\{\S+\} on input line \d+ ended by', 'A \\begin{...} has no matching \\end{...}.'),
    (r'failed to download|network|could not resolve', 'Tectonic could not download a package: connect to the internet '
     'once, or compile in Overleaf.'),
]


def error_hints(errors, log=''):
    blob = ' '.join(e.get('message', '') for e in errors or []) + '\n' + (log or '')
    hints = [h for pat, h in _HINTS if re.search(pat, blob, re.I)]
    return list(dict.fromkeys(hints))


# ---- measuring PDFs ----------------------------------------------------------------------------------------------

def page_count(pdf):
    return pdf_pages(pdf)


def pdf_words(pdf):
    """Word boxes per page from `pdftotext -bbox` (points, origin top-left), or None when unavailable."""
    if not shutil.which('pdftotext'):
        return None
    try:
        r = subprocess.run(['pdftotext', '-bbox', pdf, '-'], capture_output=True, text=True, errors='replace',
                           timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    pages = []
    for pm in re.finditer(r'<page width="([\d.]+)" height="([\d.]+)">(.*?)</page>', r.stdout, re.S):
        words = []
        for wm in re.finditer(r'<word xMin="([\d.-]+)" yMin="([\d.-]+)" xMax="([\d.-]+)" yMax="([\d.-]+)">([^<]*)</word>',
                              pm.group(3)):
            words.append((float(wm.group(1)), float(wm.group(2)), float(wm.group(3)), float(wm.group(4)),
                          wm.group(5)))
        pages.append({'width': float(pm.group(1)), 'height': float(pm.group(2)), 'words': words})
    return pages


def _lines(words, tol=2.0):
    """Group word boxes into text lines: [(top, bottom)] sorted top to bottom."""
    lines = []
    for x0, y0, x1, y1, _ in sorted(words, key=lambda w: w[3]):
        if lines and abs(lines[-1][1] - y1) <= tol:
            lines[-1] = (min(lines[-1][0], y0), max(lines[-1][1], y1))
        else:
            lines.append((y0, y1))
    return lines


_UNITS = {'in': 72.27, 'cm': 28.45, 'mm': 2.845, 'pt': 1.0, 'bp': 1.00375, 'em': 10.0}


def _geometry_bottom_pt(source):
    """The bottom margin set with the geometry package, in PDF points, or None."""
    src = strip_tex_comments(source or '')
    opts = ' '.join(re.findall(r'\\usepackage\[([^\]]*)\]\{geometry\}', src) + re.findall(r'\\geometry\{([^}]*)\}', src))
    found = None
    for key in ('margin', 'vmargin', 'bottom'):   # later keys override earlier ones
        m = re.search(r'(?<![a-z])' + key + r'\s*=\s*\{?([\d.]+)\s*(in|cm|mm|pt|bp|em)', opts)
        if m:
            found = float(m.group(1)) * _UNITS[m.group(2)] * 72 / 72.27
    return found


def layout(pdf, source=''):
    """Pages, free lines at the bottom of the last page, fill, margins and smallest text (best effort)."""
    out = {'pages': page_count(pdf), 'free_lines': None, 'page_fill': None,
           'margins_in': {'left': None, 'right': None, 'top': None, 'bottom': None},
           'smallest_text_pt': None, 'line_height_pt': None, 'lines_per_page': []}
    pages = pdf_words(pdf)
    if not pages or not any(p['words'] for p in pages):
        return out
    out['pages'] = out['pages'] or len(pages)
    all_lines = [_lines(p['words']) for p in pages]
    out['lines_per_page'] = [len(l) for l in all_lines]
    gaps = []
    for lines in all_lines:
        gaps += [b[1] - a[1] for a, b in zip(lines, lines[1:]) if 6 <= b[1] - a[1] <= 30]
    # Typical line spacing: the lower quartile of line-to-line gaps (wrapped lines and tight bullets), which ignores
    # the extra space above headings and between entries.
    gaps.sort()
    lh = gaps[len(gaps) // 4] if len(gaps) >= 4 else 13.0
    out['line_height_pt'] = round(lh, 1)
    W, H = pages[0]['width'], pages[0]['height']
    nonempty = [p for p in pages if p['words']]
    left = min(w[0] for p in nonempty for w in p['words'])
    right = W - max(w[2] for p in nonempty for w in p['words'])
    top = min(w[1] for w in nonempty[0]['words'])
    bottom_edge = max(w[3] for p in nonempty for w in p['words'])
    out['margins_in'] = {'left': round(left / 72, 2), 'right': round(right / 72, 2), 'top': round(top / 72, 2),
                         'bottom': round((H - bottom_edge) / 72, 2)}
    sizes = [w[3] - w[1] for p in nonempty for w in p['words'] if len(re.sub(r'\W', '', w[4])) >= 2]
    if sizes:
        out['smallest_text_pt'] = round(min(sizes), 1)
    # Where text could end on a page: geometry's bottom margin, else the fullest earlier page, else mirror the top.
    gb = _geometry_bottom_pt(source)
    if gb is not None:
        limit = H - gb
    elif len(nonempty) > 1:
        limit = max(max(w[3] for w in p['words']) for p in nonempty[:-1])
    else:
        limit = H - top
    last = pages[-1]['words'] or nonempty[-1]['words']
    last_bottom = max(w[3] for w in last)
    last_top = min(w[1] for w in last) if len(pages) == 1 else top
    free = max(0.0, limit - last_bottom)
    out['free_lines'] = int(free // lh)
    span = limit - last_top
    out['page_fill'] = round(min(1.0, max(0.0, (last_bottom - last_top) / span)), 2) if span > 0 else None
    return out


def lines_beyond(pdf, max_pages):
    pages = pdf_words(pdf)
    if pages is None:
        return None
    return sum(len(_lines(p['words'])) for p in pages[max_pages:])


# ---- text checks -------------------------------------------------------------------------------------------------

def visible_source_text(src):
    """Reader-visible text from LaTeX source: the document body without spacing lengths and optional arguments."""
    s = strip_tex_comments(src or '')
    m = re.search(r'\\begin\{document\}', s)
    if m:
        s = s[m.end():]
    s = s.replace('\\end{document}', ' ')
    s = re.sub(r'\\\\\s*\[[^\]]*\]', r'\\\\', s)                              # \\[2pt]
    s = re.sub(r'\\(vspace|hspace|vskip|hskip|rule|setlength|addtolength|kern|raisebox)\*?(\{[^{}]*\})+', ' ', s)
    s = re.sub(r'\{-?[\d.]+\s*(pt|em|ex|in|cm|mm|bp)\}', ' ', s)
    s = re.sub(r'\\[a-zA-Z@]+\*?\[[^\]]*\]', ' ', s)                           # \cmd[opt]
    s = re.sub(r'\\begin\{[^}]*\}(\{[^}]*\})?|\\end\{[^}]*\}', ' ', s)
    return tex_to_text(s)


def _loose(s):
    for k, v in LIGATURES.items():
        s = s.replace(k, v)
    return norm(s)


def missing_strings(pdf_text, wanted):
    hay = ' ' + _loose(pdf_text or '') + ' '
    squashed = hay.replace(' ', '')
    out = []
    for w in wanted or []:
        n = _loose(w)
        if not n:
            continue
        if (' ' + n + ' ') not in hay and n.replace(' ', '') not in squashed:
            out.append(w)
    return out


def digit_check(source_text, pdf_text, src=''):
    s = len(re.findall(r'\d', source_text or ''))
    p = len(re.findall(r'\d', pdf_text or ''))
    ok = not (s >= 5 and p < 0.8 * s)
    warning = None
    if not ok:
        if re.search(r'\{carlito\}', src or ''):
            warning = ('digits missing from the PDF text: load Carlito as \\usepackage[sfdefault,lining]{carlito}')
        else:
            warning = ('digits missing from the PDF text: the font draws numbers that applicant tracking systems '
                       'cannot read; switch to lining figures or another font')
    return {'source': s, 'pdf': p, 'ok': ok, 'warning': warning}


def render_png(pdf, out_png, page=1, dpi=80):
    """Render one page to PNG with pdftoppm. Overwrites out_png (a preview, not a user file). None if unavailable."""
    if not shutil.which('pdftoppm'):
        return None
    base = out_png[:-4] if out_png.lower().endswith('.png') else out_png
    try:
        r = subprocess.run(['pdftoppm', '-png', '-r', str(dpi), '-f', str(page), '-l', str(page), '-singlefile',
                            pdf, base], capture_output=True, text=True, errors='replace', timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return base + '.png' if r.returncode == 0 and os.path.isfile(base + '.png') else None


def pdf_fonts(pdf):
    if not shutil.which('pdffonts'):
        return {'available': False, 'all_embedded': True, 'not_embedded': []}
    try:
        r = subprocess.run(['pdffonts', pdf], capture_output=True, text=True, errors='replace', timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return {'available': False, 'all_embedded': True, 'not_embedded': []}
    bad = []
    lines = r.stdout.splitlines()
    for line in lines[2:]:
        parts = line.split()
        # columns from the right: emb sub uni object-number generation
        if len(parts) >= 6 and parts[-5] == 'no':
            bad.append(parts[0])
    return {'available': True, 'all_embedded': not bad, 'not_embedded': bad}
