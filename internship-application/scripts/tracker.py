"""Application tracker (tracker.xlsx): add, update, find, summary, checkin, checked.

Usage:
  python tracker.py add     "<folder>/tracker.xlsx" --company "Acme" --role "Software Intern" [--set key=value ...]
  python tracker.py update  "<folder>/tracker.xlsx" --id A0003 --status "Interviewing" [--set interview_date=2026-12-01]
  python tracker.py find    "<folder>/tracker.xlsx" [--company X] [--role Y] [--status S]
  python tracker.py summary "<folder>/tracker.xlsx"
  python tracker.py checkin "<folder>/tracker.xlsx" [--days N]
  python tracker.py checked "<folder>/tracker.xlsx" --id A0003

Prints one JSON object. Fields (for --set): id, date_added, company, role, term, location, deadline, status,
status_updated, next_step, interview_date, posting_url, folder, resume, gaps, notes, interview_stage, last_checked.
Exit codes: 0 ok, 1 bad input, 2 duplicate on add, 4 open in Excel, 5 openpyxl missing, 6 another run kept it busy.

This file is a thin wrapper: the work is done by jobkit/tracker.py (see its docstring for the full rules). Other
scripts may `import tracker` and use the same names (open_book, rows, read_links, due_for_checkin, ...).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(HERE, '..', '..', 'lib')):
    if os.path.isdir(os.path.join(_p, 'jobkit')):
        sys.path.insert(0, os.path.abspath(_p))
        break
from jobkit.tracker import *  # noqa: F401,F403  (re-exported for scripts that import tracker)
from jobkit.tracker import main

if __name__ == '__main__':
    main()
