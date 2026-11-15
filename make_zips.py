#!/usr/bin/env python3
"""Make the three skill zips for uploading in the Claude app (Customize -> Skills), for Cowork users.

Usage:  python3 make_zips.py [--out DIR]      (default DIR: ./dist)

Each zip holds one skill folder with the shared jobkit library copied into its scripts/ folder, and job-kit-setup also
gets the templates/ folder and CAPABILITIES.md, so every skill works on its own once uploaded. Python caches are left
out. Existing zips in DIR are moved into DIR/_old/ first; nothing is deleted.
"""
import argparse
import os
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib'))
from jobkit import files  # noqa: E402

SKILLS = ['internship-application', 'internship-tracker', 'job-kit-setup']


def add_tree(z, src, arc_root):
    for root, dirs, names in os.walk(src):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for n in names:
            if n.endswith('.pyc') or n == '.DS_Store':
                continue
            full = os.path.join(root, n)
            z.write(full, os.path.join(arc_root, os.path.relpath(full, src)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(HERE, 'dist'))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    made = []
    for skill in SKILLS:
        dest = os.path.join(a.out, f'{skill}.zip')
        files.move_to_old(dest)
        with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as z:
            add_tree(z, os.path.join(HERE, skill), skill)
            if os.path.isdir(os.path.join(HERE, skill, 'scripts')):
                add_tree(z, os.path.join(HERE, 'lib', 'jobkit'), os.path.join(skill, 'scripts', 'jobkit'))
            if skill == 'job-kit-setup':
                add_tree(z, os.path.join(HERE, 'templates'), os.path.join(skill, 'templates'))
                z.write(os.path.join(HERE, 'CAPABILITIES.md'), os.path.join(skill, 'CAPABILITIES.md'))
        made.append(dest)
    print('\n'.join(['Made:'] + made + ['Upload each zip in the Claude app: Customize -> Skills.']))


if __name__ == '__main__':
    main()
