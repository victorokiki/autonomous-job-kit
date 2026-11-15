/*
 * Autonomous Job Kit Autofill - fixture harness.
 *
 * Each tests/extension/fixture-*.html loads this file. It installs a stub `chrome` object with a
 * made-up profile, loads the real content scripts from ../../extension/content/, runs a fill
 * (calling JobKit.startFill directly, as the service worker does), checks every element that has
 * a data-expect attribute, runs the fill a second time to prove nothing changes, and writes the
 * result into <pre id="jk-results"> and the page title ("JOBKIT-TEST PASS 12/12").
 *
 * Open a fixture in Chrome to watch it, or run `node tests/extension/check.js` (headless Chrome).
 * data-expect rules: text/textarea -> value; select -> selected option text; checkbox ->
 * "checked"/"unchecked"; any element containing radios -> label of the checked radio ("" = none);
 * other elements (e.g. Workday listbox buttons) -> their text.
 */
(function () {
  'use strict';

  var PROFILE = {
    _comment: 'Fictional test profile.',
    firstName: 'Alex', middleName: 'Morgan', lastName: 'Tremblay', preferredName: '',
    legalName: 'Alex Morgan Tremblay', email: 'alex.tremblay@example.com', phone: '+1 (902) 555-0142',
    street: '123 Example Street', city: 'Halifax', state: 'NS', postalCode: 'B3H 0A1', country: 'Canada',
    linkedin: 'linkedin.com/in/alex-tremblay-example', github: 'github.com/alex-tremblay-example',
    portfolio: '', website: 'alex-tremblay.example.com',
    education: [{ school: 'Atlantic Coast University', degree: "Bachelor's Degree", field: 'Business Analytics', minor: '',
      start: 'Sep 2019', end: 'Apr 2023', startExact: '2019-09-03', endExact: '2023-04-28', gpa: '3.7' }],
    work: [{ title: 'Data Analyst', company: 'Harbourline Logistics', location: 'Halifax, NS', start: 'Jun 2024', end: 'Present', highlights: 'x' }],
    classStanding: 'Graduate', enrolled: 'no', returningToSchool: 'no', availableFrom: '2026-01-05',
    workAuthDetails: 'Canadian citizen', yearsExperience: '2', workAuthorized: 'yes', authCountry: 'Canada',
    needsSponsorship: 'no', needsSponsorshipForInternship: 'no', willingToRelocate: 'yes',
    governmentEmployee: 'no', governmentRelative: 'no', salary: '', startDate: '2026-01-05',
    gender: 'decline', pronouns: '', hispanicLatino: 'no', race: 'white', veteranStatus: 'no', disabilityStatus: 'decline',
    savedAnswers: [{ match: 'how did you hear', answer: 'Company careers page' }, { match: 'notice period', answer: 'Two weeks' }],
    automationLevel: 'lean', letterMaxWords: 250
  };
  // A tiny valid-looking PDF, base64 ("%PDF-1.4 ... %%EOF").
  var RESUME = { name: 'Alex_Tremblay_Resume.pdf', type: 'application/pdf', size: 40, data: btoa('%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'), savedAt: 0 };
  var META = { source: 'imported', date: '2026-11-01' };

  window.chrome = {
    runtime: { id: 'test', onMessage: { addListener: function () {} } },
    storage: {
      local: { get: function () { return Promise.resolve({ profile: PROFILE, profileMeta: META, resume: RESUME, settings: { showButton: true } }); } },
      onChanged: { addListener: function () {} }
    }
  };

  var FILES = ['text.js', 'rules.js', 'labels.js', 'setters.js', 'ui.js', 'engine.js', 'main.js'];
  var BASE = '../../extension/content/';

  function load(i) {
    if (i >= FILES.length) return Promise.resolve();
    return new Promise(function (resolve, reject) {
      var s = document.createElement('script');
      s.src = BASE + FILES[i];
      s.onload = resolve;
      s.onerror = function () { reject(new Error('could not load ' + FILES[i])); };
      document.head.appendChild(s);
    }).then(function () { return load(i + 1); });
  }

  function norm(s) { return String(s || '').replace(/\s+/g, ' ').trim(); }

  function actual(el) {
    if (el.tagName === 'SELECT') { var o = el.options[el.selectedIndex]; return o ? norm(o.text) : ''; }
    if (el.tagName === 'INPUT' && el.type === 'checkbox') return el.checked ? 'checked' : 'unchecked';
    if (el.tagName === 'INPUT' && el.type === 'file') return el.files && el.files.length ? el.files[0].name : '';
    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') return el.value;
    var radios = el.querySelectorAll('input[type="radio"]');
    if (radios.length) {
      for (var i = 0; i < radios.length; i++) {
        if (radios[i].checked) { var l = radios[i].labels && radios[i].labels[0]; return norm(l ? l.textContent : radios[i].value); }
      }
      return '';
    }
    return norm(el.textContent);
  }

  function snapshot() {
    return Array.prototype.map.call(document.querySelectorAll('input, select, textarea, [aria-haspopup="listbox"]'), function (el) {
      return actual(el) + '|' + (el.type === 'radio' ? el.checked : '');
    }).join('\n');
  }

  function wait(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  async function main() {
    var out = document.getElementById('jk-results');
    var checks = [];
    function check(name, ok, detail) { checks.push({ name: name, ok: !!ok, detail: detail || '' }); }
    try {
      await load(0);
      await wait(100);
      var first = await window.JobKit.startFill('test');
      document.querySelectorAll('[data-expect]').forEach(function (el) {
        var want = el.getAttribute('data-expect');
        var got = actual(el);
        var name = el.getAttribute('data-name') || el.id || el.name || el.tagName.toLowerCase();
        check(name, got === want, 'expected "' + want + '", got "' + got + '"');
      });
      var rep = document.getElementById('jobkit-report');
      var text = rep ? rep.textContent : '';
      check('report starts with "Autonomous report:"', /^Autonomous report: filled \d+/.test(text), text.slice(0, 80));
      check('hidden dropdown helper inputs are not listed', !/unlabelled/.test(text), text.slice(0, 200));
      check('report ends with profile freshness', /Profile: imported 2026-11-01, 2 saved answers\.$/.test(text), text.slice(-60));
      check('report is first in the form', rep && rep.parentNode && rep.parentNode.firstChild === rep, '');
      (window.JK_EXTRA_CHECKS || []).forEach(function (fn) { var r = fn(first, text); check(r[0], r[1], r[2]); });

      var before = snapshot();
      var second = await window.JobKit.startFill('test');
      check('second run fills nothing', second.filled === 0, 'filled ' + second.filled);
      check('second run changes nothing', snapshot() === before, '');
      check('nothing was submitted', !window.JK_SUBMITTED, '');

      var failed = checks.filter(function (c) { return !c.ok; });
      var passed = checks.length - failed.length;
      document.title = 'JOBKIT-TEST ' + (failed.length ? 'FAIL' : 'PASS') + ' ' + passed + '/' + checks.length;
      out.setAttribute('data-status', failed.length ? 'FAIL' : 'PASS');
      out.textContent = document.title + '\n' + checks.map(function (c) { return (c.ok ? 'ok   ' : 'FAIL ') + c.name + (c.ok ? '' : ' - ' + c.detail); }).join('\n') +
        '\n\nFirst run: filled ' + first.filled + ', already ' + first.already + ', left ' + first.left + '\n' + text;
    } catch (e) {
      document.title = 'JOBKIT-TEST FAIL error';
      out.setAttribute('data-status', 'FAIL');
      out.textContent = 'Harness error: ' + (e && e.stack ? e.stack : e);
    }
  }

  document.addEventListener('submit', function (e) { window.JK_SUBMITTED = true; e.preventDefault(); }, true);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', main); else main();
})();
