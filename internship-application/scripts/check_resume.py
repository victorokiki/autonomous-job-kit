#!/usr/bin/env python3
"""Fact-check a tailored resume (or a cover letter or written answer) against the master resume.

Usage:
  python check_resume.py MASTER CANDIDATE [--known FILE ...] [--allow WORD ...] [--resume]

MASTER and CANDIDATE may be .tex, .pdf, .docx, .md or .txt. --known adds files that also hold true facts
(profile.json, notes). --allow accepts words or numbers (the posting's company and role, for example).
--resume also checks that the master's email, phone and LinkedIn/GitHub links are still in the candidate.

Reports:
  new_numbers      numbers, percentages, money and years in CANDIDATE that are not in MASTER or --known
                   (years already present and the current year are fine)
  new_terms        tool-like or capitalised names in CANDIDATE that MASTER and --known never mention
  missing_contact  (--resume) contact details from MASTER missing in CANDIDATE
  placeholders     [Company], TODO, XXX, lorem ipsum, <...> slots left in the text

Prints one JSON object: ok, new_numbers[{value, raw, context}], new_terms[{term, context}], missing_contact[],
placeholders[], counts{}, advice.

Exit codes: 0 clean, 2 something flagged, 1 bad input.
The checking code lives in jobkit/bullets.py so the tracker skill runs exactly the same checks.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(HERE, '..', '..', 'lib')):
    if os.path.isdir(os.path.join(_p, 'jobkit')):
        sys.path.insert(0, os.path.abspath(_p))
        break
from jobkit import bullets  # noqa: E402

run = bullets.fact_check   # run(master, candidate, known=(), allow=(), resume=False) -> (result, exit code)
main = bullets.check_resume_cli

if __name__ == '__main__':
    main()
