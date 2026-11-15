#!/usr/bin/env python3
"""Build dashboard.html in the job-search folder: where every application stands, what to do next, and the best new matches.

Usage:
  python dashboard.py --folder "JOB_SEARCH_FOLDER" [--out dashboard.html]

Reads tracker.xlsx (through tracker.py), jobs.txt and the latest .cache/candidates-*.json written by find_jobs.py or
job_digest.py. Writes one self-contained HTML file (no network, no external scripts) that opens in any browser,
in light or dark mode. It contains:
  - a pipeline strip: applied, assessment, interview, offer, accepted (and rejected), with response rate
  - "Needs your update": applications whose status has sat too long (tracker.py checkin rules), with buttons that
    copy a ready-made update line for the user to paste to Claude (the page itself never edits the tracker)
  - to-do list: upcoming interviews, assessments, forms ready to submit, applications that need the user,
    follow-ups (submitted 21+ days ago with no update), deadlines in the next 7 days
  - applications by status and per week
  - every application, searchable, with links to the posting and its folder
  - the top matches from the latest job search
The file holds personal data: keep it in the job-search folder; it isn't uploaded anywhere.
"""
import argparse
import datetime as dt
import glob
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
for _p in (HERE, os.path.join(HERE, '..', '..', 'lib')):
    if os.path.isdir(os.path.join(_p, 'jobkit')):
        sys.path.insert(0, os.path.abspath(_p))
        break

SENT = {'Submitted', 'Online assessment', 'Interviewing', 'Offer', 'Accepted', 'Declined', 'Rejected', 'Withdrawn'}
REPLIED = {'Online assessment', 'Interviewing', 'Offer', 'Accepted', 'Declined', 'Rejected'}
ORDER = ['Ready to submit', 'Submitted', 'Online assessment', 'Interviewing', 'Offer', 'Accepted', 'Declined', 'Rejected',
         'Withdrawn', 'Needs you', 'Skipped']
# The pipeline strip: how far applications got. "Reached" counts every application at that stage or beyond.
STAGES = [('Applied', SENT), ('Assessment', {'Online assessment', 'Interviewing', 'Offer', 'Accepted', 'Declined'}),
          ('Interview', {'Interviewing', 'Offer', 'Accepted', 'Declined'}), ('Offer', {'Offer', 'Accepted', 'Declined'}),
          ('Accepted', {'Accepted'})]


def as_date(v):
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    m = re.match(r'(\d{4}-\d{2}-\d{2})', str(v or ''))
    return dt.date.fromisoformat(m.group(1)) if m else None


def load_rows(folder):
    path = os.path.join(folder, 'tracker.xlsx')
    if not os.path.exists(path):
        return []
    from jobkit import tracker
    _, ws, _ = tracker.open_book(path)
    out = []
    for r in tracker.rows(ws):
        r = tracker.read_links(ws, r)
        rec = {k: (v.isoformat()[:10] if isinstance(v, (dt.date, dt.datetime)) else str(v)) for k, v in r.items() if k != '_row'}
        folder_link = rec.get('folder', '')
        if folder_link and not re.match(r'[a-z]+:', folder_link):
            rec['folder'] = 'file://' + os.path.abspath(os.path.join(folder, folder_link))
        upd = as_date(rec.get('status_updated')) or as_date(rec.get('date_added'))
        rec['days'] = (dt.date.today() - upd).days if upd else ''
        out.append(rec)
    return out


def queue_count(folder):
    p = os.path.join(folder, 'jobs.txt')
    if not os.path.exists(p):
        return 0
    n = 0
    for line in open(p, encoding='utf-8'):
        if line.strip().lower() == '# done':
            break
        n += bool(re.search(r'https?://', line))
    return n


def latest_matches(folder, limit=15):
    files = sorted(glob.glob(os.path.join(folder, '.cache', 'candidates-*.json')))
    if not files:
        return [], ''
    d = json.load(open(files[-1], encoding='utf-8'))
    jobs = [{'fit': j['fit']['score'], 'title': j['title'], 'company': j['company'], 'location': j['location'],
             'posted': j['posted'], 'url': j['url'], 'why': j['fit']['why'], 'flags': [f.split(':')[0] for f in j['fit']['flags']]}
            for j in d.get('jobs', [])[:limit]]
    return jobs, d.get('saved', '')


def summarize(rows, today):
    counts = {s: 0 for s in ORDER}
    for r in rows:
        counts[r.get('status') or 'Needs you'] = counts.get(r.get('status') or 'Needs you', 0) + 1
    sent = [r for r in rows if r.get('status') in SENT]
    replied = [r for r in sent if r.get('status') in REPLIED]
    todo = []
    for r in rows:
        st, name = r.get('status'), f"{r.get('company')}, {r.get('role')}"
        iv, dl = as_date(r.get('interview_date')), as_date(r.get('deadline'))
        upd = as_date(r.get('status_updated')) or as_date(r.get('date_added'))
        if st == 'Interviewing' and iv and iv >= today:
            todo.append((0, iv.isoformat(), 'Interview', name, r.get('next_step') or f'on {iv:%b %-d}'))
        elif st == 'Online assessment':
            todo.append((1, '', 'Assessment', name, r.get('next_step') or 'complete the assessment'))
        elif st == 'Ready to submit':
            todo.append((2, dl.isoformat() if dl else '9999', 'Submit', name,
                         'review the open form and submit' + (f', deadline {dl:%b %-d}' if dl else '')))
        elif st == 'Needs you':
            todo.append((3, '', 'Needs you', name, r.get('next_step') or 'see application-record.md'))
        elif st == 'Submitted' and upd and (today - upd).days >= 21:
            todo.append((4, upd.isoformat(), 'Follow up', name, f'submitted {(today - upd).days} days ago with no update'))
        if dl and today <= dl <= today + dt.timedelta(days=7) and st == 'Needs you':  # Ready to submit shows its deadline already
            todo.append((2, dl.isoformat(), 'Deadline', name, f'closes {dl:%a %b %-d}'))
    todo.sort()
    weeks = []
    start = today - dt.timedelta(days=today.weekday()) - dt.timedelta(weeks=11)
    for i in range(12):
        ws = start + dt.timedelta(weeks=i)
        n = sum(1 for r in sent if (d := as_date(r.get('date_added'))) and ws <= d < ws + dt.timedelta(weeks=1))
        weeks.append({'week': ws.isoformat(), 'label': f'{ws:%b %-d}', 'n': n})
    from jobkit import tracker
    week_start = today - dt.timedelta(days=today.weekday())
    return {'pipeline': [{'stage': name, 'n': sum(1 for r in rows if r.get('status') in sts)} for name, sts in STAGES],
            'rejected': counts.get('Rejected', 0), 'due': tracker.due_for_checkin(rows, today),
            'this_week': sum(1 for r in sent if (d := as_date(r.get('date_added'))) and d >= week_start),
            'counts': [{'status': s, 'n': counts.get(s, 0)} for s in ORDER if counts.get(s, 0)],
            'sent': len(sent), 'replied': len(replied),
            'rate': round(100 * len(replied) / len(sent)) if sent else None,
            'interviews': sum(1 for r in rows if r.get('status') in ('Interviewing', 'Offer', 'Accepted', 'Declined')),
            'offers': counts.get('Offer', 0),
            'todo': [{'kind': k, 'name': n, 'detail': d} for _, _, k, n, d in todo], 'weeks': weeks}


PAGE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Job Search Dashboard</title>
<style>
:root{--page:#f6f6f3;--surface:#ffffff;--ink:#111110;--ink2:#55544f;--muted:#8a8983;--line:#e6e5df;--chip:#f0efea;
--accent:#2a6fd6;--accent-soft:#e3edfb;--good:#18864b;--good-soft:#dcf2e4;--warn:#a86400;--warn-soft:#fdf0d9;
--bad:#b23a3a;--bad-soft:#f8e3e3;--purple:#6b46c1;--purple-soft:#ece5f8;--grey-soft:#efefec;--shadow:0 1px 2px rgba(0,0,0,.04)}
@media (prefers-color-scheme:dark){:root{--page:#0e0e0d;--surface:#191918;--ink:#f1f0ec;--ink2:#c4c3bb;--muted:#8a8983;
--line:#2b2b29;--chip:#242422;--accent:#5b97ee;--accent-soft:#1c2a40;--good:#4cc37f;--good-soft:#16301f;--warn:#e8a63a;
--warn-soft:#352711;--bad:#e57373;--bad-soft:#3a1d1d;--purple:#a88be6;--purple-soft:#2a2140;--grey-soft:#262624;--shadow:none}}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:1120px;margin:0 auto;padding:28px 16px 56px}
header{display:flex;justify-content:space-between;align-items:flex-end;gap:12px;flex-wrap:wrap;margin-bottom:20px}
h1{font-size:26px;letter-spacing:-.01em;margin:0}h2{font-size:15px;margin:0 0 12px}
.sub{color:var(--ink2);margin:2px 0 0}.muted{color:var(--muted)}
.card{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:16px 18px;box-shadow:var(--shadow);margin-bottom:16px}
.pipe{display:grid;grid-template-columns:repeat(5,1fr) auto;gap:8px;align-items:stretch}
.stage{position:relative;padding:12px 14px;border-radius:12px;background:var(--chip)}
.stage .n{font-size:28px;font-weight:650;font-variant-numeric:tabular-nums;line-height:1.1}
.stage .k{font-size:13px;color:var(--ink2)}.stage .p{font-size:12px;color:var(--muted)}
.stage.on{background:var(--accent-soft)}.stage.win{background:var(--good-soft)}
.stage.rej{background:var(--grey-soft);min-width:110px}
@media (max-width:760px){.pipe{grid-template-columns:repeat(2,1fr)}}
.tiles{display:flex;gap:24px;flex-wrap:wrap;margin-top:14px;font-size:14px;color:var(--ink2)}
.tiles b{color:var(--ink);font-variant-numeric:tabular-nums}
.grid2{display:grid;grid-template-columns:1.2fr 1fr;gap:16px}.grid2>.card{margin-bottom:16px}
@media (max-width:860px){.grid2{grid-template-columns:1fr}}
ul.list{list-style:none;margin:0;padding:0}ul.list>li{padding:10px 0;border-top:1px solid var(--line)}ul.list>li:first-child{border-top:0;padding-top:0}
.row1{display:flex;justify-content:space-between;gap:8px;align-items:baseline}
.why{font-size:13px;color:var(--ink2)}
.btns{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
button{font:inherit;font-size:13px;padding:4px 10px;border-radius:99px;border:1px solid var(--line);background:var(--surface);color:var(--ink);cursor:pointer}
button:hover{border-color:var(--accent);color:var(--accent)}button:focus-visible,select:focus-visible,input:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
.tag{display:inline-block;font-size:12px;font-weight:600;padding:2px 9px;border-radius:99px;white-space:nowrap}
.s-ready{background:var(--warn-soft);color:var(--warn)}.s-sub{background:var(--accent-soft);color:var(--accent)}
.s-oa,.s-int{background:var(--purple-soft);color:var(--purple)}.s-offer,.s-acc{background:var(--good-soft);color:var(--good)}
.s-rej,.s-wd,.s-skip,.s-dec{background:var(--grey-soft);color:var(--ink2)}.s-need{background:var(--bad-soft);color:var(--bad)}
.empty{color:var(--muted);margin:0}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th,td{text-align:left;padding:9px 8px;border-top:1px solid var(--line);vertical-align:top}th{color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.04em;border-top:0}
td.n{font-variant-numeric:tabular-nums;white-space:nowrap}.wrap{overflow-x:auto}a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.controls{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}
input,select{font:inherit;font-size:14px;padding:6px 10px;border-radius:9px;border:1px solid var(--line);background:var(--surface);color:var(--ink)}
.cols{display:flex;align-items:flex-end;gap:4px;height:120px;border-bottom:1px solid var(--line);padding-top:16px}
.col{flex:1;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;height:100%;position:relative}
.col .c{width:100%;max-width:26px;background:var(--accent);border-radius:5px 5px 0 0}.col .t{position:absolute;font-size:11px}
.xl{display:flex;gap:4px;font-size:11px;color:var(--muted);margin-top:4px}.xl span{flex:1;text-align:center;white-space:nowrap;overflow:hidden}
.help{font-size:13px;color:var(--ink2);background:var(--chip);border-radius:10px;padding:10px 12px;margin-top:4px}
.flag{font-size:12px;color:var(--warn)}
#toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%) translateY(20px);background:var(--ink);color:var(--surface);padding:9px 14px;border-radius:10px;font-size:14px;opacity:0;transition:.18s;pointer-events:none;max-width:calc(100% - 32px)}
#toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
</style></head><body><main>
<header><div><h1>Your job search</h1><p class="sub" id="sub"></p></div></header>

<section class="card" aria-label="Pipeline"><div class="pipe" id="pipe"></div><div class="tiles" id="tiles"></div></section>

<div class="grid2">
 <section class="card"><h2>Needs your update</h2><ul class="list" id="due"></ul>
  <p class="help">Click what happened and paste the copied line to Claude, or just tell Claude in your own words
  ("Northwind invited me to a second interview"). Claude updates the tracker and rebuilds this page.</p></section>
 <section class="card"><h2>To do</h2><ul class="list" id="todo"></ul></section>
</div>

<section class="card"><h2>All applications</h2>
 <div class="controls"><input id="q" placeholder="Search company or role" aria-label="Search applications">
  <select id="fs" aria-label="Filter by status"><option value="">All statuses</option></select></div>
 <div class="wrap"><table><thead><tr><th>Company</th><th>Role</th><th>Status</th><th>Stage / next step</th><th>Applied</th><th>Updated</th><th>Links</th><th>Update</th></tr></thead><tbody id="rows"></tbody></table></div>
</section>

<section class="card"><h2>Applications sent per week</h2><div id="weeks"></div></section>

<section class="card"><h2>Best matches from the latest search</h2><p class="sub muted" id="msub" style="margin:-6px 0 10px"></p>
 <div class="wrap"><table><thead><tr><th>Fit</th><th>Role</th><th>Company</th><th>Location</th><th>Posted</th><th>Why</th></tr></thead><tbody id="matches"></tbody></table></div>
</section>
<div id="toast" role="status" aria-live="polite"></div>
</main>
<script>
const D = __DATA__;
const $ = id => document.getElementById(id);
const el = (tag, attrs = {}, ...kids) => { const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) { if (k === 'text') e.textContent = v; else if (k === 'style') e.style.cssText = v;
    else if (k.startsWith('on')) e[k] = v; else e.setAttribute(k, v); }
  kids.forEach(k => e.append(k)); return e; };
const safe = u => /^(https?|file):/i.test(u || '') ? u : null;
const CLS = {'Ready to submit':'s-ready','Submitted':'s-sub','Online assessment':'s-oa','Interviewing':'s-int','Offer':'s-offer',
  'Accepted':'s-acc','Declined':'s-dec','Rejected':'s-rej','Withdrawn':'s-wd','Needs you':'s-need','Skipped':'s-skip'};
const tag = s => el('span', {class: 'tag ' + (CLS[s] || 's-skip'), text: s || '—'});
function toast(msg) { const t = $('toast'); t.textContent = msg; t.classList.add('show'); clearTimeout(toast.h); toast.h = setTimeout(() => t.classList.remove('show'), 2600); }
async function copy(text) {
  try { await navigator.clipboard.writeText(text); }
  catch { const ta = el('textarea', {style: 'position:fixed;opacity:0'}); ta.value = text; document.body.append(ta); ta.select(); document.execCommand('copy'); ta.remove(); }
  toast('Copied. Paste it to Claude: ' + text);
}
const updateLine = (r, what) => what === 'No news'
  ? `Tracker: no news yet from ${r.company} (${r.role}, ${r.id}).`
  : `Tracker: ${r.company} (${r.role}, ${r.id}) is now ${what}.`;

$('sub').textContent = `Updated ${D.generated} · ${D.queue} jobs waiting in your queue`;
const sent = D.s.pipeline[0].n || 0;
D.s.pipeline.forEach((p, i) => $('pipe').append(el('div', {class: 'stage' + (p.stage === 'Accepted' && p.n ? ' win' : p.n ? ' on' : '')},
  el('div', {class: 'n', text: String(p.n)}), el('div', {class: 'k', text: p.stage}),
  el('div', {class: 'p', text: i && sent ? Math.round(100 * p.n / sent) + '% of applied' : i ? '' : 'applications sent'}))));
$('pipe').append(el('div', {class: 'stage rej'}, el('div', {class: 'n', text: String(D.s.rejected)}), el('div', {class: 'k', text: 'Rejected'})));
[['Response rate', D.s.rate === null ? '–' : D.s.rate + '%'], ['Sent this week', D.s.this_week], ['In the queue', D.queue]]
  .forEach(([k, v]) => $('tiles').append(el('span', {}, document.createTextNode(k + ': '), el('b', {text: String(v)}))));

if (!D.s.due.length) $('due').append(el('li', {class: 'empty', text: 'All caught up. Nothing waiting for news.'}));
D.s.due.forEach(r => { const b = el('div', {class: 'btns'});
  ['No news', 'Online assessment', 'Interviewing', 'Offer', 'Accepted', 'Rejected', 'Withdrawn'].forEach(w =>
    b.append(el('button', {type: 'button', text: w, onclick: () => copy(updateLine(r, w))})));
  $('due').append(el('li', {}, el('div', {class: 'row1'}, el('strong', {text: `${r.company}, ${r.role}`}), tag(r.status)),
    el('div', {class: 'why', text: r.why}), b)); });

if (!D.s.todo.length) $('todo').append(el('li', {class: 'empty', text: 'Nothing waiting on you.'}));
D.s.todo.forEach(t => $('todo').append(el('li', {}, el('div', {class: 'row1'}, el('strong', {text: t.name}),
  el('span', {class: 'tag s-skip', text: t.kind})), el('div', {class: 'why', text: t.detail}))));

[...new Set(D.rows.map(r => r.status).filter(Boolean))].forEach(s => $('fs').append(el('option', {value: s, text: s})));
const STATUSES = ['Submitted', 'Online assessment', 'Interviewing', 'Offer', 'Accepted', 'Declined', 'Rejected', 'Withdrawn'];
function drawRows() { const q = $('q').value.toLowerCase(), fs = $('fs').value, body = $('rows'); body.replaceChildren();
  const list = D.rows.filter(r => (!fs || r.status === fs) && (!q || (r.company + ' ' + r.role).toLowerCase().includes(q)));
  if (!list.length) body.append(el('tr', {}, el('td', {colspan: 8, class: 'empty',
    text: D.rows.length ? 'No matches.' : 'No applications yet. Paste a job link to Claude to start.'})));
  list.slice().reverse().forEach(r => { const links = el('td');
    if (safe(r.posting_url)) links.append(el('a', {href: r.posting_url, target: '_blank', rel: 'noopener', text: 'Posting'}));
    if (safe(r.folder)) { if (links.childNodes.length) links.append(document.createTextNode(' · ')); links.append(el('a', {href: r.folder, text: 'Files'})); }
    const sel = el('select', {'aria-label': `Update ${r.company}`}, el('option', {value: '', text: 'Set…'}));
    STATUSES.forEach(s => sel.append(el('option', {value: s, text: s})));
    sel.onchange = () => { if (sel.value) copy(updateLine(r, sel.value)); sel.value = ''; };
    const step = [r.interview_stage, r.next_step || (r.interview_date ? 'Interview ' + r.interview_date : '')].filter(Boolean).join(' · ');
    body.append(el('tr', {}, el('td', {text: r.company}), el('td', {text: r.role}), el('td', {}, tag(r.status)),
      el('td', {text: step}), el('td', {class: 'n', text: r.date_added}),
      el('td', {class: 'n', text: r.days === '' ? '' : r.days === 0 ? 'today' : r.days + 'd ago'}), links, el('td', {}, sel))); }); }
$('q').oninput = drawRows; $('fs').onchange = drawRows; drawRows();

const wmax = Math.max(1, ...D.s.weeks.map(w => w.n)), cols = el('div', {class: 'cols'}), xl = el('div', {class: 'xl'});
D.s.weeks.forEach((w, i) => { const h = 100 * w.n / wmax;
  const col = el('div', {class: 'col', title: `Week of ${w.label}: ${w.n} sent`}, el('div', {class: 'c', style: `height:${h}%`}));
  if (w.n) col.append(el('span', {class: 't', style: `bottom:calc(${h}% + 2px)`, text: String(w.n)}));
  cols.append(col); xl.append(el('span', {text: i % 2 ? '' : w.label})); });
$('weeks').append(cols, xl);

$('msub').textContent = D.matchesSaved ? `From the search on ${D.matchesSaved.replace('T', ' at ')}. Fit is out of 100.` : 'Ask Claude "find jobs that fit me" to see matches here.';
if (!D.matches.length) $('matches').append(el('tr', {}, el('td', {colspan: 6, class: 'empty', text: 'No matches yet.'})));
D.matches.forEach(m => { const a = safe(m.url) ? el('a', {href: m.url, target: '_blank', rel: 'noopener', text: m.title}) : document.createTextNode(m.title);
  const why = el('td', {text: m.why}); if (m.flags.length) why.append(el('div', {class: 'flag', text: 'Check: ' + m.flags.join(', ')}));
  $('matches').append(el('tr', {}, el('td', {class: 'n', text: String(m.fit)}), el('td', {}, a), el('td', {text: m.company}),
    el('td', {text: m.location}), el('td', {class: 'n', text: m.posted || ''}), why)); });
</script></body></html>
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--folder', default='.')
    ap.add_argument('--out')
    a = ap.parse_args()
    folder = os.path.abspath(a.folder)
    today = dt.date.today()
    rows = load_rows(folder)
    matches, saved = latest_matches(folder)
    data = {'generated': dt.datetime.now().strftime('%b %-d, %Y at %-I:%M %p'), 'queue': queue_count(folder),
            's': summarize(rows, today), 'rows': rows, 'matches': matches, 'matchesSaved': saved}
    payload = json.dumps(data, ensure_ascii=False).replace('</', '<\\/')  # can't close the script tag early
    out = a.out or os.path.join(folder, 'dashboard.html')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(PAGE.replace('__DATA__', payload))
    print(json.dumps({'ok': True, 'dashboard': out, 'applications': len(rows), 'to_do': len(data['s']['todo']),
                      'matches': len(matches)}, indent=1))


if __name__ == '__main__':
    main()
