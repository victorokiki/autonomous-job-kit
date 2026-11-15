"""Tests for internship-tracker/scripts/weekly_report.py (made-up data, temp folders only)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, 'internship-tracker', 'scripts', 'weekly_report.py')
TRACKER = os.path.join(ROOT, 'internship-tracker', 'scripts', 'tracker.py')

try:
    import openpyxl  # noqa: F401
    HAVE_OPENPYXL = True
except ImportError:
    HAVE_OPENPYXL = False


def run(*args):
    p = subprocess.run([sys.executable] + [str(a) for a in args], capture_output=True, text=True, timeout=120)
    return json.loads(p.stdout), p.returncode


class Report(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='jobkit report ')
        self.folder = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def add(self, company, role, status, today, **sets):
        args = [TRACKER, 'add', os.path.join(self.folder, 'tracker.xlsx'), '--company', company, '--role', role,
                '--status', status, '--today', today]
        for k, v in sets.items():
            args += ['--set', f'{k}={v}']
        out, code = run(*args)
        self.assertEqual(code, 0, out)
        return out['row']['id']

    def update(self, rid, today, **sets):
        args = [TRACKER, 'update', os.path.join(self.folder, 'tracker.xlsx'), '--id', rid, '--today', today]
        for k, v in sets.items():
            args += ['--set', f'{k}={v}']
        out, code = run(*args)
        self.assertEqual(code, 0, out)

    def test_empty_folder(self):
        out, code = run(SCRIPT, '--folder', self.folder, '--today', '2026-11-14')
        self.assertEqual(code, 0, out)
        self.assertEqual(out['week'], '2026-W46')
        self.assertTrue(out['path'].endswith(os.path.join('reports', '2026-W46.md')))
        self.assertEqual(out['sent_this_week'], 0)
        self.assertIsNone(out['response_rate'])
        self.assertEqual(len(out['suggestions']), 3)
        with open(out['path'], encoding='utf-8') as f:
            self.assertIn('# Weekly report 2026-W46', f.read())

    @unittest.skipUnless(HAVE_OPENPYXL, 'openpyxl not installed')
    def test_full_report(self):
        with open(os.path.join(self.folder, 'profile.json'), 'w') as f:
            json.dump({'firstName': 'Alex', 'weeklyGoal': 5}, f)
        self.add('Northwind Robotics', 'Software Intern', 'Submitted', '2026-11-10')       # sent this week
        self.add('Contoso', 'Data Intern', 'Submitted', '2026-11-11')                      # sent this week
        a3 = self.add('Fabrikam', 'QA Intern', 'Submitted', '2026-10-20')                  # older, changed this week
        self.update(a3, '2026-11-12', status='Interviewing', interview_date='2026-11-20',
                    interview_stage='Phone screen')
        self.add('Litware', 'ML Intern', 'Rejected', '2026-10-01')
        self.add('Adatum', 'Dev Intern', 'Submitted', '2026-10-15')                        # due for check-in
        self.add('Tailspin', 'Game Intern', 'Ready to submit', '2026-11-13', deadline='2026-11-30')
        self.add('Wingtip', 'Cloud Intern', 'Needs you: create an account', '2026-11-13')
        os.makedirs(os.path.join(self.folder, '.cache'))
        cands = {'saved': '2026-11-13T09:00', 'jobs': [
            {'title': 'Robotics Intern', 'company': 'Proseware', 'location': 'Halifax, NS',
             'url': 'https://jobs.lever.co/proseware/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
             'fit': {'score': 71, 'why': 'Python, ROS'}},
            {'title': 'Software Intern', 'company': 'Northwind Robotics', 'location': 'Austin, TX',
             'url': 'https://example.com/x', 'fit': {'score': 90, 'why': 'already applied'}},
            {'title': 'Data Intern', 'company': 'Margie Travel', 'location': 'Remote',
             'url': 'https://example.com/y', 'fit': {'score': 80, 'why': 'SQL'}}]}
        with open(os.path.join(self.folder, '.cache', 'candidates-2026-11-13.json'), 'w') as f:
            json.dump(cands, f)
        with open(os.path.join(self.folder, '.cache', 'candidates-2026-11-01.json'), 'w') as f:
            json.dump({'jobs': [{'title': 'Old', 'company': 'Old Co', 'location': '', 'url': 'https://e.com/o',
                                 'fit': {'score': 99, 'why': ''}}]}, f)

        out, code = run(SCRIPT, '--folder', self.folder, '--today', '2026-11-14')
        self.assertEqual(code, 0, out)
        self.assertEqual(out['sent_this_week'], 2)
        self.assertEqual(out['status_changes'], 1)
        self.assertEqual(out['interviews_next_14_days'], 1)
        self.assertEqual(out['sent_total'], 5)
        self.assertEqual(out['replied_total'], 2)
        self.assertEqual(out['response_rate'], 40)
        self.assertEqual(out['checkins_due'], 1)
        self.assertEqual(out['ready_to_submit'], 1)
        self.assertEqual(out['needs_you'], 1)
        self.assertEqual(out['best_matches'], 2)  # the tracked one is left out
        self.assertEqual(out['goal'], {'target': 5, 'sent': 2})
        self.assertEqual(len(out['suggestions']), 3)
        self.assertIn('Tailspin', out['suggestions'][0])
        with open(out['path'], encoding='utf-8') as f:
            md = f.read()
        for bit in ['2 of 5 applications sent this week', 'Northwind Robotics, Software Intern',
                    'Fabrikam, QA Intern: Interviewing on 2026-11-12 (Phone screen)', '2026-11-20: Fabrikam',
                    '2 of 5 applications sent so far got a reply', 'Adatum, Dev Intern',
                    'Submit: Tailspin, Game Intern (deadline 2026-11-30)',
                    'Needs you: Wingtip, Cloud Intern - create an account', 'Margie Travel', 'Proseware',
                    'candidates-2026-11-13.json', '## Suggestions']:
            self.assertIn(bit, md)
        self.assertNotIn('Old Co', md)
        self.assertLess(md.index('Margie Travel'), md.index('Proseware'))  # best score first

        # a second run for the same week keeps the first report in reports/_old/
        out2, _ = run(SCRIPT, '--folder', self.folder, '--today', '2026-11-14')
        self.assertTrue(os.path.exists(out2['previous_report_moved_to']))
        self.assertIn('_old', out2['previous_report_moved_to'])

        # an earlier week
        out3, _ = run(SCRIPT, '--folder', self.folder, '--week', '2026-10-21', '--today', '2026-11-14')
        self.assertEqual(out3['week'], '2026-W43')
        self.assertEqual(out3['sent_this_week'], 1)  # Fabrikam, added 2026-10-20

    def test_bad_input(self):
        _, code = run(SCRIPT, '--folder', os.path.join(self.folder, 'missing'))
        self.assertEqual(code, 1)
        _, code = run(SCRIPT, '--folder', self.folder, '--week', 'last week')
        self.assertEqual(code, 1)


if __name__ == '__main__':
    unittest.main()
