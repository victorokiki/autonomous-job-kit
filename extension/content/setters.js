/*
 * Autonomous Job Kit Autofill - put a value into a control in a way frameworks notice.
 *
 * apply(field, want, opts) -> Promise<{ok, value?, quiet?, reason?}>
 *   ok:true  value = what was entered (for the report)
 *   ok:false reason = why nothing was entered (e.g. 'no matching option')
 *   quiet:true  nothing to do and nothing to report (e.g. a "No" answer on a lone checkbox)
 *
 * Text inputs use the native value setter of the element's prototype, then input/change/blur
 * events, so React, Angular and Vue all see the change. Custom dropdowns (react-select style
 * comboboxes, Workday listbox buttons) are opened with synthetic pointer events, the option
 * list is read, and the matching option is clicked; short waits only, best effort.
 */
(function (root) {
  'use strict';
  var JK = root.JobKit = root.JobKit || {};
  var T = JK.text;

  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  function nativeSetter(el, prop) {
    var proto = Object.getPrototypeOf(el);
    while (proto) {
      var d = Object.getOwnPropertyDescriptor(proto, prop);
      if (d && d.set) return d.set;
      proto = Object.getPrototypeOf(proto);
    }
    return null;
  }

  function fire(el, type) {
    el.dispatchEvent(new Event(type, { bubbles: true, cancelable: false }));
  }

  function key(el, k) {
    el.dispatchEvent(new KeyboardEvent('keydown', { key: k, code: k, bubbles: true, cancelable: true }));
    el.dispatchEvent(new KeyboardEvent('keyup', { key: k, code: k, bubbles: true, cancelable: true }));
  }

  function pointerClick(el) {
    var opts = { bubbles: true, cancelable: true, composed: true, button: 0 };
    try { el.dispatchEvent(new PointerEvent('pointerdown', opts)); } catch (e) { /* older engines */ }
    el.dispatchEvent(new MouseEvent('mousedown', opts));
    try { el.dispatchEvent(new PointerEvent('pointerup', opts)); } catch (e2) { /* older engines */ }
    el.dispatchEvent(new MouseEvent('mouseup', opts));
    el.dispatchEvent(new MouseEvent('click', opts));
  }

  function setValue(el, value) {
    try { el.focus({ preventScroll: true }); } catch (e) { /* not focusable */ }
    var set = nativeSetter(el, 'value');
    if (set) set.call(el, value); else el.value = value;
    fire(el, 'input');
    fire(el, 'change');
    try { el.blur(); } catch (e3) { /* ignore */ }
    fire(el, 'focusout');
  }

  /* ---- converting a "want" into display text or an option picker ---- */
  function dateHow(f) {
    var t = f.q.inputType;
    var l = f.q.label;
    if (t === 'date') return 'date';
    if (t === 'month') return 'month';
    if (/\byear\b/.test(l) && !/\bmonth\b/.test(l)) return 'year';
    if (/\bmonth\b/.test(l) && !/\byear\b/.test(l)) return 'monthName';
    var ph = (f.el && f.el.getAttribute && f.el.getAttribute('placeholder')) || '';
    if (/^mm\/dd\/yyyy$/i.test(ph)) return 'mmddyyyy';
    if (/^mm\/yyyy$/i.test(ph)) return 'mmyyyy';
    if (/^(yyyy-mm-dd)$/i.test(ph)) return 'date';
    return 'text';
  }

  function displayText(want, f) {
    switch (want.kind) {
      case 'text': return want.text;
      case 'yesno': return want.value === 'yes' ? 'Yes' : 'No';
      case 'choice': return want.display;
      case 'date': return T.formatDate(want.value, dateHow(f));
    }
    return '';
  }

  /* Ordered list of option pickers to try for selects, radios and custom dropdowns. */
  function pickers(want, f) {
    var out = [];
    if (want.kind === 'yesno') {
      out.push({ matcher: function (t) { return T.classifyYesNo(t) === want.value; } });
      if (want.fallbackText) out.push({ text: want.fallbackText });
    } else if (want.kind === 'choice') {
      var m = T.choiceMatcher(want.group, want.code);
      if (m) out.push({ matcher: m });
    } else if (want.kind === 'date') {
      var how = dateHow(f);
      var p = T.parseDate(want.value);
      if (how === 'monthName' && p && p.m) {
        out.push({ matcher: function (t) { var n = T.norm(t); return n === String(p.m) || n === ('0' + p.m).slice(-2) || n.slice(0, 3) === T.MONTHS[p.m - 1].slice(0, 3); } });
      } else if (how === 'year' && p) {
        out.push({ text: String(p.y) });
      } else {
        out.push({ text: want.value, aliases: [T.formatDate(want.value, 'monthName') + ' ' + (p ? p.y : '')] });
      }
    } else {
      (want.matchers || []).forEach(function (m) { out.push({ matcher: m }); });
      // "English (fluent)" should still find "English (ENG)": also try the answer without its bracketed note.
      var bare = String(want.text || '').replace(/\s*\([^)]*\)\s*/g, ' ').trim();
      var aliases = (want.aliases || []).concat(bare && bare !== want.text ? [bare] : []);
      out.push({ text: want.text, aliases: aliases, number: want.number, prefer: want.prefer });
    }
    return out;
  }

  function pick(options, want, f) {
    var ps = pickers(want, f);
    for (var i = 0; i < ps.length; i++) {
      var idx = T.pickOption(options, ps[i]);
      if (idx !== -1) return idx;
    }
    return -1;
  }

  /* ---- per-kind setters ---- */
  function applyText(f, want) {
    var v = displayText(want, f);
    if (!v) return { ok: false, reason: 'format' };
    if (f.el.maxLength > 0 && v.length > f.el.maxLength) return { ok: false, reason: 'too long' };
    setValue(f.el, v);
    return { ok: String(f.el.value) === v || String(f.el.value).trim() !== '', value: v };
  }

  function applySelect(f, want) {
    var idx = pick(f.options, want, f);
    if (idx === -1) return { ok: false, reason: 'no matching option' };
    var el = f.el;
    try { el.focus({ preventScroll: true }); } catch (e) { /* ignore */ }
    var set = nativeSetter(el, 'value');
    if (set) set.call(el, f.options[idx].value); else el.value = f.options[idx].value;
    if (el.selectedIndex !== idx) el.selectedIndex = idx;
    fire(el, 'input');
    fire(el, 'change');
    try { el.blur(); } catch (e2) { /* ignore */ }
    return { ok: true, value: f.options[idx].text };
  }

  function applyRadio(f, want) {
    var idx = pick(f.options, want, f);
    if (idx === -1) return { ok: false, reason: 'no matching option' };
    var el = f.options[idx].el;
    if (!el.checked) el.click();
    if (!el.checked) { el.checked = true; fire(el, 'input'); fire(el, 'change'); }
    return { ok: el.checked, value: f.options[idx].text };
  }

  function applyCheckbox(f, want) {
    if (want.kind === 'yesno') {
      if (want.value !== 'yes') return { ok: false, quiet: true };
      if (!f.el.checked) f.el.click();
      return { ok: f.el.checked, value: 'ticked' };
    }
    if (want.kind === 'choice' && f.optionText) {
      var m = T.choiceMatcher(want.group, want.code);
      if (m && m(f.optionText)) {
        if (!f.el.checked) f.el.click();
        return { ok: f.el.checked, value: f.optionText };
      }
      return { ok: false, quiet: true };
    }
    return { ok: false, reason: 'not a yes/no box' };
  }

  function applyCheckboxGroup(f, want) {
    var idx = pick(f.options, want, f);
    if (idx === -1) return { ok: false, reason: 'no matching option' };
    var el = f.options[idx].el;
    if (!el.checked) el.click();
    return { ok: el.checked, value: f.options[idx].text };
  }

  function base64ToFile(resume) {
    var bin = atob(resume.data);
    var bytes = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return new File([bytes], resume.name || 'resume.pdf', { type: resume.type || 'application/pdf', lastModified: resume.savedAt || Date.now() });
  }

  function applyFile(f, want, opts) {
    var resume = opts && opts.resume;
    if (opts && opts.resumeSkipped) return { ok: false, reason: 'attach the resume tailored for this job' };
    if (!resume || !resume.data) return { ok: false, reason: 'no resume saved' };
    var accept = (f.el.getAttribute('accept') || '').toLowerCase();
    if (accept && !/pdf|application\/\*|\*\/\*/.test(accept) && !/\.pdf/.test(accept)) return { ok: false, reason: 'PDF not accepted' };
    try {
      var dt = new DataTransfer();
      dt.items.add(base64ToFile(resume));
      f.el.files = dt.files;
      fire(f.el, 'input');
      fire(f.el, 'change');
    } catch (e) {
      return { ok: false, reason: 'upload blocked' };
    }
    return { ok: !!(f.el.files && f.el.files.length), value: resume.name };
  }

  /* ---- custom dropdowns ---- */
  function rootOf(el) { return el.getRootNode ? el.getRootNode() : document; }

  function optionNodes(trigger) {
    var r = rootOf(trigger);
    var ids = ((trigger.getAttribute('aria-controls') || '') + ' ' + (trigger.getAttribute('aria-owns') || '')).split(/\s+/).filter(Boolean);
    var lists = [];
    ids.forEach(function (id) { var n = r.getElementById ? r.getElementById(id) : document.getElementById(id); if (n) lists.push(n); });
    var nodes = [];
    lists.forEach(function (l) { nodes = nodes.concat(Array.prototype.slice.call(l.querySelectorAll('[role="option"]'))); if (l.getAttribute('role') === 'option') nodes.push(l); });
    if (!nodes.length) {
      nodes = JK.labels.deepQuery(document, '[role="option"], [class*="__option"], [class*="-option"]:not([class*="options"])');
    }
    return nodes.filter(function (n) { return JK.labels.visible(n) && !n.closest('[data-jobkit-ui]') && n.getAttribute('aria-disabled') !== 'true'; });
  }

  async function waitForOptions(trigger, ms) {
    var end = Date.now() + ms;
    var nodes = [];
    while (Date.now() < end) {
      nodes = optionNodes(trigger);
      if (nodes.length) { await sleep(60); return optionNodes(trigger); }
      await sleep(80);
    }
    return nodes;
  }

  function asOptions(nodes) {
    return nodes.map(function (n) { return { text: JK.labels.textOf(n), value: n.getAttribute('data-value') || '', el: n }; });
  }

  function closeMenu(el) {
    key(el, 'Escape');
    try { el.blur(); } catch (e) { /* ignore */ }
  }

  async function applyCombobox(f, want) {
    var el = f.el;
    try { el.focus({ preventScroll: true }); } catch (e) { /* ignore */ }
    pointerClick(el);
    key(el, 'ArrowDown');
    var opts = asOptions(await waitForOptions(el, 900));
    var idx = opts.length ? pick(opts, want, f) : -1;
    if (idx === -1 && (want.kind === 'text' || want.kind === 'date')) {
      var typed = want.typeText || displayText(want, f);
      if (typed) {
        var set = nativeSetter(el, 'value');
        if (set) set.call(el, typed); else el.value = typed;
        fire(el, 'input');
        await sleep(350);
        opts = asOptions(await waitForOptions(el, 1500));
        idx = opts.length ? pick(opts, want, f) : -1;
        if (idx === -1 && want.typeText && opts.length) idx = T.pickOption(opts, { text: want.typeText, prefer: want.prefer });
      }
    }
    if (idx === -1) {
      var clear = nativeSetter(el, 'value');
      if (el.value) { if (clear) clear.call(el, ''); else el.value = ''; fire(el, 'input'); }
      closeMenu(el);
      return { ok: false, reason: 'no matching option' };
    }
    var chosen = opts[idx];
    pointerClick(chosen.el);
    await sleep(150);
    return { ok: true, value: chosen.text };
  }

  async function applyListbox(f, want) {
    var el = f.el;
    var before = JK.labels.textOf(el);
    pointerClick(el);
    var opts = asOptions(await waitForOptions(el, 1200));
    if (!opts.length) { key(el, 'Enter'); opts = asOptions(await waitForOptions(el, 800)); }
    var idx = opts.length ? pick(opts, want, f) : -1;
    if (idx === -1) {
      closeMenu(document.activeElement || el);
      return { ok: false, reason: 'no matching option' };
    }
    var chosen = opts[idx];
    pointerClick(chosen.el);
    await sleep(200);
    var after = JK.labels.textOf(el);
    return { ok: after !== before || JK.labels.hasValue(f), value: chosen.text };
  }

  async function apply(f, want, opts) {
    switch (f.kind) {
      case 'text': case 'textarea': return applyText(f, want);
      case 'select': return applySelect(f, want);
      case 'radio': return applyRadio(f, want);
      case 'checkbox': return applyCheckbox(f, want);
      case 'checkboxGroup': return applyCheckboxGroup(f, want);
      case 'file': return applyFile(f, want, opts);
      case 'combobox': return applyCombobox(f, want);
      case 'listbox': return applyListbox(f, want);
    }
    return { ok: false, reason: 'unsupported control' };
  }

  JK.setters = { apply: apply, setValue: setValue, pointerClick: pointerClick, displayText: displayText, sleep: sleep };
})(typeof globalThis !== 'undefined' ? globalThis : this);
