/*
 * Job Kit Autofill - find the form controls on a page and the question each one asks.
 *
 * collect() returns "fields" in document order:
 *   { kind, el, els, options, q: {text, label, context, control, inputType, quality}, required }
 * kind: text | textarea | select | radio | checkbox | checkboxGroup | combobox | listbox | file
 *
 * Question text, in order of trust: aria-labelledby, <label for>/wrapping label, Workday
 * formField label, aria-label, placeholder, title, fieldset legend (groups), nearby preceding
 * text ('near'), and finally id/name/data-automation-id words ('hint', low confidence).
 * Open shadow roots are searched too. Our own UI (data-jobkit-ui) is ignored.
 */
(function (root) {
  'use strict';
  var JK = root.JobKit = root.JobKit || {};
  var T = JK.text;

  var SKIP_TYPES = /^(hidden|submit|button|reset|image|password|range|color)$/;
  var CONTROL_SEL = 'input, select, textarea, [aria-haspopup="listbox"]:not(input)';

  function isOurs(el) { return !!(el.closest && el.closest('[data-jobkit-ui]')); }

  function visible(el) {
    if (!el || !el.getClientRects || !el.getClientRects().length) return false;
    var st = root.getComputedStyle ? root.getComputedStyle(el) : null;
    return !st || (st.visibility !== 'hidden' && st.display !== 'none');
  }

  /* Elements matching sel in a root and every open shadow root below it. */
  function deepQuery(scope, sel) {
    var out = Array.prototype.slice.call(scope.querySelectorAll(sel));
    var all = scope.querySelectorAll('*');
    for (var i = 0; i < all.length; i++) {
      if (all[i].shadowRoot) out = out.concat(deepQuery(all[i].shadowRoot, sel));
    }
    return out;
  }

  function collapse(s) { return String(s || '').replace(/\s+/g, ' ').trim(); }

  /* Text of a node without the text of controls inside it (e.g. a label that wraps a select). */
  function textOf(node) {
    if (!node) return '';
    if (!node.querySelector || !node.querySelector('input, select, textarea, [role="listbox"], [aria-hidden="true"], .visually-hidden-value')) {
      return collapse(node.innerText !== undefined && node.isConnected ? node.innerText || node.textContent : node.textContent);
    }
    var c = node.cloneNode(true);
    var junk = c.querySelectorAll('input, select, textarea, [role="listbox"], [aria-hidden="true"], script, style');
    for (var i = 0; i < junk.length; i++) junk[i].remove();
    return collapse(c.textContent);
  }

  function byIds(el, attr) {
    var ids = (el.getAttribute(attr) || '').split(/\s+/).filter(Boolean);
    if (!ids.length) return '';
    var rootNode = el.getRootNode ? el.getRootNode() : document;
    return collapse(ids.map(function (id) {
      var n = rootNode.getElementById ? rootNode.getElementById(id) : document.getElementById(id);
      return n ? textOf(n) : '';
    }).join(' '));
  }

  function decamel(s) {
    return collapse(String(s || '')
      .replace(/([a-z])([A-Z])/g, '$1 $2')
      .replace(/[_\-\[\]\.:]+/g, ' ')
      .replace(/\d+/g, ' '));
  }

  var GENERIC_PLACEHOLDER = /^(select|select\.\.\.|select one|choose|search|type here|type to search|start typing|enter|mm\/dd\/yyyy|mm\/yyyy|yyyy|dd\/mm\/yyyy)\.*$/i;

  /* The label text that belongs to this one control ('' when none). */
  function ownLabel(el) {
    var t = byIds(el, 'aria-labelledby');
    if (t) return t;
    if (el.labels && el.labels.length) {
      t = collapse(Array.prototype.map.call(el.labels, textOf).join(' '));
      if (t) return t;
    }
    var wd = el.closest && el.closest('[data-automation-id^="formField"]');
    if (wd) {
      var lab = wd.querySelector('label, legend, [data-automation-id="formLabel"]');
      if (lab && (t = textOf(lab))) return t;
    }
    t = collapse(el.getAttribute('aria-label'));
    if (t) return t;
    var wrap = el.closest && el.closest('label');
    if (wrap && (t = textOf(wrap))) return t;
    return '';
  }

  function placeholderOf(el) {
    var t = collapse(el.getAttribute('placeholder') || el.getAttribute('data-placeholder'));
    return t && !GENERIC_PLACEHOLDER.test(t) ? t : '';
  }

  function countControls(node) {
    return node.querySelectorAll ? node.querySelectorAll('input:not([type="hidden"]), select, textarea, [aria-haspopup="listbox"]:not(input)').length : 0;
  }

  /* Text just before the control (or group container), without crossing into another field. */
  function nearbyText(el, groupSize) {
    var node = el;
    var allowed = groupSize || 1;
    for (var depth = 0; depth < 4 && node && node !== document.body; depth++) {
      var sib = node.previousElementSibling;
      for (var k = 0; k < 3 && sib; k++, sib = sib.previousElementSibling) {
        if (isOurs(sib)) continue;
        if (countControls(sib) > 0) return '';
        var t = textOf(sib);
        if (t) return t.length <= 250 ? t : '';
      }
      node = node.parentElement;
      if (node && countControls(node) > allowed) return '';
    }
    return '';
  }

  function hintOf(el) {
    return decamel(el.getAttribute('data-automation-id') || el.getAttribute('name') || el.id || '');
  }

  /* Section heading (h2-h6, legend, role=heading) before the control + Workday section ids. */
  var headingCache = null;
  function headingsFor(rootNode) {
    if (!headingCache) headingCache = new Map();
    if (!headingCache.has(rootNode)) {
      headingCache.set(rootNode, Array.prototype.slice.call(rootNode.querySelectorAll('h2, h3, h4, h5, h6, [role="heading"]:not(h1), legend')).filter(function (h) { return !isOurs(h); }));
    }
    return headingCache.get(rootNode);
  }

  function contextOf(el) {
    var parts = [];
    var a = el.parentElement;
    for (var i = 0; i < 12 && a; i++, a = a.parentElement) {
      var id = a.getAttribute('data-automation-id') || '';
      if (/section|education|experience|work/i.test(id)) parts.push(decamel(id));
    }
    var hs = headingsFor(el.getRootNode ? el.getRootNode() : document);
    var last = null;
    for (var j = 0; j < hs.length; j++) {
      var pos = hs[j].compareDocumentPosition(el);
      if (pos & 4 /* FOLLOWING */) last = hs[j];
      else break;
    }
    if (last) parts.push(textOf(last));
    return parts.join(' ');
  }

  function question(text, quality, el, kind) {
    var inputType = (el.getAttribute && (el.getAttribute('type') || '')).toLowerCase() || (el.tagName === 'TEXTAREA' ? 'textarea' : '');
    return {
      text: T.tidy(text),
      raw: collapse(text),
      label: T.norm(text),
      context: T.norm(contextOf(el)),
      control: kind,
      inputType: inputType,
      quality: quality
    };
  }

  function singleQuestion(el, kind) {
    var t = ownLabel(el);
    if (t) return question(t, 'label', el, kind);
    t = placeholderOf(el) || collapse(el.getAttribute('title'));
    if (t) return question(t, 'label', el, kind);
    if (kind === 'file') {
      var box = el.closest('[class*="upload"], [class*="resume"], [class*="attach"], [data-automation-id]');
      if (box && (t = textOf(box))) return question(t.slice(0, 120), 'near', el, kind);
    }
    t = nearbyText(el, 1);
    if (t) return question(t, 'near', el, kind);
    t = hintOf(el);
    if (t) return question(t, 'hint', el, kind);
    return question('', 'hint', el, kind);
  }

  function commonAncestor(els) {
    var a = els[0].parentElement;
    while (a && !els.every(function (e) { return a.contains(e); })) a = a.parentElement;
    return a;
  }

  function groupContainer(els) {
    var c = els[0].closest('fieldset, [role="radiogroup"], [role="group"]');
    if (c && els.every(function (e) { return c.contains(e); })) return c;
    return commonAncestor(els);
  }

  function groupQuestion(els, kind) {
    var c = groupContainer(els);
    var t = '';
    if (c) {
      if (c.tagName === 'FIELDSET') {
        var lg = c.querySelector('legend');
        if (lg) t = textOf(lg);
      }
      t = t || byIds(c, 'aria-labelledby') || collapse(c.getAttribute('aria-label'));
      var wd = c.closest('[data-automation-id^="formField"]');
      if (!t && wd) { var lab = wd.querySelector('label, legend'); if (lab) t = textOf(lab); }
      if (!t) {
        var near = nearbyText(c, els.length);
        if (near) return question(near, 'near', els[0], kind);
      }
    }
    if (t) return question(t, 'label', els[0], kind);
    var h = hintOf(els[0]);
    return question(h, 'hint', els[0], kind);
  }

  function optionLabel(el) {
    return ownLabel(el) || collapse(el.getAttribute('value')) || '';
  }

  function isRequired(el, raw) {
    var attr = !!(el && (el.required || (el.getAttribute && el.getAttribute('aria-required') === 'true')));
    return attr || /[*\u2731]\s*\)?\s*$/.test(raw || '') || /\(required\)/i.test(raw || '');
  }

  /* Build the field list for the page (or one root). */
  function collect(scope) {
    scope = scope || document;
    headingCache = null;
    var els = deepQuery(scope, CONTROL_SEL);
    var fields = [];
    var groups = new Map();

    els.forEach(function (el) {
      if (isOurs(el) || el.disabled) return;
      var tag = el.tagName;
      var type = (el.getAttribute('type') || (tag === 'INPUT' ? 'text' : '')).toLowerCase();
      if (tag === 'INPUT' && SKIP_TYPES.test(type)) return;
      if (tag === 'INPUT' && el.readOnly && el.getAttribute('role') !== 'combobox') return;

      if (tag === 'INPUT' && (type === 'radio' || type === 'checkbox')) {
        var labelVisible = el.labels && el.labels.length && visible(el.labels[0]);
        if (!visible(el) && !labelVisible && !visible(el.parentElement)) return;
        var key = type + '|' + (el.name ? (el.form ? 'f' : 'd') + el.name : 'c');
        var cont = el.name ? null : el.closest('fieldset, [role="radiogroup"], [role="group"]');
        var mapKey = el.name ? key + '|' + (el.form ? Array.prototype.indexOf.call(document.forms, el.form) : 'x') : cont || el;
        if (!groups.has(mapKey)) {
          var g = { kind: type, els: [] };
          groups.set(mapKey, g);
          fields.push(g);
        }
        groups.get(mapKey).els.push(el);
        return;
      }

      if (tag === 'INPUT' && type === 'file') {
        fields.push({ kind: 'file', el: el });
        return;
      }
      if (!visible(el)) return;
      if (tag === 'SELECT') { fields.push({ kind: 'select', el: el }); return; }
      if (tag === 'TEXTAREA') { fields.push({ kind: 'textarea', el: el }); return; }
      if (tag === 'INPUT') {
        var combo = el.getAttribute('role') === 'combobox' || (el.getAttribute('aria-autocomplete') === 'list' && (el.getAttribute('aria-controls') || el.getAttribute('aria-owns')));
        fields.push({ kind: combo ? 'combobox' : 'text', el: el });
        return;
      }
      // Non-input listbox trigger (Workday-style button); skip wrappers that contain a real input.
      if (el.querySelector('input:not([type="hidden"]), select, textarea')) return;
      fields.push({ kind: 'listbox', el: el });
    });

    fields.forEach(function (f) {
      if (f.els) {
        f.el = f.els[0];
        if (f.kind === 'radio') {
          f.q = groupQuestion(f.els, 'radio');
        } else if (f.els.length > 1) {
          f.kind = 'checkboxGroup';
          f.q = groupQuestion(f.els, 'checkboxGroup');
        } else {
          f.kind = 'checkbox';
          f.q = singleQuestion(f.el, 'checkbox');
          // A short box label like "Yes" means the real question is the group/legend text.
          if (f.q.label.split(' ').length <= 3) {
            var gq = groupQuestion(f.els, 'checkbox');
            if (gq.text && gq.label !== f.q.label) { f.optionText = f.q.text; f.q = question(gq.text + ' ' + f.q.text, gq.quality, f.el, 'checkbox'); }
          }
        }
        f.options = f.els.map(function (e) { return { text: optionLabel(e), value: e.value, el: e }; });
        f.required = f.els.some(function (e) { return isRequired(e, ''); }) || isRequired(null, f.q.raw);
      } else {
        f.q = singleQuestion(f.el, f.kind);
        if (f.kind === 'select') {
          f.options = Array.prototype.map.call(f.el.options, function (o) { return { text: collapse(o.text), value: o.value, el: o }; });
        }
        f.required = isRequired(f.el, f.q.raw);
      }
    });
    return fields;
  }

  /* Does the control already hold an answer? (We never overwrite.) */
  function hasValue(f) {
    var el = f.el;
    switch (f.kind) {
      case 'text': case 'textarea': return String(el.value || '').trim() !== '';
      case 'select': {
        if (el.multiple) return el.selectedOptions.length > 0;
        var o = el.options[el.selectedIndex];
        return !!o && !T.isPlaceholderOption(o.text, o.value);
      }
      case 'radio': case 'checkboxGroup': return f.els.some(function (e) { return e.checked; });
      case 'checkbox': return el.checked;
      case 'file': return !!(el.files && el.files.length);
      case 'combobox': {
        if (String(el.value || '').trim()) return true;
        var box = el.closest('[class*="container"], [class*="select"], [role="group"]') || el.parentElement;
        var sv = box && box.querySelector('[class*="single-value"], [class*="singleValue"], [class*="multi-value"], [class*="multiValue"], [data-selected-value]');
        return !!(sv && collapse(sv.textContent));
      }
      case 'listbox': {
        var t = T.norm(textOf(el));
        return !!t && !/^(select|select one|choose|choose one|please select|none)\b/.test(t);
      }
    }
    return false;
  }

  /* Cheap check used to decide whether to show the page button. */
  function looksLikeForm(scope) {
    scope = scope || document;
    var els = scope.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="search"]), select, textarea');
    var n = 0;
    for (var i = 0; i < els.length && n < 2; i++) {
      if (!isOurs(els[i]) && (visible(els[i]) || els[i].type === 'file')) n++;
    }
    return n >= 2;
  }

  JK.labels = {
    collect: collect, hasValue: hasValue, looksLikeForm: looksLikeForm, textOf: textOf,
    visible: visible, deepQuery: deepQuery, commonAncestor: commonAncestor, groupContainer: groupContainer
  };
})(typeof globalThis !== 'undefined' ? globalThis : this);
