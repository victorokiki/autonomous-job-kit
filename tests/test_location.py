"""Tests for lib/jobkit/location.py: the resume and letter location line (made-up data only)."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'lib'))
sys.path.insert(0, os.path.join(ROOT, 'internship-application', 'scripts'))

from jobkit import location, postings  # noqa: E402

ME = {'city': 'Surrey', 'state': 'BC', 'willingToRelocate': 'yes'}


class LocationLine(unittest.TestCase):
    def line(self, loc, profile=ME):
        return location.location_line(profile, loc)['line']

    def test_other_city_gets_relocation_note(self):
        self.assertEqual(self.line('Toronto, ON, Canada (hybrid)'), 'Surrey, BC · Relocating to Toronto, ON')
        self.assertEqual(self.line('Winnipeg, Manitoba'), 'Surrey, BC · Relocating to Winnipeg, MB')
        self.assertEqual(self.line('Calgary AB'), 'Surrey, BC · Relocating to Calgary, AB')
        self.assertEqual(self.line('Hybrid - Mississauga, ON'), 'Surrey, BC · Relocating to Mississauga, ON')
        self.assertEqual(self.line('Toronto, Ontario; Montreal, QC'), 'Surrey, BC · Relocating to Toronto, ON')

    def test_same_metro_remote_or_unknown_keep_home(self):
        for loc in ('Vancouver, BC', 'Burnaby, British Columbia (on-site)', 'Surrey, BC', 'Remote - Canada',
                    'Toronto, ON or Remote', 'Canada', 'not stated', '', 'Ontario'):
            self.assertEqual(self.line(loc), 'Surrey, BC', loc)

    def test_not_willing_to_relocate_keeps_home(self):
        self.assertEqual(self.line('Toronto, ON', dict(ME, willingToRelocate='no')), 'Surrey, BC')

    def test_wording_and_full_province_name(self):
        p = dict(ME, state='British Columbia', relocationWording='Open to relocating to {city}')
        self.assertEqual(self.line('Toronto, ON', p), 'Surrey, BC · Open to relocating to Toronto, ON')

    def test_job_city_only(self):
        p = dict(ME, resumeLocation='job-city')
        self.assertEqual(self.line('Calgary, AB (on-site)', p), 'Calgary, AB')
        self.assertEqual(self.line('Remote - Canada', p), 'Surrey, BC')
        self.assertEqual(self.line('Vancouver, BC', p), 'Surrey, BC')
        self.assertEqual(self.line('Calgary, AB', dict(p, willingToRelocate='no')), 'Surrey, BC')

    def test_same_city_name_other_region(self):
        p = {'city': 'London', 'state': 'ON', 'willingToRelocate': 'yes'}
        self.assertEqual(self.line('London, KY', p), 'London, ON · Relocating to London, KY')

    def test_job_posting_markdown_shows_line_only_with_profile(self):
        p = {'company': 'Northwind', 'role': 'Analyst', 'location': 'Toronto, ON (on-site)'}
        self.assertIn('- Your location line: Surrey, BC · Relocating to Toronto, ON (job is in Toronto, ON)',
                      postings.render_markdown(p, profile=ME))
        self.assertNotIn('Your location line', postings.render_markdown(p))

    def test_letter_contact_line(self):
        import cover_letter as cl
        tex = cl.build_tex(dict(ME, firstName='Alex', lastName='Tremblay', phone='604-555-0100',
                                email='alex@example.com'), 'Northwind', 'Analyst', 'Dear team,', ['Hello.'],
                           'Sincerely,', ['Alex Tremblay'], job_location='Toronto, ON')
        self.assertIn('Relocating to Toronto, ON', tex)
        tex = cl.build_tex(dict(ME, firstName='Alex', lastName='Tremblay'), 'Northwind', 'Analyst', 'Dear team,',
                           ['Hello.'], 'Sincerely,', ['Alex Tremblay'], job_location='Remote')
        self.assertNotIn('Relocating', tex)

    def test_fact_check_accepts_relocation_line(self):
        import tempfile
        from jobkit import bullets
        d = tempfile.mkdtemp()
        m, c = os.path.join(d, 'master.md'), os.path.join(d, 'tailored.md')
        open(m, 'w').write('Alex Tremblay\nSurrey, BC | alex@example.com\nBuilt dashboards in Python.\n')
        r = location.location_line(ME, 'Toronto, ON (on-site)')
        open(c, 'w').write('Alex Tremblay\n' + r['line'] + ' | alex@example.com\nBuilt dashboards in Python.\n')
        res, _ = bullets.fact_check(m, c, (), [r['job_city'], r['line']], resume=True)
        self.assertEqual(res['new_terms'], [], res['new_terms'])
        res, _ = bullets.fact_check(m, c, (), [], resume=True)
        self.assertTrue(res['new_terms'])


if __name__ == '__main__':
    unittest.main()
