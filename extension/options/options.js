/*
 * Autonomous Job Kit Autofill - options page (profile editor).
 *
 * Builds the form from JobKit.schema (shared/profile-schema.js), loads the profile from
 * chrome.storage.local, and saves it back with schema.applyFormValues() so keys this page does
 * not show (kit settings, projects, ...) survive. Also: import / download profile.json, resume
 * PDF (base64, max 5 MB) and the page-button switch.
 */
(function () {
  'use strict';
  var S = globalThis.JobKit.schema;

  /* chrome.storage.local, or an in-memory stand-in when the page is opened outside the extension. */
  var store = (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) ? chrome.storage.local : (function () {
    var mem = {};
    return {
      get: function (keys) { var o = {}; [].concat(keys).forEach(function (k) { if (k in mem) o[k] = mem[k]; }); return Promise.resolve(o); },
      set: function (o) { Object.assign(mem, o); return Promise.resolve(); },
      remove: function (k) { [].concat(k).forEach(function (x) { delete mem[x]; }); return Promise.resolve(); }
    };
  })();

  var $ = function (id) { return document.getElementById(id); };
  var stored = {};
  var dirty = false;
  var uid = 0;

  function status(msg, kind) {
    var p = $('status');
    p.textContent = msg;
    p.className = kind || '';
  }

  /* Freshness stamp read by the page report ("Profile: imported 2026-11-14, ..."). Local date. */
  function meta(source) {
    var d = new Date();
    var pad = function (n) { return (n < 10 ? '0' : '') + n; };
    return { source: source, date: d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) };
  }

  function markDirty() {
    if (!dirty) { dirty = true; status('Unsaved changes.', 'warn'); }
  }

  /* ---- building controls ---- */
  function control(def, value, idBase) {
    var id = idBase + '-' + def.key;
    var wrap = document.createElement('div');
    wrap.className = 'field' + (def.type === 'textarea' ? ' wide' : '');
    var label = document.createElement('label');
    label.htmlFor = id;
    label.textContent = def.label;
    wrap.appendChild(label);
    var input;
    if (def.type === 'select') {
      input = document.createElement('select');
      var choices = def.choices.slice();
      if (value && !choices.some(function (c) { return c.value === value; })) {
        choices.push({ value: value, label: value + ' (from profile.json)' });
      }
      choices.forEach(function (c) {
        var o = document.createElement('option');
        o.value = c.value;
        o.textContent = c.label;
        input.appendChild(o);
      });
      input.value = value || '';
    } else if (def.type === 'textarea') {
      input = document.createElement('textarea');
      input.rows = 3;
      input.value = value || '';
    } else {
      input = document.createElement('input');
      input.type = def.type || 'text';
      if (input.type === 'date' && value && !/^\d{4}-\d{2}-\d{2}$/.test(value)) input.type = 'text';
      input.value = value || '';
      if (def.auto) input.autocomplete = def.auto;
      else input.autocomplete = 'off';
      input.spellcheck = false;
    }
    input.id = id;
    input.dataset.key = def.key;
    if (def.help) {
      var help = document.createElement('p');
      help.className = 'help';
      help.id = id + '-help';
      help.textContent = def.help;
      input.setAttribute('aria-describedby', help.id);
      wrap.appendChild(input);
      wrap.appendChild(help);
    } else {
      wrap.appendChild(input);
    }
    return wrap;
  }

  function listItem(listName, row, index) {
    var def = S.LISTS[listName];
    var n = ++uid;
    var box = document.createElement('div');
    box.className = 'list-item';
    box.setAttribute('role', 'group');
    if (typeof row._origin === 'number') box.dataset.origin = String(row._origin);
    var head = document.createElement('div');
    head.className = 'list-item-head';
    var h = document.createElement('h3');
    h.id = 'li-h-' + n;
    head.appendChild(h);
    var rm = document.createElement('button');
    rm.type = 'button';
    rm.className = 'danger';
    rm.textContent = 'Remove';
    head.appendChild(rm);
    box.setAttribute('aria-labelledby', h.id);
    box.appendChild(head);
    var grid = document.createElement('div');
    grid.className = 'grid';
    def.fields.forEach(function (f) { grid.appendChild(control(f, row[f.key], 'l' + n)); });
    box.appendChild(grid);
    rm.addEventListener('click', function () {
      var container = box.parentNode;
      var next = box.nextElementSibling || box.previousElementSibling;
      box.remove();
      renumber(container, listName);
      markDirty();
      var focusTarget = (next && next.querySelector('input, textarea, select')) || container.parentNode.querySelector('.add-btn');
      if (focusTarget) focusTarget.focus();
      status('Removed. Save to keep the change.', 'warn');
    });
    return box;
  }

  function renumber(container, listName) {
    var def = S.LISTS[listName];
    var items = container.querySelectorAll('.list-item');
    items.forEach(function (it, i) {
      var title = def.itemTitle + ' ' + (i + 1);
      it.querySelector('h3').textContent = title;
      it.querySelector('.list-item-head button').setAttribute('aria-label', 'Remove ' + title.toLowerCase());
    });
    var empty = container.querySelector('.empty');
    if (empty) empty.hidden = items.length > 0;
  }

  function render(profile) {
    var values = S.formValuesFromProfile(profile);
    var host = $('sections');
    host.innerHTML = '';
    var toc = $('toc');
    toc.innerHTML = '';
    toc.appendChild(tocLink('settings-h', 'Page button and resume'));
    S.SECTIONS.forEach(function (sec) {
      var fs = document.createElement('fieldset');
      fs.className = 'card';
      fs.id = 'sec-' + sec.id;
      var lg = document.createElement('legend');
      lg.textContent = sec.title;
      fs.appendChild(lg);
      var intro = sec.intro || (sec.list && S.LISTS[sec.list].intro);
      if (intro) {
        var p = document.createElement('p');
        p.className = 'intro';
        p.textContent = intro;
        fs.appendChild(p);
      }
      if (sec.fields) {
        var grid = document.createElement('div');
        grid.className = 'grid';
        sec.fields.forEach(function (f) { grid.appendChild(control(f, values.scalars[f.key], 'f')); });
        fs.appendChild(grid);
      } else if (sec.list) {
        var def = S.LISTS[sec.list];
        var container = document.createElement('div');
        container.className = 'list';
        container.dataset.list = sec.list;
        var empty = document.createElement('p');
        empty.className = 'empty';
        empty.textContent = 'Nothing here yet.';
        container.appendChild(empty);
        values.lists[sec.list].forEach(function (row, i) { container.appendChild(listItem(sec.list, row, i)); });
        fs.appendChild(container);
        var add = document.createElement('button');
        add.type = 'button';
        add.className = 'add-btn';
        add.textContent = 'Add ' + def.itemTitle.toLowerCase();
        add.addEventListener('click', function () {
          var row = {};
          def.fields.forEach(function (f) { row[f.key] = ''; });
          var item = listItem(sec.list, row);
          container.appendChild(item);
          renumber(container, sec.list);
          markDirty();
          item.querySelector('input, textarea, select').focus();
        });
        fs.appendChild(add);
        renumber(container, sec.list);
      }
      host.appendChild(fs);
      toc.appendChild(tocLink(fs.id, sec.title));
    });
  }

  function tocLink(id, text) {
    var li = document.createElement('li');
    var a = document.createElement('a');
    a.href = '#' + id;
    a.textContent = text;
    li.appendChild(a);
    return li;
  }

  /* ---- reading the form ---- */
  function readForm() {
    var scalars = {};
    document.querySelectorAll('#sections .grid > .field > [data-key]').forEach(function (el) {
      if (!el.closest('.list-item')) scalars[el.dataset.key] = el.value.trim();
    });
    var lists = {};
    document.querySelectorAll('#sections .list').forEach(function (container) {
      var name = container.dataset.list;
      lists[name] = Array.prototype.map.call(container.querySelectorAll('.list-item'), function (it) {
        var row = {};
        if (it.dataset.origin !== undefined) row._origin = Number(it.dataset.origin);
        it.querySelectorAll('[data-key]').forEach(function (el) {
          row[el.dataset.key] = el.tagName === 'TEXTAREA' ? el.value.replace(/\s+$/, '') : el.value.trim();
        });
        return row;
      }).filter(function (row) {
        return Object.keys(row).some(function (k) { return k !== '_origin' && row[k] !== ''; }) || typeof row._origin === 'number';
      });
    });
    return { scalars: scalars, lists: lists };
  }

  /* ---- actions ---- */
  async function save() {
    var next = S.applyFormValues(stored, readForm());
    try {
      await store.set({ profile: next, profileMeta: meta('saved') });
    } catch (e) {
      status('Could not save: ' + e.message, 'err');
      return;
    }
    stored = next;
    dirty = false;
    render(stored);
    status('Profile saved in this browser.', 'ok');
  }

  function download() {
    var data = S.applyFormValues(stored, readForm());
    var blob = new Blob([S.exportProfileText(data)], { type: 'application/json' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = 'profile.json';
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 2000);
    status(dirty ? 'Downloaded profile.json including unsaved changes (not saved here yet).' : 'Downloaded profile.json.', dirty ? 'warn' : 'ok');
  }

  function importFile(file) {
    var reader = new FileReader();
    reader.onload = async function () {
      var data;
      try {
        data = S.parseProfileText(reader.result);
      } catch (e) {
        status(e.message, 'err');
        return;
      }
      if (Object.keys(stored).length && !confirm('Replace the profile saved in this browser with "' + file.name + '"? Every key in the file is kept, including ones this page does not show.')) {
        status('Import cancelled.', '');
        return;
      }
      try {
        await store.set({ profile: data, profileMeta: meta('imported') });
      } catch (e2) {
        status('Could not save the imported profile: ' + e2.message, 'err');
        return;
      }
      stored = data;
      dirty = false;
      render(stored);
      status('Imported ' + file.name + ' (' + Object.keys(data).length + ' keys).', 'ok');
    };
    reader.onerror = function () { status('Could not read that file.', 'err'); };
    reader.readAsText(file);
  }

  function showResume(resume) {
    var has = !!(resume && resume.data);
    $('resume-status').textContent = has
      ? 'Saved: ' + resume.name + ' (' + Math.round((resume.size || 0) / 1024) + ' KB).'
      : 'No resume saved.';
    $('resume-remove').hidden = !has;
    $('resume-btn').textContent = has ? 'Replace PDF…' : 'Choose PDF…';
  }

  function saveResume(file) {
    var isPdf = /\.pdf$/i.test(file.name) || file.type === 'application/pdf';
    if (!isPdf) { status('Please choose a PDF file.', 'err'); return; }
    if (file.size > S.MAX_RESUME_BYTES) { status('That PDF is ' + (file.size / 1048576).toFixed(1) + ' MB; the limit is 5 MB.', 'err'); return; }
    var reader = new FileReader();
    reader.onload = async function () {
      var data = String(reader.result).split(',')[1] || '';
      var resume = { name: file.name, type: 'application/pdf', size: file.size, data: data, savedAt: Date.now() };
      try {
        await store.set({ resume: resume });
      } catch (e) {
        status('Could not store the PDF: ' + e.message, 'err');
        return;
      }
      showResume(resume);
      status('Resume saved.', 'ok');
    };
    reader.onerror = function () { status('Could not read that PDF.', 'err'); };
    reader.readAsDataURL(file);
  }

  async function init() {
    var data = await store.get(['profile', 'resume', 'settings']);
    stored = (data.profile && typeof data.profile === 'object' && !Array.isArray(data.profile)) ? data.profile : {};
    render(stored);
    showResume(data.resume);
    $('show-button').checked = !(data.settings && data.settings.showButton === false);
    if (!Object.keys(stored).length) status('No profile yet. Import your profile.json or fill in the form and save.', '');

    $('profile-form').addEventListener('input', markDirty);
    $('profile-form').addEventListener('change', markDirty);
    $('profile-form').addEventListener('submit', function (e) { e.preventDefault(); save(); });
    $('save-btn').addEventListener('click', save);
    $('export-btn').addEventListener('click', download);
    $('import-btn').addEventListener('click', function () { $('import-file').click(); });
    $('import-file').addEventListener('change', function (e) { if (e.target.files[0]) importFile(e.target.files[0]); e.target.value = ''; });
    $('resume-btn').addEventListener('click', function () { $('resume-file').click(); });
    $('resume-file').addEventListener('change', function (e) { if (e.target.files[0]) saveResume(e.target.files[0]); e.target.value = ''; });
    $('resume-remove').addEventListener('click', async function () {
      await store.remove('resume');
      showResume(null);
      status('Resume removed.', 'ok');
      $('resume-btn').focus();
    });
    $('show-button').addEventListener('change', async function (e) {
      var cur = (await store.get('settings')).settings || {};
      cur.showButton = e.target.checked;
      await store.set({ settings: cur });
      status(e.target.checked ? 'The page button will show on application pages.' : 'The page button is hidden.', 'ok');
    });
    document.addEventListener('keydown', function (e) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 's') { e.preventDefault(); save(); }
    });
    window.addEventListener('beforeunload', function (e) {
      if (dirty) { e.preventDefault(); e.returnValue = ''; }
    });
  }

  init();
})();
