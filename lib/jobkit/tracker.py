"""The application tracker: one Excel workbook (tracker.xlsx), sheet "Applications", one row per application.

Command line (through internship-application/scripts/tracker.py or internship-tracker/scripts/tracker.py):

  tracker.py add     FILE --company "Acme" --role "Software Intern" [--set term="Summer 2027" --set posting_url=...]
  tracker.py update  FILE --id A0003 --status "Interviewing" [--set interview_date=2026-12-01 ...]
  tracker.py find    FILE [--company X] [--role Y] [--status S] [--id A0003] [--set key=substring ...]
  tracker.py summary FILE
  tracker.py checkin FILE [--days N]
  tracker.py checked FILE --id A0003

FILE is the tracker.xlsx (or the job-search folder that holds it). Every command prints one JSON object.

- add: company and role are needed. A row with the same company, role and term (ignoring case, punctuation and
  "Inc.") is never added twice: the existing row comes back with "duplicate": true and exit code 2. New rows get the
  next ID (A0001, A0002, ...), today's date, and the status "Ready to submit" unless one is given.
- update: changes the row with --id (or, without --id, the single row matching --company/--role). Changing the
  status stamps "Status updated" with today's date. A status may carry a reason after a colon ("Needs you: login
  page"); the reason goes into "Next step" when that cell is empty.
- Status words are forgiving: "applied" means Submitted, "oa" means Online assessment, "phone screen" means
  Interviewing, "offer accepted" means Accepted, "not selected" means Rejected, and a unique start of a status name
  ("interv") works too.
- find: rows whose fields contain the given text. summary: counts and short lists. checkin: applications that have
  waited long enough for news (Submitted 7 days, Online assessment 5, Interviewing 5, Offer 3; --days N for every open
  status), each with a ready-made question. checked: records that the user was asked today.

Several copies of this script can run at once (batch runs): each one waits its turn on a lock in the system temp
folder (up to 60 seconds, then exit 6). When Excel has the workbook open the save is refused with exit 4.

Exit codes: 0 ok, 1 bad input, 2 duplicate on add, 4 tracker open in Excel, 5 openpyxl missing, 6 lock timeout.

Library use (dashboard.py, find_jobs.py, find_internships.py, weekly_report.py): STATUSES, FINAL, CHECKIN_DAYS,
canonical_status, as_date, open_book, rows, read_links, due_for_checkin, main.
"""
import argparse
import datetime as dt
import hashlib
import os
import re
import tempfile
import time
import urllib.parse

from . import cli
from .text import name_key, norm

__all__ = ['COLUMNS', 'KEYS', 'HEADERS', 'STATUSES', 'FINAL', 'SENT', 'REPLIED', 'CHECKIN_DAYS', 'ALIASES',
           'SHEET', 'canonical_status', 'split_status', 'as_date', 'open_book', 'rows', 'read_links',
           'due_for_checkin', 'find_rows', 'summary', 'tracker_lock', 'save_book', 'TrackerBusy', 'LockTimeout',
           'main']

SHEET = 'Applications'
COLUMNS = [
    ('id', 'ID'), ('date_added', 'Date added'), ('company', 'Company'), ('role', 'Role'), ('term', 'Term'),
    ('location', 'Location'), ('deadline', 'Deadline'), ('status', 'Status'), ('status_updated', 'Status updated'),
    ('next_step', 'Next step'), ('interview_date', 'Interview date'), ('posting_url', 'Posting'),
    ('folder', 'Folder'), ('resume', 'Resume file'), ('gaps', 'Gaps'), ('notes', 'Notes'),
    ('interview_stage', 'Interview stage'), ('last_checked', 'Last checked'),
]
KEYS = [k for k, _ in COLUMNS]
HEADERS = dict(COLUMNS)
DATE_KEYS = {'date_added', 'deadline', 'status_updated', 'interview_date', 'last_checked'}
LINK_LABELS = {'posting_url': 'Open posting', 'folder': 'Open folder'}
WIDTHS = {'id': 8, 'date_added': 12, 'company': 22, 'role': 32, 'term': 13, 'location': 20, 'deadline': 12,
          'status': 17, 'status_updated': 14, 'next_step': 28, 'interview_date': 15, 'posting_url': 14,
          'folder': 13, 'resume': 30, 'gaps': 30, 'notes': 36, 'interview_stage': 16, 'last_checked': 13}

STATUSES = ['Ready to submit', 'Submitted', 'Online assessment', 'Interviewing', 'Offer', 'Accepted', 'Declined',
            'Rejected', 'Withdrawn', 'Needs you', 'Skipped']
FINAL = {'Accepted', 'Declined', 'Rejected', 'Withdrawn', 'Skipped'}
SENT = {'Submitted', 'Online assessment', 'Interviewing', 'Offer', 'Accepted', 'Declined', 'Rejected', 'Withdrawn'}
REPLIED = {'Online assessment', 'Interviewing', 'Offer', 'Accepted', 'Declined', 'Rejected'}
CHECKIN_DAYS = {'Submitted': 7, 'Online assessment': 5, 'Interviewing': 5, 'Offer': 3}

ALIASES = {
    'applied': 'Submitted', 'sent': 'Submitted', 'submit': 'Submitted', 'application sent': 'Submitted',
    'oa': 'Online assessment', 'assessment': 'Online assessment', 'coding challenge': 'Online assessment',
    'online test': 'Online assessment', 'hackerrank': 'Online assessment', 'codesignal': 'Online assessment',
    'interview': 'Interviewing', 'interviews': 'Interviewing', 'phone screen': 'Interviewing',
    'phone interview': 'Interviewing', 'final interview': 'Interviewing', 'final round': 'Interviewing',
    'onsite': 'Interviewing', 'technical interview': 'Interviewing', 'screening': 'Interviewing',
    'hired': 'Accepted', 'got the job': 'Accepted', 'offer accepted': 'Accepted', 'accepted offer': 'Accepted',
    'declined offer': 'Declined', 'offer declined': 'Declined', 'turned down': 'Declined',
    'turned it down': 'Declined',
    'rejection': 'Rejected', 'not selected': 'Rejected', 'unsuccessful': 'Rejected', 'rejected me': 'Rejected',
    'denied': 'Rejected', 'position filled': 'Rejected',
    'withdrew': 'Withdrawn', 'withdraw': 'Withdrawn', 'pulled out': 'Withdrawn',
    'skip': 'Skipped', 'not applying': 'Skipped',
    'needs me': 'Needs you', 'blocked': 'Needs you', 'stuck': 'Needs you',
    'ready': 'Ready to submit', 'to submit': 'Ready to submit',
}
_FILLS = {'Ready to submit': 'FFF4CC', 'Submitted': 'DDEBF7', 'Online assessment': 'E4DFEC', 'Interviewing': 'FCE4D6',
          'Offer': 'C6EFCE', 'Accepted': 'A9D08E', 'Declined': 'EDEDED', 'Rejected': 'F8CBAD', 'Withdrawn': 'EDEDED',
          'Needs you': 'FFD966', 'Skipped': 'F2F2F2'}
_ASK = {
    'Submitted': 'no news yet / online assessment / interview / rejected / withdrew',
    'Online assessment': 'not done yet / done, waiting / interview / rejected / withdrew',
    'Interviewing': 'waiting to hear / another round / offer / rejected / withdrew',
    'Offer': 'still deciding / accepted / declined',
    'Ready to submit': 'submitted / still to do / skip it',
    'Needs you': 'sorted, now submitted / still stuck / skip it',
}


class TrackerBusy(Exception):
    """The workbook is open in Excel (or another program) and cannot be saved."""


class LockTimeout(Exception):
    """Another copy of the script held the tracker lock for too long."""


# ---- statuses and dates ----------------------------------------------------------------------------------------

def split_status(value):
    """("Needs you", "login page") from "Needs you: login page"; the reason is "" when there is none."""
    s = str(value or '').strip()
    if ':' in s:
        word, reason = s.split(':', 1)
        return word.strip(), reason.strip()
    return s, ''


def canonical_status(s):
    """The tracker's own status name for a forgiving status word, or None when it can't be told.

    Order: exact name (any case), then aliases, then a unique start of a status name. A reason after ":" is
    ignored here (see split_status)."""
    word = norm(split_status(s)[0])
    if not word:
        return None
    for st in STATUSES:
        if norm(st) == word:
            return st
    if word in ALIASES:
        return ALIASES[word]
    hits = [st for st in STATUSES if norm(st).startswith(word)]
    if len(hits) == 1:
        return hits[0]
    hits = {v for k, v in ALIASES.items() if k.startswith(word) and len(word) >= 3}
    return hits.pop() if len(hits) == 1 else None


def as_date(v):
    """A datetime.date from a date, datetime, Excel serial number or text starting with YYYY-MM-DD; else None."""
    if v is None or v == '':
        return None
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if 20000 < v < 80000:  # an Excel serial day number
            return dt.date(1899, 12, 30) + dt.timedelta(days=int(v))
        return None
    m = re.match(r'\s*(\d{4})-(\d{1,2})-(\d{1,2})', str(v))
    if not m:
        return None
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _iso(v):
    if isinstance(v, (dt.date, dt.datetime)):
        if isinstance(v, dt.datetime) and (v.hour or v.minute):
            return v.strftime('%Y-%m-%d %H:%M')
        return v.isoformat()[:10]
    return '' if v is None else v


# ---- opening, reading, saving ----------------------------------------------------------------------------------

def _openpyxl():
    return cli.need_package('openpyxl')


def _header_map(ws):
    """{key: column number} read from the header row (by header text, so column order doesn't matter)."""
    by_text = {norm(h): k for k, h in COLUMNS}
    by_text.update({norm(k): k for k in KEYS})
    out = {}
    for cell in ws[1]:
        k = by_text.get(norm(cell.value))
        if k and k not in out:
            out[k] = cell.column
    return out


def _style_header(ws, col):
    from openpyxl.styles import Alignment, Font, PatternFill
    c = ws.cell(row=1, column=col)
    c.font = Font(bold=True, color='FFFFFF')
    c.fill = PatternFill('solid', fgColor='305496')
    c.alignment = Alignment(vertical='center')


def _new_sheet(wb, ws):
    from openpyxl.formatting.rule import FormulaRule
    from openpyxl.styles import PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation
    ws.title = SHEET
    for i, (k, h) in enumerate(COLUMNS, 1):
        ws.cell(row=1, column=i, value=h)
        _style_header(ws, i)
        ws.column_dimensions[get_column_letter(i)].width = WIDTHS.get(k, 15)
    last = get_column_letter(len(COLUMNS))
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = f'A1:{last}1'
    scol = get_column_letter(KEYS.index('status') + 1)
    dv = DataValidation(type='list', formula1='"' + ','.join(STATUSES) + '"', allow_blank=True,
                        showErrorMessage=False)
    dv.add(f'{scol}2:{scol}5000')
    ws.add_data_validation(dv)
    for st, colour in _FILLS.items():
        ws.conditional_formatting.add(
            f'A2:{last}5000',
            FormulaRule(formula=[f'${scol}2="{st}"'], fill=PatternFill('solid', fgColor=colour, bgColor=colour)))


def open_book(path):
    """(workbook, "Applications" sheet, notes). A missing file gives a new, styled, unsaved workbook; an older
    tracker gets any missing column headers added at the end (saved with the next change). `notes` lists what
    was done, in plain words."""
    openpyxl = _openpyxl()
    notes = []
    if not os.path.exists(path):
        wb = openpyxl.Workbook()
        _new_sheet(wb, wb.active)
        notes.append('new tracker')
        return wb, wb[SHEET], notes
    try:
        wb = openpyxl.load_workbook(path)
    except Exception as e:  # not a workbook, or damaged
        raise ValueError(f'Could not read {path} as an Excel workbook ({type(e).__name__}: {e})')
    if SHEET in wb.sheetnames:
        ws = wb[SHEET]
    else:
        ws = wb.worksheets[0]
        if ws.max_row <= 1 and not any(c.value for c in ws[1]):
            _new_sheet(wb, ws)
            notes.append('set up the empty first sheet as "Applications"')
            return wb, ws, notes
        notes.append(f'no sheet named "{SHEET}"; using "{ws.title}"')
    have = _header_map(ws)
    missing = [k for k in KEYS if k not in have]
    if missing:
        from openpyxl.utils import get_column_letter
        col = max([c.column for c in ws[1] if c.value not in (None, '')] or [0])
        for k in missing:
            col += 1
            ws.cell(row=1, column=col, value=HEADERS[k])
            _style_header(ws, col)
            ws.column_dimensions[get_column_letter(col)].width = WIDTHS.get(k, 15)
        if ws.auto_filter.ref:
            ws.auto_filter.ref = f'A1:{get_column_letter(col)}{max(ws.max_row, 1)}'
        notes.append('added missing columns: ' + ', '.join(HEADERS[k] for k in missing))
    return wb, ws, notes


def _last_row(ws):
    for r in range(ws.max_row, 1, -1):
        if any(c.value not in (None, '') for c in ws[r]):
            return r
    return 1


def rows(ws):
    """Every application row as {key: cell value, ..., "_row": sheet row number}; empty rows are left out.
    Link columns hold the cell text here; use read_links for the link targets."""
    cols = _header_map(ws)
    out = []
    for r in range(2, _last_row(ws) + 1):
        rec = {}
        for k in KEYS:
            v = ws.cell(row=r, column=cols[k]).value if k in cols else None
            rec[k] = '' if v is None else (v.strip() if isinstance(v, str) else v)
        if not any(rec[k] not in ('', None) for k in KEYS):
            continue
        rec['_row'] = r
        out.append(rec)
    return out


def read_links(ws, row):
    """A copy of `row` with posting_url and folder replaced by their hyperlink targets (the folder as a path
    relative to the tracker, as stored). A cell showing only the label with no link gives ""."""
    out = dict(row)
    cols = _header_map(ws)
    for k, label in LINK_LABELS.items():
        if k not in cols or not row.get('_row'):
            continue
        cell = ws.cell(row=row['_row'], column=cols[k])
        target = cell.hyperlink.target if cell.hyperlink is not None and cell.hyperlink.target else None
        if target:
            out[k] = urllib.parse.unquote(target) if k == 'folder' else target
        elif str(cell.value or '').strip() in (label, ''):
            out[k] = ''
        else:
            out[k] = str(cell.value).strip()
    return out


def _excel_owner_file(path):
    folder, name = os.path.split(os.path.abspath(path))
    return os.path.join(folder, '~$' + name)


def save_book(wb, path):
    """Save safely: refuse when Excel has the file open (TrackerBusy); write a temporary file beside the tracker
    and swap it in, so a reader never sees half a workbook."""
    if os.path.exists(_excel_owner_file(path)):
        raise TrackerBusy(f'{os.path.basename(path)} looks open in Excel (found "~${os.path.basename(path)}" beside '
                          'it). Close it in Excel and try again. If Excel is not open, that ~$ file is left over '
                          'from a crash and can be removed by you.')
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    tmp = os.path.join(folder, f'.{os.path.basename(path)}.{os.getpid()}.tmp')
    try:
        wb.save(tmp)
        os.replace(tmp, path)
    except PermissionError:
        raise TrackerBusy(f'{os.path.basename(path)} could not be saved: it is open in another program (Excel?). '
                          'Close it and try again.')
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)  # our own temporary file, never the user's
            except OSError:
                pass


class tracker_lock:
    """Exclusive OS-level lock shared by every process working on the same tracker file.

    The lock file lives in the system temp folder, named after a hash of the tracker's real path."""

    def __init__(self, path, timeout=None):
        real = os.path.realpath(os.path.abspath(path))
        if os.name == 'nt':
            real = real.lower()
        digest = hashlib.sha1(real.encode('utf-8')).hexdigest()[:16]
        self.lock_path = os.path.join(tempfile.gettempdir(), f'jobkit-tracker-{digest}.lock')
        if timeout is None:
            try:
                timeout = float(os.environ.get('JOBKIT_LOCK_TIMEOUT', '60'))
            except ValueError:
                timeout = 60.0
        self.timeout = timeout
        self.fh = None

    def __enter__(self):
        self.fh = open(self.lock_path, 'a+')
        end = time.monotonic() + self.timeout
        while True:
            try:
                if os.name == 'nt':
                    import msvcrt
                    self.fh.seek(0)
                    msvcrt.locking(self.fh.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except OSError:
                if time.monotonic() >= end:
                    self.fh.close()
                    self.fh = None
                    raise LockTimeout(f'Another job-kit script kept the tracker busy for over {self.timeout:g} '
                                      f'seconds (lock file: {self.lock_path}). Try again in a moment.')
                time.sleep(0.05)

    def __exit__(self, *exc):
        if self.fh is None:
            return False
        try:
            if os.name == 'nt':
                import msvcrt
                self.fh.seek(0)
                msvcrt.locking(self.fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.fh.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        self.fh.close()
        self.fh = None
        return False


# ---- writing cells ---------------------------------------------------------------------------------------------

def _write_cell(ws, row_no, key, value, tracker_path):
    cols = _header_map(ws)
    cell = ws.cell(row=row_no, column=cols[key])
    if key in LINK_LABELS:
        target = str(value or '').strip()
        if not target:
            cell.value, cell.hyperlink = None, None
            return
        if key == 'folder':
            if os.path.isabs(target):
                try:
                    target = os.path.relpath(target, os.path.dirname(os.path.abspath(tracker_path)))
                except ValueError:  # another drive on Windows: keep the full path
                    pass
            target = urllib.parse.quote(target.replace('\\', '/'), safe="/:()&',-_.~+=@!$;")
        cell.value = LINK_LABELS[key]
        cell.hyperlink = target
        cell.style = 'Hyperlink'
        return
    if key in DATE_KEYS and isinstance(value, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value.strip()):
        d = as_date(value)
        if d:
            cell.value = d
            cell.number_format = 'yyyy-mm-dd'
            return
    if isinstance(value, dt.date):
        cell.value = value
        cell.number_format = 'yyyy-mm-dd'
        return
    cell.value = value if value not in ('',) else None


def _public(ws, row):
    rec = read_links(ws, row)
    return {k: _iso(rec.get(k, '')) for k in KEYS}


def _next_id(all_rows):
    n = 0
    for r in all_rows:
        m = re.fullmatch(r'A(\d+)', str(r.get('id') or '').strip(), re.I)
        if m:
            n = max(n, int(m.group(1)))
    return f'A{n + 1:04d}'


def _same_app(a, company, role, term):
    return (name_key(a.get('company')) == name_key(company) and norm(a.get('role')) == norm(role)
            and norm(a.get('term')) == norm(term))


# ---- queries ---------------------------------------------------------------------------------------------------

def due_for_checkin(rows_, today=None, days=None):
    """Applications due for a status check, longest-waiting first.

    A row is due when its status is open and has a wait (CHECKIN_DAYS, or `days` for every open status) and that
    many days have passed since the latest of status_updated, last_checked and date_added. An Interviewing row whose
    interview date has passed, and that hasn't been checked since, is always due. Rows may hold dates as date
    objects or "YYYY-MM-DD" text."""
    today = as_date(today) or dt.date.today()
    out = []
    for r in rows_:
        st = canonical_status(r.get('status')) or str(r.get('status') or '')
        if st in FINAL or not st:
            continue
        stamps = [d for d in (as_date(r.get('status_updated')), as_date(r.get('last_checked')),
                              as_date(r.get('date_added'))) if d]
        since = max(stamps) if stamps else None
        waited = (today - since).days if since else None
        iv, checked = as_date(r.get('interview_date')), as_date(r.get('last_checked'))
        why = None
        if st == 'Interviewing' and iv and iv < today and (not checked or checked <= iv):
            why = f'the interview on {iv.isoformat()} has passed'
        else:
            wait = days if days is not None else CHECKIN_DAYS.get(st)
            if wait is not None and waited is not None and waited >= wait:
                why = f'{st.lower()} {waited} days ago with no update since {since.isoformat()}'
                if since == checked:
                    why = f'last checked {waited} days ago ({since.isoformat()}), still {st.lower()}'
        if not why:
            continue
        company, role = r.get('company') or '?', r.get('role') or '?'
        ask = f'Any news from {company} about {role}? ({_ASK.get(st, "update / no change / withdrew")})'
        out.append({'id': r.get('id', ''), 'company': company, 'role': role, 'status': st,
                    'interview_stage': _iso(r.get('interview_stage', '')), 'days': waited if waited is not None else '',
                    'why': why, 'ask': ask})
    out.sort(key=lambda d: -(d['days'] if isinstance(d['days'], int) else 0))
    return out


def find_rows(rows_, company=None, role=None, status=None, rid=None, extra=None):
    """Rows matching every filter given (text filters: normalized substring; status: exact canonical name)."""
    out = []
    for r in rows_:
        if rid and str(r.get('id', '')).strip().upper() != rid.strip().upper():
            continue
        if company and norm(company) not in norm(r.get('company')) and name_key(company) not in name_key(r.get('company')):
            continue
        if role and norm(role) not in norm(r.get('role')):
            continue
        if status and r.get('status') != status:
            continue
        if extra and any(norm(v) not in norm(_iso(r.get(k, ''))) for k, v in extra.items()):
            continue
        out.append(r)
    return out


def summary(rows_, today=None):
    today = as_date(today) or dt.date.today()
    by = {}
    for r in rows_:
        st = r.get('status') or '(blank)'
        by[st] = by.get(st, 0) + 1
    by_status = {s: by[s] for s in STATUSES if s in by}
    by_status.update({s: n for s, n in by.items() if s not in by_status})
    short = lambda r, *ks: {'id': r.get('id', ''), 'company': r.get('company', ''), 'role': r.get('role', ''),
                            **{k: _iso(r.get(k, '')) for k in ks}}
    upcoming = sorted((r for r in rows_ if as_date(r.get('interview_date')) and as_date(r['interview_date']) >= today
                       and r.get('status') not in FINAL),
                      key=lambda r: as_date(r['interview_date']))
    ready = sorted((r for r in rows_ if r.get('status') == 'Ready to submit'),
                   key=lambda r: as_date(r.get('deadline')) or dt.date.max)
    stale = []
    for r in rows_:
        if r.get('status') != 'Submitted':
            continue
        since = as_date(r.get('status_updated')) or as_date(r.get('date_added'))
        if since and (today - since).days >= 21:
            stale.append(dict(short(r, 'status_updated'), days=(today - since).days))
    return {'total': len(rows_), 'by_status': by_status,
            'upcoming_interviews': [short(r, 'interview_date', 'interview_stage') for r in upcoming],
            'ready_to_submit': [short(r, 'deadline') for r in ready],
            'submitted_3_weeks_no_update': stale}


# ---- command line ----------------------------------------------------------------------------------------------

def _parse_sets(pairs):
    by_text = {norm(h): k for k, h in COLUMNS}
    by_text.update({norm(k): k for k in KEYS})
    out = {}
    for p in pairs or []:
        if '=' not in p:
            cli.fail(f'--set needs key=value, got "{p}"')
        k, v = p.split('=', 1)
        key = by_text.get(norm(k))
        if not key:
            cli.fail(f'Unknown tracker field "{k}"', fields=KEYS)
        out[key] = v.strip()
    return out


def _bad_status(value):
    cli.fail(f'Unknown status "{value}". Use one of: ' + ', '.join(STATUSES), statuses=STATUSES)


def _apply_status(changes, current_next_step=''):
    """Turn a forgiving status in `changes` into its canonical name; put a reason into next_step if empty."""
    if 'status' not in changes:
        return
    raw = changes['status']
    st = canonical_status(raw)
    if not st:
        _bad_status(raw)
    _, reason = split_status(raw)
    changes['status'] = st
    if reason and not str(current_next_step or '').strip() and not changes.get('next_step'):
        changes['next_step'] = reason


def _resolve_path(p):
    p = os.path.expanduser(p)
    if os.path.isdir(p):
        p = os.path.join(p, 'tracker.xlsx')
    return p


def _pick_row(all_rows, a):
    if a.id:
        hit = [r for r in all_rows if str(r.get('id', '')).strip().upper() == a.id.strip().upper()]
        if not hit:
            cli.fail(f'No row with ID {a.id}')
        return hit[0], False
    if not (a.company or a.role):
        cli.fail(f'{a.command} needs --id (find the ID with: tracker.py find FILE --company ...)')
    hit = find_rows(all_rows, company=a.company, role=a.role)
    exact = [r for r in hit if (not a.company or name_key(r.get('company')) == name_key(a.company))
             and (not a.role or norm(r.get('role')) == norm(a.role))]
    hit = exact if len(exact) == 1 else hit
    if len(hit) != 1:
        cli.fail(f'{len(hit)} rows match; give --id', matches=[{'id': r.get('id'), 'company': r.get('company'),
                                                                 'role': r.get('role')} for r in hit])
    return hit[0], True


def _run(a, path, today):
    exists = os.path.exists(path)
    if a.command in ('update', 'checked') and not exists:
        cli.fail(f'Tracker not found: {path}')
    if a.command in ('find', 'summary', 'checkin') and not exists:
        empty = {'find': {'count': 0, 'rows': []}, 'checkin': {'count': 0, 'due': []},
                 'summary': summary([], today)}[a.command]
        return {'ok': True, 'tracker': path, 'note': 'no tracker yet', **empty}, cli.OK
    try:
        wb, ws, notes = open_book(path)
    except ValueError as e:
        cli.fail(str(e))
    all_rows = rows(ws)
    sets = _parse_sets(a.set)
    base = {'ok': True, 'tracker': path}
    if notes:
        base['notes'] = notes

    if a.command == 'find':
        st = None
        if a.status:
            st = canonical_status(a.status) or _bad_status(a.status)
        hit = find_rows(all_rows, a.company, a.role, st, a.id, {k: v for k, v in sets.items()} or None)
        return {**base, 'count': len(hit), 'rows': [_public(ws, r) for r in hit]}, cli.OK
    if a.command == 'summary':
        return {**base, **summary(all_rows, today)}, cli.OK
    if a.command == 'checkin':
        due = due_for_checkin(all_rows, today, a.days)
        return {**base, 'count': len(due), 'due': due}, cli.OK

    if a.command == 'add':
        for k in ('company', 'role', 'status'):
            if getattr(a, k):
                sets[k] = getattr(a, k)
        if a.id:
            cli.fail('add gives the ID itself; leave out --id')
        sets.pop('id', None)
        if not sets.get('company') or not sets.get('role'):
            cli.fail('add needs a company and a role (--company "..." --role "...")')
        _apply_status(sets)
        dupes = [r for r in all_rows if _same_app(r, sets['company'], sets['role'], sets.get('term', ''))]
        if dupes:
            return {**base, 'ok': False, 'added': False, 'duplicate': True,
                    'message': 'Already in the tracker; nothing added.', 'row': _public(ws, dupes[0])}, cli.ATTENTION
        rec = {'id': _next_id(all_rows), 'date_added': today, 'status': 'Ready to submit', 'status_updated': today}
        rec.update(sets)
        if 'status_updated' not in sets:
            rec['status_updated'] = today
        row_no = _last_row(ws) + 1
        for k, v in rec.items():
            _write_cell(ws, row_no, k, v, path)
        save_book(wb, path)
        new = [r for r in rows(ws) if r['_row'] == row_no][0]
        return {**base, 'added': True, 'row': _public(ws, new)}, cli.OK

    # update / checked
    row, picked_by_name = _pick_row(all_rows, a)
    if a.command == 'checked':
        changes = {'last_checked': today}
    else:
        changes = dict(sets)
        if a.status:
            changes['status'] = a.status
        if not picked_by_name:
            for k in ('company', 'role'):
                if getattr(a, k):
                    changes[k] = getattr(a, k)
        changes.pop('id', None)
        if not changes:
            cli.fail('Nothing to change: give --status or --set key=value')
        _apply_status(changes, row.get('next_step'))
        if 'status' in changes and changes['status'] != row.get('status') and 'status_updated' not in changes:
            changes['status_updated'] = today
    before = _public(ws, row)
    for k, v in changes.items():
        _write_cell(ws, row['_row'], k, v, path)
    save_book(wb, path)
    after = _public(ws, [r for r in rows(ws) if r['_row'] == row['_row']][0])
    changed = {k: [before[k], after[k]] for k in KEYS if before[k] != after[k]}
    return {**base, 'row': after, 'changed': changed}, cli.OK


def main(argv=None):
    p = argparse.ArgumentParser(description='Add, update and read applications in tracker.xlsx.')
    p.add_argument('command', choices=['add', 'update', 'find', 'summary', 'checkin', 'checked'])
    p.add_argument('file', help='tracker.xlsx, or the job-search folder that holds it')
    p.add_argument('--set', action='append', metavar='KEY=VALUE', help='a field to set (or, with find, to filter on)')
    p.add_argument('--id', help='row ID such as A0003')
    p.add_argument('--company')
    p.add_argument('--role')
    p.add_argument('--status')
    p.add_argument('--days', type=int, help='checkin: days to wait for every open status')
    p.add_argument('--today', help=argparse.SUPPRESS)  # YYYY-MM-DD, for tests
    a = p.parse_args(argv)
    today = dt.date.today()
    if a.today:
        today = as_date(a.today) or cli.fail(f'--today must be YYYY-MM-DD, got {a.today}')
    _openpyxl()
    path = _resolve_path(a.file)
    try:
        with tracker_lock(path):
            out, code = _run(a, path, today)
    except LockTimeout as e:
        cli.fail(str(e), cli.NETWORK)
    except TrackerBusy as e:
        cli.fail(str(e), cli.FILE_BUSY)
    cli.emit(out, code)


if __name__ == '__main__':
    main()
