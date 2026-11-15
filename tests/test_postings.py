"""Tests for fetch_posting.py and jobkit.postings / eligibility / redflags.

Offline tests use small fixtures in tests/fixtures/postings/ (trimmed copies of real public postings).
Network tests run only with JOBKIT_NETWORK_TESTS=1.

    python3 -m unittest discover -s tests
    JOBKIT_NETWORK_TESTS=1 python3 -m unittest tests.test_postings
"""
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'lib'))
SCRIPTS = os.path.join(ROOT, 'internship-application', 'scripts')
SCRIPT = os.path.join(SCRIPTS, 'fetch_posting.py')
FIX = os.path.join(HERE, 'fixtures', 'postings')

from jobkit import postings, eligibility, redflags, queue  # noqa: E402

NETWORK = os.environ.get('JOBKIT_NETWORK_TESTS') == '1'


def fixture(name):
    with open(os.path.join(FIX, name), encoding='utf-8') as f:
        return f.read()


class FakeFetcher:
    """Answers requests from fixtures, by URL pattern."""

    def __init__(self, routes, redirects=None):
        self.routes, self.redirects, self.seen = routes, redirects or {}, []
        self.requests = self.answered = self.network_errors = 0

    def _find(self, url):
        self.seen.append(url)
        for pat, name in self.routes.items():
            if re.search(pat, url):
                return fixture(name)
        raise postings.FetchError(f'no route for {url}', 'notfound', 404)

    def json(self, url, data=None, headers=None):
        if data and 'ApiOrganization' in json.dumps(data):
            return {'data': {'organization': {'name': 'Ramp'}}}
        return json.loads(self._find(url))

    def html(self, url):
        return self._find(url)

    def request(self, url, accept='application/json', data=None, headers=None, follow=True):
        return 200, {}, self._find(url)

    def location(self, url):
        self.seen.append(url)
        for pat, loc in self.redirects.items():
            if re.search(pat, url):
                return loc
        return None


PROFILE_F1 = {'firstName': 'Alex', 'lastName': 'Tremblay', 'authCountry': 'United States',
              'workAuthDetails': 'F-1 student, eligible for CPT', 'needsSponsorship': 'yes',
              'needsSponsorshipForInternship': 'no', 'classStanding': 'third year',
              'education': [{'school': 'Example University', 'degree': 'Bachelor of Science', 'end': '2028-05'}]}
PROFILE_F1_FINAL = dict(PROFILE_F1, classStanding='senior', needsSponsorshipForInternship='',
                        education=[{'degree': 'BSc', 'end': '2027-05'}])
PROFILE_US_CITIZEN = {'authCountry': 'US', 'workAuthDetails': 'US citizen', 'needsSponsorship': 'no',
                      'education': [{'degree': 'BS Computer Science'}]}
PROFILE_CA_STUDY = {'authCountry': 'Canada', 'workAuthDetails': 'Study permit with co-op work permit',
                    'needsSponsorship': 'no', 'education': [{'degree': 'BEng'}]}
PROFILE_CA_CITIZEN = {'authCountry': 'Canada', 'workAuthDetails': 'Canadian citizen', 'needsSponsorship': 'no'}
PROFILE_CA_UNKNOWN = {'authCountry': 'Canada', 'education': [{'degree': 'BEng'}]}
PROFILE_UK_VISA = {'authCountry': 'UK', 'workAuthDetails': 'Student visa', 'needsSponsorship': 'yes', 'enrolled': 'no',
                   'education': [{'degree': 'MSc'}]}
PROFILE_UK_SETTLED = {'authCountry': 'UK', 'workAuthDetails': 'British citizen', 'needsSponsorship': 'no'}


# ---- links ---------------------------------------------------------------------------------------------------------

class DetectTests(unittest.TestCase):
    def test_systems(self):
        cases = {
            'https://job-boards.greenhouse.io/stripe/jobs/8194287': ('greenhouse', {'board': 'stripe', 'id': '8194287'}),
            'https://boards.greenhouse.io/embed/job_app?for=acme&token=123456': ('greenhouse', {'board': 'acme', 'id': '123456'}),
            'https://stripe.com/jobs/search?gh_jid=8194287': ('greenhouse', {'board': None, 'id': '8194287'}),
            'https://jobs.lever.co/palantir/6ed76ce8-4156-4b60-b120-403538bd66cd/apply':
                ('lever', {'company': 'palantir', 'id': '6ed76ce8-4156-4b60-b120-403538bd66cd'}),
            'https://jobs.ashbyhq.com/ramp/acf6b28d-767f-483f-8ff2-114620cd7e04':
                ('ashby', {'org': 'ramp', 'id': 'acf6b28d-767f-483f-8ff2-114620cd7e04'}),
            'https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/Switzerland-Zurich/GPU-Compiler-Intern_JR2029779':
                ('workday', {'tenant': 'nvidia', 'site': 'NVIDIAExternalCareerSite', 'slug': 'GPU-Compiler-Intern_JR2029779'}),
            'https://wd3.myworkdaysite.com/en-US/recruiting/acme/External/job/Toronto/Analyst_R-1234':
                ('workday', {'tenant': 'acme', 'site': 'External', 'slug': 'Analyst_R-1234'}),
            'https://jobs.smartrecruiters.com/ServiceNow/744000161596339-senior-software-engineer':
                ('smartrecruiters', {'company': 'ServiceNow', 'id': '744000161596339'}),
            'https://careers-gdms.icims.com/jobs/75487/intern-engineer/job': ('icims', {}),
            'https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/job/210690282':
                ('oracle', {'site': 'CX_1001', 'id': '210690282'}),
            'https://ats.rippling.com/rippling/jobs/ef0b7266-678c-4a23-a439-1a5e7362b604':
                ('rippling', {'board': 'rippling', 'id': 'ef0b7266-678c-4a23-a439-1a5e7362b604'}),
            'https://www.jobbank.gc.ca/jobsearch/jobposting/50723978': ('jobbank', {'id': '50723978'}),
            'https://www.linkedin.com/jobs/view/4000000000': ('linkedin', {}),
            'https://careers.example.com/job/42': ('other', {}),
        }
        for url, (system, want) in cases.items():
            got_system, info = postings.detect(url)
            self.assertEqual(got_system, system, url)
            for k, v in want.items():
                self.assertEqual(info.get(k), v, f'{url}: {k}')


# ---- each application system (offline fixtures) --------------------------------------------------------------------

class SystemTests(unittest.TestCase):
    def test_greenhouse(self):
        f = FakeFetcher({r'boards-api\.greenhouse\.io/v1/boards/stripe/jobs/8194287': 'greenhouse_job.json'})
        p = postings.fetch('https://job-boards.greenhouse.io/stripe/jobs/8194287', f)
        self.assertEqual(p['error'], '')
        self.assertEqual((p['company'], p['role'], p['location']), ('Stripe', 'Data Analyst, Intern', 'Toronto'))
        self.assertEqual(p['posted'], '2026-10-01')
        self.assertTrue(p['form_published'])
        labels = [q['label'] for q in p['questions']]
        self.assertIn('Resume/CV', labels)
        sponsor = next(q for q in p['questions'] if 'sponsorship' in q['label'])
        self.assertEqual(sponsor['type'], 'yes/no')
        self.assertEqual(postings.cover_letter(p)[0], 'none')
        written = postings.written_questions(p['questions'])
        self.assertTrue(any('data-related project' in w for w in written))
        self.assertFalse(any('employer' in w.lower() for w in written))
        self.assertNotIn('<', p['description'][:200])

    def test_greenhouse_embedded_gh_jid(self):
        f = FakeFetcher({r'boards-api\.greenhouse\.io/v1/boards/stripe/jobs/8194287': 'greenhouse_job.json'},
                        {r'embed/job_app\?token=8194287': 'https://job-boards.greenhouse.io/embed/job_app?for=stripe&token=8194287'})
        p = postings.fetch('https://stripe.com/jobs/search?gh_jid=8194287', f)
        self.assertEqual(p['error'], '')
        self.assertEqual(p['company'], 'Stripe')
        self.assertEqual(p['system'], 'greenhouse')

    def test_lever(self):
        f = FakeFetcher({r'api\.lever\.co/v0/postings/palantir/': 'lever_posting.json',
                         r'jobs\.lever\.co/palantir/.*/apply': 'lever_apply.html'})
        p = postings.fetch('https://jobs.lever.co/palantir/6ed76ce8-4156-4b60-b120-403538bd66cd', f)
        self.assertEqual(p['error'], '')
        self.assertEqual(p['company'], 'Palantir Technologies')
        self.assertFalse(p['check_company'])
        self.assertEqual(p['role'], 'Administrative Business Partner')
        self.assertIn('hybrid', p['location'])
        self.assertTrue(p['posted'].startswith('2026-'))
        req = {q['label']: q['required'] for q in p['questions']}
        self.assertTrue(req['Resume/CV'])
        self.assertFalse(req['Phone'])
        self.assertIn('Why do you want to work at Palantir?', postings.written_questions(p['questions']))
        status, quote = postings.cover_letter(p)
        self.assertEqual(status, 'optional')
        self.assertIn('cover letter', quote)

    def test_ashby(self):
        f = FakeFetcher({r'non-user-graphql\?op=ApiJobPosting': 'ashby_job.json'})
        p = postings.fetch('https://jobs.ashbyhq.com/ramp/acf6b28d-767f-483f-8ff2-114620cd7e04', f)
        self.assertEqual(p['error'], '')
        self.assertEqual((p['company'], p['role']), ('Ramp', 'Software Engineering Intern, Backend'))
        self.assertEqual(p['pay'], '$12.5K per month')
        self.assertIn('on-site', p['location'])
        types = {q['label']: q['type'] for q in p['questions']}
        self.assertEqual(types['Resume'], 'file')
        self.assertEqual(types['Requesting visa sponsorship?'], 'yes/no')
        self.assertEqual(postings.written_questions(p['questions']), ['Share something you’ve built that you’re proud of.'])
        self.assertEqual(postings.cover_letter(p)[0], 'none')

    def test_workday(self):
        f = FakeFetcher({r'/wday/cxs/nvidia/NVIDIAExternalCareerSite/job/GPU-Compiler-Intern_JR2029779': 'workday_job.json'})
        p = postings.fetch('https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/Switzerland-Zurich/'
                           'GPU-Compiler-Intern_JR2029779', f)
        self.assertEqual(p['error'], '')
        self.assertEqual(p['company'], 'NVIDIA Switzerland AG')
        self.assertEqual(p['role'], 'GPU Compiler Intern')
        self.assertEqual(p['posted'], '2026-11-11')
        self.assertEqual(postings.cover_letter(p)[0], 'none')

    def test_smartrecruiters(self):
        f = FakeFetcher({r'api\.smartrecruiters\.com/v1/companies/ServiceNow/postings/744000161596339': 'smartrecruiters_job.json'})
        p = postings.fetch('https://jobs.smartrecruiters.com/ServiceNow/744000161596339-senior-software-engineer', f)
        self.assertEqual(p['error'], '')
        self.assertEqual(p['company'], 'ServiceNow')
        self.assertIn('Santa Clara', p['location'])
        self.assertIn('hybrid', p['location'])
        self.assertEqual(postings.cover_letter(p)[0], 'unknown')

    def test_oracle(self):
        f = FakeFetcher({r'recruitingCEJobRequisitionDetails': 'oracle_job.json'})
        p = postings.fetch('https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/job/210690282', f)
        self.assertEqual(p['error'], '')
        self.assertEqual(p['role'], '2027 Markets Summer Analyst Program - Research')
        self.assertIn('100,000', p['pay'])
        self.assertTrue(p['check_company'])
        self.assertIn('siteNumber=CX_1001', f.seen[0])

    def test_rippling(self):
        f = FakeFetcher({r'api\.rippling\.com/platform/api/ats/v1/board/rippling/jobs/': 'rippling_job.json'})
        p = postings.fetch('https://ats.rippling.com/rippling/jobs/ef0b7266-678c-4a23-a439-1a5e7362b604', f)
        self.assertEqual(p['error'], '')
        self.assertEqual(p['company'], 'Rippling')
        self.assertEqual(postings.cover_letter(p)[0], 'optional')
        knock = next(q for q in p['questions'] if 'sponsorship' in q['label'].lower())
        self.assertTrue(knock['required'])
        self.assertEqual(knock['type'], 'yes/no')

    def test_jobbank(self):
        f = FakeFetcher({r'jobbank\.gc\.ca/jobsearch/jobposting/50723978': 'jobbank_direct.html'})
        p = postings.fetch('https://www.jobbank.gc.ca/jobsearch/jobposting/50723978', f)
        self.assertEqual(p['error'], '')
        self.assertEqual((p['company'], p['role']), ('The Roaring Rolls', 'cook'))
        self.assertEqual(p['location'], 'Canmore, AB (on-site)')
        self.assertEqual(p['posted'], '2026-11-13')
        self.assertTrue(p['deadline'].startswith('2026-12-01'))
        self.assertIn('37.35', p['pay'])
        self.assertIn('NOC 2021: 63200', p['description'])
        self.assertIn('Prepare and cook complete meals', p['description'])
        self.assertNotIn('<div', p['description'])
        self.assertEqual(postings.cover_letter(p)[0], 'unknown')
        # "who can apply" includes temporary residents: no skip for a study-permit holder
        self.assertEqual(eligibility.screen(p['description'], PROFILE_CA_STUDY, p['role'], p['location'])['screen'], 'ok')
        self.assertEqual(redflags.red_flags(p['description'], company=p['company'], role=p['role'], system='jobbank'), [])

    def test_icims_jsonld(self):
        f = FakeFetcher({r'icims\.com/jobs/75487/intern-engineer/job\?in_iframe=1': 'icims_jsonld.html'})
        p = postings.fetch('https://careers-gdms.icims.com/jobs/75487/intern-engineer/job', f)
        self.assertEqual(p['error'], '')
        self.assertEqual(p['company'], 'General Dynamics Mission Systems, Inc')
        self.assertEqual(p['role'], 'Intern Engineer')
        self.assertIn('Pittsfield', p['location'])
        self.assertEqual(p['deadline'], '')        # validThrough a year away is an automatic expiry, not a deadline
        self.assertNotIn('0.00', p['pay'])
        r = eligibility.screen(p['description'], PROFILE_F1, p['role'], p['location'])
        self.assertEqual(r['screen'], 'skip')
        self.assertTrue(any('citizenship' in w for w in r['why']))
        self.assertEqual(eligibility.screen(p['description'], PROFILE_US_CITIZEN, p['role'], p['location'])['screen'], 'ok')

    def test_linkedin_never_fetched(self):
        f = FakeFetcher({})
        p = postings.fetch('https://www.linkedin.com/jobs/view/4000000000', f)
        self.assertEqual(p['system'], 'linkedin')
        self.assertTrue(p['error'])
        self.assertIn('paste', p['hint'].lower())
        self.assertEqual(f.seen, [])

    def test_closed_posting_gives_hint(self):
        f = FakeFetcher({})
        p = postings.fetch('https://jobs.lever.co/acme/00000000-0000-0000-0000-000000000000', f)
        self.assertTrue(p['error'])
        self.assertIn('browser', p['hint'])


# ---- cover letter, pay, text helpers -------------------------------------------------------------------------------

class HelperTests(unittest.TestCase):
    def _p(self, desc, field=None, form=False, system='other'):
        p = postings.new_posting('https://example.com/job', system)
        p.update(description=desc, cover_letter_field=field, form_published=form)
        return p

    def test_cover_letter_rules(self):
        self.assertEqual(postings.cover_letter(self._p('Great team.', 'required', True))[0], 'required')
        self.assertEqual(postings.cover_letter(self._p('Great team.', 'optional', True))[0], 'optional')
        s, q = postings.cover_letter(self._p('Please submit your resume and a cover letter explaining your interest.'))
        self.assertEqual(s, 'asked')
        self.assertIn('cover letter', q)
        s, q = postings.cover_letter(self._p('No cover letter needed. Just apply!', 'optional', True))
        self.assertEqual(s, 'not wanted')
        self.assertEqual(postings.cover_letter(self._p('Please do not send a cover letter.'))[0], 'not wanted')
        self.assertEqual(postings.cover_letter(self._p('Great team.', None, True))[0], 'none')
        self.assertEqual(postings.cover_letter(self._p('Great team.', None, False, 'workday'))[0], 'none')
        self.assertEqual(postings.cover_letter(self._p('Great team.'))[0], 'unknown')

    def test_pay_from_text(self):
        self.assertEqual(postings.pay_from_text('The base salary range is $120,000 - $150,000 USD per year.'),
                         '$120,000 - $150,000 USD per year')
        self.assertEqual(postings.pay_from_text('We process $275B in annualized spend.'), '')
        self.assertEqual(postings.pay_from_text('Hourly rate: $25/hour'), '$25/hour')
        self.assertEqual(postings.pay_from_text('USD $0.00 - USD $0.00 /Yr.'), '')
        self.assertEqual(postings.pay_from_text('Salary: £30,000 - £35,000 per annum'), '£30,000 - £35,000 per annum')

    def test_dates_and_deadline(self):
        self.assertEqual(postings.iso_date('Posted on November 13, 2026'), '2026-11-13')
        self.assertEqual(postings.iso_date('2026-11-14T00:09:37.401Z'), '2026-11-14')
        self.assertEqual(postings.iso_date(1786469891368), '2026-08-11')
        self.assertIn('January 15, 2027', postings.deadline_from_text('Applications close on January 15, 2027 at noon.'))

    def test_from_text(self):
        p = postings.from_text('Junior Data Analyst at Maple Leaf Analytics\nLocation: Halifax, NS\n\nYou will build '
                               'dashboards. Please include a cover letter.', 'https://careers.example.com/jobs/77')
        self.assertEqual((p['role'], p['company'], p['location']), ('Junior Data Analyst', 'Maple Leaf Analytics', 'Halifax, NS'))
        q = postings.from_text('Data Analyst\nWe are hiring.', 'https://jobs.lever.co/mapleco/' + '1' * 8 + '-1111-1111-1111-' + '1' * 12)
        self.assertEqual(q['company'], 'Mapleco')
        self.assertTrue(q['check_company'])

    def test_markdown_format(self):
        f = FakeFetcher({r'boards-api\.greenhouse\.io/v1/boards/stripe/jobs/8194287': 'greenhouse_job.json'})
        p = postings.fetch('https://job-boards.greenhouse.io/stripe/jobs/8194287', f)
        md = postings.render_markdown(p, 'ok', [], [], postings.cover_letter(p))
        self.assertTrue(md.startswith('# Data Analyst, Intern at Stripe\n'))
        for field in ('Company', 'Role', 'URL', 'Location', 'Deadline', 'Pay', 'Posted', 'Application system',
                      'Cover letter', 'Screen', 'Red flags'):
            self.assertRegex(md, rf'(?m)^- {field}: .+$')
        self.assertIn('## Description', md)
        self.assertRegex(md, r'(?m)^- \[required\] Resume/CV \(file\)$')
        self.assertRegex(md, r'(?m)^- \[required\] Are you currently eligible to work in Canada\? \(yes/no; options: Yes, I am .+ \| No, .+\)$')
        # rank_jobs.py reads it
        sys.path.insert(0, SCRIPTS)
        try:
            import rank_jobs
        except Exception:
            return
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'job-posting.md')
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(md)
            got = rank_jobs.posting_from_md(path)
        self.assertEqual((got['title'], got['company'], got['location'], got['posted']),
                         ('Data Analyst, Intern', 'Stripe', 'Toronto', '2026-10-01'))


# ---- eligibility ---------------------------------------------------------------------------------------------------

class EligibilityTests(unittest.TestCase):
    def s(self, text, profile, role='Software Engineering Intern', loc='Austin, TX'):
        return eligibility.screen(text, profile, role, loc)['screen']

    def test_us_rules(self):
        self.assertEqual(self.s('Applicants must be U.S. citizens.', PROFILE_F1), 'skip')
        self.assertEqual(self.s('Applicants must be U.S. citizens.', PROFILE_US_CITIZEN), 'ok')
        self.assertEqual(self.s('Must be a U.S. citizen or authorized to work in the United States.', PROFILE_F1), 'ok')
        self.assertEqual(self.s('We are unable to consider candidates on F-1 OPT or CPT for this role.', PROFILE_F1), 'skip')
        self.assertEqual(self.s('Candidates on F-1 OPT/CPT are welcome to apply.', PROFILE_F1), 'ok')
        self.assertEqual(self.s('Due to ITAR, applicants must be U.S. persons.', PROFILE_F1), 'skip')
        self.assertEqual(self.s('US citizenship or permanent residence (green card) is required.', PROFILE_F1), 'skip')
        self.assertEqual(self.s('Ability to obtain a Secret security clearance is required.', PROFILE_F1, 'Engineer'), 'skip')
        self.assertEqual(self.s('Ability to obtain a Secret security clearance is required.', PROFILE_US_CITIZEN, 'Engineer'), 'ok')
        self.assertEqual(self.s('US citizenship is preferred.', PROFILE_F1), 'check')
        self.assertEqual(self.s('Some positions may require U.S. citizenship.', PROFILE_F1), 'check')

    def test_sponsorship_and_students(self):
        text = 'We do not sponsor visas now or in the future.'
        self.assertEqual(self.s(text, PROFILE_F1), 'ok')              # internship + needs no sponsorship for it
        self.assertEqual(self.s(text, PROFILE_F1_FINAL), 'skip')      # final year, needs sponsorship
        below = dict(PROFILE_F1, needsSponsorshipForInternship='')
        self.assertEqual(self.s(text, below), 'check')                # below final year: never skipped on sponsorship
        self.assertEqual(self.s(text, PROFILE_US_CITIZEN), 'ok')
        self.assertEqual(self.s('Will you now or in the future require visa sponsorship?', PROFILE_F1_FINAL), 'ok')

    def test_degree_level(self):
        self.assertEqual(self.s("Must be currently pursuing a Master's or PhD in Computer Science.", PROFILE_F1), 'skip')
        self.assertEqual(self.s("Currently pursuing a Bachelor's, Master's or PhD.", PROFILE_F1), 'ok')
        self.assertEqual(self.s("PhD students preferred.", PROFILE_F1), 'ok')

    def test_canada(self):
        text = 'Applicants must be Canadian citizens or permanent residents.'
        self.assertEqual(self.s(text, PROFILE_CA_STUDY, 'Co-op Student', 'Ottawa, ON'), 'skip')
        self.assertEqual(self.s(text, PROFILE_CA_UNKNOWN, 'Co-op Student', 'Ottawa, ON'), 'check')
        self.assertEqual(self.s(text, PROFILE_CA_CITIZEN, 'Co-op Student', 'Ottawa, ON'), 'ok')
        self.assertEqual(self.s('Open to Canadian citizens, permanent residents or those legally entitled to work in Canada.',
                                PROFILE_CA_STUDY, 'Co-op', 'Toronto, ON'), 'ok')
        self.assertEqual(self.s('You can apply if you are: a Canadian citizen; a permanent resident of Canada.',
                                PROFILE_CA_STUDY, 'cook', 'Banff, AB'), 'skip')
        self.assertEqual(self.s('Preference will be given to Canadian citizens and permanent residents.',
                                PROFILE_CA_STUDY, 'Student', 'Ottawa, ON'), 'check')

    def test_uk(self):
        loc = 'London, UK'
        self.assertEqual(self.s('You must have the right to work in the UK; we cannot offer visa sponsorship.',
                                PROFILE_UK_VISA, 'Graduate Analyst', loc), 'skip')
        self.assertEqual(self.s('You must have the right to work in the UK.', PROFILE_UK_VISA, 'Graduate Analyst', loc), 'check')
        self.assertEqual(self.s('You must already have the right to work in the UK.', PROFILE_UK_VISA, 'Graduate Analyst', loc), 'skip')
        self.assertEqual(self.s('You must have the right to work in the UK.', PROFILE_UK_SETTLED, 'Graduate Analyst', loc), 'ok')
        r = eligibility.screen('Visa sponsorship is available for this role.', PROFILE_UK_VISA, 'Analyst', loc)
        self.assertEqual(r['screen'], 'ok')
        self.assertTrue(any('note' in w for w in r['why']))

    def test_boilerplate_ignored(self):
        text = ('We are an equal opportunity employer and consider all applicants without regard to citizenship status '
                'or national origin.')
        self.assertEqual(self.s(text, PROFILE_F1), 'ok')

    def test_no_profile_never_skips_silently(self):
        r = eligibility.screen('Applicants must be U.S. citizens.', None, 'Intern', 'Austin, TX')
        self.assertEqual(r['screen'], 'check')
        self.assertTrue(r['check'])

    def test_user_status(self):
        st = eligibility.user_status(PROFILE_F1)
        self.assertTrue(st['f1'])
        self.assertEqual(st['degree_level'], 'undergraduate')
        self.assertFalse(st['final_year'])
        st = eligibility.user_status(PROFILE_CA_CITIZEN)
        self.assertEqual(st['citizen_of'], ['CA'])


# ---- red flags -----------------------------------------------------------------------------------------------------

FILLER = (' You will analyse data, prepare reports and work with the team. Requirements include strong communication '
          'skills and attention to detail. Responsibilities cover planning, testing and documentation.') * 3


class RedFlagTests(unittest.TestCase):
    def flags(self, text, **kw):
        return [f['flag'] for f in redflags.red_flags(text + FILLER, **kw)]

    def test_positives(self):
        cases = [
            ('A refundable training fee of $150 is required before you start.', 'pay'),
            ('You will receive a cheque to purchase your home office equipment from our approved vendor.', 'cheque'),
            ('Please contact our hiring manager on Telegram: @hrdesk to schedule your interview.', 'chat app'),
            ('Interviews are conducted via WhatsApp only.', 'chat app'),
            ('Salary will be paid in Bitcoin every week.', 'crypto'),
            ('No interview needed, you will be hired immediately.', 'interview'),
            ("Send a copy of your driver's license and your SSN with your application.", 'SIN/SSN'),
            ('Please respond within 24 hours to secure your position.', 'pressure'),
        ]
        for text, word in cases:
            got = self.flags(text, company='Acme Corp', role='Analyst')
            self.assertTrue(any(word.lower() in g.lower() for g in got), f'{text} -> {got}')

    def test_personal_email(self):
        self.assertTrue(self.flags('Send your resume to acme.hr.dept@gmail.com today.', company='Acme Corp'))
        self.assertTrue(self.flags('Questions? Write to jane.doe@outlook.com', company='Acme', system='greenhouse'))
        # a small business on Job Bank using its own gmail is normal
        self.assertEqual(self.flags('Send your resume to roaringrolls@gmail.com', company='The Roaring Rolls', system='jobbank'), [])

    def test_high_pay_unskilled(self):
        got = redflags.red_flags('Data entry clerk wanted, no experience. Earn $45/hour from home.', role='Data Entry Clerk')
        self.assertIn('pay far above normal for unskilled entry-level work', [g['flag'] for g in got])
        self.assertFalse(self.flags('Pay: $45/hour.', role='Senior Software Engineer'))
        self.assertFalse(self.flags('Pay: $22/hour.', role='Data Entry Clerk'))
        got = redflags.red_flags('Virtual assistant, beginners welcome, £35 per hour.' + FILLER, role='Virtual Assistant')
        self.assertTrue(any('pay far above' in g['flag'] for g in got))

    def test_short_vague(self):
        self.assertIn('very short, vague description', [g['flag'] for g in redflags.red_flags('Work from home. Great pay. Apply now.')])

    def test_negatives(self):
        safe = [
            'We will never ask you to pay a fee or for your bank details during the hiring process.',
            'There is no application fee.',
            'Employees are paid biweekly by direct deposit or check.',
            'Experience building Telegram bots and WhatsApp Business API integrations is a plus.',
            "Must have a valid driver's license.",
            'A background check and SSN are collected for Form I-9 after an offer is accepted.',
            'We are hiring immediately. Immediate start available.',
            'Our signal processing team builds radar systems and sends data through Signal pipelines.',
            'Company-provided laptop and equipment; we reimburse your home office setup.',
            'Beware of recruitment fraud: we never ask candidates to buy equipment or pay fees.',
            'Applications close within 2 weeks of posting.',
        ]
        for text in safe:
            self.assertEqual(self.flags(text, company='Acme Corp', role='Software Engineer', system='greenhouse'), [], text)

    def test_quote_present(self):
        got = redflags.red_flags('Pay the $99 registration fee to start.' + FILLER)
        self.assertIn('registration fee', got[0]['quote'])


# ---- the command line ----------------------------------------------------------------------------------------------

def run_cli(args):
    r = subprocess.run([sys.executable, SCRIPT] + args, capture_output=True, text=True, encoding='utf-8')
    return r.returncode, json.loads(r.stdout)


def run_main(args):
    """Run fetch_posting.main() in this process (so postings.fetch can be patched). Returns (code, json)."""
    sys.path.insert(0, SCRIPTS)
    import fetch_posting
    buf = io.StringIO()
    with mock.patch.object(sys, 'argv', ['fetch_posting.py'] + args), contextlib.redirect_stdout(buf):
        try:
            fetch_posting.main()
            code = 0
        except SystemExit as e:
            code = e.code
    return code, json.loads(buf.getvalue())


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='jobkit test ')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, name, content):
        path = os.path.join(self.tmp, name)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content if isinstance(content, str) else json.dumps(content))
        return path

    def test_text_mode(self):
        desc = self.write('pasted.txt', 'Software Developer Co-op at Harbour Robotics\nLocation: Halifax, NS\n\n'
                          'Build robot software in Python. Applicants must be Canadian citizens or permanent residents. '
                          'Please include a cover letter with your resume.' + FILLER)
        prof = self.write('profile.json', PROFILE_CA_STUDY)
        out = os.path.join(self.tmp, 'out dir')
        code, d = run_cli(['--text', desc, '--url', 'https://careers.harbour.example/jobs/12', '--out-dir', out, '--profile', prof])
        self.assertEqual(code, 0, d)
        p = d['postings'][0]
        self.assertEqual((p['company'], p['role']), ('Harbour Robotics', 'Software Developer Co-op'))
        self.assertEqual(p['screen'], 'skip')
        self.assertEqual(p['cover_letter'], 'asked')
        self.assertTrue(os.path.isfile(p['file']))
        self.assertTrue(os.path.basename(p['file']).startswith('01 Harbour Robotics - Software Developer Co-op'))
        with open(p['file'], encoding='utf-8') as fh:
            md = fh.read()
        self.assertIn('- Screen: skip', md)
        # running again keeps the old file in _old/
        run_cli(['--text', desc, '--url', 'https://careers.harbour.example/jobs/12', '--out-dir', out])
        self.assertTrue(os.listdir(os.path.join(out, '_old')))

    def test_bad_input(self):
        code, d = run_cli(['--out-dir', self.tmp])
        self.assertEqual(code, 1)
        self.assertFalse(d['ok'])
        code, d = run_cli(['not-a-link', '--out-dir', self.tmp])
        self.assertEqual(code, 1)

    def test_network_blocked(self):
        code, d = run_cli(['http://127.0.0.1:9/jobs/1', '--out-dir', self.tmp])
        self.assertEqual(code, 2)
        self.assertTrue(d['network_blocked'])
        self.assertTrue(d['postings'][0]['hint'])

    def test_linkedin_cli(self):
        code, d = run_cli(['https://www.linkedin.com/jobs/view/4000000000', '--out-dir', self.tmp])
        self.assertEqual(code, 2)
        self.assertEqual(d['postings'][0]['system'], 'linkedin')
        self.assertFalse(d['network_blocked'])

    def test_jobs_move_skips_and_tracker(self):
        gh = 'https://job-boards.greenhouse.io/stripe/jobs/8194287'
        other = 'https://job-boards.greenhouse.io/acme/jobs/1111'
        jobs = self.write('jobs.txt', f'{gh}  # Stripe | Data Analyst, Intern\n{other}\n\n# done\n')
        prof = self.write('profile.json', PROFILE_F1)

        real_fetch = postings.fetch

        def fake_fetch(url, f=None):
            if 'stripe' in url:
                return real_fetch(url, FakeFetcher({r'stripe/jobs/8194287': 'greenhouse_job.json'}))
            p = postings.new_posting(url, 'greenhouse')
            p.update(company='Acme Corp', role='Security Intern', location='Arlington, VA', form_published=True,
                     description='Applicants must be U.S. citizens due to government contract requirements.' + FILLER)
            return p

        tracker = None
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = 'Applications'
            ws.append(['ID', 'Date added', 'Company', 'Role', 'Term', 'Location', 'Deadline', 'Status', 'Status updated',
                       'Next step', 'Interview date', 'Posting', 'Folder', 'Resume file', 'Gaps', 'Notes'])
            ws.append(['A0001', '2026-10-02', 'Stripe, Inc.', 'Data Analyst, Intern', '', 'Toronto', '', 'Submitted',
                       '2026-10-02', '', '', 'Open posting', '', '', '', ''])
            ws.cell(row=2, column=12).hyperlink = gh + '?gh_src=abc'
            tracker = os.path.join(self.tmp, 'tracker.xlsx')
            wb.save(tracker)
        except ImportError:
            pass
        args = ['--jobs', jobs, '--out-dir', os.path.join(self.tmp, 'out'), '--profile', prof, '--move-skips']
        if tracker:
            args += ['--tracker', tracker]
        with mock.patch.object(postings, 'fetch', side_effect=fake_fetch):
            code, d = run_main(args)
        self.assertEqual(code, 0, d)
        by = {p['url']: p for p in d['postings']}
        self.assertEqual(by[other]['screen'], 'skip')
        self.assertEqual(by[gh]['screen'], 'ok')
        self.assertEqual(d['moved_below_done'], [other])
        q = queue.read_queue(jobs)
        self.assertEqual([e['url'] for e in q['waiting']], [gh])
        self.assertIn('skipped: US citizenship required', q['done'][0]['note'])
        if tracker:
            self.assertTrue(by[gh]['same_posting_in_tracker'])
            self.assertEqual(by[gh]['in_tracker'][0]['id'], 'A0001')
            self.assertFalse(by[other]['in_tracker'])


# ---- live (network) ------------------------------------------------------------------------------------------------

@unittest.skipUnless(NETWORK, 'set JOBKIT_NETWORK_TESTS=1 to run network tests')
class NetworkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = postings.Fetcher()

    def test_greenhouse_live(self):
        jobs = self.f.json('https://boards-api.greenhouse.io/v1/boards/stripe/jobs')['jobs']
        p = postings.fetch(f"https://job-boards.greenhouse.io/stripe/jobs/{jobs[0]['id']}", self.f)
        self.assertEqual(p['error'], '')
        self.assertTrue(p['role'] and p['description'] and p['questions'])

    def test_lever_live(self):
        jobs = self.f.json('https://api.lever.co/v0/postings/palantir?mode=json&limit=1')
        p = postings.fetch(jobs[0]['hostedUrl'], self.f)
        self.assertEqual(p['error'], '')
        self.assertTrue(p['company'] and p['questions'])

    def test_ashby_live(self):
        jobs = self.f.json('https://api.ashbyhq.com/posting-api/job-board/ramp')['jobs']
        p = postings.fetch(jobs[0]['jobUrl'], self.f)
        self.assertEqual(p['error'], '')
        self.assertEqual(p['company'], 'Ramp')

    def test_jobbank_live(self):
        page = self.f.request('https://www.jobbank.gc.ca/jobsearch/jobsearch?searchstring=cook&sort=D&fsrc=16',
                              accept='text/html')[2]
        m = re.search(r'/jobsearch/jobposting/(\d+)', page)
        self.assertTrue(m)
        p = postings.fetch('https://www.jobbank.gc.ca/jobsearch/jobposting/' + m.group(1), self.f)
        self.assertEqual(p['error'], '')
        self.assertIn('NOC 2021:', p['description'])


if __name__ == '__main__':
    unittest.main()
