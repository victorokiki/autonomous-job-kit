#!/usr/bin/env python3
"""Fetch job postings from application systems' public job data and save each as a job-posting.md file.

Usage
  fetch_posting.py URL [URL ...] --out-dir DIR [--tracker tracker.xlsx] [--profile profile.json]
  fetch_posting.py --jobs jobs.txt [--limit N] --out-dir DIR [--tracker ...] [--profile ... [--move-skips]]
  fetch_posting.py --text FILE --url URL --out-dir DIR [--company NAME] [--role TITLE] [...]

What it does
  Reads each posting without a browser (Greenhouse, Lever, Ashby, Workday, SmartRecruiters, iCIMS, Oracle Recruiting
  Cloud, Rippling, Canada's Job Bank, or any page with schema.org JobPosting data) and writes DIR/NN Company - Role.md
  in the job-posting.md format: details, the description as plain text, and the published application questions.
  An existing file with the same name is moved to DIR/_old/ first.
  --profile   screens each posting against your work authorization and degree (ok / check / skip, with the sentences).
              Without --profile, restrictive sentences are still listed, as "check" (never "skip").
  --tracker   lists tracker rows for the same company and says whether this exact posting is already there.
  --jobs      reads the waiting links in jobs.txt (above "# done"); --limit N takes the first N (default 10).
  --move-skips  (with --jobs and --profile) moves links screened "skip" below "# done" with "skipped: <reason>".
  --text      uses a description you pasted into FILE (plain text or HTML) instead of downloading.
  LinkedIn links are never fetched: you get a hint to paste the description or find the company's own posting.

Output: one JSON object
  {"ok", "postings": [{url, file, company, role, location, deadline, pay, posted, system, cover_letter,
   cover_letter_quote, questions, written, screen, screen_why, check, red_flags, in_tracker, same_posting_in_tracker,
   check_company, error, hint}], "moved_below_done", "network_blocked", "hint"?}
Exit codes: 0 every posting read, 2 some need the browser (see "error" / "hint"), 1 bad input.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(HERE, '..', '..', 'lib')):
    if os.path.isdir(os.path.join(_p, 'jobkit')):
        sys.path.insert(0, os.path.abspath(_p))
        break
from jobkit import cli, files, text, queue  # noqa: E402
from jobkit import postings, eligibility, redflags  # noqa: E402

TRACKER_COLUMNS = ['id', 'date_added', 'company', 'role', 'term', 'location', 'deadline', 'status', 'status_updated',
                   'next_step', 'interview_date', 'posting_url', 'folder', 'resume', 'gaps', 'notes', 'interview_stage',
                   'last_checked']
TRACKER_HEADERS = ['ID', 'Date added', 'Company', 'Role', 'Term', 'Location', 'Deadline', 'Status', 'Status updated',
                   'Next step', 'Interview date', 'Posting', 'Folder', 'Resume file', 'Gaps', 'Notes', 'Interview stage',
                   'Last checked']


def _rows_with_openpyxl(path):
    openpyxl = cli.need_package('openpyxl')
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb['Applications'] if 'Applications' in wb.sheetnames else wb.worksheets[0]
    head = [str(c.value or '').strip().lower() for c in ws[1]]
    index = {}
    for i, key in enumerate(TRACKER_COLUMNS):
        label = TRACKER_HEADERS[i].lower()
        if label in head:
            index[key] = head.index(label)
        elif key in head:
            index[key] = head.index(key)
    out = []
    for r in ws.iter_rows(min_row=2):
        row = {}
        for key, i in index.items():
            if i < len(r):
                cell = r[i]
                link = cell.hyperlink.target if cell.hyperlink is not None and cell.hyperlink.target else None
                row[key] = link if key in ('posting_url', 'folder') and link else cell.value
        if any(v not in (None, '') for v in row.values()):
            out.append(row)
    wb.close()
    return out


def tracker_rows(path):
    """Rows of tracker.xlsx as dicts (posting_url = the link target). Uses jobkit.tracker when present."""
    try:
        from jobkit import tracker as tk
    except ImportError:
        return _rows_with_openpyxl(path)
    try:
        wb, ws, _ = tk.open_book(path)
        out = []
        for row in tk.rows(ws):
            try:
                row = tk.read_links(ws, row) or row
            except Exception:
                pass
            out.append(row)
        return out
    except SystemExit:
        raise
    except Exception:
        return _rows_with_openpyxl(path)


def tracker_matches(rows, company, url):
    keys = queue.posting_keys(url)
    ck = text.name_key(company)
    same_company, same_posting = [], False
    for r in rows:
        if keys and keys & queue.posting_keys(str(r.get('posting_url') or '')):
            same_posting = True
        if ck and text.name_key(r.get('company')) == ck:
            same_company.append({k: (str(r.get(k)) if r.get(k) is not None else '')
                                 for k in ('id', 'company', 'role', 'status', 'date_added')})
    return same_company, same_posting


def process(p, n, args, profile, rows):
    """Screen, flag and write one posting; returns its JSON entry."""
    entry = {'url': p['url'], 'file': None, 'company': p.get('company', ''), 'role': p.get('role', ''),
             'location': p.get('location', ''), 'deadline': p.get('deadline', ''), 'pay': p.get('pay', ''),
             'posted': p.get('posted', ''), 'system': p.get('system', 'other'), 'cover_letter': 'unknown',
             'cover_letter_quote': '', 'questions': 0, 'written': [], 'screen': 'ok', 'screen_why': [], 'check': [],
             'red_flags': [], 'in_tracker': [], 'same_posting_in_tracker': False,
             'check_company': bool(p.get('check_company')), 'error': p.get('error', ''), 'hint': p.get('hint', '')}
    if rows is not None:
        entry['in_tracker'], entry['same_posting_in_tracker'] = tracker_matches(rows, p.get('company'), p['url'])
    if p.get('error'):
        return entry
    cl = postings.cover_letter(p)
    entry['cover_letter'], entry['cover_letter_quote'] = cl
    entry['questions'] = len(p['questions'])
    entry['written'] = postings.written_questions(p['questions'])
    result = eligibility.screen(p.get('description', ''), profile, p.get('role', ''), p.get('location', ''))
    if profile is None and result['screen'] == 'skip':
        result['screen'] = 'check'
    entry['screen'], entry['screen_why'], entry['check'] = result['screen'], result['why'], result['check']
    entry['_skip_reason'] = eligibility.short_reason(result)
    entry['red_flags'] = redflags.red_flags(p.get('description', ''), url=p['url'], company=p.get('company'),
                                            role=p.get('role'), system=p.get('system'))
    name = files.safe_name(f"{n:02d} {p.get('company') or 'Unknown'} - {p.get('role') or 'Unknown role'}", 110) + '.md'
    path = os.path.join(args.out_dir, name)
    files.write_text(path, postings.render_markdown(p, entry['screen'], entry['screen_why'], entry['red_flags'], cl))
    entry['file'] = path
    return entry


def main():
    ap = argparse.ArgumentParser(description='Fetch job postings into job-posting.md files (prints one JSON object).')
    ap.add_argument('urls', nargs='*', help='posting links')
    ap.add_argument('--out-dir', required=True, help='folder for the .md files')
    ap.add_argument('--jobs', help='jobs.txt queue: read its waiting links')
    ap.add_argument('--limit', type=int, default=10, help='with --jobs: how many waiting links (default 10)')
    ap.add_argument('--text', help='a file holding a pasted description (use with --url)')
    ap.add_argument('--url', help='the posting link for --text')
    ap.add_argument('--company', help='with --text: company name, when the text does not make it clear')
    ap.add_argument('--role', help='with --text: job title, when the text does not make it clear')
    ap.add_argument('--tracker', help='tracker.xlsx: list rows for the same company')
    ap.add_argument('--profile', help='profile.json: screen each posting against your status')
    ap.add_argument('--move-skips', action='store_true', help='with --jobs and --profile: move skipped links below "# done"')
    ap.add_argument('--delay', type=float, default=1.0, help=argparse.SUPPRESS)
    args = ap.parse_args()

    if args.text and not args.url:
        cli.fail('--text needs --url (the link the description came from).')
    if args.move_skips and not (args.jobs and args.profile):
        cli.fail('--move-skips works only together with --jobs and --profile.')
    cli.need_files(args.text, args.tracker, args.profile, args.jobs)
    profile = None
    if args.profile:
        profile = cli.load_json(args.profile)
        if not isinstance(profile, dict):
            cli.fail(f'{args.profile} is not a valid profile.json (expected a JSON object).')

    links = list(args.urls)
    if args.jobs:
        links += [e['url'] for e in queue.read_queue(args.jobs)['waiting'][:max(0, args.limit)]]
    if not links and not args.text:
        cli.fail('Give at least one posting link, --jobs jobs.txt (with waiting links), or --text FILE --url URL.')
    for u in links + ([args.url] if args.url else []):
        if not u.lower().startswith(('http://', 'https://')):
            cli.fail(f'Not a web link: {u}')

    rows = None
    if args.tracker:
        try:
            rows = tracker_rows(args.tracker)
        except SystemExit:
            raise
        except Exception as e:
            cli.fail(f'Could not read the tracker {args.tracker}: {e}')

    os.makedirs(args.out_dir, exist_ok=True)
    fetcher = postings.Fetcher(delay=args.delay)
    out, n = [], 0
    if args.text:
        n += 1
        p = postings.finish(postings.from_text(text.read_text(args.text), args.url, args.company or '', args.role or ''))
        out.append(process(p, n, args, profile, rows))
    for u in links:
        n += 1
        out.append(process(postings.fetch(u, fetcher), n, args, profile, rows))

    moved = []
    if args.move_skips:
        reasons = {e['url']: f"skipped: {e.get('_skip_reason') or 'not eligible'}" for e in out if e['screen'] == 'skip'}
        if reasons:
            moved = queue.move_below_done(args.jobs, reasons)
    for e in out:
        e.pop('_skip_reason', None)

    network_blocked = fetcher.requests > 0 and fetcher.answered == 0 and fetcher.network_errors > 0
    result = {'ok': not any(e['error'] for e in out), 'postings': out, 'moved_below_done': moved,
              'network_blocked': network_blocked}
    if network_blocked:
        result['hint'] = ('No job site could be reached (offline, or this environment blocks network access). '
                          'Open the postings in the browser, or paste a description and use --text FILE --url URL.')
    cli.emit(result, cli.OK if result['ok'] else cli.ATTENTION)


if __name__ == '__main__':
    main()
