"""Tests for internship-application/scripts/find_internships.py (made-up listings; the live test needs
JOBKIT_NETWORK_TESTS=1)."""
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, 'internship-application', 'scripts', 'find_internships.py')
TRACKER = os.path.join(ROOT, 'internship-application', 'scripts', 'tracker.py')
sys.path.insert(0, os.path.dirname(SCRIPT))
sys.path.insert(0, os.path.join(ROOT, 'lib'))

import find_internships as fi  # noqa: E402

try:
    import openpyxl  # noqa: F401
    HAVE_OPENPYXL = True
except ImportError:
    HAVE_OPENPYXL = False

TODAY = dt.date(2026, 11, 14)


def ts(days_ago):
    return int(dt.datetime(TODAY.year, TODAY.month, TODAY.day, 12, tzinfo=dt.timezone.utc).timestamp()) - days_ago * 86400


def listing(n, company, title, locations, **kw):
    x = {'source': 'Simplify', 'category': 'Software', 'company_name': company, 'id': f'id-{n}', 'title': title,
         'active': True, 'terms': ['Summer 2027'], 'date_updated': ts(1), 'date_posted': ts(1),
         'url': f'https://boards.greenhouse.io/{company.lower().replace(" ", "")}/jobs/{1000 + n}',
         'locations': locations, 'company_url': '', 'is_visible': True, 'sponsorship': 'Other',
         'degrees': ["Bachelor's"]}
    x.update(kw)
    return x


LISTINGS = [
    listing(1, 'Northwind Robotics', 'Software Engineering Intern', ['Austin, TX']),
    listing(2, 'Contoso', 'Data Science Intern', ['NYC'], category='AI/ML/Data', date_posted=ts(3)),
    listing(3, 'Fabrikam', 'Hardware Intern', ['Toronto, ON, Canada'], category='Hardware'),
    listing(4, 'Litware', 'Software Intern', ['Remote in USA'], sponsorship='Does Not Offer Sponsorship'),
    listing(5, 'Adatum', 'Software Intern', ['Arlington, VA'], sponsorship='U.S. Citizenship is Required'),
    listing(6, 'Closed Co', 'Software Intern', ['Boston, MA'], active=False),
    listing(7, 'Linky', 'Software Intern', ['Boston, MA'], url='https://www.linkedin.com/jobs/view/123'),
    listing(8, 'Old Term Inc', 'Software Intern', ['Boston, MA'], terms=['Summer 2026']),
    listing(9, 'Tailspin', 'Senior Software Intern', ['Seattle, WA'], date_posted=ts(40)),
    listing(10, 'Wingtip', 'PhD Research Intern', ['San Jose, CA'], degrees=['PhD']),
    listing(11, 'Northwind Robotics', 'Software Engineering Intern', ['Dallas, TX']),  # same company + title
    listing(12, 'Proseware', 'Software Intern', ['London, UK', 'Chicago, IL']),
]


class Helpers(unittest.TestCase):
    def test_exports(self):
        self.assertTrue(callable(fi.posting_keys) and callable(fi.role_key) and callable(fi.queued))
        self.assertEqual(fi.role_key('Acme, Inc.', 'Intern'), fi.role_key('ACME', 'intern'))

    def test_us_locations(self):
        for loc in ['Austin, TX', 'NYC', 'Remote in USA', 'California', 'United States', 'SF', 'Washington, DC',
                    'Arlington County, Arlington, VA']:
            self.assertTrue(fi.is_us_location(loc), loc)
        for loc in ['Toronto, ON, Canada', 'London, UK', 'Paris, France', 'Remote in Canada', 'Canada',
                    'Dubai - United Arab Emirates', 'Ontario, Canada']:
            self.assertFalse(fi.is_us_location(loc), loc)

    def test_degree_level(self):
        self.assertEqual(fi.degree_level("Bachelor's"), 'bachelor')
        self.assertEqual(fi.degree_level("Master's"), 'master')
        self.assertEqual(fi.degree_level('PhD'), 'phd')
        self.assertEqual(fi.degree_level('MBA'), 'mba')
        self.assertIsNone(fi.degree_level('banana'))

    def test_location_match(self):
        self.assertTrue(fi._location_match('Austin, TX', 'TX'))
        self.assertTrue(fi._location_match('Texas', 'TX'))
        self.assertTrue(fi._location_match('Austin, TX', 'Texas'))
        self.assertTrue(fi._location_match('NYC', 'New York'))
        self.assertTrue(fi._location_match('Remote in USA', 'remote'))
        self.assertTrue(fi._location_match('Toronto, ON, Canada', 'ON'))
        self.assertFalse(fi._location_match('Austin, TX', 'CA'))
        self.assertFalse(fi._location_match('Boston, MA', 'Austin'))


class Search(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='jobkit search ')
        self.folder = self.tmp.name
        self.src = os.path.join(self.folder, 'listings.json')
        with open(self.src, 'w', encoding='utf-8') as f:
            json.dump(LISTINGS, f)

    def tearDown(self):
        self.tmp.cleanup()

    def profile(self, **kw):
        with open(os.path.join(self.folder, 'profile.json'), 'w', encoding='utf-8') as f:
            json.dump(kw, f)

    def run_cli(self, *args):
        p = subprocess.run([sys.executable, SCRIPT, '--folder', self.folder, '--source', self.src,
                            '--today', TODAY.isoformat()] + list(args), capture_output=True, text=True, timeout=120)
        return json.loads(p.stdout), p.returncode

    def companies(self, out):
        return sorted(r['company'] for r in out['results'])

    def test_us_profile_defaults(self):
        self.profile(country='United States', needsSponsorship='no')
        out, code = self.run_cli()
        self.assertEqual(code, 0, out)
        self.assertEqual(out['found'], len(LISTINGS))
        self.assertEqual(self.companies(out), ['Adatum', 'Contoso', 'Litware', 'Northwind Robotics', 'Proseware',
                                               'Tailspin', 'Wingtip'])
        sk = out['skipped']
        self.assertEqual(sk['closed'], 1)
        self.assertEqual(sk['linkedin_or_no_link'], 1)
        self.assertEqual(sk['other_term'], 1)
        self.assertEqual(sk['outside_us'], 1)
        self.assertEqual(sk['duplicate'], 1)
        prose = [r for r in out['results'] if r['company'] == 'Proseware'][0]
        self.assertEqual(prose['location'], 'Chicago, IL')
        self.assertEqual(out['results'][0]['posted'], '2026-11-13')  # newest first
        for k in ('company', 'role', 'location', 'url', 'posted', 'sponsorship'):
            self.assertIn(k, out['results'][0])

    def test_include_abroad_and_non_us_profile(self):
        self.profile(country='United States')
        out, _ = self.run_cli('--include-abroad')
        self.assertIn('Fabrikam', self.companies(out))
        self.profile(country='Canada')
        out, _ = self.run_cli()
        self.assertIn('Fabrikam', self.companies(out))

    def test_sponsorship_and_citizenship(self):
        self.profile(country='United States', needsSponsorshipForInternship='yes')
        out, _ = self.run_cli()
        self.assertNotIn('Litware', self.companies(out))
        self.assertNotIn('Adatum', self.companies(out))
        out, _ = self.run_cli('--no-needs-sponsorship')
        self.assertIn('Litware', self.companies(out))
        out, _ = self.run_cli('--no-needs-sponsorship', '--no-citizenship')
        self.assertIn('Litware', self.companies(out))
        self.assertNotIn('Adatum', self.companies(out))

    def test_filters(self):
        self.profile(country='United States')
        out, _ = self.run_cli('--category', 'data')
        self.assertEqual(self.companies(out), ['Contoso'])
        out, _ = self.run_cli('--category', 'machine learning', '--category', 'hardware', '--include-abroad')
        self.assertEqual(self.companies(out), ['Contoso', 'Fabrikam'])
        out, _ = self.run_cli('--location', 'TX', '--location', 'Remote')
        self.assertEqual(self.companies(out), ['Litware', 'Northwind Robotics'])
        out, _ = self.run_cli('--location', 'New York')
        self.assertEqual(self.companies(out), ['Contoso'])
        out, _ = self.run_cli('--keyword', 'software', '--exclude-keyword', 'senior')
        self.assertNotIn('Tailspin', self.companies(out))
        self.assertNotIn('Contoso', self.companies(out))
        out, _ = self.run_cli('--degree', 'bachelor')
        self.assertNotIn('Wingtip', self.companies(out))
        out, _ = self.run_cli('--days', '7')
        self.assertNotIn('Tailspin', self.companies(out))
        out, _ = self.run_cli('--term', 'Summer 2026')
        self.assertEqual(self.companies(out), ['Old Term Inc'])
        out, _ = self.run_cli('--limit', '2')
        self.assertEqual(len(out['results']), 2)
        self.assertEqual(out['kept'], 7)

    def test_profile_term(self):
        self.profile(country='United States', internshipTerm='Summer 2026')
        out, _ = self.run_cli()
        self.assertEqual(out['term'], 'Summer 2026')
        self.assertEqual(self.companies(out), ['Old Term Inc'])

    def test_append_then_skip_queued(self):
        self.profile(country='United States')
        out, code = self.run_cli('--append', '--limit', '3')
        self.assertEqual(code, 0)
        self.assertEqual(len(out['appended']), 3)
        with open(os.path.join(self.folder, 'jobs.txt'), encoding='utf-8') as f:
            text = f.read()
        self.assertIn('# Northwind Robotics | Software Engineering Intern | Austin, TX | posted 2026-11-13', text)
        out, _ = self.run_cli()
        self.assertEqual(out['skipped']['already_in_jobs_txt'], 4)  # 3 links + the same company and title
        self.assertEqual(out['kept'], 4)

    @unittest.skipUnless(HAVE_OPENPYXL, 'openpyxl not installed')
    def test_skip_tracked(self):
        self.profile(country='United States')
        tr = os.path.join(self.folder, 'tracker.xlsx')
        subprocess.run([sys.executable, TRACKER, 'add', tr, '--company', 'Contoso Inc.', '--role', 'data science intern'],
                       capture_output=True, check=True)
        subprocess.run([sys.executable, TRACKER, 'add', tr, '--company', 'Someone Else', '--role', 'Other',
                        '--set', 'posting_url=https://boards.greenhouse.io/litware/jobs/1004?gh_src=x'],
                       capture_output=True, check=True)
        out, _ = self.run_cli()
        self.assertEqual(out['skipped']['already_tracked'], 2)
        self.assertNotIn('Contoso', self.companies(out))
        self.assertNotIn('Litware', self.companies(out))

    def test_bad_input(self):
        out, code = self.run_cli('--degree', 'wizard')
        self.assertEqual(code, 1)
        p = subprocess.run([sys.executable, SCRIPT, '--folder', os.path.join(self.folder, 'nope')],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 1)

    def test_network_failure_exit_6(self):
        p = subprocess.run([sys.executable, SCRIPT, '--folder', self.folder, '--source',
                            'http://127.0.0.1:9/listings.json'], capture_output=True, text=True, timeout=120)
        self.assertEqual(p.returncode, 6, p.stdout)


class Tidy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='jobkit tidy ')
        self.folder = self.tmp.name
        with open(os.path.join(self.folder, 'profile.json'), 'w') as f:
            json.dump({'country': 'United States'}, f)

    def tearDown(self):
        self.tmp.cleanup()

    @unittest.skipUnless(HAVE_OPENPYXL, 'openpyxl not installed')
    def test_tidy(self):
        tr = os.path.join(self.folder, 'tracker.xlsx')
        subprocess.run([sys.executable, TRACKER, 'add', tr, '--company', 'Contoso', '--role', 'Data Intern',
                        '--set', 'posting_url=https://jobs.lever.co/contoso/11111111-2222-3333-4444-555555555555'],
                       capture_output=True, check=True)
        subprocess.run([sys.executable, TRACKER, 'add', tr, '--company', 'Litware Inc', '--role', 'Software Intern'],
                       capture_output=True, check=True)
        lines = [
            '# my queue',
            'https://jobs.lever.co/contoso/11111111-2222-3333-4444-555555555555/apply?lever-source=x  # Contoso | Data Intern',
            'https://boards.greenhouse.io/litware/jobs/77  # Litware | Software Intern | Remote in USA | posted 2026-11-01',
            'https://boards.greenhouse.io/northwind/jobs/1  # Northwind | Robotics Intern | Austin, TX | posted 2026-11-10',
            'https://boards.greenhouse.io/northwind/jobs/1?gh_src=dup  # Northwind | Robotics Intern | Austin, TX',
            'https://boards.greenhouse.io/fabrikam/jobs/5  # Fabrikam | HW Intern | Toronto, ON, Canada | posted 2026-11-09',
            'https://boards.greenhouse.io/proseware/jobs/6  # Proseware | Intern | London, UK; Chicago, IL | posted 2026-11-09',
            'https://boards.greenhouse.io/adatum/jobs/8  # Adatum | Intern | Boston, MA',
            'https://boards.greenhouse.io/adatum/jobs/9',
            '',
            '# done',
            'https://boards.greenhouse.io/adatum/jobs/8  # applied earlier',
            'https://boards.greenhouse.io/old/jobs/2  # finished',
        ]
        path = os.path.join(self.folder, 'jobs.txt')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')
        p = subprocess.run([sys.executable, SCRIPT, '--folder', self.folder, '--tidy'], capture_output=True, text=True)
        out = json.loads(p.stdout)
        self.assertEqual(p.returncode, 0, out)
        reasons = {m['url']: m['reason'] for m in out['moved']}
        self.assertEqual(len(reasons), 5, reasons)
        self.assertIn('A0001', reasons['https://jobs.lever.co/contoso/11111111-2222-3333-4444-555555555555/apply?lever-source=x'])
        self.assertIn('A0002', reasons['https://boards.greenhouse.io/litware/jobs/77'])
        self.assertEqual(reasons['https://boards.greenhouse.io/northwind/jobs/1?gh_src=dup'], 'listed twice')
        self.assertIn('outside the US', reasons['https://boards.greenhouse.io/fabrikam/jobs/5'])
        self.assertIn('below # done', reasons['https://boards.greenhouse.io/adatum/jobs/8'])
        self.assertEqual(out['still_waiting'], 3)
        with open(path, encoding='utf-8') as f:
            new = f.read().splitlines()
        done_at = new.index('# done')
        waiting = [l for l in new[:done_at] if l.startswith('http')]
        self.assertEqual([l.split()[0] for l in waiting], ['https://boards.greenhouse.io/northwind/jobs/1',
                                                           'https://boards.greenhouse.io/proseware/jobs/6',
                                                           'https://boards.greenhouse.io/adatum/jobs/9'])
        self.assertEqual(new[0], '# my queue')
        self.assertEqual(len([l for l in new if l.startswith('http')]), 10)  # nothing lost
        self.assertTrue(any('Fabrikam | HW Intern | Toronto, ON, Canada | posted 2026-11-09 | outside the US' in l
                            for l in new[done_at:]))
        # running again moves nothing
        p = subprocess.run([sys.executable, SCRIPT, '--folder', self.folder, '--tidy'], capture_output=True, text=True)
        self.assertEqual(json.loads(p.stdout)['moved'], [])

    def test_tidy_without_queue(self):
        p = subprocess.run([sys.executable, SCRIPT, '--folder', self.folder, '--tidy'], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0)
        self.assertEqual(json.loads(p.stdout)['waiting'], 0)


@unittest.skipUnless(os.environ.get('JOBKIT_NETWORK_TESTS') == '1', 'set JOBKIT_NETWORK_TESTS=1 for network tests')
class Live(unittest.TestCase):
    def test_live_list(self):
        with tempfile.TemporaryDirectory(prefix='jobkit live ') as folder:
            with open(os.path.join(folder, 'profile.json'), 'w') as f:
                json.dump({'country': 'United States'}, f)
            p = subprocess.run([sys.executable, SCRIPT, '--folder', folder, '--limit', '5', '--append'],
                               capture_output=True, text=True, timeout=300)
            out = json.loads(p.stdout)
            self.assertEqual(p.returncode, 0, out)
            self.assertGreater(out['found'], 100)
            self.assertTrue(out['results'])
            for r in out['results']:
                self.assertTrue(r['url'].startswith('http'))
                self.assertNotIn('linkedin.com', r['url'])
            self.assertEqual(len(out['appended']), len(out['results']))


if __name__ == '__main__':
    unittest.main()
