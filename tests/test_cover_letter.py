"""Tests for internship-application/scripts/cover_letter.py (made-up data only)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, 'internship-application', 'scripts')
SCRIPT = os.path.join(SCRIPTS, 'cover_letter.py')
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.join(ROOT, 'lib'))

import cover_letter as cl  # noqa: E402

HAVE_LATEX = any(shutil.which(e) for e in ('tectonic', 'xelatex', 'lualatex', 'pdflatex'))
HAVE_PDFTOTEXT = bool(shutil.which('pdftotext'))

MASTER = r"""\documentclass{article}
\begin{document}
Alex Morgan Tremblay
\section{Experience}
Data Analyst, Harbourline Logistics
\begin{itemize}
\item Cut weekly shipment reporting from 6 hours to 40 minutes by automating data pulls with Python and SQL.
\item Reduced duplicate customer records by 18\% during a 120,000-row CRM migration.
\item Built a Power BI dashboard used by 4 regional managers.
\end{itemize}
\end{document}
"""

PROFILE = {
    'firstName': 'Alex', 'lastName': 'Tremblay', 'resumeName': 'Alex Morgan Tremblay',
    'email': 'alex.tremblay@example.com', 'phone': '+1 (902) 555-0142', 'city': 'Halifax', 'state': 'NS',
    'country': 'Canada', 'linkedin': 'linkedin.com/in/alex-tremblay-example',
    'github': 'github.com/alex-tremblay-example', 'skills': 'Python, SQL, Excel, Power BI',
    'letterMaxWords': 250,
}

POSTING = """# Data Analyst Intern at Northwind Freight

- Company: Northwind Freight
- Role: Data Analyst Intern
- URL: https://example.com/jobs/1
- Location: Toronto, ON; hybrid
- Cover letter: optional

## Description
Northwind Freight runs 35 depots across Canada. You will build reports in Tableau and SQL for our operations team.
"""

BODY = (
    "I am writing to apply for the Data Analyst Intern role at Northwind Freight. At Harbourline Logistics I cut "
    "weekly shipment reporting from 6 hours to 40 minutes by automating data pulls with Python and SQL, and I reduced "
    "duplicate customer records by 18% during a 120,000-row CRM migration.\n\n"
    "Your posting asks for someone who can turn messy operational data into clear reports for managers. That is the "
    "work I enjoy most. I built a Power BI dashboard that 4 regional managers use every week to track on-time "
    "delivery, and I wrote the validation rules that kept a large customer table clean through a migration. I like "
    "careful work with numbers and I am patient with details, which matters when managers rely on a weekly report.\n\n"
    "I would welcome the chance to bring the same care to the reporting team at Northwind Freight. Thank you for your "
    "time and consideration; I look forward to hearing from you about next steps."
)


def letter(body=BODY, greeting='Dear Hiring Team,', signoff='Sincerely,\nAlex Morgan Tremblay'):
    return '\n\n'.join(x for x in (greeting, body, signoff) if x) + '\n'


class Unit(unittest.TestCase):
    def test_split_letter(self):
        g, body, s, names = cl.split_letter(cl.paragraphs(letter()))
        self.assertEqual(g, 'Dear Hiring Team,')
        self.assertEqual(s, 'Sincerely,')
        self.assertEqual(names, ['Alex Morgan Tremblay'])
        self.assertEqual(len(body), 3)
        self.assertGreater(cl.word_count(body), 150)

    def test_missing_greeting_and_signoff(self):
        g, body, s, names = cl.split_letter(cl.paragraphs(BODY))
        self.assertIsNone(g)
        self.assertIsNone(s)

    def test_invented_number_is_fix(self):
        facts = cl.text.tex_to_text(MASTER) + json.dumps(PROFILE)
        fix, review = cl.check_numbers('I raised sales by 35% and cut costs by $12,000.', facts, '', '')
        self.assertEqual(len(fix), 2)
        self.assertTrue(any('35%' in f for f in fix))

    def test_known_numbers_pass(self):
        facts = cl.text.tex_to_text(MASTER) + json.dumps(PROFILE)
        fix, review = cl.check_numbers(BODY, facts, POSTING, 'Northwind Freight Data Analyst Intern')
        self.assertEqual(fix, [])
        self.assertEqual(review, [])

    def test_posting_number_is_review(self):
        fix, review = cl.check_numbers('Your 35 depots impress me.', cl.text.tex_to_text(MASTER), POSTING, '')
        self.assertEqual(fix, [])
        self.assertEqual(len(review), 1)

    def test_posting_term_not_in_master_is_review(self):
        out = cl.check_terms('I am skilled in Tableau and SQL.', cl.text.tex_to_text(MASTER), POSTING,
                             PROFILE['skills'])
        self.assertEqual(len(out), 1)
        self.assertIn('tableau', out[0])

    def test_placeholders_and_characters(self):
        self.assertTrue(cl.check_placeholders('Dear [Hiring Manager], I love <company>. TODO'))
        self.assertEqual(cl.check_placeholders('A plain sentence.'), [])
        self.assertTrue(cl.check_characters('Great team \U0001F680'))
        self.assertEqual(cl.check_characters('Café “quotes” — fine…'), [])

    def test_tex_escape(self):
        self.assertEqual(cl.tex_escape('R&D 50% $5 #1 a_b'), 'R\\&D 50\\% \\$5 \\#1 a\\_b')
        self.assertEqual(cl.tex_escape('"hi"'), "``hi''")
        self.assertEqual(cl.tex_escape('a—b'), 'a---b')


class Cli(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix='jk test letter ')
        self.master = os.path.join(self.dir, 'master.tex')
        self.posting = os.path.join(self.dir, 'job-posting.md')
        with open(self.master, 'w', encoding='utf-8') as f:
            f.write(MASTER)
        with open(self.posting, 'w', encoding='utf-8') as f:
            f.write(POSTING)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def profile(self, **extra):
        p = dict(PROFILE, **extra)
        path = os.path.join(self.dir, 'profile.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(p, f)
        return path

    def run_cl(self, text_, *extra, profile=None):
        path = os.path.join(self.dir, 'letter.txt')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text_)
        cmd = [sys.executable, SCRIPT, path, '--profile', profile or self.profile(), '--master', self.master,
               '--company', 'Northwind Freight', '--role', 'Data Analyst Intern',
               '--out', os.path.join(self.dir, 'Alex_Morgan_Tremblay_Cover_Letter_Northwind_Freight.pdf')] + list(extra)
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        return r.returncode, json.loads(r.stdout)

    def test_bad_input(self):
        r = subprocess.run([sys.executable, SCRIPT, os.path.join(self.dir, 'nope.txt'), '--profile', self.profile(),
                            '--master', self.master, '--company', 'X', '--role', 'Y', '--out', 'x.pdf'],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertFalse(json.loads(r.stdout)['ok'])

    @unittest.skipUnless(HAVE_LATEX and HAVE_PDFTOTEXT, 'needs a LaTeX engine and pdftotext')
    def test_layouts_keep_digits(self):
        for style in ('', 'carlito'):
            with self.subTest(style=style or 'default'):
                code, out = self.run_cl(letter(), '--posting', self.posting, profile=self.profile(letterStyle=style))
                self.assertEqual(code, 0, out)
                self.assertTrue(out['ok'])
                self.assertEqual(out['pages'], 1)
                txt = subprocess.run(['pdftotext', out['pdf'], '-'], capture_output=True, text=True).stdout
                for needle in ('120,000', '18%', '40 minutes', '555-0142'):
                    self.assertIn(needle, txt)
                self.assertEqual(out['digits']['letter_body'], out['digits']['pdf'])
                if style == 'carlito':
                    self.assertIn('ALEX MORGAN TREMBLAY', txt)
                    self.assertIn('Re: Data Analyst Intern', txt)
                    self.assertIn('Toronto, ON', txt)      # location from the posting
                else:
                    self.assertIn('github.com/alex-tremblay-example', txt)
                    self.assertIn('Hiring Team', txt)

    @unittest.skipUnless(HAVE_LATEX and HAVE_PDFTOTEXT, 'needs a LaTeX engine and pdftotext')
    def test_fix_and_review_items(self):
        bad = BODY.replace('by 18%', 'by 37%') + ' I am an expert in Tableau. \U0001F680 [Hiring Manager]'
        code, out = self.run_cl(letter(bad, greeting=None), '--posting', self.posting)
        self.assertEqual(code, 2)
        self.assertFalse(out['ok'])
        joined = ' '.join(out['fix'])
        self.assertIn('37%', joined)
        self.assertIn('greeting', joined)
        self.assertIn('Placeholder', joined)
        self.assertIn("can't print", joined)
        self.assertTrue(any('tableau' in r for r in out['review']))

    @unittest.skipUnless(HAVE_LATEX, 'needs a LaTeX engine')
    def test_word_limits(self):
        code, out = self.run_cl(letter(), '--max-words', '100')
        self.assertEqual(code, 2)
        self.assertTrue(any('limit is 100' in f for f in out['fix']))
        code, out = self.run_cl(letter('I would like to apply for this role. Thank you for reading.'))
        self.assertEqual(code, 2)
        self.assertTrue(any('only' in r for r in out['review']))

    @unittest.skipUnless(HAVE_LATEX and HAVE_PDFTOTEXT, 'needs a LaTeX engine and pdftotext')
    def test_combine_order_and_old_versions(self):
        resume_src = '\\documentclass{article}\\begin{document}RESUMEMARKER page\\end{document}\n'
        pdf_bytes, errors = cl.local_compile(resume_src, cl.pick_engine())
        self.assertIsNotNone(pdf_bytes, errors)
        resume_pdf = os.path.join(self.dir, 'Alex_Morgan_Tremblay_Resume_Northwind_Freight.pdf')
        with open(resume_pdf, 'wb') as f:
            f.write(pdf_bytes)

        def first_page(path):
            return subprocess.run(['pdftotext', '-f', '1', '-l', '1', path, '-'], capture_output=True,
                                  text=True).stdout

        code, out = self.run_cl(letter(), '--combine', resume_pdf)
        self.assertEqual(code, 0, out)
        self.assertTrue(out['combined'].endswith('Alex_Morgan_Tremblay_Resume_and_Cover_Letter_Northwind_Freight.pdf'))
        self.assertEqual(out['combined_order'], 'resume-first')
        self.assertIn('RESUMEMARKER', first_page(out['combined']))
        self.assertEqual(cl.text.pdf_pages(out['combined']), 2)

        code, out = self.run_cl(letter(), '--combine', resume_pdf,
                                profile=self.profile(combinedOrder='letter-first'))
        self.assertEqual(code, 0, out)
        self.assertEqual(out['combined_order'], 'letter-first')
        self.assertNotIn('RESUMEMARKER', first_page(out['combined']))
        self.assertIn('Dear Hiring Team', first_page(out['combined']))
        # the second run moved the first outputs into _old/
        self.assertTrue(out['previous_version_moved_to'] and os.path.exists(out['previous_version_moved_to']))
        self.assertTrue(os.path.exists(out['previous_combined_moved_to']))


if __name__ == '__main__':
    unittest.main()
