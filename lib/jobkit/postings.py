"""Reading job postings from application systems' public job data, without a browser.

    from jobkit.postings import Fetcher, fetch, from_text, render_markdown
    f = Fetcher()
    p = fetch('https://job-boards.greenhouse.io/acme/jobs/123', f)   # -> posting dict (see new_posting)

Supported (public endpoints, found by reading real postings):
  greenhouse       boards-api.greenhouse.io/v1/boards/<board>/jobs/<id>?questions=true&pay_transparency=true
                   (board links, embed links "?for=<board>&token=<id>", and company pages with "?gh_jid=<id>": the
                   board is learned from the embed redirect)
  lever            api.lever.co/v0/postings/<company>/<id> plus the /apply page for the form (custom question cards)
  ashby            jobs.ashbyhq.com/api/non-user-graphql (jobPosting with applicationForm; organization name)
  workday          <tenant>.wdN.myworkdayjobs.com/wday/cxs/<tenant>/<site>/job/<slug>  (also myworkdaysite.com)
  smartrecruiters  api.smartrecruiters.com/v1/companies/<company>/postings/<id>
  icims            the job page with ?in_iframe=1 (schema.org JobPosting JSON-LD)
  oracle           <host>/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails (Oracle Recruiting Cloud)
  rippling         api.rippling.com/platform/api/ats/v1/board/<board>/jobs/<id>
  jobbank          www.jobbank.gc.ca/jobsearch/jobposting/<id> (HTML with schema.org microdata; Accept: text/html)
  other            any page with schema.org JobPosting JSON-LD
LinkedIn is never fetched.

Politeness: at most one request per second per host, a descriptive User-Agent, a timeout on every request.
"""
import datetime as dt
import html
import json
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

from .text import html_to_text, name_key, norm

USER_AGENT = 'Mozilla/5.0 (compatible; JobKit/2.0; personal job-search helper reading public job postings)'
TIMEOUT = 25
SYSTEMS = ('greenhouse', 'lever', 'ashby', 'workday', 'smartrecruiters', 'icims', 'oracle', 'rippling', 'jobbank',
           'linkedin', 'other')
_UUID = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'


class FetchError(Exception):
    """kind: 'network' (no connection at all), 'http' (the server answered with an error), 'parse', 'notfound'."""

    def __init__(self, message, kind='http', status=None):
        super().__init__(message)
        self.kind, self.status = kind, status


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Fetcher:
    """HTTP GET/POST with a per-host pause, timeouts and counters (to tell "offline" from "this site failed")."""

    def __init__(self, delay=1.0, timeout=TIMEOUT, user_agent=USER_AGENT):
        self.delay, self.timeout, self.user_agent = delay, timeout, user_agent
        self._last = {}
        self.requests = 0
        self.network_errors = 0
        self.answered = 0

    def _pause(self, host):
        wait = self._last.get(host, 0) + self.delay - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last[host] = time.monotonic()

    def request(self, url, accept='application/json', data=None, headers=None, follow=True):
        """(status, headers, text). Raises FetchError."""
        host = urllib.parse.urlsplit(url).netloc.lower()
        h = {'User-Agent': self.user_agent, 'Accept': accept, 'Accept-Language': 'en-CA,en;q=0.9'}
        h.update(headers or {})
        body = None
        if data is not None:
            body = json.dumps(data).encode('utf-8')
            h['Content-Type'] = 'application/json'
        req = urllib.request.Request(url, data=body, headers=h, method='POST' if body else 'GET')
        opener = urllib.request.build_opener() if follow else urllib.request.build_opener(_NoRedirect)
        for attempt in (1, 2):
            self._pause(host)
            self.requests += 1
            try:
                with opener.open(req, timeout=self.timeout) as r:
                    self.answered += 1
                    raw = r.read()
                    charset = r.headers.get_content_charset() or 'utf-8'
                    return r.status, dict(r.headers), raw.decode(charset, errors='replace')
            except urllib.error.HTTPError as e:
                self.answered += 1
                if not follow and e.code in (301, 302, 303, 307, 308):
                    return e.code, dict(e.headers), ''
                if e.code in (429, 500, 502, 503, 504) and attempt == 1:
                    time.sleep(2)
                    continue
                raise FetchError(f'{host} answered HTTP {e.code}', 'notfound' if e.code in (404, 410) else 'http', e.code)
            except (urllib.error.URLError, socket.timeout, ConnectionError, OSError) as e:
                reason = getattr(e, 'reason', e)
                if attempt == 1 and isinstance(reason, (socket.timeout, TimeoutError)):
                    continue
                self.network_errors += 1
                raise FetchError(f'could not connect to {host}: {reason}', 'network')
        raise FetchError(f'{host} did not answer', 'network')

    def json(self, url, data=None, headers=None):
        _, _, text = self.request(url, data=data, headers=headers)
        try:
            return json.loads(text)
        except ValueError:
            raise FetchError(f'{urllib.parse.urlsplit(url).netloc} did not return JSON', 'parse')

    def html(self, url):
        return self.request(url, accept='text/html,application/xhtml+xml')[2]

    def location(self, url):
        status, headers, _ = self.request(url, accept='text/html', follow=False)
        return headers.get('Location') or headers.get('location')


# ---- the posting record ----------------------------------------------------------------------------------------

def new_posting(url, system='other'):
    return {'url': url, 'system': system, 'company': '', 'role': '', 'location': '', 'deadline': '', 'pay': '',
            'posted': '', 'description': '', 'questions': [], 'form_published': False, 'cover_letter_field': None,
            'cover_letter_note': '', 'check_company': False, 'error': '', 'hint': ''}


def detect(url):
    """(system, info) for a posting link."""
    u = urllib.parse.urlsplit(str(url or '').strip())
    host, path = u.netloc.lower(), u.path
    q = dict(urllib.parse.parse_qsl(u.query))
    seg = [s for s in path.split('/') if s]
    if 'linkedin.' in host or host == 'lnkd.in':
        return 'linkedin', {}
    if 'greenhouse.io' in host or q.get('gh_jid'):
        info = {'eu': '.eu.' in host, 'board': q.get('for'), 'id': q.get('gh_jid') or q.get('token')}
        if 'greenhouse.io' in host:
            m = re.search(r'/(?:v1/boards/)?([\w.-]+)/jobs/(\d+)', path)
            if m and m.group(1) != 'embed':
                info['board'], info['id'] = m.group(1), m.group(2)
        return 'greenhouse', info
    if host.endswith('lever.co'):
        m = re.search(r'/([\w.-]+)/(' + _UUID + ')', path, re.I)
        return 'lever', {'eu': '.eu.' in host, 'company': m.group(1) if m else (seg[0] if seg else ''),
                         'id': m.group(2).lower() if m else ''}
    if host.endswith('ashbyhq.com'):
        m = re.search(r'/([^/]+)/(' + _UUID + ')', path, re.I)
        return 'ashby', {'org': urllib.parse.unquote(m.group(1)) if m else (seg[0] if seg else ''),
                         'id': m.group(2).lower() if m else ''}
    if 'myworkdayjobs.com' in host or 'myworkdaysite.com' in host or 'myworkday.com' in host:
        tenant = site = ''
        rest = seg[:]
        if rest and re.fullmatch(r'[a-z]{2}(-[A-Za-z]{2})?', rest[0]):
            rest = rest[1:]
        if 'myworkdaysite.com' in host or (rest and rest[0] == 'recruiting'):
            if rest and rest[0] == 'recruiting':
                rest = rest[1:]
            tenant, rest = (rest[0], rest[1:]) if rest else ('', [])
        else:
            tenant = host.split('.')[0]
        if rest and rest[0] in ('wday', 'cxs'):
            rest = [r for r in rest if r not in ('wday', 'cxs')]
            if rest and rest[0] == tenant:
                rest = rest[1:]
        site = rest[0] if rest else ''
        slug = next((s for s in reversed(rest[1:]) if re.search(r'_[A-Za-z0-9-]*\d', s)), rest[-1] if len(rest) > 1 else '')
        return 'workday', {'base': f'{u.scheme or "https"}://{u.netloc}', 'tenant': tenant, 'site': site, 'slug': slug}
    if 'smartrecruiters.com' in host:
        m = re.search(r'/([^/]+)/(\d{6,})', path)
        return 'smartrecruiters', {'company': m.group(1) if m else '', 'id': m.group(2) if m else ''}
    if host.endswith('icims.com'):
        return 'icims', {}
    if 'oraclecloud.com' in host:
        m = re.search(r'/sites/([^/]+)/(?:job|requisitions/preview)/(\d+)', path)
        return 'oracle', {'host': u.netloc, 'site': m.group(1) if m else '', 'id': m.group(2) if m else ''}
    if 'rippling.com' in host and ('ats.' in host or '/jobs/' in path):
        m = re.search(r'/([^/]+)/jobs/(' + _UUID + ')', path, re.I)
        return 'rippling', {'board': m.group(1) if m else '', 'id': m.group(2) if m else ''}
    if 'jobbank.gc.ca' in host or 'guichetemplois.gc.ca' in host:
        m = re.search(r'/jobposting/(\d+)', path)
        return 'jobbank', {'id': m.group(1) if m else ''}
    return 'other', {}


# ---- shared helpers --------------------------------------------------------------------------------------------

def clean_text(s):
    """Plain text from HTML with lone bullet markers joined to their item and spacing tidied."""
    t = html_to_text(s)
    lines, out = t.splitlines(), []
    i = 0
    while i < len(lines):
        line = lines[i].replace('\xa0', ' ').strip()
        if line in ('-', '•', '*') :
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                out.append('- ' + lines[j].strip())
                i = j + 1
                continue
            i += 1
            continue
        line = re.sub(r'^[•●▪·]\s*', '- ', line)
        out.append(line)
        i += 1
    text = '\n'.join(out)
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def iso_date(value):
    """'YYYY-MM-DD' from an ISO string, epoch milliseconds, or text like 'November 13, 2026'; '' when unknown."""
    if value in (None, ''):
        return ''
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit() and len(value) >= 12):
        try:
            return dt.datetime.fromtimestamp(int(value) / 1000, dt.timezone.utc).strftime('%Y-%m-%d')
        except (ValueError, OverflowError, OSError):
            return ''
    s = str(value).strip()
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', s)
    if m:
        return m.group(0)
    m = re.search(r'([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})', s)
    if m:
        try:
            return dt.datetime.strptime(f'{m.group(1)[:3]} {m.group(2)} {m.group(3)}', '%b %d %Y').strftime('%Y-%m-%d')
        except ValueError:
            pass
    m = re.search(r'(\d{1,2})\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})', s)
    if m:
        try:
            return dt.datetime.strptime(f'{m.group(2)[:3]} {m.group(1)} {m.group(3)}', '%b %d %Y').strftime('%Y-%m-%d')
        except ValueError:
            pass
    return ''


def _real_deadline(value, today=None):
    """Listing end dates far in the future are automatic expiry dates, not deadlines."""
    d = iso_date(value)
    if not d:
        return ''
    today = today or dt.date.today()
    try:
        days = (dt.date.fromisoformat(d) - today).days
    except ValueError:
        return ''
    return d if -30 <= days <= 180 else ''


_PAY = re.compile(
    r'(?:(?:CA|US|C|A)?[$£€]|\b(?:CAD|USD|GBP|EUR)\s?)\s?\d[\d,]*(?:\.\d+)?\s?[kK]?'
    r'(?:\s?(?:-|–|—|to)\s?(?:(?:CA|US|C)?[$£€]|(?:CAD|USD|GBP|EUR)\s?)?\s?\d[\d,]*(?:\.\d+)?\s?[kK]?)?'
    r'(?:\s?(?:CAD|USD|GBP|EUR))?(?:\s?(?:/|per|an|a)\s?(?:hour|hr|year|yr|annum|month|week|day))?', re.I)
_PAY_WORDS = re.compile(r'\b(?:salary|pay|compensation|wage|rate|base|stipend|range|hourly|annual|per\s+(?:hour|year))\b', re.I)


def pay_from_text(text):
    """A pay range or rate quoted in a description, or ''. Ignores money that isn't pay (e.g. "$275B in spend")."""
    for line in str(text or '').splitlines():
        for m in _PAY.finditer(line):
            s = m.group(0).strip()
            ranged = bool(re.search(r'\d\s?[kK]?\s?(?:-|–|—|to)\s?\D{0,4}\d', s))
            unit = bool(re.search(r'(?:/|per|an|a)\s?(?:hour|hr|year|yr|annum|month|week|day)$', s, re.I))
            if re.search(r'\d\s?[bBmM]\b', line[m.end():m.end() + 3]) and not unit:
                continue
            if ranged or unit or _PAY_WORDS.search(line):
                if re.fullmatch(r'\D*\d{1,3}\D*', s) and not unit:
                    continue  # "$5" alone: too small to be a salary
                if not re.search(r'[1-9]', s):
                    continue  # "$0.00 - $0.00": a blank pay field
                return s
    return ''


_DEADLINE = re.compile(r'\b(?:deadline|apply\s+by|applications?\s+(?:will\s+)?(?:close|closes|are\s+due|due|must\s+be\s+received)|'
                       r'closing\s+date|accepting\s+applications\s+(?:until|through)|submit\s+(?:your\s+application\s+)?by|'
                       r'posting\s+(?:closes|ends))\b[^.\n]{0,80}', re.I)
_DATEISH = re.compile(r'\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}|\b\d{1,2}\s+(?:jan|feb|mar|apr|'
                      r'may|jun|jul|aug|sep|oct|nov|dec)|\d{4}-\d{2}-\d{2}|\b\d{1,2}/\d{1,2}/\d{2,4}', re.I)


def deadline_from_text(text):
    for m in _DEADLINE.finditer(str(text or '')):
        if _DATEISH.search(m.group(0)):
            return re.sub(r'\s+', ' ', m.group(0)).strip(' :-')
    return ''


def _place(*parts):
    return ', '.join(p for p in (str(x or '').strip() for x in parts) if p)


def _workplace(value):
    v = norm(value).replace(' ', '')
    return {'onsite': 'on-site', 'hybrid': 'hybrid', 'remote': 'remote', 'telecommute': 'remote'}.get(v, '')


def _with_mode(location, mode):
    if mode and mode not in location.lower():
        return f'{location} ({mode})' if location else mode
    return location


_YESNO = {'yes', 'no'}


def question(label, required, qtype, options=None):
    opts = [str(o).strip() for o in (options or []) if str(o).strip()]
    if qtype == 'select' and opts and ({o.lower() for o in opts} <= _YESNO or (
            len(opts) == 2 and re.match(r'yes\b', opts[0], re.I) and re.match(r'no\b', opts[1], re.I))):
        qtype = 'yes/no'
    return {'label': re.sub(r'\s+', ' ', html_to_text(label)).strip(), 'required': bool(required), 'type': qtype,
            'options': opts}


def _cover_field(posting):
    for q in posting['questions']:
        if re.search(r'cover\s*letter|letter\s+of\s+(?:interest|motivation)|motivation\s+letter', q['label'], re.I):
            posting['cover_letter_field'] = 'required' if q['required'] else 'optional'
            return


# ---- Greenhouse --------------------------------------------------------------------------------------------------

_GH_TYPES = {'input_text': 'text', 'textarea': 'textarea', 'input_file': 'file', 'multi_value_single_select': 'select',
             'multi_value_multi_select': 'multi', 'boolean': 'yes/no'}


def _greenhouse_board(info, url, f):
    if info.get('board'):
        return info['board']
    if info.get('id'):
        try:
            loc = f.location(f"https://boards.greenhouse.io/embed/job_app?token={info['id']}") or ''
            m = re.search(r'[?&]for=([\w.-]+)', loc) or re.search(r'greenhouse\.io/([\w.-]+)/jobs/', loc)
            if m:
                return m.group(1)
        except FetchError as e:
            if e.kind == 'network':
                raise
    try:
        page = f.html(url)
        m = re.search(r'greenhouse\.io/embed/job_board/js\?for=([\w.-]+)', page) or \
            re.search(r'(?:job-)?boards(?:\.eu)?\.greenhouse\.io/([\w.-]+)', page)
        if m and m.group(1) not in ('embed', 'v1'):
            return m.group(1)
    except FetchError as e:
        if e.kind == 'network':
            raise
    return ''


def fetch_greenhouse(url, info, f):
    p = new_posting(url, 'greenhouse')
    board = _greenhouse_board(info, url, f)
    if not board or not info.get('id'):
        raise FetchError('could not tell which Greenhouse board this job belongs to', 'parse')
    bases = ['https://boards-api.eu.greenhouse.io', 'https://boards-api.greenhouse.io'] if info.get('eu') else \
        ['https://boards-api.greenhouse.io', 'https://boards-api.eu.greenhouse.io']
    d, last = None, None
    for base in bases:
        try:
            d = f.json(f"{base}/v1/boards/{board}/jobs/{info['id']}?questions=true&pay_transparency=true")
            break
        except FetchError as e:
            last = e
            if e.kind != 'notfound':
                raise
    if d is None:
        raise last
    p['company'] = d.get('company_name') or board
    p['check_company'] = not d.get('company_name')
    p['role'] = (d.get('title') or '').strip()
    p['location'] = ((d.get('location') or {}).get('name') or '').strip()
    p['posted'] = iso_date(d.get('first_published') or d.get('updated_at'))
    p['deadline'] = iso_date(d.get('application_deadline'))
    p['description'] = clean_text(d.get('content') or '')
    ranges = d.get('pay_input_ranges') or []
    if ranges:
        r = ranges[0]
        lo, hi = r.get('min_cents'), r.get('max_cents')
        cur = r.get('currency_type') or ''
        fmt = lambda c: f'{c / 100:,.0f}' if c is not None else '?'
        p['pay'] = f"{fmt(lo)} - {fmt(hi)} {cur}".strip() + (f" ({r['title']})" if r.get('title') else '')
    p['form_published'] = 'questions' in d
    for qd in d.get('questions') or []:
        fields = [x for x in qd.get('fields') or [] if x.get('type') != 'input_hidden']
        if not fields:
            continue
        main = next((x for x in fields if x.get('type') == 'input_file'), fields[0])
        qtype = _GH_TYPES.get(main.get('type'), 'text')
        opts = [v.get('label') for v in main.get('values') or []]
        p['questions'].append(question(qd.get('label') or '', qd.get('required'), qtype, opts))
    _cover_field(p)
    return p


# ---- Lever -------------------------------------------------------------------------------------------------------

_LEVER_TYPES = {'multiple-choice': 'select', 'multiple-select': 'multi', 'dropdown': 'select', 'textarea': 'textarea',
                'text': 'text', 'file-upload': 'file', 'date': 'text'}


def lever_form(page):
    """Questions from a Lever /apply page: the standard fields and the custom question cards (JSON in a hidden input)."""
    qs = []
    for m in re.finditer(r'<div class="application-label">(.*?)</div>', page, re.S):
        raw = m.group(1)
        label = re.sub(r'✱|✳|\*', '', html_to_text(raw)).strip()
        if label:
            qs.append(question(label, 'class="required"' in raw, 'file' if re.search(r'resume|cv\b', label, re.I) else 'text'))
    for m in re.finditer(r'<input[^>]*name="cards\[[^\]]+\]\[baseTemplate\]"[^>]*>', page):
        v = re.search(r'value="([^"]*)"', m.group(0))
        if not v:
            continue
        try:
            card = json.loads(html.unescape(v.group(1)))
        except ValueError:
            continue
        for fld in card.get('fields') or []:
            opts = [o.get('text') if isinstance(o, dict) else o for o in fld.get('options') or []]
            qs.append(question(fld.get('text') or '', fld.get('required'), _LEVER_TYPES.get(fld.get('type'), 'text'), opts))
    comments = re.search(r'<textarea[^>]*name="comments"[^>]*>', page)
    note = ''
    if comments:
        ph = re.search(r'placeholder="([^"]*)"', comments.group(0))
        if ph and re.search(r'cover\s+letter', ph.group(1), re.I):
            note = f'Additional information box: "{html.unescape(ph.group(1))}"'
    return qs, note


def fetch_lever(url, info, f):
    p = new_posting(url, 'lever')
    if not info.get('company') or not info.get('id'):
        raise FetchError('this Lever link does not point at one posting', 'parse')
    api = 'https://api.eu.lever.co' if info.get('eu') else 'https://api.lever.co'
    try:
        d = f.json(f"{api}/v0/postings/{info['company']}/{info['id']}")
    except FetchError as e:
        if e.kind != 'notfound' or info.get('eu'):
            raise
        d = f.json(f"https://api.eu.lever.co/v0/postings/{info['company']}/{info['id']}")
    cats = d.get('categories') or {}
    p['role'] = (d.get('text') or '').strip()
    locs = cats.get('allLocations') or ([cats['location']] if cats.get('location') else [])
    p['location'] = _with_mode('; '.join(locs), _workplace(d.get('workplaceType')))
    p['posted'] = iso_date(d.get('createdAt'))
    parts = [d.get('description') or '']
    for lst in d.get('lists') or []:
        parts.append(f"<h3>{lst.get('text', '')}</h3><ul>{lst.get('content', '')}</ul>")
    parts.append(d.get('additional') or '')
    p['description'] = clean_text('\n'.join(parts))
    sr = d.get('salaryRange') or {}
    if sr.get('min') or sr.get('max'):
        interval = str(sr.get('interval') or '').replace('-', ' ')
        p['pay'] = f"{sr.get('min', 0):,} - {sr.get('max', 0):,} {sr.get('currency', '')} {interval}".strip()
    p['company'] = info['company']
    p['check_company'] = True
    apply_url = d.get('applyUrl') or (d.get('hostedUrl', '').rstrip('/') + '/apply')
    try:
        page = f.html(apply_url)
        t = re.search(r'<title>([^<]+)', page)
        if t:
            title = html.unescape(t.group(1)).strip()
            if ' - ' in title:
                p['company'], p['check_company'] = title.split(' - ', 1)[0].strip(), False
        p['questions'], p['cover_letter_note'] = lever_form(page)
        p['form_published'] = bool(p['questions'])
        _cover_field(p)
        if not p['cover_letter_field'] and p['cover_letter_note']:
            p['cover_letter_field'] = 'optional'
    except FetchError as e:
        if e.kind == 'network':
            raise
    return p


# ---- Ashby -------------------------------------------------------------------------------------------------------

_ASHBY_Q = ('query ApiJobPosting($organizationHostedJobsPageName: String!, $jobPostingId: String!) { '
            'jobPosting(organizationHostedJobsPageName: $organizationHostedJobsPageName, jobPostingId: $jobPostingId) { '
            'id title locationName workplaceType employmentType descriptionHtml publishedDate applicationDeadline '
            'compensationTierSummary secondaryLocationNames applicationForm { sections { title fieldEntries { '
            '... on FormFieldEntry { id field isRequired descriptionHtml isHidden } } } } } }')
_ASHBY_ORG = ('query ApiOrganizationFromHostedJobsPageName($organizationHostedJobsPageName: String!) { '
              'organization: organizationFromHostedJobsPageName(organizationHostedJobsPageName: $organizationHostedJobsPageName) '
              '{ name } }')
_ASHBY_TYPES = {'String': 'text', 'LongText': 'textarea', 'Email': 'text', 'Phone': 'text', 'File': 'file',
                'Boolean': 'yes/no', 'ValueSelect': 'select', 'MultiValueSelect': 'multi', 'Date': 'text',
                'Number': 'text', 'Location': 'text', 'EducationHistory': 'text', 'Score': 'select', 'SocialLink': 'text'}


def _ashby_graphql(f, op, query, variables):
    d = f.json(f'https://jobs.ashbyhq.com/api/non-user-graphql?op={op}',
               data={'operationName': op, 'variables': variables, 'query': query})
    if d.get('errors') and not d.get('data'):
        msg = d['errors'][0].get('message', 'error') if isinstance(d['errors'], list) else 'error'
        if 'secondaryLocationNames' in msg:
            raise FetchError(msg, 'schema')
        raise FetchError(f'Ashby: {msg}', 'parse')
    return d.get('data') or {}


def fetch_ashby(url, info, f):
    p = new_posting(url, 'ashby')
    if not info.get('org') or not info.get('id'):
        raise FetchError('this Ashby link does not point at one posting', 'parse')
    v = {'organizationHostedJobsPageName': info['org'], 'jobPostingId': info['id']}
    try:
        data = _ashby_graphql(f, 'ApiJobPosting', _ASHBY_Q, v)
    except FetchError as e:
        if e.kind != 'schema':
            raise
        data = _ashby_graphql(f, 'ApiJobPosting', _ASHBY_Q.replace(' secondaryLocationNames', ''), v)
    jp = data.get('jobPosting')
    if not jp:
        raise FetchError('Ashby has no such posting (it may be closed)', 'notfound')
    try:
        org = (_ashby_graphql(f, 'ApiOrganizationFromHostedJobsPageName', _ASHBY_ORG,
                              {'organizationHostedJobsPageName': info['org']}).get('organization') or {}).get('name')
    except FetchError:
        org = None
    p['company'] = org or info['org']
    p['check_company'] = not org
    p['role'] = (jp.get('title') or '').strip()
    locs = [jp.get('locationName') or ''] + list(jp.get('secondaryLocationNames') or [])
    p['location'] = _with_mode('; '.join(l for l in locs if l), _workplace(jp.get('workplaceType')))
    p['posted'] = iso_date(jp.get('publishedDate'))
    p['deadline'] = iso_date(jp.get('applicationDeadline'))
    p['pay'] = jp.get('compensationTierSummary') or ''
    p['description'] = clean_text(jp.get('descriptionHtml') or '')
    form = jp.get('applicationForm') or {}
    p['form_published'] = bool(form.get('sections'))
    for sec in form.get('sections') or []:
        for e in sec.get('fieldEntries') or []:
            fld = e.get('field') or {}
            if not fld or e.get('isHidden'):
                continue
            opts = [o.get('label') for o in fld.get('selectableValues') or [] if isinstance(o, dict)]
            p['questions'].append(question(fld.get('title') or '', e.get('isRequired'),
                                           _ASHBY_TYPES.get(fld.get('type'), 'text'), opts))
    _cover_field(p)
    if not p['pay']:
        p['pay'] = pay_from_text(p['description'])
    return p


# ---- Workday -----------------------------------------------------------------------------------------------------

def _workday_posted(info):
    s = str(info.get('postedOn') or '')
    if re.search(r'today', s, re.I):
        return dt.date.today().isoformat()
    if re.search(r'yesterday', s, re.I):
        return (dt.date.today() - dt.timedelta(days=1)).isoformat()
    m = re.search(r'(\d+)\+?\s+days?\s+ago', s, re.I)
    if m and '+' not in s:
        return (dt.date.today() - dt.timedelta(days=int(m.group(1)))).isoformat()
    return ''


def fetch_workday(url, info, f):
    p = new_posting(url, 'workday')
    if not (info.get('tenant') and info.get('site') and info.get('slug')):
        raise FetchError('this Workday link does not point at one posting', 'parse')
    d = f.json(f"{info['base']}/wday/cxs/{info['tenant']}/{info['site']}/job/{info['slug']}")
    j = d.get('jobPostingInfo') or {}
    if not j:
        raise FetchError('Workday returned no posting (it may be closed)', 'notfound')
    org = ((d.get('hiringOrganization') or {}).get('name') or '').strip()
    org = re.sub(r'^[A-Z]{0,4}\d{1,5}\s+', '', org)
    p['company'] = org or info['tenant'].replace('-', ' ').title()
    p['check_company'] = not org
    p['role'] = (j.get('title') or '').strip()
    locs = [j.get('location') or ''] + list(j.get('additionalLocations') or [])
    p['location'] = _with_mode('; '.join(l for l in locs if l), _workplace(j.get('remoteType') or ''))
    p['posted'] = iso_date(j.get('startDate')) or _workday_posted(j)
    p['deadline'] = _real_deadline(j.get('endDate'))
    p['description'] = clean_text(j.get('jobDescription') or '')
    p['pay'] = pay_from_text(p['description'])
    p['cover_letter_field'] = None       # Workday doesn't publish its form: "none" unless the description asks
    return p


# ---- SmartRecruiters ---------------------------------------------------------------------------------------------

def fetch_smartrecruiters(url, info, f):
    p = new_posting(url, 'smartrecruiters')
    if not info.get('company') or not info.get('id'):
        raise FetchError('this SmartRecruiters link does not point at one posting', 'parse')
    d = f.json(f"https://api.smartrecruiters.com/v1/companies/{info['company']}/postings/{info['id']}")
    p['company'] = ((d.get('company') or {}).get('name') or info['company']).strip()
    p['role'] = (d.get('name') or '').strip()
    loc = d.get('location') or {}
    mode = 'remote' if loc.get('remote') else 'hybrid' if loc.get('hybrid') else ''
    p['location'] = _with_mode(loc.get('fullLocation') or _place(loc.get('city'), loc.get('region'), loc.get('country')), mode)
    p['posted'] = iso_date(d.get('releasedDate'))
    secs = (d.get('jobAd') or {}).get('sections') or {}
    parts = []
    for key in ('jobDescription', 'qualifications', 'additionalInformation', 'companyDescription'):
        sec = secs.get(key) or {}
        if sec.get('text'):
            parts.append(f"<h3>{sec.get('title') or ''}</h3>{sec['text']}")
    p['description'] = clean_text('\n'.join(parts))
    p['pay'] = pay_from_text(p['description'])
    return p


# ---- Oracle Recruiting Cloud -------------------------------------------------------------------------------------

def fetch_oracle(url, info, f):
    p = new_posting(url, 'oracle')
    if not info.get('id'):
        raise FetchError('this Oracle link does not point at one posting', 'parse')
    finder = f'ById;Id="{info["id"]}"' + (f',siteNumber={info["site"]}' if info.get('site') else '')
    d = f.json(f"https://{info['host']}/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails?"
               f"expand=all&onlyData=true&finder={urllib.parse.quote(finder, safe=';=,')}")
    items = d.get('items') or []
    if not items:
        raise FetchError('Oracle returned no posting (it may be closed)', 'notfound')
    j = items[0]
    p['role'] = (j.get('Title') or '').strip()
    locs = [j.get('PrimaryLocation') or ''] + [x.get('Name') or '' for x in j.get('secondaryLocations') or []]
    p['location'] = _with_mode('; '.join(l for l in locs if l), _workplace(j.get('WorkplaceType') or j.get('WorkplaceTypeCode') or ''))
    p['posted'] = iso_date(j.get('ExternalPostedStartDate'))
    p['deadline'] = _real_deadline(j.get('ExternalPostedEndDate'))
    parts = [j.get(k) or '' for k in ('ExternalDescriptionStr', 'ExternalResponsibilitiesStr', 'ExternalQualificationsStr',
                                     'OrganizationDescriptionStr', 'CorporateDescriptionStr')]
    flex = [x for x in j.get('requisitionFlexFields') or [] if x.get('Value')]
    p['description'] = clean_text('\n'.join(parts) + ''.join(f"<p>{x.get('Prompt')}: {x['Value']}</p>" for x in flex))
    pay = next((x['Value'] for x in flex if re.search(r'pay|salary|wage|compensation', str(x.get('Prompt')), re.I)), '')
    p['pay'] = pay or pay_from_text(p['description'])
    host = info['host'].split('.')[0]
    guess = host.upper() if len(host) <= 5 else host.title()
    p['company'] = j.get('LegalEmployer') or j.get('Organization') or guess
    p['check_company'] = not (j.get('LegalEmployer') or j.get('Organization'))
    return p


# ---- Rippling ----------------------------------------------------------------------------------------------------

_RIPPLING_TYPES = {'SHORT_ANSWER': 'text', 'LONG_ANSWER': 'textarea', 'PARAGRAPH': 'textarea', 'FILE': 'file',
                   'PHONE_NUMBER': 'text', 'PRONOUN': 'select', 'EMAIL': 'text', 'URL': 'text',
                   'select': 'select', 'text': 'text', 'textarea': 'textarea', 'paragraph': 'textarea',
                   'longtext': 'textarea', 'file': 'file', 'date': 'text', 'number': 'text', 'boolean': 'yes/no'}


def fetch_rippling(url, info, f):
    p = new_posting(url, 'rippling')
    if not info.get('board') or not info.get('id'):
        raise FetchError('this Rippling link does not point at one posting', 'parse')
    d = f.json(f"https://api.rippling.com/platform/api/ats/v1/board/{info['board']}/jobs/{info['id']}")
    p['company'] = (d.get('companyName') or info['board']).strip()
    p['check_company'] = not d.get('companyName')
    p['role'] = (d.get('name') or '').strip()
    p['location'] = '; '.join(str(x.get('name') if isinstance(x, dict) else x) for x in d.get('workLocations') or [])
    p['posted'] = iso_date(d.get('createdOn'))
    desc = d.get('description') or {}
    p['description'] = clean_text((desc.get('role') or '') + '\n' + (desc.get('company') or '')) if isinstance(desc, dict) \
        else clean_text(str(desc))
    pr = d.get('payRangeDetails') or []
    if pr and isinstance(pr[0], dict):
        r = pr[0]
        lo, hi = r.get('rangeStart') or r.get('min'), r.get('rangeEnd') or r.get('max')
        if lo or hi:
            p['pay'] = f"{lo:,} - {hi:,} {r.get('currency', '')} {str(r.get('frequency') or '').lower()}".strip() \
                if isinstance(lo, (int, float)) and isinstance(hi, (int, float)) else f'{lo} - {hi}'
    if not p['pay']:
        p['pay'] = pay_from_text(p['description'])
    app = d.get('activeJobApplication') or {}
    for q in app.get('basicQuestions') or []:
        p['questions'].append(question(q.get('title') or '', q.get('required'), _RIPPLING_TYPES.get(q.get('fieldType'), 'text')))
    for block in app.get('additionalQuestions') or []:
        for q in ((block.get('form') or {}).get('questions') or []):
            qtype = _RIPPLING_TYPES.get(q.get('dataType'), 'text')
            opts = q.get('strChoices') or [str(x) for x in q.get('intChoices') or []]
            if qtype == 'select' and q.get('isMultiSelectEnabled') and len(opts) > 2:
                qtype = 'multi'
            p['questions'].append(question(q.get('title') or '', q.get('isRequired'), qtype, opts))
    p['form_published'] = bool(app)
    _cover_field(p)
    return p


# ---- Job Bank (Canada) -------------------------------------------------------------------------------------------

def _prop(page, name):
    m = re.search(r'property="%s"[^>]*>(.*?)</(?:span|p|h1|div|strong)>' % name, page, re.S)
    return re.sub(r'\s+', ' ', html_to_text(m.group(1))).strip() if m else ''


def parse_jobbank(page, url):
    p = new_posting(url, 'jobbank')
    p['role'] = _prop(page, 'title')
    m = re.search(r'property="hiringOrganization".*?property="name"[^>]*>(.*?)</span>', page, re.S)
    p['company'] = re.sub(r'\s+', ' ', html_to_text(m.group(1))).strip() if m else ''
    p['posted'] = iso_date(_prop(page, 'datePosted'))
    adv = iso_date(_prop(page, 'validThrough'))
    p['deadline'] = f'{adv} (advertised until)' if adv else ''
    city, region = _prop(page, 'addressLocality'), _prop(page, 'addressRegion')
    mode = ''
    wl = re.search(r'Work location</span>\s*<span>([^<]+)</span>', page)
    if wl:
        mode = wl.group(1).strip().lower().replace('on site', 'on-site')
    p['location'] = _with_mode(_place(city, region), mode)
    sal = re.search(r'property="baseSalary"(.*?)</li>', page, re.S)
    if sal:
        s = re.sub(r'\s+', ' ', html_to_text('<span ' + sal.group(1))).strip()
        s = re.sub(r'^[^$\d]*', '', s)
        s = re.sub(r'\b(YEAR|HOUR|WEEK|MONTH)\s+', '', s)
        p['pay'] = ('$' + s.lstrip('$ ')).replace('$ ', '$') if s else ''
    parts = []
    head = re.search(r'<h2[^>]*>\s*Job details\s*</h2>(.*?)(?:<div[^>]*job-posting-detail-requirements|<h3>\s*Advertised until)', page, re.S)
    if head:
        block = re.sub(r'(?s)<span[^>]*class="hidden"[^>]*>.*?</span>', ' ', head.group(1))
        items = []
        for li in re.findall(r'(?s)<li[^>]*>(.*?)</li>', block):
            t = re.sub(r'\s+', ' ', html_to_text(li)).strip(' -')
            if t and not re.match(r'^(?:Location|Work location|Salary|Source|Various locations)\b', t) and t not in items:
                items.append(t)
        if items:
            parts.append('\n'.join('- ' + t for t in items))
    req = re.search(r'job-posting-detail-requirements[^>]*>(.*?)(?:Show how to apply|<h3>\s*Advertised until|id="howtoapply)', page, re.S)
    if req:
        parts.append(clean_text(req.group(1)))
    else:
        desc = re.search(r'property="description"[^>]*>(.*?)</span>', page, re.S)
        if desc:
            parts.append(clean_text(html.unescape(desc.group(1))))
    text = '\n\n'.join(x for x in parts if x.strip())
    # "Who can apply" as one sentence, so the eligibility screen reads it as a whole
    text = re.sub(r'(You can apply if you are:|The employer accepts applications from:)\s*((?:\n\s*-\s*[^\n]+)+)',
                  lambda m: m.group(1) + ' ' + '; '.join(x.strip(' -') for x in m.group(2).strip().splitlines()) + '.', text)
    noc = re.search(r'class="noc-title">([^<]*)</span>\s*<span class="noc-no">NOC\s*(\d{5})', page)
    if noc:
        text += f'\n\nNOC 2021: {noc.group(2)} ({noc.group(1).strip()})'
    else:
        n = re.search(r'NOC\s*(?:2021)?\s*:?\s*(\d{5})', page)
        if n:
            text += f'\n\nNOC 2021: {n.group(1)}'
    if re.search(r'provided by a partner site', page):
        text += '\n\n(This posting comes from a partner site; the full posting and how to apply are on the employer\'s site.)'
    p['description'] = re.sub(r'\n{3,}', '\n\n', text).strip()
    return p


def fetch_jobbank(url, info, f):
    if not info.get('id'):
        raise FetchError('this Job Bank link does not point at one posting', 'parse')
    page = f.request(f"https://www.jobbank.gc.ca/jobsearch/jobposting/{info['id']}", accept='text/html')[2]
    if 'property="title"' not in page:
        raise FetchError('Job Bank did not return the posting (it may have expired)', 'notfound')
    return parse_jobbank(page, url)


# ---- schema.org JobPosting JSON-LD (iCIMS and any other site) ----------------------------------------------------

def _jsonld_objects(page):
    for m in re.finditer(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', page, re.S | re.I):
        try:
            d = json.loads(m.group(1).strip())
        except ValueError:
            try:
                d = json.loads(html.unescape(m.group(1).strip()))
            except ValueError:
                continue
        stack = [d]
        while stack:
            x = stack.pop()
            if isinstance(x, list):
                stack.extend(x)
            elif isinstance(x, dict):
                t = x.get('@type')
                if t == 'JobPosting' or (isinstance(t, list) and 'JobPosting' in t):
                    yield x
                if '@graph' in x:
                    stack.append(x['@graph'])


def parse_jsonld(page, url, system='other'):
    """Posting from a page's JobPosting JSON-LD, or None when there is none."""
    j = next(_jsonld_objects(page), None)
    if not j:
        return None
    p = new_posting(url, system)
    p['role'] = html.unescape(str(j.get('title') or '')).strip()
    org = j.get('hiringOrganization')
    p['company'] = html.unescape(str((org.get('name') if isinstance(org, dict) else org) or '')).strip()
    locs = j.get('jobLocation') or []
    locs = locs if isinstance(locs, list) else [locs]
    names = []
    for loc in locs:
        a = (loc or {}).get('address') if isinstance(loc, dict) else None
        if isinstance(a, dict):
            names.append(_place(a.get('addressLocality'), a.get('addressRegion'), a.get('addressCountry')
                                if isinstance(a.get('addressCountry'), str) else (a.get('addressCountry') or {}).get('name')))
        elif isinstance(a, str):
            names.append(a)
    mode = 'remote' if 'TELECOMMUTE' in str(j.get('jobLocationType') or '').upper() else ''
    p['location'] = _with_mode('; '.join(n for n in names if n), mode)
    p['posted'] = iso_date(j.get('datePosted'))
    p['deadline'] = _real_deadline(j.get('validThrough'))
    p['description'] = clean_text(str(j.get('description') or ''))
    sal = j.get('baseSalary')
    if isinstance(sal, dict):
        v = sal.get('value') or {}
        if isinstance(v, dict):
            lo, hi, unit = v.get('minValue'), v.get('maxValue'), v.get('unitText') or ''
            amount = f'{lo} - {hi}' if lo and hi and lo != hi else str(lo or hi or v.get('value') or '')
        else:
            amount, unit = str(v), ''
        if amount.strip():
            p['pay'] = f"{amount} {sal.get('currency') or ''} {str(unit).lower()}".strip()
    if not p['pay']:
        p['pay'] = pay_from_text(p['description'])
    return p


def fetch_page(url, info, f, system='other'):
    page_url = url
    if system == 'icims':
        u = urllib.parse.urlsplit(url)
        q = dict(urllib.parse.parse_qsl(u.query))
        q['in_iframe'] = '1'
        page_url = urllib.parse.urlunsplit((u.scheme, u.netloc, u.path, urllib.parse.urlencode(q), ''))
    page = f.html(page_url)
    p = parse_jsonld(page, url, system)
    if p is None:
        raise FetchError('no job data on this page (it may need JavaScript)', 'parse')
    if not p['company']:
        p['company'] = company_from_url(url)
        p['check_company'] = True
    return p


# ---- pasted text -------------------------------------------------------------------------------------------------

def company_from_url(url):
    system, info = detect(url)
    slug = info.get('board') or info.get('company') or info.get('org') or info.get('tenant') or ''
    if not slug:
        host = urllib.parse.urlsplit(str(url or '')).netloc.lower().split(':')[0]
        parts = [x for x in host.split('.') if x not in ('www', 'jobs', 'careers', 'apply', 'boards', 'job-boards')]
        slug = parts[-2] if len(parts) >= 2 else (parts[0] if parts else '')
        slug = re.sub(r'^(careers|jobs)-', '', slug)
    return re.sub(r'[-_]+', ' ', urllib.parse.unquote(slug)).strip().title()


def from_text(text, url, company='', role=''):
    """A posting from a description the user pasted (plain text or HTML)."""
    system, _ = detect(url) if url else ('other', {})
    p = new_posting(url, system if system != 'linkedin' else 'linkedin')
    body = clean_text(text) if re.search(r'<(p|div|li|br|ul)\b', text or '', re.I) else str(text or '').strip()
    body = re.sub(r'\r\n?', '\n', body)
    p['description'] = re.sub(r'\n{3,}', '\n\n', body)
    lines = [l.strip() for l in p['description'].splitlines() if l.strip()]

    def field(*names):
        for l in lines[:40]:
            m = re.match(r'^(?:%s)\s*[:\-–]\s*(.+)$' % '|'.join(names), l, re.I)
            if m:
                return m.group(1).strip()
        return ''

    head = lines[0] if lines else ''
    m = re.match(r'^#?\s*(.+?)\s+at\s+(.+)$', head)
    p['role'] = role or field('job title', 'title', 'role', 'position') or (m.group(1) if m else (head if len(head) <= 100 else ''))
    p['company'] = company or field('company', 'employer', 'organization', 'organisation') or (m.group(2) if m else '')
    if not p['company']:
        p['company'] = company_from_url(url) if url else ''
        p['check_company'] = True
    p['location'] = field('location', 'job location', 'work location', 'city')
    p['pay'] = field('salary', 'pay', 'compensation', 'wage') or pay_from_text(p['description'])
    p['posted'] = iso_date(field('posted', 'date posted', 'posted on'))
    p['deadline'] = field('deadline', 'apply by', 'closing date', 'application deadline') or deadline_from_text(p['description'])
    return p


# ---- one entry point ---------------------------------------------------------------------------------------------

_FETCHERS = {'greenhouse': fetch_greenhouse, 'lever': fetch_lever, 'ashby': fetch_ashby, 'workday': fetch_workday,
             'smartrecruiters': fetch_smartrecruiters, 'oracle': fetch_oracle, 'rippling': fetch_rippling,
             'jobbank': fetch_jobbank}
_STAFFING = re.compile(r'\b(?:staffing|recruit(?:ing|ment|ers?)|talent\s+(?:solutions|partners|acquisition\s+partners)|'
                       r'robert\s+half|teksystems|randstad|adecco|insight\s+global|kforce|aerotek|manpower|hays|michael\s+page|'
                       r'kelly\s+services|apex\s+systems|cybercoders|jobot|motion\s+recruitment|modis|akkodis|beacon\s+hill|'
                       r'actalent|procom|astra\s+north)\b', re.I)
_CLIENT = re.compile(r'\b(?:our\s+client|on\s+behalf\s+of\s+(?:a|our)\s+client|client\s+company|for\s+a\s+(?:leading|well[- ]known)\s+client)\b', re.I)


def hint_for(system, err):
    if system == 'linkedin':
        return ('LinkedIn is never fetched. Paste the description and run with --text FILE --url URL, or find the '
                "same job on the company's own careers page or application system.")
    if err.kind == 'network':
        return 'No connection to this site. Open the posting in the browser and read it there.'
    if err.kind == 'notfound':
        return 'The posting seems closed or moved. Open the link in the browser to check, or look on the company careers page.'
    return 'Open the posting in the browser and read it there, or paste the description with --text FILE --url URL.'


def fetch(url, f=None):
    """Posting dict for a link. Never raises: problems come back in "error" and "hint"."""
    f = f or Fetcher()
    system, info = detect(url)
    p = new_posting(url, system)
    if system == 'linkedin':
        p['error'] = 'LinkedIn is not fetched'
        p['hint'] = hint_for('linkedin', None)
        return p
    try:
        if system in _FETCHERS:
            p = _FETCHERS[system](url, info, f)
        else:
            p = fetch_page(url, info, f, system)
        p['system'] = system
    except FetchError as e:
        p['error'] = str(e)
        p['error_kind'] = e.kind
        p['hint'] = hint_for(system, e)
        if system in _FETCHERS and e.kind in ('parse', 'notfound') and system != 'jobbank':
            # second chance: the page itself may carry JSON-LD
            try:
                q = fetch_page(url, info, f, system)
                q['system'] = system
                return finish(q)
            except FetchError:
                pass
        return p
    except Exception as e:  # unexpected data shape: report, don't crash the batch
        p['error'] = f'could not read this posting ({type(e).__name__}: {e})'
        p['hint'] = hint_for(system, FetchError('', 'parse'))
        return p
    return finish(p)


def finish(p):
    """Fill gaps that every system shares: pay and deadline from the text, staffing-agency check."""
    if not p['pay']:
        p['pay'] = pay_from_text(p['description'])
    if not p['deadline']:
        p['deadline'] = deadline_from_text(p['description'])
    if _STAFFING.search(p['company'] or '') or _CLIENT.search(p['description'] or ''):
        p['check_company'] = True
    p['description'] = p['description'] or ''
    return p


# ---- cover letter, written questions, markdown -------------------------------------------------------------------

_CL_NOT = re.compile(r"\bno\s+cover\s+letters?\b|\bcover\s+letters?\s+(?:is\s+|are\s+)?(?:not|never)\s+(?:required|needed|necessary|"
                     r"accepted|considered|read|reviewed)\b|\b(?:do\s+not|don'?t|no\s+need\s+to|please\s+don'?t)\s+(?:need\s+to\s+)?"
                     r"(?:send|include|submit|attach|write|upload)\s+(?:a\s+|any\s+)?cover\s+letters?\b|\bskip\s+the\s+cover\s+letter\b|"
                     r"\bwithout\s+a\s+cover\s+letter\b", re.I)
_CL_ASK = re.compile(r"\b(?:include|attach|submit|send|provide|upload|along\s+with|accompanied\s+by|together\s+with|with)\b[^.]{0,60}"
                     r"\bcover\s+letter\b|\bcover\s+letter\b[^.]{0,40}\b(?:is\s+)?(?:required|must|mandatory|should|is\s+requested|"
                     r"expected)\b|\b(?:resume|cv)\s+(?:and|&|\+)\s+(?:a\s+)?cover\s+letter\b|\bletter\s+of\s+(?:interest|intent|"
                     r"motivation)\b", re.I)
_CL_OPT = re.compile(r"\bcover\s+letters?\s*(?:\(optional\)|(?:is|are)\s+optional|optional)\b|\boptional(?:ly)?[^.]{0,30}cover\s+letter\b", re.I)


def cover_letter(p):
    """(status, quote): required|optional|asked|not wanted|none|unknown."""
    from .redflags import split_sentences
    sents = split_sentences(p.get('description') or '')
    no = next((s for s in sents if _CL_NOT.search(s)), None)
    if no:
        return 'not wanted', no[:240]
    if p.get('cover_letter_field') == 'required':
        return 'required', ''
    opt = next((s for s in sents if _CL_OPT.search(s)), None)
    ask = next((s for s in sents if _CL_ASK.search(s) and not _CL_OPT.search(s) and not re.search(r'\?\s*$', s)), None)
    if ask:
        return 'asked', ask[:240]
    if p.get('cover_letter_field') == 'optional':
        return 'optional', p.get('cover_letter_note') or ''
    if opt:
        return 'optional', opt[:240]
    if p.get('form_published') or p.get('system') == 'workday':
        return 'none', ''
    return 'unknown', ''


_FACTUAL = re.compile(r'\b(?:name|e-?mail|phone|linkedin|github|website|portfolio|url|link|address|city|location|located|'
                      r'relocat\w*|salary|compensation|pay\b|pronoun|hear\s+about|how\s+did\s+you|referr\w*|graduat\w*|degree|gpa|'
                      r'school|university|college|employer|company|job\s+title|start\s+date|notice\s+period|availab\w*|'
                      r'citizenship|sponsor\w*|authori[sz]\w*|visa|gender|race|ethnic\w*|veteran|disab\w*|deadline|'
                      r'resume|cv\b|cover\s+letter|transcript|pronunciation|preferred|languages?|country|state|province|'
                      r'zip|postal|date\s+of|when\s+can|years\s+of\s+experience|consent|privacy|agree|acknowledge|'
                      r'certify|recording|notetak\w*|ai\s+tool)\b', re.I)
_OPEN = re.compile(r'^(?:why|what|how|describe|tell|share|explain|please\s+(?:describe|tell|share|explain|provide|give|write)|'
                   r'give|in\s+(?:\d+|a\s+few|one|two)|briefly|walk\s+us|talk\s+about|if\s+you\s+could|imagine)\b|'
                   r'\b(?:words?\s+or\s+(?:less|fewer)|paragraphs?|in\s+\d+\s+words|essay|motivat\w*|interest\w*\s+in|'
                   r'proud|accomplishment|challenge|example\s+of|a\s+time\s+(?:when|you)|excite\w*)\b', re.I)


def written_questions(questions):
    """Open-ended questions that need a drafted answer (essays, "why us", "tell us about a project")."""
    out = []
    for q in questions or []:
        label, t = q.get('label') or '', q.get('type')
        if t in ('file', 'select', 'multi', 'yes/no'):
            continue
        if re.search(r'^(?:additional\s+information|comments?|anything\s+else)$', label, re.I):
            continue
        if t == 'textarea' and not _FACTUAL.search(label):
            out.append(label)
        elif _OPEN.search(label) and (not _FACTUAL.search(label) or re.search(r'\bwhy\b|\bproud|\bbuilt\b|\bproject', label, re.I)):
            out.append(label)
    return out


def question_line(q, max_options=12):
    opts = q.get('options') or []
    extra = ''
    if opts:
        shown = opts[:max_options]
        extra = '; options: ' + ' | '.join(shown) + (f' | ... (+{len(opts) - max_options} more)' if len(opts) > max_options else '')
    return f"- [{'required' if q.get('required') else 'optional'}] {q.get('label')} ({q.get('type')}{extra})"


def _loc_line(profile, loc):
    from .location import location_line
    r = location_line(profile, loc)
    return f"{r['line']} ({r['why']})" if r['line'] else f"(set city in profile.json; {r['why']})"


def render_markdown(p, screen='ok', screen_why=None, flags=None, cl=('unknown', ''), profile=None):
    """job-posting.md text (format in the spec, section 2). With a profile, adds the location line for the resume
    and letter (location.location_line)."""
    status, quote = cl
    reasons = '; '.join(w.rsplit(' -> ', 1)[-1] for w in (screen_why or []) if not w.rsplit(' -> ', 1)[-1].startswith('note:'))
    flags_line = '; '.join(f"{x['flag']} (\"{x['quote']}\")" for x in flags or []) or 'none'
    lines = [f"# {p.get('role') or 'Unknown role'} at {p.get('company') or 'Unknown company'}", '',
             f"- Company: {p.get('company') or 'unknown'}" + (' (check: name uncertain)' if p.get('check_company') else ''),
             f"- Role: {p.get('role') or 'unknown'}",
             f"- URL: {p.get('url') or ''}",
             f"- Location: {p.get('location') or 'not stated'}",
             *([f"- Your location line: {_loc_line(profile, p.get('location'))}"] if profile else []),
             f"- Deadline: {p.get('deadline') or 'not stated'}",
             f"- Pay: {p.get('pay') or 'not stated'}",
             f"- Posted: {p.get('posted') or 'unknown'}",
             f"- Application system: {p.get('system') or 'other'}",
             f"- Cover letter: {status}" + (f' ("{quote}")' if quote else ''),
             f"- Screen: {screen}" + (f' ({reasons})' if reasons else ''),
             f"- Red flags: {flags_line}",
             '', '## Description', '', (p.get('description') or '(no description)').strip(), '',
             '## Application questions', '']
    if p.get('questions'):
        lines += [question_line(q) for q in p['questions']]
    else:
        lines.append('- (the application form is not published; read it in the browser)' if not p.get('form_published')
                     else '- (no questions beyond the standard form)')
    return '\n'.join(lines).rstrip() + '\n'
