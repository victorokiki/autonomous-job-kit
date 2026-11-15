"""Find open internships in the SimplifyJobs list, filter them for the user, and (optionally) queue them in jobs.txt.

Usage:
  python find_internships.py --folder "JOB_SEARCH_FOLDER" [filters] [--append]
  python find_internships.py --folder "JOB_SEARCH_FOLDER" --tidy

Source: the SimplifyJobs Summer 2027 internship list (a public JSON file on GitHub), kept in the system temp folder
for 3 hours so repeated searches don't download it again.

Filters (all optional):
  --term "Summer 2027"      term to look for (default: profile internshipTerm, else Summer 2027; "any" = every term)
  --category Software       Software, Data (AI/ML/Data), Hardware, Product, Quant; repeat for several
  --location CA --location Remote --location "New York"   state/province codes, cities or Remote; repeatable
  --keyword intern --exclude-keyword senior               words in the job title; repeatable
  --degree bachelor         keep listings open to this degree (bachelor, master, phd, associate, mba)
  --needs-sponsorship / --no-needs-sponsorship            drop listings that don't sponsor or need U.S. citizenship
                            (default: profile needsSponsorshipForInternship, else needsSponsorship)
  --no-citizenship          drop listings that require U.S. citizenship
  --days 14                 posted in the last N days
  --limit 25                how many results to list (and append)
  --include-abroad          keep non-U.S. locations for a U.S. profile (otherwise only U.S. locations are kept)

Always skipped: closed or hidden listings, LinkedIn links, postings the tracker already has (matched by
link, by the site's job ID, or by company plus title), postings already in jobs.txt (waiting or done; same link, job ID, or the note's "Company | Role"), and repeats
within the list.

--append adds the results to jobs.txt above "# done" with the note "Company | Role | Location | posted DATE".

--tidy downloads nothing: it moves waiting links in jobs.txt below "# done", with the reason in the note, when they
are already in the tracker (same link, job ID, or the note's "Company | Role"), listed twice, or (U.S. profile)
located outside the U.S. according to the note.

Output: one JSON object: ok, found, kept, skipped {reason: count}, results [{company, role, location, url, posted,
sponsorship, category, terms}], appended. --tidy gives ok, waiting, moved [{url, reason}], still_waiting.
Exit codes: 0 ok, 1 bad input, 5 openpyxl missing (needed to read the tracker), 6 download failed.

Other scripts import posting_keys, role_key and queued(path) from here.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(HERE, '..', '..', 'lib')):
    if os.path.isdir(os.path.join(_p, 'jobkit')):
        sys.path.insert(0, os.path.abspath(_p))
        break
from jobkit import cli, files, text, queue  # noqa: E402,F401
from jobkit.queue import posting_keys, role_key  # noqa: E402  (re-exported for other scripts)
from jobkit.text import norm  # noqa: E402

SOURCE_URL = 'https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/.github/scripts/listings.json'
CACHE_HOURS = 3
DEFAULT_TERM = 'Summer 2027'
USER_AGENT = 'Mozilla/5.0 (compatible; job-kit personal internship search)'

US_STATES = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas', 'CA': 'California', 'CO': 'Colorado',
    'CT': 'Connecticut', 'DE': 'Delaware', 'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho',
    'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana',
    'ME': 'Maine', 'MD': 'Maryland', 'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota',
    'MS': 'Mississippi', 'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
    'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York', 'NC': 'North Carolina',
    'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania',
    'RI': 'Rhode Island', 'SC': 'South Carolina', 'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas',
    'UT': 'Utah', 'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia',
    'WI': 'Wisconsin', 'WY': 'Wyoming', 'DC': 'District of Columbia', 'PR': 'Puerto Rico',
}
_STATE_NAMES = {norm(v): k for k, v in US_STATES.items()}
_US_WORDS = re.compile(r'\b(usa|u s a|united states|us|nationwide)\b')
_US_SHORT = {'nyc', 'sf', 'la', 'south sf', 'dc', 'remote'}
_ABROAD_WORDS = re.compile(r'\b(canada|united kingdom|uk|england|scotland|wales|ireland|france|germany|'
                           r'switzerland|netherlands|india|china|japan|singapore|australia|mexico|brazil|israel|'
                           r'spain|italy|poland|sweden|denmark|united arab emirates|uae|hong kong|taiwan|korea)\b')
_CITY_ALIASES = {'new york': 'nyc', 'new york city': 'nyc', 'san francisco': 'sf', 'los angeles': 'la'}
_CATEGORY_WORDS = {'machine learning': 'ml', 'artificial intelligence': 'ai', 'data science': 'data',
                   'swe': 'software', 'software engineering': 'software', 'pm': 'product',
                   'product management': 'product', 'quantitative': 'quant', 'quantitative finance': 'quant',
                   'finance': 'quant', 'electrical': 'hardware', 'embedded': 'hardware'}
_DEGREES = [('phd', r'\b(phd|ph d|doctor|doctoral|doctorate)\b'), ('mba', r'\bmba\b'),
            ('master', r'\b(master|masters|ms|msc|m s|meng|graduate)\b'),
            ('associate', r'\b(associate|associates)\b'),
            ('bachelor', r'\b(bachelor|bachelors|bs|bsc|ba|b s|beng|undergraduate|undergrad)\b')]


# ---- helpers other scripts use ---------------------------------------------------------------------------------

def queued(path):
    """(set of cleaned links, set of posting keys) for every link in jobs.txt (see jobkit.queue.queued_links)."""
    return queue.queued_links(path)


jobs_urls = queued  # older name


def degree_level(value):
    """Canonical degree word (phd, mba, master, associate, bachelor) for a degree name, or None."""
    s = norm(value)
    for name, pattern in _DEGREES:
        if re.search(pattern, s):
            return name
    return None


def is_us_location(loc):
    """True when a SimplifyJobs-style location string is in the U.S. ("Austin, TX", "Remote in USA", "NYC",
    "California"); False for anything else ("Toronto, ON, Canada", "London, UK", "Paris, France")."""
    raw = str(loc or '').strip()
    if not raw:
        return False
    n = norm(raw)
    if _ABROAD_WORDS.search(n):
        return False
    if _US_WORDS.search(n) or n in _US_SHORT:
        return True
    parts = [p.strip() for p in re.split(r'[,\-–]', raw) if p.strip()]
    last = parts[-1] if parts else raw
    if len(last) == 2 and last.upper() in US_STATES:
        return True
    return norm(last) in _STATE_NAMES or n in _STATE_NAMES


def us_profile(profile):
    c = norm((profile or {}).get('country'))
    return c in {'us', 'usa', 'u s', 'u s a', 'united states', 'united states of america', 'america'}


def _yes(v):
    return v if isinstance(v, bool) else norm(v) in {'yes', 'y', 'true', '1'}


def default_needs_sponsorship(profile):
    p = profile or {}
    for k in ('needsSponsorshipForInternship', 'needsSponsorship'):
        v = p.get(k)
        if isinstance(v, bool) or norm(v):
            return _yes(v)
    return False


# ---- download --------------------------------------------------------------------------------------------------

def _cache_path():
    return os.path.join(tempfile.gettempdir(), 'jobkit-cache', 'simplify-summer2027-listings.json')


def load_listings(source=None, refresh=False):
    """(listings, note). `source` may be a local JSON file (tests). Raises OSError when the download fails and no
    cached copy exists."""
    if source and not re.match(r'https?://', source):
        with open(source, encoding='utf-8') as f:
            return json.load(f), f'read {source}'
    url = source or SOURCE_URL
    cache = _cache_path()
    fresh = os.path.exists(cache) and time.time() - os.path.getmtime(cache) < CACHE_HOURS * 3600
    if fresh and not refresh and not source:
        try:
            with open(cache, encoding='utf-8') as f:
                return json.load(f), 'used the copy downloaded in the last 3 hours'
        except ValueError:
            pass
    try:
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
        data = json.loads(raw.decode('utf-8'))
        if not isinstance(data, list):
            raise ValueError('the listings file is not a list')
    except (urllib.error.URLError, OSError, ValueError) as e:
        if os.path.exists(cache) and not source:
            try:
                with open(cache, encoding='utf-8') as f:
                    return json.load(f), f'download failed ({e}); used the older cached copy'
            except ValueError:
                pass
        raise OSError(f'Could not download the internship list: {e}')
    if not source:
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        tmp = cache + f'.{os.getpid()}.part'
        with open(tmp, 'wb') as f:
            f.write(raw)
        os.replace(tmp, cache)
    return data, 'downloaded'


# ---- tracker and queue -----------------------------------------------------------------------------------------

def tracker_keys(folder):
    """({posting key: tracker ID}, {role key: tracker ID}) for every row in the folder's tracker.xlsx."""
    path = os.path.join(folder, 'tracker.xlsx')
    keys, roles = {}, {}
    if not os.path.exists(path):
        return keys, roles
    from jobkit import tracker
    try:
        _, ws, _ = tracker.open_book(path)
    except ValueError as e:
        cli.fail(str(e))
    for row in tracker.rows(ws):
        row = tracker.read_links(ws, row)
        rid = str(row.get('id') or '')
        for k in posting_keys(row.get('posting_url')):
            keys[k] = rid
        rk = role_key(row.get('company'), row.get('role'))
        if rk:
            roles[rk] = rid
    return keys, roles


def _note_fields(note):
    return [p.strip() for p in str(note or '').split('|')]


def queued_role_keys(path):
    """Role keys ("company|title") read from the notes in jobs.txt written as "Company | Role | ..."."""
    q = queue.read_queue(path)
    out = set()
    for e in q['waiting'] + q['done']:
        f = _note_fields(e['note'])
        rk = role_key(f[0], f[1]) if len(f) >= 2 else None
        if rk:
            out.add(rk)
    return out


# ---- matching --------------------------------------------------------------------------------------------------

def _term_ok(listing, term):
    if norm(term) in ('any', 'all', ''):
        return True
    return any(norm(t) == norm(term) for t in listing.get('terms') or [])


def _category_ok(listing, cats):
    if not cats:
        return True
    have = norm(listing.get('category'))
    have_words = set(have.split())
    for c in cats:
        q = _CATEGORY_WORDS.get(norm(c), norm(c))
        if not q:
            continue
        if q in have or set(q.split()) <= have_words:
            return True
        if q == 'data' and have_words & {'ai', 'ml'}:
            return True
        if q in ('ai', 'ml') and 'data' in have_words:
            return True
    return False


def _location_match(loc, want):
    n = norm(loc)
    w = want.strip()
    wn = norm(w)
    if not wn:
        return False
    if wn == 'remote':
        return 'remote' in n
    if len(w) == 2 and w.isalpha():  # a state or province code
        code = w.upper()
        if any(p.strip().upper() == code for p in loc.split(',')[1:]):
            return True
        state = US_STATES.get(code)
        return bool(state) and (n == norm(state) or n.endswith(' ' + norm(state)))
    if ' ' + wn + ' ' in ' ' + n + ' ':
        return True
    alias = _CITY_ALIASES.get(wn)
    if alias and (n == alias or n.startswith(alias + ' ')):
        return True
    if wn in _STATE_NAMES:  # a state name also matches "City, XX"
        return any(p.strip().upper() == _STATE_NAMES[wn] for p in loc.split(',')[1:])
    return False


def _words_in(title, words):
    t = ' ' + norm(title) + ' '
    return any(' ' + norm(w) + ' ' in t for w in words if norm(w))


def _posted(listing):
    ts = listing.get('date_posted') or listing.get('date_updated')
    try:
        return dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).date()
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def search(listings, a, profile, tracked, tracked_roles, queued_keys, today=None, queued_roles=()):
    """Filter listings. Returns (kept list of result dicts, newest first; skipped counts by reason)."""
    today = today or dt.date.today()
    skipped = {}

    def skip(reason):
        skipped[reason] = skipped.get(reason, 0) + 1

    term = a.term or (profile.get('internshipTerm') or '').strip() or DEFAULT_TERM
    needs_sp = a.needs_sponsorship if a.needs_sponsorship is not None else default_needs_sponsorship(profile)
    us_only = us_profile(profile) and not a.include_abroad
    want_degree = degree_level(a.degree) if a.degree else None
    tracked_set = set(tracked)
    seen, kept = set(), []
    for x in listings:
        if not isinstance(x, dict):
            continue
        url = str(x.get('url') or '').strip().split('#')[0]
        company, role = str(x.get('company_name') or '').strip(), str(x.get('title') or '').strip()
        locs = [str(l).strip() for l in (x.get('locations') or []) if str(l).strip()]
        sponsorship = str(x.get('sponsorship') or '')
        if not x.get('active', True) or x.get('is_visible') is False:
            skip('closed'); continue
        if not url or 'linkedin.com' in url.lower():
            skip('linkedin_or_no_link'); continue
        if not _term_ok(x, term):
            skip('other_term'); continue
        if not _category_ok(x, a.category):
            skip('category'); continue
        if us_only and locs:
            us_locs = [l for l in locs if is_us_location(l)]
            if not us_locs:
                skip('outside_us'); continue
            locs = us_locs
        if a.location and not any(_location_match(l, w) for l in locs for w in a.location):
            skip('location'); continue
        if a.keyword and not _words_in(role, a.keyword):
            skip('keyword'); continue
        if a.exclude_keyword and _words_in(role, a.exclude_keyword):
            skip('excluded_keyword'); continue
        degrees = {degree_level(d) for d in x.get('degrees') or []} - {None}
        if want_degree and degrees and want_degree not in degrees:
            skip('degree'); continue
        sp = norm(sponsorship)
        if (needs_sp or a.no_citizenship) and 'citizenship' in sp:
            skip('citizenship_required'); continue
        if needs_sp and ('does not' in sp or 'no sponsorship' in sp):
            skip('no_sponsorship'); continue
        posted = _posted(x)
        if a.days is not None and posted and (today - posted).days > a.days:
            skip('too_old'); continue
        keys = posting_keys(url)
        rk = role_key(company, role)
        if keys & tracked_set or (rk and rk in tracked_roles):
            skip('already_tracked'); continue
        if keys & queued_keys or (rk and rk in queued_roles):
            skip('already_in_jobs_txt'); continue
        if keys & seen or (rk and rk in seen):
            skip('duplicate'); continue
        seen |= keys | ({rk} if rk else set())
        kept.append({'company': company, 'role': role, 'location': '; '.join(locs), 'url': url,
                     'posted': posted.isoformat() if posted else '', 'sponsorship': sponsorship,
                     'category': x.get('category') or '', 'terms': x.get('terms') or []})
    kept.sort(key=lambda r: r['posted'], reverse=True)
    return kept, skipped


# ---- tidy ------------------------------------------------------------------------------------------------------

def _move_lines(path, reasons):
    """Move the waiting lines {line index: reason} to just below "# done" with the reason added to the note.
    (Done by line, so the first of two identical links stays where it is.)"""
    q = queue.read_queue(path)
    by_line = {e['line']: e for e in q['waiting']}
    kept = [l for i, l in enumerate(q['lines']) if i not in reasons]
    at = next((i for i, l in enumerate(kept) if l.strip().lower() == queue.DONE), None)
    if at is None:
        kept += ['', queue.DONE]
        at = len(kept) - 1
    new = []
    for i in sorted(reasons):
        e = by_line[i]
        new.append(f"{e['url']}  # {(e['note'] + ' | ') if e['note'] else ''}{reasons[i]}")
    kept[at + 1:at + 1] = new
    tmp = path + f'.{os.getpid()}.part'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write('\n'.join(kept).rstrip('\n') + '\n')
    os.replace(tmp, path)


def tidy(folder, profile):
    path = os.path.join(folder, 'jobs.txt')
    q = queue.read_queue(path)
    if not q['waiting']:
        return {'ok': True, 'jobs_txt': path, 'waiting': 0, 'moved': [], 'still_waiting': 0}
    tracked, tracked_roles = tracker_keys(folder)
    us_only = us_profile(profile)
    done_keys = set()
    for e in q['done']:
        if 'listed twice' not in e['note']:  # a copy moved there by an earlier tidy; its original still waits
            done_keys |= posting_keys(e['url'])
    seen_keys, seen_roles, reasons, moved = set(), set(), {}, []
    for e in q['waiting']:
        keys = posting_keys(e['url'])
        f = _note_fields(e['note'])
        rk = role_key(f[0], f[1]) if len(f) >= 2 else None
        why = None
        hit = next((tracked[k] for k in keys if k in tracked), None)
        if hit is None and rk and rk in tracked_roles:
            hit = tracked_roles[rk]
        if hit is not None:
            why = f'already in tracker ({hit})' if hit else 'already in tracker'
        elif keys & seen_keys or (rk and rk in seen_roles):
            why = 'listed twice'
        elif keys & done_keys:
            why = 'listed twice (already below # done)'
        elif us_only and len(f) >= 3 and f[2]:
            places = [p.strip() for p in f[2].split(';') if p.strip()]
            if places and not any(is_us_location(p) for p in places):
                why = f'outside the US ({f[2]})'
        seen_keys |= keys
        if rk:
            seen_roles.add(rk)
        if why:
            reasons[e['line']] = why
            moved.append({'url': e['url'], 'reason': why})
    if reasons:
        _move_lines(path, reasons)
    return {'ok': True, 'jobs_txt': path, 'waiting': len(q['waiting']), 'moved': moved,
            'still_waiting': len(q['waiting']) - len(moved)}


# ---- command line ----------------------------------------------------------------------------------------------

def main(argv=None):
    p = argparse.ArgumentParser(description='Find internships in the SimplifyJobs list, or tidy jobs.txt.')
    p.add_argument('--folder', required=True, help='the job-search folder (profile.json, tracker.xlsx, jobs.txt)')
    p.add_argument('--tidy', action='store_true', help='tidy jobs.txt instead of searching (no download)')
    p.add_argument('--term')
    p.add_argument('--category', action='append')
    p.add_argument('--location', action='append')
    p.add_argument('--keyword', action='append')
    p.add_argument('--exclude-keyword', action='append')
    p.add_argument('--degree')
    p.add_argument('--needs-sponsorship', dest='needs_sponsorship', action='store_true', default=None)
    p.add_argument('--no-needs-sponsorship', dest='needs_sponsorship', action='store_false')
    p.add_argument('--no-citizenship', action='store_true')
    p.add_argument('--days', type=int)
    p.add_argument('--limit', type=int, default=25)
    p.add_argument('--include-abroad', action='store_true')
    p.add_argument('--append', action='store_true', help='add the results to jobs.txt')
    p.add_argument('--refresh', action='store_true', help='download again even if the cached copy is recent')
    p.add_argument('--source', help=argparse.SUPPRESS)  # a local listings.json (tests)
    p.add_argument('--today', help=argparse.SUPPRESS)   # YYYY-MM-DD (tests)
    a = p.parse_args(argv)

    folder = os.path.abspath(os.path.expanduser(a.folder))
    if not os.path.isdir(folder):
        cli.fail(f'Folder not found: {folder}')
    if a.limit < 0:
        cli.fail('--limit must be 0 or more')
    if a.degree and not degree_level(a.degree):
        cli.fail(f'Unknown degree "{a.degree}". Use bachelor, master, phd, associate or mba.')
    profile = cli.load_json(os.path.join(folder, 'profile.json'), {}) or {}
    if not isinstance(profile, dict):
        profile = {}

    if a.tidy:
        cli.emit(tidy(folder, profile))

    today = None
    if a.today:
        try:
            today = dt.date.fromisoformat(a.today)
        except ValueError:
            cli.fail(f'--today must be YYYY-MM-DD, got {a.today}')
    try:
        listings, note = load_listings(a.source, a.refresh)
    except OSError as e:
        cli.fail(str(e), cli.NETWORK)
    except ValueError as e:
        cli.fail(f'The internship list could not be read: {e}')
    if not isinstance(listings, list):
        cli.fail('The internship list is not in the expected format (a JSON list).')
    tracked, tracked_roles = tracker_keys(folder)
    _, queued_keys = queued(os.path.join(folder, 'jobs.txt'))
    kept, skipped = search(listings, a, profile, tracked, tracked_roles, queued_keys, today,
                           queued_role_keys(os.path.join(folder, 'jobs.txt')))
    results = kept[:a.limit]
    appended = []
    if a.append and results:
        entries = []
        for r in results:
            parts = [r['company'], r['role'], r['location'] or 'location not stated',
                     f"posted {r['posted'] or 'unknown'}"]
            entries.append((r['url'], ' | '.join(s.replace('|', '/').replace('#', '') for s in parts)))
        appended = queue.append_links(os.path.join(folder, 'jobs.txt'), entries)
    term = a.term or (profile.get('internshipTerm') or '').strip() or DEFAULT_TERM
    cli.emit({'ok': True, 'source': note, 'term': term, 'found': len(listings), 'kept': len(kept),
              'skipped': skipped, 'results': results, 'appended': appended})


if __name__ == '__main__':
    main()
