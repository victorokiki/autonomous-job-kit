"""Comparing a tailored resume with the master: bullets (what was kept, reworded, merged or has no source) and facts
(numbers, tools and names that appear in the tailored copy but nowhere in the master).

Public functions
----------------
extract_bullets(path) -> [str]          bullets of a .tex (\\item and custom macros whose name contains "item"),
                                        .docx (list paragraphs or lines starting with a bullet sign), .md/.txt/.pdf
tex_bullets(src) -> [str]               docx_bullets(path) -> [str]          plain_bullets(text) -> [str]
similarity(a, b) -> float (0-1)
classify(master_bullets, tailored_bullets) -> [{"text", "kind", "source": [str], "score"}]
    kind: "unchanged" | "reworded" | "merged" | "no_source"
is_skills_line(text) -> bool            "Data: Python, SQL, Excel" style lines (left out of the unchanged share)
numbers_in(text) -> [{"value", "raw", "context"}]
terms_in_text(text) -> [{"term", "context"}]           tool-like and proper-noun terms
contacts_in(text) -> {"emails", "phones", "links"}
placeholders_in(text) -> [str]
fact_check(master, candidate, known=(), allow=(), resume=False, today=None) -> (result dict, exit code)
check_resume_cli(argv=None)             the check_resume.py command line (both skills run this)
"""
import argparse
import datetime as dt
import difflib
import html
import os
import re
import zipfile

from . import cli
from .text import collapse, norm, read_text, strip_tex_comments, tex_project_text, tex_to_text

STOP = set('''a an the and or of to in on for with by at from as into via per over under using use used is are was were be
been being this that these those it its their our my your we i our than then so such across within each every all any
more most less new up out about after before while during through who which what when where how'''.split())


# ---- bullet extraction -------------------------------------------------------------------------------------------

def _braced(s, i):
    """Given s[i] == '{', return (content, index after the closing brace)."""
    depth, j = 0, i
    while j < len(s):
        c = s[j]
        if c == '\\':
            j += 2
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1
    return s[i + 1:], len(s)


def _drop_definitions(s):
    """Remove \\newcommand / \\renewcommand / \\def blocks so macro bodies don't count as bullets."""
    out, i = [], 0
    pat = re.compile(r'\\(?:re)?newcommand\*?|\\providecommand\*?|\\def\s*\\[A-Za-z@]+[^{]*')
    while True:
        m = pat.search(s, i)
        if not m:
            out.append(s[i:])
            break
        out.append(s[i:m.start()])
        j = m.end()
        braces = 0
        while j < len(s) and braces < (1 if m.group(0).startswith('\\def') else 2):
            while j < len(s) and s[j] in ' \t\n':
                j += 1
            if j < len(s) and s[j] == '[':
                k = s.find(']', j)
                j = k + 1 if k > 0 else j + 1
                continue
            if j < len(s) and s[j] == '{':
                _, j = _braced(s, j)
                braces += 1
            elif j < len(s) and s[j] == '\\' and braces == 0:      # \newcommand\name{...}
                k = re.match(r'\\[A-Za-z@]+', s[j:])
                j += k.end() if k else 1
                braces += 1
            else:
                break
        i = j
    return ''.join(out)


def _clean_tex(fragment):
    return collapse(tex_to_text(fragment)).strip(' ,;')


def tex_bullets(src):
    s = _drop_definitions(strip_tex_comments(src or ''))
    m = re.search(r'\\begin\{document\}', s)
    if m:
        s = s[m.end():]
    found = []
    stop = re.compile(r'\\item\b|\\end\{|\\begin\{|\n\s*\n|\\[A-Za-z]*[Ii]tem[A-Za-z]*\b|\\section|\\entry\b')
    for m in re.finditer(r'\\item\b(\s*\[[^\]]*\])?', s):
        nxt = stop.search(s, m.end())
        found.append((m.start(), s[m.end():nxt.start() if nxt else len(s)]))
    for m in re.finditer(r'\\([A-Za-z]*[Ii]tem[A-Za-z]*)\*?\s*(?=\{)', s):
        name = m.group(1)
        if name == 'item' or re.search(r'(Start|End|List)$', name):
            continue
        j, args = m.end(), []
        while j < len(s) and s[j] == '{' and len(args) < 3:
            arg, j = _braced(s, j)
            args.append(arg)
            while j < len(s) and s[j] in ' \t' :
                j += 1
        found.append((m.start(), ' '.join(args)))
    out = []
    for _, frag in sorted(found):
        t = _clean_tex(frag)
        if len(re.sub(r'\W', '', t)) >= 3:
            out.append(t)
    return out


_MARK = re.compile(r'^\s*(?:[•\-–—▪●◦*·]|\u2022)\s+')


def docx_bullets(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read('word/document.xml').decode('utf-8', errors='replace')
    out = []
    for p in re.findall(r'<w:p[ >].*?</w:p>', xml, re.S):
        text = html.unescape(''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', p))).strip()
        if not text:
            continue
        style = re.search(r'<w:pStyle w:val="([^"]+)"', p)
        listy = '<w:numPr>' in p or (style and 'list' in style.group(1).lower())
        if listy or _MARK.match(text):
            out.append(collapse(_MARK.sub('', text)))
    return [t for t in out if len(re.sub(r'\W', '', t)) >= 3]


def plain_bullets(text):
    out, cur = [], None
    for line in (text or '').splitlines():
        if _MARK.match(line):
            if cur:
                out.append(cur)
            cur = _MARK.sub('', line).strip()
        elif cur is not None and line.strip() and not line.strip().isupper() and (
                line.strip()[0].islower() or not cur.rstrip().endswith('.')) and len(line.strip()) > 2:
            cur += ' ' + line.strip()
        else:
            if cur:
                out.append(cur)
            cur = None
    if cur:
        out.append(cur)
    return [collapse(t) for t in out if len(re.sub(r'\W', '', t)) >= 3]


def extract_bullets(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == '.tex':
        return tex_bullets(tex_project_text(path))
    if ext == '.docx':
        return docx_bullets(path)
    return plain_bullets(read_text(path))


# ---- similarity and classification ------------------------------------------------------------------------------

def _tokens(text):
    out = []
    for w in norm(text).split():
        if w in STOP:
            continue
        if len(w) > 4 and w.endswith('ing'):
            w = w[:-3]
        elif len(w) > 3 and w.endswith('ed'):
            w = w[:-2]
        elif len(w) > 3 and w.endswith('s') and not w.endswith('ss'):
            w = w[:-1]
        out.append(w)
    return out


def similarity(a, b):
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return 0.0
    ratio = difflib.SequenceMatcher(None, na, nb).ratio()
    ta, tb = set(_tokens(a)), set(_tokens(b))
    dice = 2 * len(ta & tb) / (len(ta) + len(tb)) if ta and tb else 0.0
    return round(max(ratio, dice), 3)


def _coverage(t, m):
    return len(t & m) / len(t) if t else 0.0


def is_skills_line(text):
    return bool(re.match(r"^[A-Z][\w &/'-]{0,30}:\s", text or '')) and (text or '').count(',') >= 1


def classify(master, tailored):
    mtok = [set(_tokens(m)) for m in master]
    out = []
    for t in tailored:
        tt = set(_tokens(t))
        if not master:
            out.append({'text': t, 'kind': 'no_source', 'source': [], 'score': 0.0})
            continue
        scored = sorted(((similarity(t, m), i) for i, m in enumerate(master)), reverse=True)
        best_s, best_i = scored[0]
        same_digits = re.findall(r'\d+', t) == re.findall(r'\d+', master[best_i])
        if norm(t) == norm(master[best_i]) or (best_s >= 0.96 and same_digits):
            out.append({'text': t, 'kind': 'unchanged', 'source': [master[best_i]], 'score': best_s})
            continue
        best_cov = _coverage(tt, mtok[best_i])
        # merged: two master bullets together explain the tailored one much better than either alone
        cands = sorted(range(len(master)), key=lambda i: -_coverage(tt, mtok[i]))[:6]
        merged = None
        for x in range(len(cands)):
            for y in range(x + 1, len(cands)):
                i, j = cands[x], cands[y]
                union = _coverage(tt, mtok[i] | mtok[j])
                only_i, only_j = len((tt & mtok[i]) - mtok[j]), len((tt & mtok[j]) - mtok[i])
                single = max(_coverage(tt, mtok[i]), _coverage(tt, mtok[j]))
                if union >= 0.6 and union - single >= 0.2 and only_i >= 2 and only_j >= 2:
                    if not merged or union > merged[0]:
                        merged = (union, i, j)
        if merged and merged[0] > best_cov + 0.15:
            _, i, j = merged
            i, j = min(i, j), max(i, j)
            out.append({'text': t, 'kind': 'merged', 'source': [master[i], master[j]], 'score': round(merged[0], 3)})
        elif best_s >= 0.45 or best_cov >= 0.5:
            out.append({'text': t, 'kind': 'reworded', 'source': [master[best_i]],
                        'score': round(max(best_s, best_cov), 3)})
        else:
            out.append({'text': t, 'kind': 'no_source', 'source': [master[best_i]] if best_s >= 0.25 else [],
                        'score': best_s})
    return out


# ---- facts -------------------------------------------------------------------------------------------------------

_EMAIL = re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+')
_URLISH = re.compile(r'(?:https?://|www\.)\S+|\b[\w-]+(?:\.[\w-]+)*\.(?:com|ca|org|net|io|dev|co|uk|edu|app)(?:/\S*)?',
                     re.I)
_PHONE = re.compile(r'(?<!\w)\+?\d[\d\s().-]{7,}\d(?!\w)')
_NUM = re.compile(r'(?<![A-Za-z\d.,/])([$£€]\s?)?(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(\s?%|[kKM](?![A-Za-z])|\+)?'
                  r'(?![A-Za-z\d]|\.\d)')


def _strip_contacts(text):
    text = _EMAIL.sub(' ', text or '')
    text = _URLISH.sub(' ', text)
    return _PHONE.sub(lambda m: ' ' if len(re.sub(r'\D', '', m.group(0))) >= 10 else m.group(0), text)


def _context(text, start, end, width=45):
    return collapse(text[max(0, start - width):end + width])


def _value(m):
    v = float(m.group(2).replace(',', '') + (m.group(3) or ''))
    suf = (m.group(4) or '').strip()
    if suf in ('k', 'K'):
        v *= 1000
    elif suf == 'M':
        v *= 1000000
    return ('%f' % v).rstrip('0').rstrip('.')


def numbers_in(text):
    t = _strip_contacts(text)
    return [{'value': _value(m), 'raw': m.group(0).strip(), 'context': _context(t, m.start(), m.end())}
            for m in _NUM.finditer(t)]


COMMON = set('''about above academic account accounting achieved across action active activities added addition
additional administration advanced agile all also analysis analyst analytics analysed analyzed and annual applied april
assistant associate august automated automation award awards bachelor based best board budget built business by
campus candidate career centre center certificate certification certifications certified city client clients club
college commerce committee communication community company computer conference core course courses coursework created
customer customers daily data database day december degree delivered department design designed developed developer
development diploma director division during east education engineer engineering english experience february french
friday full fund general global graduate group head high honours honors hours ideas improved inc including industry
information intern internship interests january july june junior key lab languages lead leadership learning led level
limited ltd made management manager march master may member minor monday month monthly national new north november
october office officer online operations part personal present president professional profile program programme project
projects public qualifications reduced regional relevant report reporting reports research school science selected
senior september service services skills society software south spring staff student students summary summer support
system systems team teams technical technologies technology the thursday time tools training tuesday university
volunteer wednesday week weekly west winter work worked working year years jan feb mar apr jun jul aug sep sept
oct nov dec'''.split())

_TERM = re.compile(r'[A-Za-z][A-Za-z0-9]*(?:[+#]+|(?:[./-][A-Za-z0-9]+)+)?[+#]*')


def _tool_like(tok):
    core = tok.rstrip('.')
    return bool(re.search(r'[a-z][A-Z]|[A-Z]{2,}|\d|[+#]|\.[A-Za-z]', core[1:] if len(core) > 1 else '')) or \
        bool(re.fullmatch(r'[A-Z]{2,}[a-z]?s?', core))


def terms_in_text(text):
    t = _strip_contacts(text)
    out, seen = [], set()
    for m in _TERM.finditer(t):
        tok = m.group(0).rstrip('.-/')
        if len(tok) < 2:
            continue
        before = t[max(0, m.start() - 3):m.start()]
        sentence_start = m.start() == 0 or bool(re.search(r'[.!?:;|•(\n\[]\s*$|^\s*$', before)) or \
            bool(re.search(r'(^|\n)\s*$', t[max(0, m.start() - 40):m.start()]))
        tool = _tool_like(tok)
        proper = tok[0].isupper() and not sentence_start and tok.lower() not in COMMON and tok.lower() not in STOP
        if not (tool or proper):
            continue
        if not tool and tok.lower() in COMMON:
            continue
        key = tok.lower()
        if key not in seen:
            seen.add(key)
            out.append({'term': tok, 'context': _context(t, m.start(), m.end())})
    return out


def _known(term, hay_lower, hay_norm):
    low = term.lower()
    if re.search(r'(?<![a-z0-9])' + re.escape(low) + r'(?![a-z0-9])', hay_lower):
        return True
    n = norm(term)
    variants = {n, n.rstrip('s'), n + 's'}
    return any(v and (' ' + v + ' ') in hay_norm for v in variants)


def contacts_in(text):
    text = text or ''
    emails = sorted({e.lower().rstrip('.') for e in _EMAIL.findall(text)})
    phones = sorted({re.sub(r'\D', '', p)[-10:] for p in _PHONE.findall(text) if len(re.sub(r'\D', '', p)) >= 10})
    links = sorted({l.lower().rstrip('/.') for l in re.findall(
        r'(?:linkedin\.com/in/[\w%-]+|github\.com/[\w.-]+)', text, re.I)})
    return {'emails': emails, 'phones': phones, 'links': links}


_PLACEHOLDERS = [
    re.compile(r'\[(?:company(?: name)?|role|position|job title|title|your name|name|hiring manager|manager|team|city|'
               r'date|location|x+|insert[^\]]*)\]', re.I),
    re.compile(r'\[[A-Z][A-Za-z ]{2,30}\]'),
    re.compile(r'\b(?:TODO|TBD|FIXME)\b'),
    re.compile(r'\bX{3,}\b|\bx{3,}\b'),
    re.compile(r'lorem ipsum', re.I),
    re.compile(r'<(?![a-z]+://)[A-Za-z][^<>@\n]{1,60}>'),
]


def placeholders_in(text):
    out = []
    for pat in _PLACEHOLDERS:
        for m in pat.finditer(text or ''):
            if m.group(0) not in out:
                out.append(m.group(0))
    return out


def _text(path):
    """Readable text; for LaTeX only the document body (no preamble lengths or macro definitions)."""
    if path.lower().endswith('.tex'):
        from .latex import visible_source_text
        return visible_source_text(_drop_definitions(strip_tex_comments(tex_project_text(path))))
    return read_text(path)


def _raw(path):
    try:
        if path.lower().endswith('.tex'):
            return tex_project_text(path)
        if path.lower().endswith(('.docx', '.pdf')):
            return ''
        with open(path, encoding='utf-8-sig', errors='replace') as f:
            return f.read()
    except OSError:
        return ''


def fact_check(master, candidate, known=(), allow=(), resume=False, today=None):
    """Compare CANDIDATE with MASTER (+ known files). Returns (result, exit code)."""
    today = today or dt.date.today()
    master_text = _text(master)
    master_raw = _raw(master)
    known_text = ''
    for k in known or ():
        if k and os.path.isfile(k):
            known_text += '\n' + _text(k) + '\n' + _raw(k)
    cand_text = _text(candidate)
    cand_raw = _raw(candidate)
    if not norm(cand_text):
        return {'ok': False, 'error': f'No text could be read from {candidate}'}, cli.BAD_INPUT

    allow_words = set()
    allow_values = set()
    for a in allow or ():
        for w in re.split(r'[\s,/|]+', a or ''):
            if w:
                allow_words.add(w.lower())
                if re.fullmatch(r'[\d.,]+%?', w):
                    allow_values.add(_value(_NUM.search(w)) if _NUM.search(w) else w)
        allow_words.add((a or '').lower())

    reference = master_text + '\n' + master_raw + '\n' + known_text
    ref_values = {n['value'] for n in numbers_in(reference)}
    new_numbers, seen = [], set()
    for n in numbers_in(cand_text):
        v = n['value']
        if v in ref_values or v in allow_values or v in seen or n['raw'].lower() in allow_words:
            continue
        if v == str(today.year):
            continue
        seen.add(v)
        new_numbers.append(n)

    ref_lower = reference.lower()
    ref_norm = ' ' + norm(reference) + ' '
    new_terms = []
    for t in terms_in_text(cand_text):
        low = t['term'].lower()
        if low in allow_words or any(low == w for a in allow_words for w in a.split()):
            continue
        if _known(t['term'], ref_lower, ref_norm):
            continue
        new_terms.append(t)

    missing = []
    if resume:
        mc = contacts_in(master_text + '\n' + master_raw)
        cc = contacts_in(cand_text + '\n' + cand_raw)
        for kind in ('emails', 'phones', 'links'):
            for item in mc[kind]:
                if item not in cc[kind]:
                    missing.append(item)

    placeholders = placeholders_in(cand_text)
    flagged = bool(new_numbers or new_terms or missing or placeholders)
    result = {
        'ok': not flagged,
        'master': master, 'candidate': candidate,
        'new_numbers': new_numbers, 'new_terms': new_terms,
        'missing_contact': missing, 'placeholders': placeholders,
        'counts': {'new_numbers': len(new_numbers), 'new_terms': len(new_terms),
                   'missing_contact': len(missing), 'placeholders': len(placeholders)},
        'advice': ('Nothing new found.' if not flagged else
                   'Every number and tool must come from the master or the profile: remove or correct new_numbers, '
                   'check each new_terms item is a real fact from the master (never add posting keywords the user '
                   'lacks), restore missing contact details and fill placeholders.'),
    }
    return result, (cli.ATTENTION if flagged else cli.OK)


def check_resume_cli(argv=None):
    p = argparse.ArgumentParser(
        prog='check_resume.py',
        description='Fact-check a tailored resume, letter or answer against the master resume.')
    p.add_argument('master', help='master resume (.tex, .docx, .pdf, .md or .txt)')
    p.add_argument('candidate', help='the text to check (.tex, .pdf, .docx, .md or .txt)')
    p.add_argument('--known', nargs='*', default=[], help='other files with true facts (profile.json, notes)')
    p.add_argument('--allow', nargs='*', default=[], help='words or numbers to accept (company, role, posting terms)')
    p.add_argument('--resume', action='store_true', help='also check contact details from the master are present')
    a = p.parse_args(argv)
    cli.need_files(a.master, a.candidate, *a.known)
    res, code = fact_check(a.master, a.candidate, a.known, a.allow, a.resume)
    cli.emit(res, code)
