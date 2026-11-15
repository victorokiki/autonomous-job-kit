#!/usr/bin/env python3
"""Write short, polite email drafts about an application. It never sends anything: the user copies and sends them.

Usage:
  python email_drafts.py --folder JOB_SEARCH_FOLDER --id A0007 --kind followup|thankyou|accept|decline|withdraw
         [--to EMAIL] [--interviewer NAME] [--note TEXT]
  python email_drafts.py --folder JOB_SEARCH_FOLDER --due [--days 10]

The draft is built from the tracker row (company, role, dates, interview stage), profile.json (name, email, phone)
and the application's folder (application-record.md for the date applied, job-posting.md for the role title). It is
written to <application folder>/email-<kind>-YYYY-MM-DD.md with To (when known), Subject and Body. When the row has no
application folder, the draft goes to <JOB_SEARCH_FOLDER>/emails/ instead. An older draft with the same name is
moved into _old/, never deleted.

Kinds:
  followup  a check-in after silence (normally 10+ days after the status became Submitted)
  thankyou  within a day of an interview; names the interviewer and stage when known and leaves a
            <one thing you discussed> slot for the user to fill
  accept    accept an offer          decline   turn down an offer politely
  withdraw  withdraw an application politely

--due lists Submitted rows with no news for --days days (default 10) and Interviewing rows whose interview date is
today or yesterday, each with the suggested kind. It writes nothing.

Output: one JSON object: {ok, drafts: [{id, kind, path, subject, to, slots}], warnings: []} or {ok, due: [...]}.
Exit codes: 0 ok, 1 bad input (no tracker, unknown ID, bad arguments), 5 openpyxl missing.
"""
import argparse
import datetime as dt
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(HERE, '..', '..', 'lib')):
    if os.path.isdir(os.path.join(_p, 'jobkit')):
        sys.path.insert(0, os.path.abspath(_p))
        break
from jobkit import cli, files, text  # noqa: E402

try:
    from jobkit import tracker as _tracker
except Exception:  # pragma: no cover - the tracker module is optional; a small reader below takes over
    _tracker = None

KINDS = ('followup', 'thankyou', 'accept', 'decline', 'withdraw')
FOLLOWUP_DAYS = 10

# Column order of tracker.xlsx (used only when jobkit.tracker is not available)
_COLUMNS = [
    ('id', 'ID'), ('date_added', 'Date added'), ('company', 'Company'), ('role', 'Role'), ('term', 'Term'),
    ('location', 'Location'), ('deadline', 'Deadline'), ('status', 'Status'), ('status_updated', 'Status updated'),
    ('next_step', 'Next step'), ('interview_date', 'Interview date'), ('posting_url', 'Posting'),
    ('folder', 'Folder'), ('resume', 'Resume file'), ('gaps', 'Gaps'), ('notes', 'Notes'),
    ('interview_stage', 'Interview stage'), ('last_checked', 'Last checked'),
]


# ---- reading the tracker ------------------------------------------------------------------------------------------

def as_date(v):
    if _tracker is not None:
        return _tracker.as_date(v)
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    m = re.match(r'\s*(\d{4})-(\d{1,2})-(\d{1,2})', str(v or ''))
    if not m:
        return None
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def read_rows(path):
    """Tracker rows as dicts (link columns hold their targets)."""
    if _tracker is not None:
        _, ws, _ = _tracker.open_book(path)
        return [_tracker.read_links(ws, r) for r in _tracker.rows(ws)]
    openpyxl = cli.need_package('openpyxl')
    wb = openpyxl.load_workbook(path)
    ws = wb['Applications'] if 'Applications' in wb.sheetnames else wb.worksheets[0]
    by_header = {text.norm(h): k for k, h in _COLUMNS}
    cols = {}
    for c in ws[1]:
        k = by_header.get(text.norm(c.value))
        if k and k not in cols:
            cols[k] = c.column
    out = []
    for r in range(2, ws.max_row + 1):
        rec = {}
        for k, _ in _COLUMNS:
            cell = ws.cell(row=r, column=cols[k]) if k in cols else None
            v = cell.value if cell is not None else None
            if cell is not None and k in ('posting_url', 'folder') and cell.hyperlink is not None and cell.hyperlink.target:
                v = cell.hyperlink.target
            elif k in ('posting_url', 'folder') and str(v or '').strip() in ('Open posting', 'Open folder'):
                v = ''
            rec[k] = '' if v is None else (v.strip() if isinstance(v, str) else v)
        if any(rec[k] not in ('', None) for k, _ in _COLUMNS):
            out.append(rec)
    return out


def canonical(status):
    s = str(status or '').strip()
    if _tracker is not None:
        return _tracker.canonical_status(s) or s
    return s


# ---- the application folder ---------------------------------------------------------------------------------------

def job_folder(folder, row):
    """The application's folder: the tracker's Folder link, else Applications/* named "... Company - Role"."""
    link = str(row.get('folder') or '').strip()
    if link:
        link = re.sub(r'^file://', '', link)
        try:
            from urllib.parse import unquote
            link = unquote(link)
        except ImportError:  # pragma: no cover
            pass
        path = link if os.path.isabs(link) else os.path.join(folder, link)
        if os.path.isdir(path):
            return os.path.abspath(path)
    want_c, want_r = text.name_key(row.get('company')), text.norm(row.get('role'))
    best = None
    for d in sorted(glob.glob(os.path.join(folder, 'Applications', '*'))):
        if not os.path.isdir(d):
            continue
        name = re.sub(r'^\d{4}-\d{2}-\d{2}\s+', '', os.path.basename(d))
        comp, _, role = name.partition(' - ')
        if want_c and text.name_key(comp) == want_c:
            if want_r and text.norm(role) == want_r:
                return os.path.abspath(d)
            if best is None and want_r and (want_r in text.norm(role) or text.norm(role) in want_r):
                best = os.path.abspath(d)
    return best


def _read(path):
    try:
        with open(path, encoding='utf-8-sig', errors='replace') as f:
            return f.read()
    except OSError:
        return ''


_DATE_WORDS = r'(?:date applied|applied on|applied|submitted on|submitted|date submitted|application date)'


def applied_date(job_dir, row):
    """The date applied: application-record.md when it says, else the tracker (Status updated for a Submitted row,
    else Date added). Returns (date or None, source)."""
    if job_dir:
        rec = _read(os.path.join(job_dir, 'application-record.md'))
        m = re.search(_DATE_WORDS + r'[^\n:]{0,20}:\s*\**\s*(\d{4}-\d{2}-\d{2})', rec, re.I)
        if m:
            return as_date(m.group(1)), 'application-record.md'
    if canonical(row.get('status')) == 'Submitted' and as_date(row.get('status_updated')):
        return as_date(row.get('status_updated')), 'tracker status_updated'
    d = as_date(row.get('date_added'))
    return d, ('tracker date_added' if d else None)


def posting_role(job_dir):
    if not job_dir:
        return ''
    src = _read(os.path.join(job_dir, 'job-posting.md'))
    m = re.search(r'^-\s*Role:\s*(.+)$', src, re.M)
    return m.group(1).strip() if m else ''


# ---- writing the drafts -------------------------------------------------------------------------------------------

def nice_date(d):
    return f'{d.strftime("%B")} {d.day}, {d.year}' if d else ''


def full_name(profile):
    name = (profile.get('resumeName') or '').strip()
    if not name:
        first = (profile.get('preferredName') or profile.get('firstName') or '').strip()
        name = ' '.join(x for x in (first, (profile.get('lastName') or '').strip()) if x)
    return re.sub(r'\s+', ' ', name) or '<your name>'


def signature(profile):
    contact = ' | '.join(x for x in ((profile.get('email') or '').strip(), (profile.get('phone') or '').strip()) if x)
    return full_name(profile) + ('\n' + contact if contact else '')


def greeting(name):
    return f'Dear {name.strip()},' if name and name.strip() else 'Dear Hiring Team,'


def compose(kind, row, profile, role, applied, interviewer='', note='', today=None):
    """-> (subject, body, slots[])."""
    today = today or dt.date.today()
    company = str(row.get('company') or '').strip() or '<company>'
    role = role or str(row.get('role') or '').strip() or '<role>'
    stage = str(row.get('interview_stage') or '').strip()
    interview = as_date(row.get('interview_date'))
    slots = []
    paras = [greeting(interviewer)]

    if kind == 'followup':
        subject = f'Following up on my application: {role}'
        when = f' on {nice_date(applied)}' if applied else ''
        paras.append(f'I applied for the {role} position at {company}{when} and wanted to follow up on my '
                     f'application. I am still very interested in the role and would be glad to send anything else '
                     f'that would help with your review.')
        paras.append('Could you let me know where things stand, or whether there is a better person to ask?')
    elif kind == 'thankyou':
        subject = f'Thank you: {role} interview'
        if interview == today or interview is None:
            when = 'today'
        elif interview == today - dt.timedelta(days=1):
            when = 'yesterday'
        else:
            when = f'on {nice_date(interview)}'
        stage_part = f' for the {stage}' if stage else ''
        paras.append(f'Thank you for taking the time to speak with me {when}{stage_part} about the {role} position at '
                     f'{company}.')
        paras.append('I especially enjoyed our conversation about <one thing you discussed>, and it made me even more '
                     'interested in joining the team.')
        paras.append('Please let me know if there is anything else I can share. I look forward to hearing about the '
                     'next steps.')
        slots.append('<one thing you discussed>')
    elif kind == 'accept':
        subject = f'Offer acceptance: {role}'
        paras.append(f'Thank you for offering me the {role} position at {company}. I am delighted to accept the '
                     f'offer as described in your letter.')
        paras.append('Please let me know the next steps, including any forms or documents you need from me before '
                     'my first day. I look forward to joining the team.')
    elif kind == 'decline':
        subject = f'{role} offer'
        paras.append(f'Thank you very much for offering me the {role} position at {company}, and for the time you '
                     f'and the team spent with me during the process.')
        paras.append('After careful thought, I have decided to decline the offer. This was not an easy decision, and '
                     f'I have a great deal of respect for {company}.')
        paras.append('I hope our paths cross again, and I wish you and the team all the best.')
    elif kind == 'withdraw':
        subject = f'Withdrawing my application: {role}'
        paras.append(f'I am writing to withdraw my application for the {role} position at {company}.')
        paras.append('Thank you for your time and consideration. I appreciate the opportunity to have been part of '
                     'your process and hope to stay in touch.')
    else:  # guarded by argparse
        raise ValueError(kind)

    if note and note.strip():
        paras.insert(len(paras) - (0 if kind in ('decline', 'withdraw') else 1), note.strip())
    closing = 'Thank you,' if kind == 'followup' else 'Best regards,'
    body = '\n\n'.join(paras) + f'\n\n{closing}\n{signature(profile)}\n'
    return subject, body, slots


def draft_text(kind, to, subject, body, company):
    label = {'followup': 'Follow-up', 'thankyou': 'Thank-you note', 'accept': 'Offer acceptance',
             'decline': 'Offer decline', 'withdraw': 'Withdrawal'}[kind]
    lines = [f'# {label} to {company} (draft)', '',
             '_Draft only: nothing has been sent. Read it, fill any <...> slot, then send it from your own email._', '']
    if to:
        lines.append(f'To: {to}')
    lines.append(f'Subject: {subject}')
    lines += ['', body]
    return '\n'.join(lines)


def kind_warnings(kind, row, today):
    status = canonical(row.get('status'))
    out = []
    since = as_date(row.get('status_updated')) or as_date(row.get('date_added'))
    if kind == 'followup':
        if status != 'Submitted':
            out.append(f'This application is "{status or "no status"}", not Submitted: check a follow-up still fits')
        elif since and (today - since).days < FOLLOWUP_DAYS:
            out.append(f'Only {(today - since).days} days since the status changed; a follow-up usually waits '
                       f'{FOLLOWUP_DAYS} or more')
    elif kind == 'thankyou':
        interview = as_date(row.get('interview_date'))
        if status != 'Interviewing':
            out.append(f'This application is "{status or "no status"}", not Interviewing')
        if interview and (today - interview).days > 1:
            out.append(f'The interview was {(today - interview).days} days ago: send the thank-you soon')
        if interview and interview > today:
            out.append('The interview date is in the future: send this after the interview')
    elif kind in ('accept', 'decline') and status != 'Offer':
        out.append(f'This application is "{status or "no status"}", not Offer: check before replying to an offer')
    elif kind == 'withdraw' and status in ('Accepted', 'Declined', 'Rejected', 'Withdrawn', 'Skipped'):
        out.append(f'This application is already "{status}"')
    return out


def due(rows, days, today):
    out = []
    for r in rows:
        status = canonical(r.get('status'))
        base = {'id': r.get('id'), 'company': r.get('company'), 'role': r.get('role'), 'status': status}
        if status == 'Submitted':
            since = as_date(r.get('status_updated')) or as_date(r.get('date_added'))
            if since and (today - since).days >= days:
                n = (today - since).days
                out.append(dict(base, kind='followup', days=n, why=f'no news for {n} days since it was submitted'))
        elif status == 'Interviewing':
            interview = as_date(r.get('interview_date'))
            if interview and 0 <= (today - interview).days <= 1:
                when = 'today' if interview == today else 'yesterday'
                stage = str(r.get('interview_stage') or '').strip()
                out.append(dict(base, kind='thankyou', interview_date=interview.isoformat(),
                                why=f'interview {when}' + (f' ({stage})' if stage else '')))
    return out


def main():
    ap = argparse.ArgumentParser(description='Draft follow-up, thank-you and offer emails (never sends).')
    ap.add_argument('--folder', required=True, help='the job-search folder (holds tracker.xlsx and profile.json)')
    ap.add_argument('--id')
    ap.add_argument('--kind', choices=KINDS)
    ap.add_argument('--to', default='')
    ap.add_argument('--interviewer', default='')
    ap.add_argument('--note', default='')
    ap.add_argument('--due', action='store_true')
    ap.add_argument('--days', type=int, default=FOLLOWUP_DAYS)
    a = ap.parse_args()

    folder = os.path.abspath(a.folder)
    if not os.path.isdir(folder):
        cli.fail(f'Folder not found: {a.folder}')
    tracker_path = os.path.join(folder, 'tracker.xlsx')
    if not os.path.isfile(tracker_path):
        cli.fail(f'No tracker.xlsx in {folder}')
    if not a.due and not (a.id and a.kind):
        cli.fail('Give --id and --kind, or --due')
    if a.days < 0:
        cli.fail('--days must be 0 or more')
    try:
        rows = read_rows(tracker_path)
    except Exception as e:
        cli.fail(f'Could not read the tracker: {e}')
    today = dt.date.today()

    if a.due:
        cli.emit({'ok': True, 'days': a.days, 'due': due(rows, a.days, today)})

    match = [r for r in rows if str(r.get('id') or '').strip().upper() == a.id.strip().upper()]
    if not match:
        cli.fail(f'No application with ID {a.id} in the tracker')
    row = match[0]
    profile = cli.load_json(os.path.join(folder, 'profile.json'), {}) or {}
    if not isinstance(profile, dict):
        profile = {}

    job_dir = job_folder(folder, row)
    applied, applied_source = applied_date(job_dir, row)
    role = posting_role(job_dir) or str(row.get('role') or '').strip()
    subject, body, slots = compose(a.kind, row, profile, role, applied, a.interviewer, a.note, today)
    company = str(row.get('company') or '').strip() or 'the employer'
    to = a.to.strip()

    warnings = kind_warnings(a.kind, row, today)
    out_dir = job_dir or os.path.join(folder, 'emails')
    if not job_dir:
        warnings.append('No application folder found for this row: the draft went to the emails/ folder')
    name = f'email-{a.kind}-{today.isoformat()}.md'
    if not job_dir:
        name = f'email-{a.kind}-{today.isoformat()} {files.safe_name(company)}.md'
    path = os.path.join(out_dir, name)
    moved = files.write_text(path, draft_text(a.kind, to, subject, body, company))

    draft = {'id': row.get('id'), 'kind': a.kind, 'path': path, 'subject': subject, 'to': to or None,
             'slots': slots, 'applied': applied.isoformat() if applied else None, 'applied_source': applied_source}
    if moved:
        draft['previous_version_moved_to'] = moved
    cli.emit({'ok': True, 'drafts': [draft], 'warnings': warnings, 'sent': False})


if __name__ == '__main__':
    main()
