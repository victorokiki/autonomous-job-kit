#!/usr/bin/env python3
"""Compare the bullets of a tailored resume with the master resume.

Usage:
  python compare_bullets.py MASTER TAILORED

MASTER and TAILORED are .tex (bullets are \\item lines and custom macros whose name contains "item", such as
\\resumeItem{...}) or .docx (list paragraphs, or paragraphs starting with a bullet sign). .md, .txt and .pdf are read
on a best-effort basis (lines starting with a bullet sign).

Every tailored bullet is classified:
  unchanged  same as a master bullet
  reworded   clearly based on one master bullet
  merged     combines two master bullets
  no_source  no master bullet explains it: check it is a real fact before keeping it

Prints one JSON object: ok, counts{unchanged, reworded, merged, no_source}, total, unchanged_share (skills lines such
as "Data: Python, SQL, Excel" are left out of the share), advice, bullets[{text, kind, source[], score}],
master_unused[] (master bullets no tailored bullet came from).

Exit codes: 0 looks tailored, 2 to review (more than half unchanged, or any no_source), 1 bad input.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(HERE, '..', '..', 'lib')):
    if os.path.isdir(os.path.join(_p, 'jobkit')):
        sys.path.insert(0, os.path.abspath(_p))
        break
from jobkit import bullets, cli  # noqa: E402


def run(master, tailored):
    """Returns (result dict, exit code)."""
    for path in (master, tailored):
        if not os.path.isfile(path):
            return {'ok': False, 'error': f'File not found: {path}'}, cli.BAD_INPUT
    try:
        mb = bullets.extract_bullets(master)
        tb = bullets.extract_bullets(tailored)
    except Exception as e:  # unreadable .docx, bad zip, encoding trouble
        return {'ok': False, 'error': f'Could not read the bullets: {e}'}, cli.BAD_INPUT
    if not mb:
        return {'ok': False, 'error': f'No bullets found in the master {master}'}, cli.BAD_INPUT
    if not tb:
        return {'ok': False, 'error': f'No bullets found in {tailored}'}, cli.BAD_INPUT
    items = bullets.classify(mb, tb)
    counts = {k: 0 for k in ('unchanged', 'reworded', 'merged', 'no_source')}
    for it in items:
        counts[it['kind']] += 1
        if bullets.is_skills_line(it['text']):
            it['skills_line'] = True
    scored = [it for it in items if not it.get('skills_line')] or items
    share = round(sum(1 for it in scored if it['kind'] == 'unchanged') / len(scored), 2)
    used = {s for it in items for s in it['source'] if it['kind'] != 'no_source'}
    unused = [b for b in mb if b not in used]
    advice = []
    if share > 0.5:
        advice.append(f'{round(share * 100)}% of the bullets are unchanged from the master: reword the ones closest '
                      'to the posting (same facts, the posting\'s words where they are true).')
    if counts['no_source']:
        advice.append(f'{counts["no_source"]} bullet(s) have no source in the master: make sure each states a real '
                      'fact from the master or profile, or remove it.')
    if not advice:
        advice.append('Looks tailored: every bullet traces back to the master.')
    attention = share > 0.5 or counts['no_source'] > 0
    res = {'ok': not attention, 'master': master, 'tailored': tailored, 'counts': counts, 'total': len(items),
           'unchanged_share': share, 'advice': ' '.join(advice), 'bullets': items, 'master_unused': unused}
    return res, (cli.ATTENTION if attention else cli.OK)


def main(argv=None):
    p = argparse.ArgumentParser(description='Classify each tailored bullet against the master resume.')
    p.add_argument('master')
    p.add_argument('tailored')
    a = p.parse_args(argv)
    res, code = run(a.master, a.tailored)
    cli.emit(res, code)


if __name__ == '__main__':
    main()
