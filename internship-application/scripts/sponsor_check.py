#!/usr/bin/env python3
"""Check employers against the UK Home Office register of licensed sponsors (workers).

Usage:
  python sponsor_check.py --folder "JOB_SEARCH_FOLDER" "Company A" ["Company B" ...] [--refresh]

The register is public (gov.uk, "Register of licensed sponsors: workers") and updated most working days. It's
downloaded once into <folder>/.cache/uk-sponsor-register.csv and refreshed when older than 7 days (or with --refresh).

For each company, prints:
  listed     the name matches a register entry (after dropping Ltd, Limited, PLC, LLP, Group, UK, The ...)
  possible   a register entry starts with the name, or the other way round ("Acme" vs "Acme Software Ltd"): check it
  not found  no match. Big employers often sponsor under a different legal name, so this is a check, never a verdict
with the matching entries' routes (Skilled Worker, Global Business Mobility ...) and ratings.

Being on the register means the employer may sponsor; it doesn't mean this job is eligible or that they will.
Not immigration advice. Exit codes: 0 ok, 1 bad input or the register couldn't be downloaded.
"""
import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.request

PAGE = 'https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers'
USER_AGENT = 'Mozilla/5.0 (compatible; personal job-search script; reads the public sponsor register)'
MAX_AGE = 7 * 24 * 3600
SUFFIX = re.compile(r'\b(the|ltd|limited|plc|llp|lp|llc|inc|incorporated|corp|corporation|company|co|group|holdings|'
                    r'uk|u k|gb|international|services|t a|trading as)\b')


def norm(name):
    s = re.sub(r'[^a-z0-9]+', ' ', str(name or '').lower().replace('&', ' and '))
    return re.sub(r'\s+', ' ', SUFFIX.sub(' ', s)).strip()


def _get(url):
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def register_path(folder, refresh=False):
    """Path to a cached copy of the register, downloading it if missing, stale or refresh is set."""
    cache = os.path.join(folder, '.cache')
    os.makedirs(cache, exist_ok=True)
    path = os.path.join(cache, 'uk-sponsor-register.csv')
    if refresh or not os.path.exists(path) or time.time() - os.path.getmtime(path) > MAX_AGE:
        page = _get(PAGE).decode('utf-8', errors='replace')
        m = re.search(r'https://assets\.publishing\.service\.gov\.uk/[^"\s]+\.csv', page)
        if not m:
            raise RuntimeError('no CSV link on the gov.uk register page (its layout may have changed)')
        data = _get(m.group(0))
        tmp = path + '.part'
        with open(tmp, 'wb') as f:
            f.write(data)
        os.replace(tmp, path)
    return path


def load_register(folder, refresh=False):
    """{normalized name: [{name, town, route, rating}, ...]}"""
    out = {}
    with open(register_path(folder, refresh), newline='', encoding='utf-8-sig', errors='replace') as f:
        for row in csv.DictReader(f):
            name = (row.get('Organisation Name') or '').strip()
            if not name:
                continue
            out.setdefault(norm(name), []).append({'name': name, 'town': (row.get('Town/City') or '').strip(),
                                                   'route': (row.get('Route') or '').strip(),
                                                   'rating': (row.get('Type & Rating') or '').strip()})
    return out


def check(company, register):
    key = norm(company)
    if not key:
        return {'company': company, 'status': 'not found', 'entries': []}
    if key in register:
        return {'company': company, 'status': 'listed', 'entries': register[key][:5]}
    if len(key) >= 4:
        near = [e for k, v in register.items() if k.startswith(key + ' ') or key.startswith(k + ' ') for e in v]
        if near:
            return {'company': company, 'status': 'possible', 'entries': near[:5]}
    return {'company': company, 'status': 'not found', 'entries': []}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--folder', default='.')
    ap.add_argument('--refresh', action='store_true')
    ap.add_argument('companies', nargs='+')
    a = ap.parse_args()
    try:
        reg = load_register(os.path.abspath(a.folder), a.refresh)
    except Exception as e:
        print(json.dumps({'ok': False, 'error': f"Couldn't read the sponsor register: {type(e).__name__}: {str(e)[:150]}",
                          'hint': f'Open {PAGE} in the browser and search the CSV by hand.'}))
        sys.exit(1)
    print(json.dumps({'ok': True, 'source': PAGE, 'results': [check(c, reg) for c in a.companies],
                      'note': 'On the register = may sponsor. It does not make a job eligible. Not immigration advice.'},
                     indent=1))


if __name__ == '__main__':
    main()
