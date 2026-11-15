"""Fact-check a resume or letter against the master: same command, checks and output as internship-application's check_resume.py."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(HERE, '..', '..', 'lib')):
    if os.path.isdir(os.path.join(_p, 'jobkit')): sys.path.insert(0, os.path.abspath(_p)); break
if __name__ == '__main__': from jobkit.bullets import check_resume_cli; check_resume_cli()
