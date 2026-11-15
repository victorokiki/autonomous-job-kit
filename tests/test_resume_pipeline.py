"""Tests for the resume pipeline: jobkit.latex, jobkit.bullets and the build/compare/check/ats/check_tailored scripts.

Run from the repository root:  python3 -m unittest discover -s tests
Everything uses the fictional master (templates/master-resume.tex) and fixtures in tests/fixtures/resume/.
Tests that compile LaTeX are skipped when no LaTeX engine is installed.
"""
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'lib'))
from jobkit import bullets, latex  # noqa: E402

SCRIPTS = os.path.join(ROOT, 'internship-application', 'scripts')
TRACKER_SCRIPTS = os.path.join(ROOT, 'internship-tracker', 'scripts')
FIX = os.path.join(ROOT, 'tests', 'fixtures', 'resume')
MASTER = os.path.join(ROOT, 'templates', 'master-resume.tex')
NAME = 'Alex Morgan Tremblay'
HAVE_LATEX = bool(latex.engines_available())


def run_script(path, *args):
    r = subprocess.run([sys.executable, path] + [str(a) for a in args], capture_output=True, text=True,
                       encoding='utf-8')
    try:
        data = json.loads(r.stdout)
    except ValueError:
        raise AssertionError(f'not one JSON object from {os.path.basename(path)}: {r.stdout!r} {r.stderr!r}')
    return r.returncode, data


def read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def make_docx(path, paragraphs):
    """A minimal .docx: paragraphs are (text, is_list)."""
    body = ''
    for t, listy in paragraphs:
        ppr = '<w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr>' if listy else ''
        body += f'<w:p>{ppr}<w:r><w:t xml:space="preserve">{t}</w:t></w:r></w:p>'
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           f'<w:body>{body}</w:body></w:document>')
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('[Content_Types].xml', '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/'
                   'package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/></Types>')
        z.writestr('word/document.xml', doc)


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='jobkit test resume ')   # a space on purpose

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def copy(self, src, *parts):
        dest = os.path.join(self.tmp, *parts)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy(src, dest)
        return dest


class LatexHelpers(unittest.TestCase):
    def test_parse_errors_tectonic_and_classic(self):
        log = ('error: main.tex:12: Undefined control sequence\n'
               '! Undefined control sequence.\nl.12 \\badcmd\n'
               '! Missing } inserted.\n<inserted text>\nl.30 }\n')
        errs = latex.parse_errors(log)
        self.assertEqual(errs[0], {'line': 12, 'file': 'main.tex', 'message': 'Undefined control sequence'})
        self.assertIn({'line': 30, 'file': None, 'message': 'Missing } inserted.'}, errs)
        self.assertEqual(len(errs), 2)
        hints = latex.error_hints(errs, log)
        self.assertTrue(any('misspelled' in h for h in hints))
        self.assertTrue(any('braces' in h for h in hints))

    def test_digit_check(self):
        warn = latex.digit_check('Cut 6 hours to 40 minutes in 2024', 'Cut hours to minutes in', '{carlito}')
        self.assertFalse(warn['ok'])
        self.assertIn('lining', warn['warning'])
        self.assertTrue(latex.digit_check('2024 2023 18', '2024 2023 18')['ok'])
        self.assertIn('font', latex.digit_check('1234567', '', '')['warning'])

    def test_missing_strings_loose(self):
        pdf = 'ALEX MORGAN TREMBLAY\nData Analyst \ufb01nds things'
        self.assertEqual(latex.missing_strings(pdf, [NAME, 'finds things', 'Power BI']), ['Power BI'])

    def test_visible_source_text_skips_preamble(self):
        src = ('\\documentclass[11pt]{article}\\usepackage[margin=0.6in]{geometry}\\begin{document}'
               'Hello\\\\[2pt] world \\vspace{-3pt} 42 items\\end{document}')
        vis = latex.visible_source_text(src)
        self.assertIn('42', vis)
        self.assertNotIn('11', vis)
        self.assertNotIn('2pt', vis)

    def test_geometry_bottom(self):
        self.assertAlmostEqual(latex._geometry_bottom_pt('\\usepackage[margin=1in]{geometry}'), 72.0, places=1)
        self.assertAlmostEqual(latex._geometry_bottom_pt('\\usepackage[margin=1in,bottom=0.5in]{geometry}'), 36.0,
                               places=1)
        self.assertIsNone(latex._geometry_bottom_pt('\\usepackage{fullpage}'))

    def test_engine_choice(self):
        self.assertIsNone(latex.choose_engine('no-such-engine'))
        chosen = latex.choose_engine()
        if latex.engines_available():
            self.assertIn(chosen, latex.engines_available())
        else:
            self.assertIsNone(chosen)


class BulletExtraction(TempDirCase):
    def test_master_bullets(self):
        bs = bullets.extract_bullets(MASTER)
        self.assertEqual(len(bs), 12)
        self.assertIn('Answered 30-40 customer emails a day in English and French.', bs)
        self.assertTrue(all('\\' not in b for b in bs))

    def test_custom_item_macros(self):
        src = ('\\newcommand{\\resumeItem}[1]{\\item\\small{#1}}\n\\newcommand{\\resumeItemListStart}{\\begin{itemize}}\n'
               '\\begin{document}\n\\resumeItemListStart\n\\resumeItem{Built a \\textbf{SQL} report for 3 teams}\n'
               '\\resumeItem{Wrote tests in Python}\n\\resumeItemListEnd\n\\begin{itemize}\\item Plain item\n'
               '\\end{itemize}\n\\end{document}')
        self.assertEqual(bullets.tex_bullets(src),
                         ['Built a SQL report for 3 teams', 'Wrote tests in Python', 'Plain item'])

    def test_docx_bullets(self):
        path = os.path.join(self.tmp, 'cv.docx')
        make_docx(path, [('Alex Morgan Tremblay', False), ('Built a dashboard for 4 managers', True),
                         ('\u2022 Answered customer emails', False), ('Experience', False)])
        self.assertEqual(bullets.extract_bullets(path),
                         ['Built a dashboard for 4 managers', 'Answered customer emails'])


class Classification(unittest.TestCase):
    def test_kinds(self):
        items = bullets.classify(bullets.extract_bullets(MASTER),
                                 bullets.extract_bullets(os.path.join(FIX, 'tailored.tex')))
        kinds = {i['text'][:20]: i['kind'] for i in items}
        self.assertEqual(kinds['Automated weekly shi'], 'reworded')
        self.assertEqual(kinds['Kept inventory count'], 'merged')
        self.assertEqual(kinds['Presented quarterly '], 'no_source')
        self.assertEqual(kinds['Built a Power BI das'], 'unchanged')
        # a changed number is never "unchanged"
        self.assertEqual(kinds['Reduced duplicate cu'], 'reworded')
        merged = [i for i in items if i['kind'] == 'merged'][0]
        self.assertEqual(len(merged['source']), 2)

    def test_similarity_bounds(self):
        self.assertEqual(bullets.similarity('Same text here', 'same text here!'), 1.0)
        self.assertLess(bullets.similarity('Cooked pasta for a restaurant', 'Built SQL dashboards'), 0.4)

    def test_compare_cli(self):
        code, out = run_script(os.path.join(SCRIPTS, 'compare_bullets.py'), MASTER, os.path.join(FIX, 'tailored.tex'))
        self.assertEqual(code, 2)
        self.assertEqual(out['counts']['no_source'], 1)
        self.assertEqual(out['total'], 11)
        self.assertIn('Relevant courses: Database Systems, Statistics for Business, Data Visualization.',
                      out['master_unused'])
        code, out = run_script(os.path.join(SCRIPTS, 'compare_bullets.py'), MASTER, os.path.join(FIX, 'missing.tex'))
        self.assertEqual(code, 1)


class FactCheck(TempDirCase):
    def write(self, name, body):
        path = os.path.join(self.tmp, name)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(body)
        return path

    def test_tailored_fixture(self):
        res, code = bullets.fact_check(MASTER, os.path.join(FIX, 'tailored.tex'), resume=True)
        self.assertEqual(code, 2)
        self.assertEqual([n['raw'] for n in res['new_numbers']], ['25%'])
        self.assertEqual([t['term'] for t in res['new_terms']], ['Tableau'])
        self.assertEqual(res['missing_contact'], [])
        res, code = bullets.fact_check(MASTER, os.path.join(FIX, 'tailored.tex'), allow=['Tableau', '25%'])
        self.assertEqual(code, 0, res)

    def test_numbers_years_and_allow(self):
        year = dt.date.today().year
        cand = self.write('c.txt', f'Data analyst since 2019, still in {year}. Grew sales 37% and saved $12k in 2017.')
        res, _ = bullets.fact_check(MASTER, cand)
        raws = [n['raw'] for n in res['new_numbers']]
        self.assertIn('37%', raws)
        self.assertIn('$12k', raws)
        self.assertIn('2017', raws)
        self.assertNotIn('2019', raws)
        self.assertNotIn(str(year), raws)
        res, _ = bullets.fact_check(MASTER, cand, allow=['37%', '2017'])
        self.assertEqual([n['raw'] for n in res['new_numbers']], ['$12k'])

    def test_money_equivalents_and_known(self):
        master = self.write('m.txt', 'Managed a $1.2M budget and 120,000 rows.')
        cand = self.write('c.txt', 'Managed a 1,200,000 budget; 120k rows; 14 projects.')
        known = self.write('profile.json', '{"yearsExperience": "14"}')
        res, code = bullets.fact_check(master, cand, known=[known])
        self.assertEqual(res['new_numbers'], [])

    def test_placeholders_and_contacts(self):
        cand = self.write('c.md', 'Dear [Company] team, TODO: add <one thing you discussed>. XXX\n'
                                  'Contact: alex.tremblay@example.com')
        res, code = bullets.fact_check(MASTER, cand, resume=True)
        self.assertEqual(code, 2)
        self.assertIn('[Company]', res['placeholders'])
        self.assertIn('TODO', res['placeholders'])
        self.assertIn('<one thing you discussed>', res['placeholders'])
        self.assertIn('9025550142', res['missing_contact'])
        self.assertIn('linkedin.com/in/alex-tremblay-example', res['missing_contact'])
        self.assertNotIn('alex.tremblay@example.com', res['missing_contact'])

    def test_both_check_resume_scripts_agree(self):
        args = (MASTER, os.path.join(FIX, 'tailored.tex'), '--resume', '--allow', 'Northwind Freight')
        c1, o1 = run_script(os.path.join(SCRIPTS, 'check_resume.py'), *args)
        c2, o2 = run_script(os.path.join(TRACKER_SCRIPTS, 'check_resume.py'), *args)
        self.assertEqual((c1, o1), (c2, o2))
        self.assertEqual(c1, 2)
        code, out = run_script(os.path.join(SCRIPTS, 'check_resume.py'), MASTER, os.path.join(self.tmp, 'nope.tex'))
        self.assertEqual(code, 1)
        self.assertFalse(out['ok'])

    def test_clean_copy_passes(self):
        res, code = bullets.fact_check(MASTER, MASTER, resume=True)
        self.assertEqual(code, 0, res)


class AtsHelpers(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, SCRIPTS)
        import ats_check
        self.ats = ats_check

    def test_headings(self):
        self.assertTrue(self.ats.is_standard('Professional Summary'))
        self.assertTrue(self.ats.is_standard('LICENSES & CERTIFICATIONS'))
        self.assertTrue(self.ats.is_standard('Awards and Honours'))
        self.assertFalse(self.ats.is_standard('My Journey'))
        src = read(MASTER) + '\\section*{Things I Love}'
        heads = self.ats.tex_headings(src)
        self.assertIn('Selected Projects', heads)
        self.assertIn('Things I Love', heads)

    def test_two_column(self):
        two = '\n'.join(f'Left column text {i}          Right column text {i}' for i in range(12))
        one = '\n'.join(f'A normal single column line number {i}' for i in range(12))
        self.assertTrue(self.ats.two_column(two))
        self.assertFalse(self.ats.two_column(one))


@unittest.skipUnless(HAVE_LATEX, 'no LaTeX engine installed')
class Pipeline(TempDirCase):
    def test_build_master_no_limit(self):
        main = self.copy(MASTER, 'resume', 'main.tex')
        out = os.path.join(self.tmp, 'out dir', 'master.pdf')
        code, res = run_script(os.path.join(SCRIPTS, 'build_resume.py'), main, '--out', out, '--max-pages', '0',
                               '--expect', NAME)
        self.assertEqual(code, 0, res)
        self.assertTrue(res['ok'])
        self.assertEqual(res['pages'], 1)
        self.assertEqual(res['digits']['source'], res['digits']['pdf'])
        self.assertGreaterEqual(res['free_lines'], 3)
        self.assertAlmostEqual(res['margins_in']['left'], 0.6, delta=0.05)
        self.assertTrue(10 <= res['smallest_text_pt'] <= 12)
        self.assertEqual(sorted(os.listdir(os.path.join(self.tmp, 'resume'))), ['main.tex'])   # nothing written
        # a second build moves the first PDF to _old
        code, res = run_script(os.path.join(SCRIPTS, 'build_resume.py'), main, '--out', out, '--max-pages', '0')
        self.assertTrue(res['previous_version_moved_to'] and os.path.isfile(res['previous_version_moved_to']))

    def test_build_too_long(self):
        main = self.copy(os.path.join(FIX, 'long.tex'), 'long.tex')
        code, res = run_script(os.path.join(SCRIPTS, 'build_resume.py'), main, '--out',
                               os.path.join(self.tmp, 'long.pdf'))
        self.assertEqual(code, 2)
        self.assertEqual(res['pages'], 2)
        self.assertGreater(res['lines_over'], 10)

    def test_build_error_line(self):
        main = self.copy(os.path.join(FIX, 'broken.tex'), 'broken.tex')
        code, res = run_script(os.path.join(SCRIPTS, 'build_resume.py'), main, '--out',
                               os.path.join(self.tmp, 'b.pdf'))
        self.assertEqual(code, 1)
        want = [i for i, l in enumerate(read(main).splitlines(), 1) if 'notarealcommand' in l][0]
        self.assertEqual(res['errors'][0]['line'], want)
        self.assertTrue(res['hints'])
        self.assertFalse(os.path.exists(os.path.join(self.tmp, 'b.pdf')))

    def test_missing_digits_warning(self):
        src = read(MASTER).replace('[sfdefault,lining]', '[sfdefault]')
        main = os.path.join(self.tmp, 'nolining.tex')
        with open(main, 'w', encoding='utf-8') as f:
            f.write(src)
        code, res = run_script(os.path.join(SCRIPTS, 'build_resume.py'), main, '--out',
                               os.path.join(self.tmp, 'nl.pdf'), '--max-pages', '0')
        if res['digits']['pdf'] >= res['digits']['source']:
            self.skipTest('this engine keeps old-style digits readable')
        self.assertEqual(code, 2)
        self.assertTrue(any('lining' in w for w in res['warnings']))

    def test_ats_check_master(self):
        main = self.copy(MASTER, 'main.tex')
        pdf = os.path.join(self.tmp, 'm.pdf')
        run_script(os.path.join(SCRIPTS, 'build_resume.py'), main, '--out', pdf, '--max-pages', '0')
        code, res = run_script(os.path.join(SCRIPTS, 'ats_check.py'), pdf, '--name', NAME, '--tex', main,
                               '--posting', os.path.join(FIX, 'posting.md'), '--master', main)
        self.assertEqual(code, 0, res)
        self.assertTrue(res['checks']['name_near_top'])
        self.assertFalse(res['checks']['two_column'])
        self.assertIn('power bi', res['keywords']['in_resume'])
        self.assertIn('snowflake', res['keywords']['not_in_master'])
        code, res = run_script(os.path.join(SCRIPTS, 'ats_check.py'), pdf, '--name', 'Jordan Someone Else')
        self.assertEqual(code, 2)
        self.assertFalse(res['checks']['name_near_top'])

    def test_check_tailored_end_to_end(self):
        master = self.copy(MASTER, 'resume', 'main.tex')
        app = os.path.join(self.tmp, 'Applications', '2026-11-14 Northwind Freight - Junior Data Analyst')
        tailored = self.copy(os.path.join(FIX, 'tailored.tex'), app, 'resume-src', 'main.tex')
        posting = self.copy(os.path.join(FIX, 'posting.md'), app, 'job-posting.md')
        profile = self.copy(os.path.join(FIX, 'profile.json'), 'profile.json')
        out = os.path.join(app, 'Alex_Morgan_Tremblay_Resume_Northwind_Freight.pdf')
        args = [tailored, '--master', master, '--name', NAME, '--posting', posting, '--profile', profile,
                '--out', out, '--check-template']
        code, res = run_script(os.path.join(SCRIPTS, 'check_tailored.py'), *args)
        self.assertEqual(code, 2, res)
        self.assertFalse(res['ok'])
        self.assertTrue(any('25%' in f for f in res['fix']))
        self.assertTrue(any('tableau' in f.lower() for f in res['fix']))
        self.assertTrue(any('no clear source' in r for r in res['review']))
        self.assertEqual(res['bullets']['counts']['merged'], 1)
        self.assertEqual(res['facts']['counts']['new_numbers'], 1)
        self.assertEqual(res['page']['pages'], 1)
        self.assertIn('snowflake', res['keywords']['not_in_master'])
        self.assertTrue(res['template']['ok'])
        self.assertTrue(os.path.isfile(out))
        changes = read(res['changes'])
        for section in ('## Angle', '## Page', '## Reworded', '## Kept as is', '## Dropped from the master', '## Gaps'):
            self.assertIn(section, changes)
        self.assertIn('After: Automated weekly shipment reporting', changes)
        self.assertIn('- snowflake', changes)
        if shutil.which('pdftoppm'):
            self.assertTrue(res['png'] and os.path.isfile(res['png']))
        # running again keeps the earlier changes file in _old/
        run_script(os.path.join(SCRIPTS, 'check_tailored.py'), *args[:-1])
        self.assertTrue(os.listdir(os.path.join(app, '_old')))

    def test_check_tailored_stops_when_too_long(self):
        master = self.copy(MASTER, 'resume', 'main.tex')
        tailored = self.copy(os.path.join(FIX, 'long.tex'), 'app', 'main.tex')
        code, res = run_script(os.path.join(SCRIPTS, 'check_tailored.py'), tailored, '--master', master, '--name',
                               NAME, '--out', os.path.join(self.tmp, 'app', 'r.pdf'))
        self.assertEqual(code, 2)
        self.assertGreater(res['page']['lines_over'], 10)
        self.assertNotIn('bullets', res)
        self.assertEqual(len(res['fix']), 1)

    def test_check_tailored_clean_copy(self):
        master = self.copy(MASTER, 'resume', 'main.tex')
        tailored = self.copy(MASTER, 'app', 'main.tex')
        code, res = run_script(os.path.join(SCRIPTS, 'check_tailored.py'), tailored, '--master', master, '--name',
                               NAME, '--out', os.path.join(self.tmp, 'app', 'r.pdf'))
        self.assertEqual(code, 2)            # an untouched copy: everything unchanged, page not full
        self.assertEqual(res['fix'], [])
        self.assertTrue(any('unchanged' in r for r in res['review']))


class NoLatex(TempDirCase):
    def test_missing_engine_exit_3(self):
        missing = [e for e in ('pdflatex', 'xelatex', 'lualatex') if not shutil.which(e)]
        if not missing:
            self.skipTest('every engine is installed')
        main = self.copy(MASTER, 'main.tex')
        code, res = run_script(os.path.join(SCRIPTS, 'build_resume.py'), main, '--out',
                               os.path.join(self.tmp, 'x.pdf'), '--engine', missing[0])
        self.assertEqual(code, 3)
        self.assertFalse(res['ok'])


if __name__ == '__main__':
    unittest.main()
