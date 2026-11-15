#!/usr/bin/env python3
"""Find jobs and internships in Canada, the US or the UK (search.json "country") from several public sources, rank them by fit, and queue the best in jobs.txt.

Usage:
  python find_jobs.py --folder "JOB_SEARCH_FOLDER" [--source NAME ...] [--days 30] [--limit 25] [--min-score N] [--append]
  python find_jobs.py --folder "JOB_SEARCH_FOLDER" --check-sources     (tries every employer board in search.json once)
  python find_jobs.py --folder "JOB_SEARCH_FOLDER" --add-employer URL  (registers a company's board from any link to it:
                                                                        Greenhouse, Lever, Ashby, SmartRecruiters, Workday)

Settings come from search.json in the folder (tracks, places, employers; see README "Job search settings") and the
master resume in resume/ (for ranking). Sources (all public job data, read politely, one request a second per site,
one every 5 seconds for Job Bank as its robots.txt asks):
  simplify-intern   SimplifyJobs internship list (locations in your country only)
  simplify-newgrad  SimplifyJobs new-grad list (locations in your country only)
  jobbank           (Canada only) Government of Canada Job Bank search, one search per entry in search.json "jobbank_queries"
  greenhouse        each board in search.json employers.greenhouse
  lever             each company in employers.lever
  ashby             each organization in employers.ashby
  smartrecruiters   each company in employers.smartrecruiters (postings in your country)
  workday           each {"host", "tenant", "site"} in employers.workday
  remotive          remote jobs open to your country (Remotive API; its terms allow personal use with a link back)

Keeps only postings in your country (or remote and open to it) whose title fits a track in search.json and isn't
excluded (senior, manager, ...). Drops LinkedIn links, postings already in tracker.xlsx (link, job ID, or company and
title) and links already in jobs.txt. Every result has a fit score from rank_jobs.py.

--append adds results scoring at least --min-score (default: search.json min_score_to_queue, else 55), best first,
at most search.json max_queue_per_run, above "# done", each with a note "Company | Role | Location | posted DATE |
fit N (track)". Nothing is deleted. Prints one JSON object; also saves every candidate to
.cache/candidates-YYYY-MM-DD.json in the folder for job_digest.py.
Exit codes: 0 ok, 1 bad input.
"""
import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
for _p in (HERE, os.path.join(HERE, '..', '..', 'lib')):
    if os.path.isdir(os.path.join(_p, 'jobkit')):
        sys.path.insert(0, os.path.abspath(_p))
        break
from jobkit.queue import posting_keys, queued_links, role_key as name_key  # same duplicate rules everywhere
from jobkit.text import norm
import rank_jobs

USER_AGENT = 'Mozilla/5.0 (compatible; personal job-search script; reads public job postings)'
GAPS = {'www.jobbank.gc.ca': 5.0}
_last = {}
SIMPLIFY = {
    'simplify-intern': 'https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/.github/scripts/listings.json',
    'simplify-newgrad': 'https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/.github/scripts/listings.json',
}
ALL_SOURCES = ['simplify-intern', 'simplify-newgrad', 'jobbank', 'greenhouse', 'lever', 'ashby', 'smartrecruiters',
               'workday', 'remotive']


def get(url, data=None, headers=None, raw=False, timeout=30):
    host = urllib.parse.urlparse(url).netloc
    wait = GAPS.get(host, 1.0) - (time.time() - _last.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    # Job Bank answers 500 to an Accept header that prefers JSON, so pages ask for HTML
    h = {'User-Agent': USER_AGENT, 'Accept': 'text/html,application/xhtml+xml' if raw else 'application/json'}
    h.update(headers or {})
    body = json.dumps(data).encode() if isinstance(data, (dict, list)) else data
    if isinstance(data, (dict, list)):
        h['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=body, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            text = r.read().decode('utf-8', errors='replace')
    finally:
        _last[host] = time.time()
    return text if raw else json.loads(text)


def day(v):
    """YYYY-MM-DD from epoch seconds or milliseconds, ISO text, or 'November 10, 2026'."""
    if v in (None, ''):
        return ''
    if isinstance(v, (int, float)):
        return dt.date.fromtimestamp(v / 1000 if v > 1e11 else v).isoformat()
    s = str(v).strip()
    m = re.match(r'(\d{4}-\d{2}-\d{2})', s)
    if m:
        return m.group(1)
    for fmt in ('%B %d, %Y', '%b %d, %Y'):
        try:
            return dt.datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    return ''


def job(source, company, title, location, url, posted='', description='', kind=''):
    return {'source': source, 'company': html.unescape(str(company or '')).strip(), 'title': html.unescape(str(title or '')).strip(),
            'location': str(location or '').strip(), 'url': url, 'posted': day(posted), 'description': description or '',
            'kind': kind}


# ---- sources -------------------------------------------------------------------------------------------------

def simplify(name, search):
    cache = os.path.join(tempfile.gettempdir(), f'{name}-listings.json')
    if os.path.exists(cache) and time.time() - os.path.getmtime(cache) < 3 * 3600:
        data = json.load(open(cache, encoding='utf-8'))
    else:
        data = get(SIMPLIFY[name], timeout=90)
        json.dump(data, open(cache, 'w', encoding='utf-8'))  # temp folder only
    out = []
    for x in data:
        if not x.get('active') or not x.get('is_visible', True):
            continue
        locs = x.get('locations') or []
        here = [l for l in locs if rank_jobs.place_fit(l, search) not in (None, 'remote')]
        if not here:
            continue
        out.append(job(name, x.get('company_name'), x.get('title'), '; '.join(here[:3]), x.get('url'),
                       x.get('date_posted'), kind='internship' if name.endswith('intern') else 'new grad'))
    return out


def jobbank(search, errors=None):
    out = []
    for q in search.get('jobbank_queries', []):
        # Job Bank ignores free-text locations ("Vancouver, BC"); the province filter fprov is what narrows results.
        params = {'searchstring': q, 'sort': 'D'}
        if search.get('province'):
            params['fprov'] = search['province'].upper()
        try:
            page = get('https://www.jobbank.gc.ca/jobsearch/jobsearch?' + urllib.parse.urlencode(params), raw=True)
        except Exception as e:  # one failed search shouldn't lose the others
            if errors is not None:
                errors[f'jobbank:{q}'] = f'{type(e).__name__}: {str(e)[:100]}'
            continue
        for m in re.finditer(r'<article id="article-(\d+)"(.*?)</article>', page, re.S):
            pid, body = m.group(1), m.group(2)
            def cls(c):
                # an <li> holds icon <span>s, so match it to its own closing tag first
                mm = re.search(rf'<li class="{c}">(.*?)</li>', body, re.S) or re.search(rf'<span class="{c}">(.*?)</span>', body, re.S)
                return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', mm.group(1))).replace('Location', '').strip() if mm else ''
            loc = cls('location').replace('(', ', ').replace(')', '')
            out.append(job('jobbank', cls('business'), cls('noctitle'), loc + ', Canada',
                           f'https://www.jobbank.gc.ca/jobsearch/jobposting/{pid}', cls('date'),
                           description=cls('salary')))
    return out


def greenhouse(board, search):
    d = get(f'https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true')
    name = board
    try:
        name = get(f'https://boards-api.greenhouse.io/v1/boards/{board}').get('name') or board
    except Exception:
        pass
    return [job('greenhouse', name, j.get('title'), (j.get('location') or {}).get('name'), j.get('absolute_url'),
                j.get('first_published') or j.get('updated_at'), j.get('content')) for j in d.get('jobs', [])]


def lever(company, search):
    d = get(f'https://api.lever.co/v0/postings/{company}?mode=json')
    out = []
    for j in d:
        cats = j.get('categories') or {}
        loc = ', '.join(filter(None, [cats.get('location'), j.get('workplaceType') if j.get('workplaceType') == 'remote' else '']))
        out.append(job('lever', company.replace('-', ' ').title(), j.get('text'), loc, j.get('hostedUrl'), j.get('createdAt'),
                       (j.get('descriptionPlain') or '') + ' ' + ' '.join(l.get('content', '') for l in j.get('lists') or [])))
    return out


def ashby(org, search):
    d = get(f'https://api.ashbyhq.com/posting-api/job-board/{org}?includeCompensation=false')
    out = []
    for j in d.get('jobs', []):
        places = [j.get('location') or ''] + [s.get('location', '') for s in j.get('secondaryLocations') or []]
        country = ((j.get('address') or {}).get('postalAddress') or {}).get('addressCountry') or ''
        loc = '; '.join(p for p in places if p)
        if country and country.lower() not in loc.lower():
            loc += f', {country}'
        if j.get('isRemote'):
            loc += ' (Remote)'
        out.append(job('ashby', org, j.get('title'), loc, j.get('jobUrl'), j.get('publishedAt'), j.get('descriptionPlain')))
    return out


def smartrecruiters(company, search):
    c = rank_jobs.COUNTRIES[rank_jobs.country_code(search)]
    d = get(f"https://api.smartrecruiters.com/v1/companies/{company}/postings?country={c['sr']}&limit=100")
    out = []
    for j in d.get('content', []):
        l = j.get('location') or {}
        loc = ', '.join(filter(None, [l.get('city'), l.get('region'), {'ca': 'Canada', 'us': 'United States', 'gb': 'United Kingdom'}[c['sr']],
                                      'Remote' if l.get('remote') else '']))
        out.append(job('smartrecruiters', (j.get('company') or {}).get('name') or company, j.get('name'), loc,
                       f"https://jobs.smartrecruiters.com/{company}/{j.get('id')}", j.get('releasedDate')))
    return out


def workday(w, search):
    base = f"https://{w['host']}/wday/cxs/{w['tenant']}/{w['site']}"
    out = []
    for q in w.get('queries') or ['']:
        d = get(base + '/jobs', data={'appliedFacets': {}, 'limit': 20, 'offset': 0, 'searchText': q})
        for j in d.get('jobPostings', []):
            out.append(job('workday', w.get('company') or w['tenant'], j.get('title'), j.get('locationsText'),
                           f"https://{w['host']}/{w['site']}{j.get('externalPath', '')}", ''))
    return out


def remotive(search):
    c = rank_jobs.COUNTRIES[rank_jobs.country_code(search)]
    out = []
    for cat in search.get('remotive_categories', ['data', 'software-dev', 'customer-support']):
        d = get(f'https://remotive.com/api/remote-jobs?category={urllib.parse.quote(cat)}&limit=100')
        for j in d.get('jobs', []):
            where = j.get('candidate_required_location') or ''
            if not re.search(c['remotive'], where, re.I):
                continue
            out.append(job('remotive', j.get('company_name'), j.get('title'), f"Remote ({where}, open to {c['name']})",
                           j.get('url'), j.get('publication_date'), j.get('description')))
    return out


def collect(search, sources, errors):
    """Run each source; a failing one is recorded in errors and the rest still run."""
    emp = search.get('employers') or {}
    plan = []
    for s in sources:
        if s.startswith('simplify'):
            plan.append((s, s, lambda s=s: simplify(s, search)))
        elif s == 'jobbank':
            if rank_jobs.country_code(search) != 'CA':
                continue  # Job Bank lists Canadian jobs only
            plan.append((s, s, lambda: jobbank(search, errors)))
        elif s == 'remotive':
            plan.append((s, s, lambda: remotive(search)))
        elif s in ('greenhouse', 'lever', 'ashby', 'smartrecruiters'):
            fn = globals()[s]
            plan += [(s, f'{s}:{b}', lambda b=b, fn=fn: fn(b, search)) for b in emp.get(s, [])]
        elif s == 'workday':
            plan += [(s, f"workday:{w.get('tenant')}", lambda w=w: workday(w, search)) for w in emp.get('workday', [])]
    found, counts = [], {}
    for source, label, fn in plan:
        try:
            got = fn()
            counts[label] = len(got)
            found += got
        except urllib.error.HTTPError as e:
            errors[label] = f'HTTP {e.code}' + (' (no such board: check the name in search.json)' if e.code == 404 else '')
        except Exception as e:
            errors[label] = f'{type(e).__name__}: {str(e)[:120]}'
    return found, counts


# ---- filtering and ranking -------------------------------------------------------------------------------------

def tracker_index(folder):
    path = os.path.join(folder, 'tracker.xlsx')
    keys = set()
    if not os.path.exists(path):
        return keys
    from jobkit import tracker
    _, ws, _ = tracker.open_book(path)
    for row in tracker.rows(ws):
        row = tracker.read_links(ws, row)
        keys |= posting_keys(row['posting_url'])
        k = name_key(row['company'], row['role'])
        if k:
            keys.add(k)
    return keys


def run(folder, sources, days=None, today=None):
    """Collect, filter and score. Returns (ranked list, report dict)."""
    search = rank_jobs.load_search(folder)
    master = rank_jobs.master_text(folder)
    errors, skipped = {}, {k: 0 for k in ('linkedin', 'not_in_country', 'title_not_in_tracks', 'excluded_title',
                                          'too_old', 'already_tracked', 'already_in_jobs_txt', 'duplicate')}
    found, counts = collect(search, sources, errors)
    tracked = tracker_index(folder)
    queued, queued_keys = queued_links(os.path.join(folder, 'jobs.txt'))
    today = today or dt.date.today()
    seen, keep = set(), []
    for j in found:
        url = j.get('url') or ''
        if not url or 'linkedin.com' in url.lower():
            skipped['linkedin'] += 1; continue
        if rank_jobs.place_fit(j['location'], search) is None and not (j['source'] == 'remotive'):
            skipped['not_in_country'] += 1; continue
        if excluded(j['title'], search):
            skipped['excluded_title'] += 1; continue
        if not rank_jobs.best_track(j['title'], search)[0]:
            skipped['title_not_in_tracks'] += 1; continue
        if days and j['posted'] and (today - dt.date.fromisoformat(j['posted'])).days > days:
            skipped['too_old'] += 1; continue
        keys = posting_keys(url) | ({name_key(j['company'], j['title'])} - {None})
        if keys & tracked:
            skipped['already_tracked'] += 1; continue
        if posting_keys(url) & queued_keys or url.split('?')[0].rstrip('/').lower() in {q.lower() for q in queued}:
            skipped['already_in_jobs_txt'] += 1; continue
        dupe = name_key(j['company'], j['title'])
        if dupe in seen or posting_keys(url) & seen:
            skipped['duplicate'] += 1; continue
        seen |= posting_keys(url) | {dupe}
        j['fit'] = rank_jobs.score(j, master, search, today)
        keep.append(j)
    order(keep)
    enriched = enrich(keep, master, search, today, search.get('enrich_top', 30))
    report = {'found': len(found), 'per_source': counts, 'errors': errors, 'skipped': skipped, 'kept': len(keep),
              'descriptions_fetched': enriched}
    return keep, report


def order(jobs):
    jobs.sort(key=lambda j: j['posted'] or '0000', reverse=True)  # newest first among equal scores (stable sort)
    jobs.sort(key=lambda j: -j['fit']['score'])


def enrich(jobs, master, search, today, top):
    """Listings without a description (SimplifyJobs, Job Bank, SmartRecruiters) can't be skill-matched or screened, so
    read the full posting for the best few with jobkit.postings, rescore, and re-sort."""
    try:
        from jobkit import postings
    except Exception:
        return 0
    fetcher = postings.Fetcher()
    n = 0
    for j in jobs[:top]:
        if len(rank_jobs.text_of(j['description'])) > 400 or 'linkedin.com' in j['url'].lower():
            continue
        try:
            p = postings.fetch(j['url'], fetcher)
        except Exception:
            continue
        if p and not p.get('error') and p.get('description'):
            j['description'] = p['description']
            if p.get('posted') and not j['posted']:
                j['posted'] = day(p['posted'])
            j['fit'] = rank_jobs.score(j, master, search, today)
            n += 1
    order(jobs)
    return n


def excluded(title, search):
    return rank_jobs.excluded(title, search)


def queueable(j, profile):
    """Co-op and student-only roles need enrolment in a school program; queue them only when the profile says the
    user is enrolled and returning to school after the job. They still show in results and the digest."""
    student_only = any(f.startswith('co-op or student only') for f in j['fit']['flags'])
    return not student_only or (profile.get('enrolled') == 'yes' and profile.get('returningToSchool') == 'yes')


def pick_for_queue(jobs, folder, search, min_score):
    try:
        profile = json.load(open(os.path.join(folder, 'profile.json'), encoding='utf-8'))
    except (OSError, ValueError):
        profile = {}
    return [j for j in jobs if j['fit']['score'] >= min_score and queueable(j, profile)][:search.get('max_queue_per_run', 15)]


def note(j):
    loc = j['location'].replace('|', '/').replace('#', '')[:60]
    return (f"{j['url']}  # {j['company'].replace('|', '/')} | {j['title'].replace('|', '/')} | {loc} | "
            f"posted {j['posted'] or 'unknown'} | fit {j['fit']['score']} ({j['fit']['track']})")


def append(folder, picks):
    """Queue the picked postings in jobs.txt above "# done" (jobkit.queue: skips any already there)."""
    from jobkit.queue import append_links
    return append_links(os.path.join(folder, 'jobs.txt'),
                        [(j['url'], note(j).split('  # ', 1)[1]) for j in picks])


def save_cache(folder, ranked, report):
    d = os.path.join(folder, '.cache')
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f'candidates-{dt.date.today().isoformat()}.json')
    slim = [{k: v for k, v in j.items() if k != 'description'} for j in ranked]
    json.dump({'saved': dt.datetime.now().isoformat(timespec='minutes'), 'report': report, 'jobs': slim},
              open(path, 'w', encoding='utf-8'), indent=1)
    return path


def add_employer(folder, url):
    """Register a company's job board in search.json from any link to it (a posting or the careers page)."""
    path = os.path.join(folder, 'search.json')
    search = json.load(open(path, encoding='utf-8'))
    emp = search.setdefault('employers', {})
    u = urllib.parse.urlparse(url.strip())
    host, parts = u.netloc.lower(), [p for p in u.path.split('/') if p]
    entry, kind = None, None
    if host.endswith('greenhouse.io') and parts:
        q = urllib.parse.parse_qs(u.query)
        kind, entry = 'greenhouse', (q.get('for') or [parts[0]])[0]
    elif host.endswith('lever.co') and parts:
        kind, entry = 'lever', parts[0]
    elif host.endswith('ashbyhq.com') and parts:
        kind, entry = 'ashby', parts[0]
    elif 'smartrecruiters.com' in host and parts:
        kind, entry = 'smartrecruiters', parts[0]
    elif 'myworkdayjobs.com' in host or 'myworkdaysite.com' in host:
        rest = [p for p in parts if not re.fullmatch(r'[a-z]{2}-[A-Z]{2}', p)]
        if 'recruiting' in rest:  # myworkdaysite.com/recruiting/<tenant>/<site>
            i = rest.index('recruiting')
            tenant, site = rest[i + 1], rest[i + 2]
        else:
            tenant, site = host.split('.')[0], rest[0] if rest else ''
        kind = 'workday'
        entry = {'company': tenant, 'host': host, 'tenant': tenant, 'site': site,
                 'queries': ['engineer', 'analyst', 'data']}
    if not kind:
        return {'ok': False, 'error': 'not a Greenhouse, Lever, Ashby, SmartRecruiters or Workday link',
                'hint': "Add the company's careers search to jobbank_queries instead, or open the posting and run fetch_posting.py on it."}
    errors = {}
    probe = {'greenhouse': greenhouse, 'lever': lever, 'ashby': ashby, 'smartrecruiters': smartrecruiters, 'workday': workday}[kind]
    try:
        n = len(probe(entry, search))
    except Exception as e:
        return {'ok': False, 'kind': kind, 'entry': entry, 'error': f'the board did not answer: {str(e)[:150]}'}
    current = emp.setdefault(kind, [])
    if entry not in current and not (kind == 'workday' and any(w.get('host') == host and w.get('site') == entry['site'] for w in current)):
        current.append(entry)
        with open(path, 'w', encoding='utf-8') as f:  # edited in place
            json.dump(search, f, indent=2, ensure_ascii=False)
    return {'ok': True, 'kind': kind, 'entry': entry, 'postings_now': n}


def check_sources(folder):
    search = rank_jobs.load_search(folder)
    errors = {}
    _, counts = collect(search, ['greenhouse', 'lever', 'ashby', 'smartrecruiters', 'workday'], errors)
    return {'ok': True, 'working': counts, 'failing': errors}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--folder', default='.')
    ap.add_argument('--source', action='append', default=[], choices=ALL_SOURCES)
    ap.add_argument('--days', type=int, default=45)
    ap.add_argument('--limit', type=int, default=25)
    ap.add_argument('--min-score', type=int)
    ap.add_argument('--append', action='store_true')
    ap.add_argument('--check-sources', action='store_true')
    ap.add_argument('--add-employer', metavar='URL', help="add a company's job board to search.json from any link to it")
    a = ap.parse_args()
    folder = os.path.abspath(a.folder)
    if not os.path.exists(os.path.join(folder, 'search.json')):
        print(json.dumps({'ok': False, 'error': f'no search.json in {folder}'}))
        sys.exit(1)
    if a.add_employer:
        r = add_employer(folder, a.add_employer)
        print(json.dumps(r, indent=1))
        sys.exit(0 if r['ok'] else 1)
    if a.check_sources:
        print(json.dumps(check_sources(folder), indent=1))
        return
    search = rank_jobs.load_search(folder)
    ranked, report = run(folder, a.source or ALL_SOURCES, a.days)
    cache = save_cache(folder, ranked, report)
    min_score = a.min_score if a.min_score is not None else search.get('min_score_to_queue', 55)
    added = []
    if a.append:
        added = pick_for_queue(ranked, folder, search, min_score)
        if added:
            append(folder, added)
    shown = [{'fit': j['fit']['score'], 'track': j['fit']['track'], 'company': j['company'], 'title': j['title'],
              'location': j['location'], 'posted': j['posted'], 'source': j['source'], 'url': j['url'],
              'why': j['fit']['why'], 'gaps': j['fit']['gaps'][:6], 'flags': [f.split(':')[0] for f in j['fit']['flags']]}
             for j in ranked[:a.limit]]
    print(json.dumps({'ok': True, 'report': report, 'min_score': min_score, 'added_to_jobs_txt': len(added),
                      'cache': cache, 'top': shown}, indent=1))


if __name__ == '__main__':
    main()
