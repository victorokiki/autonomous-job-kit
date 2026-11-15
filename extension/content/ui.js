/*
 * Autonomous Job Kit Autofill - what the user (and Claude) sees on the page.
 *
 *  - Page button "Fill with Autonomous" (right edge). Only a trusted click (event.isTrusted) starts
 *    a fill, so page scripts cannot trigger it.
 *  - Result panel listing filled / already filled / left for you.
 *  - Report block: visually hidden but readable text at the top of the form, starting with
 *    "Autonomous report:", for Claude's get_page_text.
 *  - Marks: solid green outline on fields we filled, dashed amber outline on fields left empty.
 *
 * The button and panel live in an open shadow root so page CSS cannot restyle them.
 */
(function (root) {
  'use strict';
  var JK = root.JobKit = root.JobKit || {};

  var REPORT_ID = 'jobkit-report';
  var HOST_ID = 'jobkit-ui-host';
  var WORKING_TEXT = 'Autonomous report: busy filling this page. Check back in about 5 seconds.';

  var host = null, shadow = null, button = null, panel = null, onFillCb = null;
  var marked = new Map(); // element -> {outline, outlineOffset}

  var CSS = [
    ':host { all: initial; }',
    '* { box-sizing: border-box; }',
    '.jk { --bg:#ffffff; --fg:#1d2433; --muted:#5b6475; --line:#d8dde6; --accent:#1f5fbf; --accent-fg:#ffffff; --ok:#1b7f3b; --warn:#9a5b00; --shadow:0 8px 28px rgba(15,23,42,.18);',
    '  font: 13px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; color: var(--fg); }',
    '@media (prefers-color-scheme: dark) { .jk { --bg:#1c212b; --fg:#e8ecf3; --muted:#a7b0c0; --line:#3a4252; --accent:#7fb0ff; --accent-fg:#0d1420; --ok:#6fd38f; --warn:#f3b34c; --shadow:0 8px 28px rgba(0,0,0,.5); } }',
    '.btn-fill { position: fixed; right: 0; top: 42%; z-index: 2147483646; display: flex; align-items: center; gap: 6px;',
    '  padding: 9px 12px 9px 10px; border: 1px solid var(--line); border-right: 0; border-radius: 10px 0 0 10px;',
    '  background: var(--accent); color: var(--accent-fg); font: 600 13px/1 system-ui, -apple-system, "Segoe UI", sans-serif; cursor: pointer; box-shadow: var(--shadow); }',
    '.btn-fill:hover { filter: brightness(1.08); }',
    '.btn-fill[hidden] { display: none; }',
    '.btn-fill:focus-visible, .close:focus-visible, summary:focus-visible { outline: 3px solid #f0b400; outline-offset: 2px; }',
    '.btn-fill[aria-busy="true"] { opacity: .75; cursor: progress; }',
    '.mark { display:inline-grid; place-items:center; width:20px; height:20px; border-radius:5px; background: var(--accent-fg); color: var(--accent); font: 800 10px/1 system-ui, sans-serif; }',
    '.panel { position: fixed; right: 12px; bottom: 12px; z-index: 2147483647; width: min(360px, calc(100vw - 24px)); max-height: min(70vh, 560px);',
    '  display: flex; flex-direction: column; background: var(--bg); color: var(--fg); border: 1px solid var(--line); border-radius: 12px; box-shadow: var(--shadow); }',
    '.head { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 12px 14px; border-bottom: 1px solid var(--line); }',
    '.head h2 { margin: 0; font-size: 14px; font-weight: 700; }',
    '.close { border: 1px solid var(--line); background: transparent; color: var(--fg); border-radius: 8px; width: 28px; height: 28px; font-size: 16px; line-height: 1; cursor: pointer; }',
    '.body { padding: 10px 14px 14px; overflow: auto; }',
    '.counts { display: flex; gap: 12px; margin: 0 0 8px; padding: 0; list-style: none; }',
    '.counts b { font-size: 16px; }',
    '.ok { color: var(--ok); } .warn { color: var(--warn); }',
    'details { border-top: 1px solid var(--line); padding: 6px 0; }',
    'summary { cursor: pointer; font-weight: 600; padding: 2px 0; }',
    'ul.items { margin: 6px 0 0; padding-left: 18px; }',
    'ul.items li { margin: 2px 0; }',
    '.why { color: var(--muted); }',
    '.note { margin: 10px 0 0; color: var(--muted); }'
  ].join('\n');

  function el(tag, attrs, text) {
    var n = document.createElement(tag);
    if (attrs) for (var k in attrs) n.setAttribute(k, attrs[k]);
    if (text !== undefined) n.textContent = text;
    return n;
  }

  function ensureHost() {
    if (host && host.isConnected) return;
    host = document.getElementById(HOST_ID);
    if (!host) {
      host = el('div', { id: HOST_ID, 'data-jobkit-ui': '' });
      host.style.cssText = 'all: initial; position: static;';
      (document.body || document.documentElement).appendChild(host);
    }
    shadow = host.shadowRoot || host.attachShadow({ mode: 'open' });
    shadow.innerHTML = '';
    shadow.appendChild(el('style', null, CSS));
    var wrap = el('div', { 'class': 'jk' });
    shadow.appendChild(wrap);
    button = null;
    panel = null;
  }

  function wrapNode() { ensureHost(); return shadow.querySelector('.jk'); }

  /* ---- page button ---- */
  function showButton(show, onFill) {
    onFillCb = onFill || onFillCb;
    if (!show) { if (button) { button.remove(); button = null; } return; }
    if (button && button.isConnected) return;
    var w = wrapNode();
    button = el('button', { type: 'button', 'class': 'btn-fill', title: 'Fill this form from your Autonomous Job Kit profile (Alt+Shift+F). Nothing is submitted.' });
    button.appendChild(el('span', { 'class': 'mark', 'aria-hidden': 'true' }, 'JK'));
    button.appendChild(el('span', null, 'Fill with Autonomous'));
    button.addEventListener('click', function (e) {
      if (!e.isTrusted) return; // page scripts cannot start a fill
      if (onFillCb) onFillCb('button');
    });
    if (panel && panel.isConnected) button.hidden = true;
    w.appendChild(button);
  }

  function setBusy(busy) {
    if (!button) return;
    button.setAttribute('aria-busy', busy ? 'true' : 'false');
    button.lastChild.textContent = busy ? 'Filling…' : 'Fill with Autonomous';
  }

  /* ---- report block (light DOM, readable by get_page_text) ---- */
  function reportTarget(fields) {
    var counts = new Map();
    (fields || []).forEach(function (f) {
      var form = f.el && f.el.closest && f.el.closest('form');
      if (form && form.getRootNode() === document) counts.set(form, (counts.get(form) || 0) + 1);
    });
    var best = null, n = 0;
    counts.forEach(function (v, k) { if (v > n) { n = v; best = k; } });
    return best || document.body || document.documentElement;
  }

  function setReport(text, fields) {
    var r = document.getElementById(REPORT_ID);
    if (!r) {
      r = el('div', { id: REPORT_ID, 'data-jobkit-ui': '', role: 'status', 'aria-live': 'polite' });
      r.style.cssText = 'position:absolute !important; width:1px !important; height:1px !important; margin:-1px !important; padding:0 !important; border:0 !important; overflow:hidden !important; clip:rect(0 0 0 0) !important; clip-path:inset(50%) !important; white-space:normal !important;';
    }
    var target = reportTarget(fields);
    if (r.parentNode !== target || target.firstChild !== r) target.insertBefore(r, target.firstChild);
    r.textContent = text;
    return r;
  }

  function working(fields) { return setReport(WORKING_TEXT, fields); }

  var REASONS = {
    'consent': 'agreement - yours to tick', 'sensitive': 'sensitive - left for you', 'open-ended': 'open question',
    'not in profile': 'not in profile', 'no matching option': 'no matching option', 'ambiguous': 'sponsorship answers differ',
    'other-country': 'about a different country', 'low confidence': 'unsure', 'not about you': 'not about you',
    'no resume saved': 'no resume saved', 'PDF not accepted': 'PDF not accepted', 'file': 'file', 'format': 'format unclear'
  };
  var KINDS = { text: 'text', textarea: 'textarea', select: 'dropdown', combobox: 'dropdown', listbox: 'dropdown', radio: 'choice', checkbox: 'checkbox', checkboxGroup: 'checkboxes', file: 'file' };

  function describeLeft(item) {
    var bits = [KINDS[item.kind] || item.kind];
    if (item.required) bits.push('required');
    var why = REASONS[item.reason];
    if (why && why !== bits[0]) bits.push(why);
    return item.label + ' (' + bits.join(', ') + ')';
  }

  /* "Profile: imported 2026-11-14, 2 saved answers." - lets Claude spot an out-of-date profile. */
  function freshness(profile, meta) {
    var n = Array.isArray(profile && profile.savedAnswers) ? profile.savedAnswers.filter(function (a) { return a && a.match && a.answer; }).length : 0;
    var when = meta && meta.date ? (meta.source === 'saved' ? 'saved ' : 'imported ') + meta.date : 'import date unknown';
    return 'Profile: ' + when + ', ' + n + ' saved answer' + (n === 1 ? '' : 's') + '.';
  }

  function reportText(res, fresh) {
    var left = res.left.slice().sort(function (a, b) { return (b.required ? 1 : 0) - (a.required ? 1 : 0); });
    var t = 'Autonomous report: filled ' + res.filled.length + ', already filled ' + res.already.length + ', left ' + left.length + '.';
    if (left.length) {
      var shown = left.slice(0, 30).map(describeLeft);
      t += ' Left: ' + shown.join('; ') + (left.length > 30 ? '; and ' + (left.length - 30) + ' more' : '') + '.';
    }
    if (res.filled.length) t += ' Filled: ' + res.filled.slice(0, 40).map(function (i) { return i.label; }).join('; ') + '.';
    t += ' Nothing was submitted. Review every answer before continuing.';
    if (fresh) t += ' ' + fresh;
    return t;
  }

  /* ---- result panel ---- */
  function list(title, items, open, cls, fmt) {
    var d = el('details');
    if (open) d.open = true;
    var s = el('summary', cls ? { 'class': cls } : null, title + ' (' + items.length + ')');
    d.appendChild(s);
    if (items.length) {
      var ul = el('ul', { 'class': 'items' });
      items.forEach(function (i) { ul.appendChild(fmt(i)); });
      d.appendChild(ul);
    }
    return d;
  }

  function showPanel(res, message) {
    var w = wrapNode();
    if (panel) panel.remove();
    panel = el('section', { 'class': 'panel', role: 'region', 'aria-label': 'Autonomous Job Kit report' });
    var head = el('div', { 'class': 'head' });
    head.appendChild(el('h2', null, message ? 'Autonomous Job Kit' : 'Autonomous Job Kit filled this page'));
    var close = el('button', { type: 'button', 'class': 'close', 'aria-label': 'Close Autonomous Job Kit report' }, '×');
    close.addEventListener('click', function () { panel.remove(); panel = null; if (button) { button.hidden = false; button.focus(); } });
    head.appendChild(close);
    panel.appendChild(head);
    var body = el('div', { 'class': 'body' });
    if (message) {
      body.appendChild(el('p', null, message));
    } else {
      var counts = el('ul', { 'class': 'counts' });
      [['Filled', res.filled.length, 'ok'], ['Already filled', res.already.length, ''], ['Left for you', res.left.length, 'warn']].forEach(function (c) {
        var li = el('li', c[2] ? { 'class': c[2] } : null);
        li.appendChild(el('b', null, String(c[1])));
        li.appendChild(document.createTextNode(' ' + c[0]));
        counts.appendChild(li);
      });
      body.appendChild(counts);
      body.appendChild(list('Left for you', res.left, true, 'warn', function (i) {
        var li = el('li', null, i.label + (i.required ? ' *' : ''));
        var why = REASONS[i.reason];
        if (why) li.appendChild(el('span', { 'class': 'why' }, ' - ' + why));
        return li;
      }));
      body.appendChild(list('Filled', res.filled, false, 'ok', function (i) {
        var li = el('li', null, i.label);
        if (i.value) li.appendChild(el('span', { 'class': 'why' }, ': ' + String(i.value).slice(0, 60)));
        return li;
      }));
      body.appendChild(list('Already filled (not changed)', res.already, false, '', function (i) { return el('li', null, i.label); }));
      body.appendChild(el('p', { 'class': 'note' }, 'Nothing was submitted. Green outline = filled by Autonomous Job Kit, dashed amber = left for you. Check every answer before you continue.'));
    }
    panel.appendChild(body);
    w.appendChild(panel);
    if (button) button.hidden = true; // the panel replaces the button until it is closed
    close.focus();
  }

  /* ---- marks ---- */
  function markTarget(f) {
    if (f.els && f.els.length > 1) {
      var c = JK.labels.groupContainer(f.els);
      if (c && c !== document.body && c.tagName !== 'FORM') return c;
    }
    var n = f.el;
    for (var i = 0; i < 4 && n; i++) {
      var r = n.getBoundingClientRect ? n.getBoundingClientRect() : null;
      if (r && r.width >= 16 && r.height >= 10) return n;
      n = n.parentElement;
    }
    return f.el;
  }

  function mark(f, type) {
    var t = markTarget(f);
    if (!t || !t.style) return;
    if (!marked.has(t)) marked.set(t, { outline: t.style.outline, offset: t.style.outlineOffset });
    t.style.setProperty('outline', type === 'filled' ? '2px solid #1b7f3b' : '2px dashed #d08700', 'important');
    t.style.setProperty('outline-offset', '2px', 'important');
    t.setAttribute('data-jobkit-mark', type);
    if (type === 'left') {
      var clear = function () { unmark(t); };
      (f.els || [f.el]).forEach(function (e) { e.addEventListener('change', clear, { once: true }); e.addEventListener('input', clear, { once: true }); });
    }
  }

  function unmark(t) {
    var prev = marked.get(t);
    if (!prev) return;
    t.style.outline = prev.outline;
    t.style.outlineOffset = prev.offset;
    t.removeAttribute('data-jobkit-mark');
    marked.delete(t);
  }

  /* type 'left' clears only amber marks (a re-run keeps the green marks from earlier runs). */
  function clearMarks(type) {
    Array.from(marked.keys()).forEach(function (t) { if (!type || t.getAttribute('data-jobkit-mark') === type) unmark(t); });
  }

  JK.ui = {
    showButton: showButton, setBusy: setBusy, working: working, setReport: setReport, reportText: reportText,
    showPanel: showPanel, freshness: freshness, mark: mark, clearMarks: clearMarks, WORKING_TEXT: WORKING_TEXT
  };
})(typeof globalThis !== 'undefined' ? globalThis : this);
