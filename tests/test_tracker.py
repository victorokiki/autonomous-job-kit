"""Tests for lib/jobkit/tracker.py and the tracker.py command line (made-up data, temp folders only)."""
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'lib'))
SCRIPTS = [os.path.join(ROOT, 'internship-application', 'scripts', 'tracker.py'),
           os.path.join(ROOT, 'internship-tracker', 'scripts', 'tracker.py')]

try:
    import openpyxl  # noqa: F401
    HAVE_OPENPYXL = True
except ImportError:
    HAVE_OPENPYXL = False

from jobkit import tracker  # noqa: E402


def run(*args, script=SCRIPTS[0], env=None):
    p = subprocess.run([sys.executable, script] + [str(a) for a in args], capture_output=True, text=True,
                       env=env, timeout=120)
    return json.loads(p.stdout), p.returncode


class StatusWords(unittest.TestCase):
    def test_exact_any_case(self):
        for s in tracker.STATUSES:
            self.assertEqual(tracker.canonical_status(s.upper()), s)

    def test_aliases(self):
        cases = {'applied': 'Submitted', 'sent': 'Submitted', 'OA': 'Online assessment',
                 'coding challenge': 'Online assessment', 'assessment': 'Online assessment',
                 'phone screen': 'Interviewing', 'final interview': 'Interviewing', 'interview': 'Interviewing',
                 'hired': 'Accepted', 'got the job': 'Accepted', 'offer accepted': 'Accepted',
                 'declined offer': 'Declined', 'turned down': 'Declined', 'rejection': 'Rejected',
                 'not selected': 'Rejected', 'Unsuccessful': 'Rejected'}
        for word, want in cases.items():
            self.assertEqual(tracker.canonical_status(word), want, word)

    def test_alias_before_prefix(self):
        self.assertEqual(tracker.canonical_status('offer accepted'), 'Accepted')
        self.assertEqual(tracker.canonical_status('offer'), 'Offer')

    def test_prefix_and_unknown(self):
        self.assertEqual(tracker.canonical_status('interv'), 'Interviewing')
        self.assertEqual(tracker.canonical_status('withdr'), 'Withdrawn')
        self.assertIsNone(tracker.canonical_status('s'))          # Submitted or Skipped: ambiguous
        self.assertIsNone(tracker.canonical_status('banana'))
        self.assertIsNone(tracker.canonical_status(''))

    def test_reason(self):
        self.assertEqual(tracker.split_status('Needs you: login page'), ('Needs you', 'login page'))
        self.assertEqual(tracker.canonical_status('Needs you: login page'), 'Needs you')


class Dates(unittest.TestCase):
    def test_as_date(self):
        d = dt.date(2026, 11, 14)
        self.assertEqual(tracker.as_date(d), d)
        self.assertEqual(tracker.as_date(dt.datetime(2026, 11, 14, 9, 30)), d)
        self.assertEqual(tracker.as_date('2026-11-14'), d)
        self.assertEqual(tracker.as_date('2026-11-14 14:00'), d)
        self.assertEqual(tracker.as_date(46340), d)  # Excel serial number
        self.assertIsNone(tracker.as_date('not stated'))
        self.assertIsNone(tracker.as_date(None))
        self.assertIsNone(tracker.as_date('2026-13-40'))


class Checkin(unittest.TestCase):
    T = dt.date(2026, 11, 14)

    def row(self, **kw):
        base = {'id': 'A0001', 'company': 'Northwind Robotics', 'role': 'Software Intern', 'status': 'Submitted',
                'date_added': '2026-10-01', 'status_updated': '', 'last_checked': '', 'interview_date': '',
                'interview_stage': ''}
        base.update(kw)
        return base

    def test_waits(self):
        T = self.T
        due = lambda **kw: tracker.due_for_checkin([self.row(**kw)], T)
        self.assertEqual(len(due(status_updated='2026-11-07')), 1)        # Submitted, 7 days
        self.assertEqual(len(due(status_updated='2026-11-08')), 0)        # 6 days
        self.assertEqual(len(due(status='Online assessment', status_updated='2026-11-09')), 1)
        self.assertEqual(len(due(status='Online assessment', status_updated='2026-11-10')), 0)
        self.assertEqual(len(due(status='Offer', status_updated='2026-11-11')), 1)
        self.assertEqual(len(due(status='Offer', status_updated='2026-11-12')), 0)
        self.assertEqual(len(due(status='Rejected', status_updated='2026-01-01')), 0)   # final
        self.assertEqual(len(due(status='Ready to submit', status_updated='2026-01-01')), 0)  # no wait

    def test_last_checked_resets_and_days_override(self):
        T = self.T
        r = self.row(status_updated='2026-10-01', last_checked='2026-11-12')
        self.assertEqual(tracker.due_for_checkin([r], T), [])
        self.assertEqual(len(tracker.due_for_checkin([r], T, days=2)), 1)
        rts = self.row(status='Ready to submit', status_updated='2026-11-10')
        self.assertEqual(len(tracker.due_for_checkin([rts], T, days=3)), 1)

    def test_past_interview_always_due(self):
        T = self.T
        r = self.row(status='Interviewing', status_updated='2026-11-12', interview_date='2026-11-13',
                     interview_stage='Final round')
        d = tracker.due_for_checkin([r], T)
        self.assertEqual(len(d), 1)
        self.assertIn('2026-11-13', d[0]['why'])
        self.assertEqual(d[0]['interview_stage'], 'Final round')
        for k in ('id', 'company', 'role', 'status', 'interview_stage', 'why', 'ask'):
            self.assertIn(k, d[0])
        self.assertIn('offer', d[0]['ask'])
        r['last_checked'] = '2026-11-14'
        self.assertEqual(tracker.due_for_checkin([r], T), [])
        r2 = self.row(status='Interviewing', status_updated='2026-11-12', interview_date='2026-11-20')
        self.assertEqual(tracker.due_for_checkin([r2], T), [])

    def test_date_objects_accepted(self):
        r = self.row(status_updated=dt.datetime(2026, 11, 1), date_added=dt.date(2026, 10, 1))
        self.assertEqual(len(tracker.due_for_checkin([r], self.T)), 1)


@unittest.skipUnless(HAVE_OPENPYXL, 'openpyxl not installed')
class CommandLine(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='jobkit tracker ')  # a space in the path on purpose
        self.path = os.path.join(self.tmp.name, 'tracker.xlsx')

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_defaults_and_duplicates(self):
        out, code = run('add', self.path, '--company', 'Northwind Robotics Inc.', '--role', 'Software Intern',
                        '--set', 'term=Summer 2027', '--today', '2026-11-14')
        self.assertEqual(code, 0, out)
        row = out['row']
        self.assertEqual(row['id'], 'A0001')
        self.assertEqual(row['status'], 'Ready to submit')
        self.assertEqual(row['date_added'], '2026-11-14')
        self.assertEqual(row['status_updated'], '2026-11-14')
        out, code = run('add', self.path, '--company', 'NORTHWIND ROBOTICS', '--role', 'software intern',
                        '--set', 'term=summer 2027')
        self.assertEqual(code, 2)
        self.assertTrue(out['duplicate'])
        self.assertEqual(out['row']['id'], 'A0001')
        out, code = run('add', self.path, '--company', 'Northwind Robotics', '--role', 'Software Intern',
                        '--set', 'term=Fall 2027', '--status', 'applied')
        self.assertEqual(code, 0)
        self.assertEqual(out['row']['id'], 'A0002')
        self.assertEqual(out['row']['status'], 'Submitted')
        out, code = run('add', self.path, '--company', 'Only Company')
        self.assertEqual(code, 1)

    def test_update_status_reason_and_stamp(self):
        run('add', self.path, '--company', 'Contoso', '--role', 'Data Intern', '--today', '2026-11-01')
        out, code = run('update', self.path, '--id', 'a0001', '--status', 'Needs you: login page',
                        '--today', '2026-11-05')
        self.assertEqual(code, 0, out)
        self.assertEqual(out['row']['status'], 'Needs you')
        self.assertEqual(out['row']['next_step'], 'login page')
        self.assertEqual(out['row']['status_updated'], '2026-11-05')
        # same status again: no new stamp; next_step not overwritten by a new reason
        out, _ = run('update', self.path, '--id', 'A0001', '--status', 'needs you: other', '--today', '2026-11-09')
        self.assertEqual(out['row']['status_updated'], '2026-11-05')
        self.assertEqual(out['row']['next_step'], 'login page')
        out, code = run('update', self.path, '--id', 'A0001', '--status', 'zebra')
        self.assertEqual(code, 1)
        self.assertIn('Submitted', out['error'])
        out, code = run('update', self.path, '--id', 'A0099', '--status', 'Submitted')
        self.assertEqual(code, 1)
        out, code = run('update', self.path, '--company', 'contoso', '--status', 'phone screen',
                        '--set', 'interview_date=2026-11-20', '--today', '2026-11-10')
        self.assertEqual(code, 0, out)
        self.assertEqual(out['row']['status'], 'Interviewing')
        self.assertEqual(out['row']['interview_date'], '2026-11-20')
        self.assertIn('status', out['changed'])

    def test_hyperlinks_round_trip(self):
        app = os.path.join(self.tmp.name, 'Applications', '2026-11-14 Fabrikam - QA Intern')
        url = 'https://boards.greenhouse.io/fabrikam/jobs/4012345?gh_src=abc'
        run('add', self.path, '--company', 'Fabrikam', '--role', 'QA Intern', '--set', f'posting_url={url}',
            '--set', f'folder={app}')
        out, _ = run('find', self.path, '--company', 'fabrikam')
        self.assertEqual(out['rows'][0]['posting_url'], url)
        self.assertEqual(out['rows'][0]['folder'], 'Applications/2026-11-14 Fabrikam - QA Intern')
        import openpyxl
        ws = openpyxl.load_workbook(self.path)['Applications']
        self.assertEqual(ws['L2'].value, 'Open posting')
        self.assertEqual(ws['M2'].value, 'Open folder')
        self.assertEqual(ws['L2'].hyperlink.target, url)
        self.assertNotIn(' ', ws['M2'].hyperlink.target)  # stored percent-encoded
        _, ws2, _ = tracker.open_book(self.path)
        rec = tracker.read_links(ws2, tracker.rows(ws2)[0])
        self.assertEqual(rec['posting_url'], url)

    def test_new_file_styling(self):
        run('add', self.path, '--company', 'Litware', '--role', 'Intern')
        import openpyxl
        ws = openpyxl.load_workbook(self.path)['Applications']
        self.assertEqual([c.value for c in ws[1]], [h for _, h in tracker.COLUMNS])
        self.assertEqual(ws.freeze_panes, 'A2')
        self.assertTrue(ws.auto_filter.ref)
        self.assertTrue(ws['A1'].font.bold)
        self.assertTrue(ws.data_validations.dataValidation)
        self.assertIn('Submitted', ws.data_validations.dataValidation[0].formula1)
        self.assertTrue(len(ws.conditional_formatting) > 0)

    def test_older_tracker_missing_columns(self):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Applications'
        old = [h for _, h in tracker.COLUMNS][:-2]
        ws.append(old)
        ws.append(['A0007', '2026-10-01', 'Tailspin Toys', 'Game Dev Intern', '', '', '', 'Submitted', '2026-10-01'])
        wb.save(self.path)
        _, ws2, notes = tracker.open_book(self.path)
        self.assertTrue(any('Interview stage' in n for n in notes))
        r = tracker.rows(ws2)[0]
        self.assertEqual(r['interview_stage'], '')
        out, code = run('checked', self.path, '--id', 'A0007', '--today', '2026-11-14')
        self.assertEqual(code, 0, out)
        self.assertEqual(out['row']['last_checked'], '2026-11-14')
        hdr = [c.value for c in openpyxl.load_workbook(self.path)['Applications'][1]]
        self.assertEqual(hdr[-2:], ['Interview stage', 'Last checked'])
        out, _ = run('add', self.path, '--company', 'Wingtip', '--role', 'Intern')
        self.assertEqual(out['row']['id'], 'A0008')

    def test_find_summary_checkin(self):
        for c, r, st, d in [('Alpha Labs', 'ML Intern', 'Submitted', '2026-10-01'),
                            ('Beta Corp', 'Data Intern', 'Ready to submit', '2026-11-10'),
                            ('Gamma Co', 'Dev Intern', 'Interviewing', '2026-11-01')]:
            run('add', self.path, '--company', c, '--role', r, '--status', st, '--today', d)
        run('update', self.path, '--id', 'A0003', '--set', 'interview_date=2026-11-20', '--today', '2026-11-01')
        out, _ = run('find', self.path, '--status', 'ready')
        self.assertEqual([x['company'] for x in out['rows']], ['Beta Corp'])
        out, _ = run('find', self.path, '--role', 'intern')
        self.assertEqual(out['count'], 3)
        out, _ = run('summary', self.path, '--today', '2026-11-14')
        self.assertEqual(out['total'], 3)
        self.assertEqual(out['by_status']['Submitted'], 1)
        self.assertEqual(len(out['upcoming_interviews']), 1)
        self.assertEqual(len(out['ready_to_submit']), 1)
        self.assertEqual(len(out['submitted_3_weeks_no_update']), 1)
        out, _ = run('checkin', self.path, '--today', '2026-11-14')
        self.assertEqual({d['id'] for d in out['due']}, {'A0001', 'A0003'})
        run('checked', self.path, '--id', 'A0001', '--today', '2026-11-14')
        out, _ = run('checkin', self.path, '--today', '2026-11-14')
        self.assertEqual({d['id'] for d in out['due']}, {'A0003'})
        out, _ = run('checkin', self.path, '--days', '1', '--today', '2026-11-16')
        self.assertIn('A0002', {d['id'] for d in out['due']})

    def test_folder_argument_and_missing_file(self):
        out, code = run('summary', self.tmp.name)
        self.assertEqual(code, 0)
        self.assertEqual(out['total'], 0)
        out, code = run('update', self.tmp.name, '--id', 'A0001', '--status', 'Submitted')
        self.assertEqual(code, 1)
        out, code = run('add', self.tmp.name, '--company', 'Proseware', '--role', 'Intern', script=SCRIPTS[1])
        self.assertEqual(code, 0)
        self.assertTrue(os.path.exists(self.path))

    def test_excel_open_gives_exit_4(self):
        run('add', self.path, '--company', 'Adatum', '--role', 'Intern')
        owner = os.path.join(self.tmp.name, '~$tracker.xlsx')
        open(owner, 'w').close()
        out, code = run('update', self.path, '--id', 'A0001', '--status', 'Submitted')
        self.assertEqual(code, 4)
        self.assertIn('Excel', out['error'])

    def test_lock_timeout_gives_exit_6(self):
        lock = tracker.tracker_lock(self.path)
        with lock:
            env = dict(os.environ, JOBKIT_LOCK_TIMEOUT='0.5')
            out, code = run('summary', self.path, env=env)
        self.assertEqual(code, 6)
        self.assertFalse(out['ok'])

    def test_parallel_adds_all_land(self):
        procs = [subprocess.Popen([sys.executable, SCRIPTS[i % 2], 'add', self.path, '--company', f'Company {i}',
                                   '--role', 'Software Intern'], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True) for i in range(8)]
        results = [(p.communicate(timeout=120), p.returncode) for p in procs]
        for (outp, err), code in results:
            self.assertEqual(code, 0, err or outp)
        out, _ = run('find', self.path)
        self.assertEqual(out['count'], 8)
        self.assertEqual(sorted(r['id'] for r in out['rows']), [f'A{i:04d}' for i in range(1, 9)])
        self.assertEqual(len({r['company'] for r in out['rows']}), 8)


if __name__ == '__main__':
    unittest.main()
