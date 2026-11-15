"""jobs.txt (the queue of postings to apply to) and the keys used to spot the same posting twice.

jobs.txt format: one posting link per line. Text after "#" on a line is a note. A line that is exactly "# done"
splits the file: links above it are waiting, links below it are finished or skipped. Blank lines and comment-only
lines are kept as they are. Nothing in this module removes a line; finished links are moved below "# done".
"""
import os
import re
import urllib.parse

from .text import name_key, norm

DONE = '# done'
_URL = re.compile(r'https?://\S+')
_UUID = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'


def clean_url(url):
    """Scheme and host in lower case, no fragment, no tracking parameters, no trailing slash."""
    u = urllib.parse.urlsplit(str(url or '').strip())
    keep = [(k, v) for k, v in urllib.parse.parse_qsl(u.query)
            if not re.match(r'(utm_|ref$|source$|src$|lever-source|gh_src|iis|iisn)', k, re.I)]
    path = re.sub(r'/+$', '', u.path) or '/'
    return urllib.parse.urlunsplit((u.scheme.lower() or 'https', u.netloc.lower(), path,
                                    urllib.parse.urlencode(keep), ''))


def posting_keys(url):
    """Keys that identify a posting whatever link points at it: the cleaned link without its query, plus the
    application system's own job ID when the link shows one (Greenhouse, Lever, Ashby, Workday, SmartRecruiters,
    iCIMS, Job Bank, or a jobId-style parameter)."""
    if not url:
        return set()
    u = urllib.parse.urlsplit(str(url).strip())
    host, path = u.netloc.lower(), u.path
    q = dict(urllib.parse.parse_qsl(u.query))
    keys = {clean_url(url).split('?')[0]}
    if q.get('gh_jid'):
        keys.add('greenhouse:' + q['gh_jid'])
    m = re.search(r'greenhouse\.io/.*?/jobs/(\d+)', host + path) or re.search(r'[?&]token=(\d+)', u.query)
    if m and 'greenhouse' in host:
        keys.add('greenhouse:' + m.group(1))
    m = re.search(_UUID, path, re.I)
    if m and 'lever.co' in host:
        keys.add('lever:' + m.group(0).lower())
    if m and 'ashbyhq.com' in host:
        keys.add('ashby:' + m.group(0).lower())
    if 'myworkday' in host:
        m = re.search(r'_([A-Z]{0,4}-?\d{3,}(?:-\d+)?)(?:/|$|\?)', path + '/')
        if m:
            keys.add(f"workday:{host.split('.')[0]}:{m.group(1).upper()}")
    if 'smartrecruiters.com' in host:
        m = re.search(r'/(\d{6,})', path)
        if m:
            keys.add('smartrecruiters:' + m.group(1))
    if 'icims.com' in host:
        m = re.search(r'/jobs/(\d+)', path)
        if m:
            keys.add(f"icims:{host.split('.')[0]}:{m.group(1)}")
    if 'jobbank.gc.ca' in host:
        m = re.search(r'/jobposting/(\d+)', path)
        if m:
            keys.add('jobbank:' + m.group(1))
    for k in ('jobId', 'jobid', 'job_id', 'jid', 'reqId', 'requisitionId', 'id'):
        if q.get(k) and re.fullmatch(r'[\w-]{4,}', q[k]):
            keys.add(f'{host}:{k}:{q[k]}')
            break
    return keys


def role_key(company, role):
    """One key for "this company, this job title" (case, punctuation and "Inc." ignored), or None."""
    c, r = name_key(company), norm(role)
    return f'{c}|{r}' if c and r else None


def _split(line):
    m = _URL.search(line)
    url = m.group(0).rstrip(').,;') if m else None
    note = line.split('#', 1)[1].strip() if '#' in line and (not m or line.index('#') > m.start()) else ''
    return url, note


def read_queue(path):
    """{"waiting": [{"url", "note", "line"}], "done": [...], "lines": [...]} for a jobs.txt (empty when missing)."""
    out = {'waiting': [], 'done': [], 'lines': []}
    if not path or not os.path.exists(path):
        return out
    with open(path, encoding='utf-8-sig') as f:
        lines = f.read().splitlines()
    out['lines'] = lines
    below = False
    for i, line in enumerate(lines):
        if line.strip().lower() == DONE:
            below = True
            continue
        url, note = _split(line)
        if url:
            out['done' if below else 'waiting'].append({'url': url, 'note': note, 'line': i})
    return out


def queued_links(path):
    """(set of cleaned links, set of posting keys) for every link in jobs.txt, waiting or done."""
    q = read_queue(path)
    links, keys = set(), set()
    for e in q['waiting'] + q['done']:
        links.add(clean_url(e['url']).split('?')[0])
        keys |= posting_keys(e['url'])
    return links, keys


def _write(path, lines):
    tmp = path + '.part'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines).rstrip('\n') + '\n')
    os.replace(tmp, path)


def append_links(path, entries):
    """Add (url, note) pairs above "# done" (or at the end), skipping postings already anywhere in the file.
    Returns the links actually added."""
    q = read_queue(path)
    _, have = queued_links(path)
    lines = list(q['lines'])
    at = next((i for i, l in enumerate(lines) if l.strip().lower() == DONE), len(lines))
    added = []
    for url, note in entries:
        keys = posting_keys(url)
        if keys & have:
            continue
        have |= keys
        lines.insert(at + len(added), f'{url}  # {note}' if note else url)
        added.append(url)
    if added:
        _write(path, lines)
    return added


def move_below_done(path, reasons, lines_only=None):
    """Move waiting links to just below "# done" (adding the line if needed), each with its reason added to its
    note. `reasons` maps a link (or any link with the same posting key) to a short reason. With `lines_only` (a set
    of 0-based line numbers from read_queue), only those lines move, so one copy of a duplicate can stay.
    Returns links moved."""
    q = read_queue(path)
    if not q['waiting']:
        return []
    want = {}
    for url, why in reasons.items():
        for k in posting_keys(url):
            want[k] = why
    lines = list(q['lines'])
    moving = []
    for e in q['waiting']:
        if lines_only is not None and e['line'] not in lines_only:
            continue
        why = next((want[k] for k in posting_keys(e['url']) if k in want), None)
        if why is not None:
            moving.append((e, why))
    if not moving:
        return []
    drop = {e['line'] for e, _ in moving}
    kept = [l for i, l in enumerate(lines) if i not in drop]
    at = next((i for i, l in enumerate(kept) if l.strip().lower() == DONE), None)
    if at is None:
        kept += ['', DONE]
        at = len(kept) - 1
    new = [f"{e['url']}  # {(e['note'] + ' | ') if e['note'] else ''}{why}" for e, why in moving]
    kept[at + 1:at + 1] = new
    _write(path, kept)
    return [e['url'] for e, _ in moving]
