"""Turning resumes, postings and letters into plain text, and normalizing names for comparisons."""
import html
import os
import re
import shutil
import subprocess
import zipfile

_COMPANY_NOISE = re.compile(r'\b(inc|incorporated|llc|ltd|limited|corp|corporation|co|company|plc|llp|gmbh|sa|ag|'
                            r'the|group|holdings|technologies|technology|labs)\b')


def norm(text):
    """Lower case, letters and digits only, single spaces: for loose comparisons."""
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', str(text or '').lower())).strip()


def name_key(company):
    """A company name reduced for matching ("Acme, Inc." and "ACME" give the same key)."""
    k = _COMPANY_NOISE.sub(' ', norm(str(company or '').replace('&', ' and ')))
    return re.sub(r'\s+', ' ', k).strip() or norm(company)


def collapse(text):
    return re.sub(r'\s+', ' ', str(text or '')).strip()


# ---- LaTeX -----------------------------------------------------------------------------------------------------

def strip_tex_comments(src):
    return re.sub(r'(?<!\\)%.*', '', src)


def tex_to_text(src):
    """Readable text from LaTeX source: comments, commands and braces dropped, arguments kept."""
    s = strip_tex_comments(src)
    s = re.sub(r'\\(documentclass|usepackage|newcommand|renewcommand|setlength|titleformat|titlespacing|setlist|'
               r'geometry|pagestyle|hypersetup|definecolor|input|include)\b(\[[^\]]*\])?(\{[^{}]*\})*', ' ', s)
    s = re.sub(r'\\(href)\{[^{}]*\}', ' ', s)                # keep a link's label, drop its target
    s = s.replace('\\&', '&').replace('\\%', '%').replace('\\$', '$').replace('\\#', '#').replace('\\_', '_')
    s = s.replace('--', '-').replace('~', ' ').replace('\\\\', '\n')
    s = re.sub(r'\\textbar\{\}|\\textbar\b', '|', s)
    s = re.sub(r'\\[a-zA-Z@]+\*?(\[[^\]]*\])?', ' ', s)       # remaining commands (arguments stay as text)
    s = re.sub(r'[{}]', ' ', s)
    return re.sub(r'[ \t]+', ' ', s)


def tex_project_text(main_tex):
    """Text of a LaTeX resume including files it pulls in with \\input or \\include."""
    seen, parts = set(), []

    def walk(path):
        real = os.path.realpath(path)
        if real in seen or not os.path.isfile(real):
            return
        seen.add(real)
        with open(real, encoding='utf-8', errors='replace') as f:
            src = f.read()
        parts.append(src)
        for m in re.finditer(r'\\(?:input|include)\{([^}]+)\}', strip_tex_comments(src)):
            name = m.group(1)
            child = os.path.join(os.path.dirname(real), name if name.endswith('.tex') else name + '.tex')
            walk(child)

    walk(main_tex)
    return '\n'.join(parts)


# ---- Word, PDF, HTML --------------------------------------------------------------------------------------------

def docx_paragraphs(path):
    """Paragraph texts of a .docx, using python-docx when present and the raw XML otherwise."""
    try:
        from docx import Document
        return [p.text for p in Document(path).paragraphs]
    except ImportError:
        pass
    with zipfile.ZipFile(path) as z:
        xml = z.read('word/document.xml').decode('utf-8', errors='replace')
    paras = []
    for p in re.findall(r'<w:p[ >].*?</w:p>', xml, re.S):
        paras.append(html.unescape(''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', p))))
    return paras


def pdf_text(path, layout=False):
    """Text layer of a PDF (what applicant tracking systems read): pdftotext when installed, else pypdf.
    Returns None when neither can read it."""
    if shutil.which('pdftotext'):
        args = ['pdftotext'] + (['-layout'] if layout else []) + [path, '-']
        r = subprocess.run(args, capture_output=True, text=True, errors='replace')
        if r.returncode == 0:
            return r.stdout
    try:
        from pypdf import PdfReader
        return '\n'.join((page.extract_text() or '') for page in PdfReader(path).pages)
    except Exception:
        return None


def pdf_pages(path):
    """Number of pages in a PDF, or None."""
    try:
        from pypdf import PdfReader
        return len(PdfReader(path).pages)
    except Exception:
        pass
    if shutil.which('pdfinfo'):
        r = subprocess.run(['pdfinfo', path], capture_output=True, text=True, errors='replace')
        m = re.search(r'^Pages:\s+(\d+)', r.stdout, re.M)
        if m:
            return int(m.group(1))
    return None


def html_to_text(s):
    """Plain text from HTML, keeping paragraph and list breaks."""
    s = html.unescape(str(s or ''))
    s = re.sub(r'(?is)<(script|style)[^>]*>.*?</\1>', ' ', s)
    s = re.sub(r'(?i)<br\s*/?>|</(p|div|li|h[1-6]|tr|ul|ol)>', '\n', s)
    s = re.sub(r'(?i)<li[^>]*>', '- ', s)
    s = re.sub(r'<[^>]+>', ' ', s)
    s = html.unescape(s)
    lines = [re.sub(r'[ \t\xa0]+', ' ', l).strip() for l in s.splitlines()]
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()


def read_text(path):
    """Plain text of a resume, letter, posting or note: .tex (with its \\input files), .docx, .pdf, .html, .md, .txt."""
    ext = os.path.splitext(path)[1].lower()
    if ext == '.tex':
        return tex_to_text(tex_project_text(path))
    if ext == '.docx':
        return '\n'.join(docx_paragraphs(path))
    if ext == '.pdf':
        return pdf_text(path) or ''
    with open(path, encoding='utf-8-sig', errors='replace') as f:
        raw = f.read()
    if ext in ('.html', '.htm'):
        return html_to_text(raw)
    return raw
