#!/usr/bin/env python3
"""Daily job digest: search every source, rank by fit, write a short report of what's new, and optionally queue the best.

Usage:
  python job_digest.py --folder "JOB_SEARCH_FOLDER" [--queue] [--top 15] [--days 14]

What it does:
  1. Runs the same search as find_jobs.py (all sources, postings from the last --days days).
  2. Marks postings not seen in an earlier digest as new (remembered in .cache/seen.json in the folder).
  3. Writes digests/YYYY-MM-DD.md in the folder: the best new matches with their fit score and why, flags worth a
     look before applying, skill gaps that keep coming up, and any source that failed.
  4. With --queue, adds new matches scoring at least search.json min_score_to_queue to jobs.txt (at most
     max_queue_per_run), exactly as find_jobs.py --append does. Without it, nothing outside digests/ and .cache/ changes.

It never applies, opens a browser or contacts anyone. Prints one JSON object with the counts and the digest path.
"""
import argparse
import collections
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
for _p in (HERE, os.path.join(HERE, '..', '..', 'lib')):
    if os.path.isdir(os.path.join(_p, 'jobkit')):
        sys.path.insert(0, os.path.abspath(_p))
        break
import find_jobs
import rank_jobs
from jobkit.queue import posting_keys


def load_seen(folder):
    try:
        return json.load(open(os.path.join(folder, '.cache', 'seen.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def save_seen(folder, seen):
    d = os.path.join(folder, '.cache')
    os.makedirs(d, exist_ok=True)
    cutoff = (dt.date.today() - dt.timedelta(days=120)).isoformat()
    seen = {k: v for k, v in seen.items() if v >= cutoff}  # forget very old postings so the file stays small
    json.dump(seen, open(os.path.join(d, 'seen.json'), 'w', encoding='utf-8'))


def key(j):
    keys = sorted(posting_keys(j['url']))
    return keys[0] if keys else j['url']


def md_escape(s):
    return str(s or '').replace('|', '/').replace('\n', ' ').strip()


def write_digest(folder, today, new, older_count, report, queued, min_score, top):
    d = os.path.join(folder, 'digests')
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f'{today.isoformat()}.md')
    good = [j for j in new if j['fit']['score'] >= min_score]
    lines = [f'# Job digest, {today:%A %B %-d, %Y}', '',
             f"{len(new)} new postings match your tracks ({len(good)} score {min_score} or more). "
             f"{older_count} matches from earlier digests are still open. "
             f"Searched {report['found']} postings from {len(report['per_source'])} sources."]
    if queued:
        lines += ['', f'Added {len(queued)} to jobs.txt: ' + '; '.join(f"{j['company']} ({j['fit']['score']})" for j in queued) + '.']
    lines += ['', '## Best new matches', '']
    if new:
        lines += ['| Fit | Role | Company | Location | Posted | Why |', '|---|---|---|---|---|---|']
        for j in new[:top]:
            lines.append(f"| {j['fit']['score']} | [{md_escape(j['title'])}]({j['url']}) | {md_escape(j['company'])} | "
                         f"{md_escape(j['location'])[:40]} | {j['posted'] or '?'} | {md_escape(j['fit']['why'])} |")
    else:
        lines.append('Nothing new today.')
    flagged = [j for j in new[:top] if j['fit']['flags']]
    if flagged:
        lines += ['', '## Check before applying', '']
        for j in flagged:
            lines.append(f"- **{md_escape(j['company'])}, {md_escape(j['title'])}**: " +
                         '; '.join(f.split(':')[0] for f in j['fit']['flags']))
    gaps = collections.Counter(g for j in new[:max(top, 30)] for g in j['fit']['gaps'])
    if gaps:
        lines += ['', '## Skills these postings ask for that your resume does not show', '',
                  ', '.join(f'{g} ({n})' for g, n in gaps.most_common(10)) + '.',
                  'These are never added to a resume. If one keeps coming up, a short course or project could close it.']
    if report['errors']:
        lines += ['', '## Sources that failed today', ''] + [f'- {k}: {v}' for k, v in report['errors'].items()]
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--folder', default='.')
    ap.add_argument('--queue', action='store_true', help='add the best new matches to jobs.txt')
    ap.add_argument('--top', type=int, default=15)
    ap.add_argument('--days', type=int, default=14)
    a = ap.parse_args()
    folder = os.path.abspath(a.folder)
    if not os.path.exists(os.path.join(folder, 'search.json')):
        print(json.dumps({'ok': False, 'error': f'no search.json in {folder}'}))
        sys.exit(1)
    search = rank_jobs.load_search(folder)
    today = dt.date.today()
    ranked, report = find_jobs.run(folder, find_jobs.ALL_SOURCES, a.days, today)
    find_jobs.save_cache(folder, ranked, report)
    seen = load_seen(folder)
    new = [j for j in ranked if key(j) not in seen]
    older = len(ranked) - len(new)
    min_score = search.get('min_score_to_queue', 55)
    queued = []
    if a.queue:
        queued = find_jobs.pick_for_queue(new, folder, search, min_score)
        if queued:
            find_jobs.append(folder, queued)
    path = write_digest(folder, today, new, older, report, queued, min_score, a.top)
    for j in ranked:
        seen.setdefault(key(j), today.isoformat())
    save_seen(folder, seen)
    print(json.dumps({'ok': True, 'digest': path, 'new': len(new), 'new_above_min': sum(1 for j in new if j['fit']['score'] >= min_score),
                      'still_open_from_before': older, 'queued': len(queued), 'source_errors': report['errors'],
                      'top': [f"{j['fit']['score']} {j['company']}: {j['title']} ({j['location'][:30]})" for j in new[:5]]}, indent=1))


if __name__ == '__main__':
    main()
