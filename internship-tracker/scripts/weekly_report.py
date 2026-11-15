"""Write a plain-English weekly report of the job search: reports/YYYY-Www.md in the job-search folder.

Usage:
  python weekly_report.py --folder "JOB_SEARCH_FOLDER" [--week YYYY-MM-DD]

--week is any date in the week to report on (weeks run Monday to Sunday; default: this week). An earlier report for
the same week is moved into reports/_old/ first, never deleted.

The report covers: applications sent that week (by "Date added" of rows with a sent status), status changes that
week, interviews in the next 14 days, the response rate so far (assessments, interviews, offers and rejections out
of all applications sent), applications due for a status check (tracker.py checkin rules), to-dos (Ready to submit
and Needs you rows), the week's best new matches from the latest .cache/candidates-*.json (written by find_jobs.py),
progress against profile.json "weeklyGoal" when it is set, and three plain suggestions.

Prints one JSON object: ok, path, week, start, end, and the counts behind each section. Exit code 0 (1 for a bad
folder or date, 5 when openpyxl is missing and a tracker exists).
"""
import argparse
import datetime as dt
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(HERE, '..', '..', 'lib')):
    if os.path.isdir(os.path.join(_p, 'jobkit')):
        sys.path.insert(0, os.path.abspath(_p))
        break
from jobkit import cli, files, text, queue  # noqa: E402,F401
from jobkit.queue import posting_keys, role_key  # noqa: E402

SENT = {'Submitted', 'Online assessment', 'Interviewing', 'Offer', 'Accepted', 'Declined', 'Rejected', 'Withdrawn'}
REPLIED = {'Online assessment', 'Interviewing', 'Offer', 'Accepted', 'Declined', 'Rejected'}


def as_date(v):
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    try:
        return dt.date.fromisoformat(str(v or '').strip()[:10])
    except ValueError:
        return None


def load_rows(folder):
    """Tracker rows as plain dicts (dates as YYYY-MM-DD text, links resolved). [] when there is no tracker."""
    path = os.path.join(folder, 'tracker.xlsx')
    if not os.path.exists(path):
        return []
    from jobkit import tracker
    try:
        _, ws, _ = tracker.open_book(path)
    except ValueError as e:
        cli.fail(str(e))
    out = []
    for r in tracker.rows(ws):
        r = tracker.read_links(ws, r)
        out.append({k: (v.isoformat()[:10] if isinstance(v, (dt.date, dt.datetime)) else ('' if v is None else str(v)))
                    for k, v in r.items() if k != '_row'})
    return out


def latest_matches(folder, rows, start, end, limit=5):
    """Top matches from the newest candidates file (skipping jobs already in the tracker), and the file's name."""
    found = sorted(glob.glob(os.path.join(folder, '.cache', 'candidates-*.json')))
    if not found:
        return [], ''
    path = found[-1]
    data = cli.load_json(path, {}) or {}
    tracked = set()
    for r in rows:
        tracked |= posting_keys(r.get('posting_url'))
        k = role_key(r.get('company'), r.get('role'))
        if k:
            tracked.add(k)
    jobs = []
    for j in data.get('jobs', []) if isinstance(data, dict) else []:
        if not isinstance(j, dict):
            continue
        fit = j.get('fit') if isinstance(j.get('fit'), dict) else {}
        keys = posting_keys(j.get('url')) | ({role_key(j.get('company'), j.get('title'))} - {None})
        if keys & tracked:
            continue
        try:
            score = float(fit.get('score') or 0)
        except (TypeError, ValueError):
            score = 0.0
        jobs.append({'title': j.get('title', ''), 'company': j.get('company', ''), 'location': j.get('location', ''),
                     'url': j.get('url', ''), 'score': fit.get('score', ''), 'why': fit.get('why', ''), '_s': score})
    jobs.sort(key=lambda j: -j['_s'])
    for j in jobs:
        j.pop('_s')
    return jobs[:limit], os.path.basename(path)


def week_bounds(day):
    start = day - dt.timedelta(days=day.weekday())
    return start, start + dt.timedelta(days=6)


def label(r):
    return f"{r.get('company') or '?'}, {r.get('role') or '?'}"


def build(folder, day, today):
    from jobkit import tracker
    rows = load_rows(folder)
    profile = cli.load_json(os.path.join(folder, 'profile.json'), {}) or {}
    if not isinstance(profile, dict):
        profile = {}
    start, end = week_bounds(day)
    ref = min(today, end)  # "now" for this report: today, or the week's last day for a past week
    in_week = lambda v: (d := as_date(v)) is not None and start <= d <= end

    sent_week = [r for r in rows if r.get('status') in SENT and in_week(r.get('date_added'))]
    changes = [r for r in rows if in_week(r.get('status_updated'))
               and as_date(r.get('status_updated')) != as_date(r.get('date_added'))]
    soon = sorted((r for r in rows if (d := as_date(r.get('interview_date'))) and ref <= d <= ref + dt.timedelta(days=14)
                   and r.get('status') not in tracker.FINAL), key=lambda r: as_date(r['interview_date']))
    sent_all = [r for r in rows if r.get('status') in SENT]
    replied = [r for r in sent_all if r.get('status') in REPLIED]
    rate = round(100 * len(replied) / len(sent_all)) if sent_all else None
    due = tracker.due_for_checkin(rows, ref)
    ready = sorted((r for r in rows if r.get('status') == 'Ready to submit'),
                   key=lambda r: as_date(r.get('deadline')) or dt.date.max)
    needs = [r for r in rows if r.get('status') == 'Needs you']
    stale = [r for r in rows if r.get('status') == 'Submitted'
             and (d := as_date(r.get('status_updated')) or as_date(r.get('date_added'))) and (ref - d).days >= 21]
    matches, match_file = latest_matches(folder, rows, start, end)
    goal = profile.get('weeklyGoal')
    try:
        goal = int(goal) if goal not in (None, '') else None
    except (TypeError, ValueError):
        goal = None
    queue_waiting = len(queue.read_queue(os.path.join(folder, 'jobs.txt'))['waiting'])

    # three plain suggestions, most useful first
    tips = []
    if ready:
        r = ready[0]
        dl = as_date(r.get('deadline'))
        tips.append(f"Submit the {len(ready)} application{'s' * (len(ready) != 1)} marked Ready to submit"
                    + (f", starting with {label(r)} (closes {dl.isoformat()})." if dl else f", starting with {label(r)}."))
    if soon:
        r = soon[0]
        tips.append(f"Prepare for the interview with {r.get('company')} on {as_date(r['interview_date']).isoformat()}: "
                    "reread the posting and your tailored resume, and have two stories ready.")
    if needs:
        tips.append(f"Clear {len(needs)} 'Needs you' item{'s' * (len(needs) != 1)}"
                    f" (first: {label(needs[0])}{': ' + needs[0]['next_step'] if needs[0].get('next_step') else ''}).")
    if due:
        tips.append(f"Tell Claude about any news on {len(due)} application{'s' * (len(due) != 1)} waiting for an "
                    "update (tracker.py checkin lists them).")
    if goal and len(sent_week) < goal:
        tips.append(f"Send {goal - len(sent_week)} more application{'s' * (goal - len(sent_week) != 1)} to reach "
                    f"your weekly goal of {goal}.")
    if stale:
        tips.append(f"Send a short follow-up for {len(stale)} application{'s' * (len(stale) != 1)} submitted three "
                    "or more weeks ago with no reply.")
    if matches:
        m = matches[0]
        tips.append(f"Look at the best new match: {m['title']} at {m['company']} (fit {m['score']}).")
    if rate is not None and len(sent_all) >= 10 and rate < 10:
        tips.append('Replies are rare so far: aim at roles that fit your skills more closely and tailor each '
                    'resume to the posting\'s own words.')
    if not queue_waiting:
        tips.append('jobs.txt has nothing waiting: run a search (find_jobs.py or find_internships.py) to refill it.')
    tips += ['Run a fresh job search so next week starts with new matches.',
             'Keep the master resume up to date with anything new you did this week.',
             'Check the tracker for deadlines in the coming week.']
    seen, suggestions = set(), []
    for t in tips:
        if t not in seen:
            seen.add(t)
            suggestions.append(t)
        if len(suggestions) == 3:
            break

    iso = start.isocalendar()
    week_name = f'{iso[0]}-W{iso[1]:02d}'
    L = [f'# Weekly report {week_name} ({start:%b} {start.day} to {end:%b} {end.day}, {end.year})', '']
    if goal:
        L += [f'**Goal:** {len(sent_week)} of {goal} applications sent this week'
              + (' - goal reached.' if len(sent_week) >= goal else '.'), '']
    L += [f'## Applications sent this week ({len(sent_week)})']
    L += [f"- {label(r)} ({r.get('date_added')}) - now {r.get('status')}" for r in sent_week] or ['- None.']
    L += ['', f'## Status changes this week ({len(changes)})']
    L += [f"- {label(r)}: {r.get('status')} on {r.get('status_updated')}"
          + (f" ({r.get('interview_stage')})" if r.get('interview_stage') else '') for r in changes] or ['- None.']
    L += ['', f'## Interviews in the next 14 days ({len(soon)})']
    L += [f"- {r.get('interview_date')}: {label(r)}" + (f" - {r.get('interview_stage')}" if r.get('interview_stage') else '')
          for r in soon] or ['- None scheduled.']
    L += ['', '## Response rate']
    L += [f'- {len(replied)} of {len(sent_all)} applications sent so far got a reply '
          f'(assessment, interview, offer or rejection): {rate}%.' if sent_all else '- No applications sent yet.']
    L += ['', f'## Waiting for news ({len(due)})']
    L += [f"- {d['company']}, {d['role']}: {d['why']}." for d in due] or ['- Nothing due for a check-in.']
    L += ['', f'## To do ({len(ready) + len(needs)})']
    L += [f"- Submit: {label(r)}" + (f" (deadline {r.get('deadline')})" if r.get('deadline') else '') for r in ready]
    L += [f"- Needs you: {label(r)}" + (f" - {r.get('next_step')}" if r.get('next_step') else '') for r in needs]
    if not ready and not needs:
        L += ['- Nothing waiting on you.']
    L += ['', f'## Best new matches ({len(matches)})']
    if matches:
        L += [f"- [{m['title']} at {m['company']}]({m['url']}) - {m['location']} - fit {m['score']}"
              + (f": {m['why']}" if m['why'] else '') for m in matches]
        L += [f'  (from {match_file})']
    else:
        L += ['- No saved search results yet (find_jobs.py writes them).']
    L += ['', '## Suggestions'] + [f'{i}. {t}' for i, t in enumerate(suggestions, 1)] + ['']

    path = os.path.join(folder, 'reports', f'{week_name}.md')
    moved = files.write_text(path, '\n'.join(L))
    out = {'ok': True, 'path': path, 'week': week_name, 'start': start.isoformat(), 'end': end.isoformat(),
           'sent_this_week': len(sent_week), 'status_changes': len(changes), 'interviews_next_14_days': len(soon),
           'response_rate': rate, 'sent_total': len(sent_all), 'replied_total': len(replied),
           'checkins_due': len(due), 'ready_to_submit': len(ready), 'needs_you': len(needs),
           'best_matches': len(matches), 'goal': {'target': goal, 'sent': len(sent_week)} if goal else None,
           'suggestions': suggestions}
    if moved:
        out['previous_report_moved_to'] = moved
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description='Write the weekly job-search report (reports/YYYY-Www.md).')
    p.add_argument('--folder', required=True, help='the job-search folder')
    p.add_argument('--week', help='any date (YYYY-MM-DD) in the week to report on; default this week')
    p.add_argument('--today', help=argparse.SUPPRESS)  # YYYY-MM-DD, for tests
    a = p.parse_args(argv)
    folder = os.path.abspath(os.path.expanduser(a.folder))
    if not os.path.isdir(folder):
        cli.fail(f'Folder not found: {folder}')
    today = as_date(a.today) if a.today else dt.date.today()
    if today is None:
        cli.fail(f'--today must be YYYY-MM-DD, got {a.today}')
    day = as_date(a.week) if a.week else today
    if day is None:
        cli.fail(f'--week must be a date like 2026-11-09, got {a.week}')
    cli.emit(build(folder, day, today))


if __name__ == '__main__':
    main()
