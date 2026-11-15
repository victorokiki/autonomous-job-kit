"""Tests for internship-tracker/scripts/email_drafts.py against a made-up tracker in a temp folder."""
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, 'internship-tracker', 'scripts', 'email_drafts.py')

try:
    import openpyxl
except ImportError:  # pragma: no cover
    openpyxl = None

HEADERS = ['ID', 'Date added', 'Company', 'Role', 'Term', 'Location', 'Deadline', 'Status', 'Status updated',
           'Next step', 'Interview date', 'Posting', 'Folder', 'Resume file', 'Gaps', 'Notes', 'Interview stage',
           'Last checked']
TODAY = dt.date.today()


def days_ago(n):
    return (TODAY - dt.timedelta(days=n)).isoformat()


@unittest.skipIf(openpyxl is None, 'openpyxl is not installed')
class EmailDrafts(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix='jk test emails ')
        with open(os.path.join(self.dir, 'profile.json'), 'w', encoding='utf-8') as f:
            json.dump({'firstName': 'Alex', 'lastName': 'Tremblay', 'resumeName': 'Alex Morgan Tremblay',
                       'email': 'alex.tremblay@example.com', 'phone': '+1 (902) 555-0142'}, f)
        app = os.path.join(self.dir, 'Applications', f'{days_ago(20)} Northwind Freight - Data Analyst Intern')
        os.makedirs(app)
        with open(os.path.join(app, 'application-record.md'), 'w', encoding='utf-8') as f:
            f.write(f'# Application record\n\n- Date applied: {days_ago(14)}\n- Mode: Review\n')
        with open(os.path.join(app, 'job-posting.md'), 'w', encoding='utf-8') as f:
            f.write('# Data Analyst Intern (Summer) at Northwind Freight\n\n- Company: Northwind Freight\n'
                    '- Role: Data Analyst Intern (Summer)\n')
        self.app = app
        os.makedirs(os.path.join(self.dir, 'Applications', f'{days_ago(9)} Bluefin Labs - Software Intern'))

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Applications'
        ws.append(HEADERS)
        data = [
            ['A0001', days_ago(20), 'Northwind Freight', 'Data Analyst Intern', 'Summer 2027', 'Toronto, ON', '',
             'Submitted', days_ago(14), '', '', '', '', '', '', '', '', ''],
            ['A0002', days_ago(9), 'Bluefin Labs', 'Software Intern', '', '', '', 'Interviewing', days_ago(3), '',
             days_ago(1), '', '', '', '', '', 'second interview', ''],
            ['A0003', days_ago(30), 'Cedar Analytics', 'Junior Analyst', '', '', '', 'Offer', days_ago(2), '', '',
             '', '', '', '', '', '', ''],
            ['A0004', days_ago(4), 'Maple Robotics', 'Co-op Student', '', '', '', 'Submitted', days_ago(3), '', '',
             '', '', '', '', '', '', ''],
        ]
        for row in data:
            ws.append(row)
        rel = os.path.relpath(app, self.dir)
        cell = ws.cell(row=2, column=13, value='Open folder')
        cell.hyperlink = rel
        wb.save(os.path.join(self.dir, 'tracker.xlsx'))

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def run_ed(self, *args):
        r = subprocess.run([sys.executable, SCRIPT, '--folder', self.dir] + list(args), capture_output=True,
                           text=True, timeout=120)
        return r.returncode, json.loads(r.stdout)

    def read(self, path):
        with open(path, encoding='utf-8') as f:
            return f.read()

    def test_followup(self):
        code, out = self.run_ed('--id', 'A0001', '--kind', 'followup', '--to', 'recruiting@example.com')
        self.assertEqual(code, 0, out)
        d = out['drafts'][0]
        self.assertEqual(os.path.dirname(d['path']), self.app)
        self.assertEqual(os.path.basename(d['path']), f'email-followup-{TODAY.isoformat()}.md')
        body = self.read(d['path'])
        self.assertIn('To: recruiting@example.com', body)
        self.assertIn('Subject: Following up on my application: Data Analyst Intern (Summer)', body)
        applied = dt.date.fromisoformat(days_ago(14))
        self.assertIn(f'{applied.strftime("%B")} {applied.day}, {applied.year}', body)
        self.assertIn('alex.tremblay@example.com', body)
        self.assertEqual(out['warnings'], [])
        self.assertFalse(out['sent'])

    def test_thankyou(self):
        code, out = self.run_ed('--id', 'a0002', '--kind', 'thankyou', '--interviewer', 'Jordan Lee',
                                '--note', 'I have attached the sample report we talked about.')
        self.assertEqual(code, 0, out)
        d = out['drafts'][0]
        body = self.read(d['path'])
        self.assertIn('Dear Jordan Lee,', body)
        self.assertIn('yesterday for the second interview', body)
        self.assertIn('<one thing you discussed>', body)
        self.assertIn('sample report', body)
        self.assertNotIn('\nTo:', body)
        self.assertIn('Bluefin Labs - Software Intern', d['path'])     # found by folder name, no link

    def test_offer_replies_and_withdraw(self):
        for kind, needle in (('accept', 'delighted to accept'), ('decline', 'decline the offer'),
                             ('withdraw', 'withdraw my application')):
            with self.subTest(kind=kind):
                code, out = self.run_ed('--id', 'A0003' if kind != 'withdraw' else 'A0004', '--kind', kind)
                self.assertEqual(code, 0, out)
                d = out['drafts'][0]
                self.assertIn(needle, self.read(d['path']))
                self.assertIn(os.path.join(self.dir, 'emails'), d['path'])   # no application folder

    def test_warning_and_old_versions(self):
        code, out = self.run_ed('--id', 'A0004', '--kind', 'followup')
        self.assertTrue(any('3 days' in w for w in out['warnings']))
        code, out = self.run_ed('--id', 'A0004', '--kind', 'followup')
        self.assertTrue(os.path.exists(out['drafts'][0]['previous_version_moved_to']))

    def test_due(self):
        code, out = self.run_ed('--due')
        self.assertEqual(code, 0, out)
        kinds = {d['id']: d['kind'] for d in out['due']}
        self.assertEqual(kinds, {'A0001': 'followup', 'A0002': 'thankyou'})
        code, out = self.run_ed('--due', '--days', '3')
        self.assertIn('A0004', {d['id'] for d in out['due']})

    def test_bad_input(self):
        code, out = self.run_ed('--id', 'A0999', '--kind', 'followup')
        self.assertEqual(code, 1)
        self.assertFalse(out['ok'])
        code, out = self.run_ed('--kind', 'followup')
        self.assertEqual(code, 1)


if __name__ == '__main__':
    unittest.main()
