#!/usr/bin/env node
/*
 * Autonomous Job Kit Autofill - checks that run without a browser extension install.
 *
 * Usage (from the repo root):  node tests/extension/check.js [--no-browser]
 *
 *  1. manifest.json: valid JSON, MV3, required files exist, permissions are the minimal set,
 *     content-script order matches background.js.
 *  2. `node --check` on every extension JS file; no network APIs anywhere in extension code.
 *  3. profile.json round trip with templates/profile.example.json (unknown keys and number
 *     types survive the editor; export/parse is lossless).
 *  4. Matching-rules table: sample questions -> expected field or "left" reason.
 *  5. Fixture forms in headless Google Chrome (skipped when Chrome is not found or with
 *     --no-browser): each fixture-*.html must end with the title "JOBKIT-TEST PASS n/n".
 * Prints one line per check and exits 1 when anything fails.
 */
'use strict';
const fs = require('fs');
const path = require('path');
const assert = require('assert');
const { spawnSync } = require('child_process');

const REPO = path.resolve(__dirname, '..', '..');
const EXT = path.join(REPO, 'extension');
let failures = 0;
function ok(name) { console.log('ok    ' + name); }
function fail(name, why) { failures++; console.log('FAIL  ' + name + (why ? ' - ' + why : '')); }
function test(name, fn) { try { fn(); ok(name); } catch (e) { fail(name, e.message); } }

function walk(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((d) => {
    const p = path.join(dir, d.name);
    return d.isDirectory() ? walk(p) : [p];
  });
}

/* 1. manifest */
let manifest = null;
test('manifest.json is valid JSON (MV3)', () => {
  manifest = JSON.parse(fs.readFileSync(path.join(EXT, 'manifest.json'), 'utf8'));
  assert.strictEqual(manifest.manifest_version, 3);
  assert.ok(manifest.name && manifest.version && manifest.description);
  assert.ok(manifest.description.length <= 132, 'description longer than 132 characters');
});
if (manifest) {
  test('manifest permissions are minimal', () => {
    assert.deepStrictEqual([...manifest.permissions].sort(), ['activeTab', 'scripting', 'storage']);
    const cs = manifest.content_scripts[0].matches;
    assert.deepStrictEqual([...manifest.host_permissions].sort(), [...cs].sort(), 'host_permissions must equal content-script matches');
    assert.ok(cs.every((m) => /^https:\/\/\*\.[a-z.]+\/(hcmUI\/)?\*$/.test(m)), 'unexpected match pattern');
  });
  test('manifest files exist', () => {
    const files = [manifest.background.service_worker, manifest.action.default_popup, manifest.options_ui.page]
      .concat(Object.values(manifest.icons), Object.values(manifest.action.default_icon), manifest.content_scripts[0].js);
    files.forEach((f) => assert.ok(fs.existsSync(path.join(EXT, f)), 'missing ' + f));
  });
  test('content-script order matches background.js', () => {
    const bg = fs.readFileSync(path.join(EXT, 'background.js'), 'utf8');
    const list = bg.match(/const CONTENT_FILES = \[([\s\S]*?)\]/)[1].match(/'([^']+)'/g).map((s) => s.slice(1, -1));
    assert.deepStrictEqual(list, manifest.content_scripts[0].js);
  });
  test('Alt+Shift+F command declared', () => {
    assert.strictEqual(manifest.commands['fill-page'].suggested_key.default, 'Alt+Shift+F');
  });
  test('icons are PNGs of the declared size', () => {
    Object.entries(manifest.icons).forEach(([size, f]) => {
      const b = fs.readFileSync(path.join(EXT, f));
      assert.strictEqual(b.slice(1, 4).toString(), 'PNG');
      assert.strictEqual(b.readUInt32BE(16), Number(size));
    });
  });
}

/* 2. syntax and no network */
const jsFiles = walk(EXT).filter((f) => f.endsWith('.js'));
jsFiles.concat(walk(__dirname).filter((f) => f.endsWith('.js'))).forEach((f) => {
  const r = spawnSync(process.execPath, ['--check', f], { encoding: 'utf8' });
  if (r.status === 0) ok('node --check ' + path.relative(REPO, f));
  else fail('node --check ' + path.relative(REPO, f), r.stderr.trim().split('\n')[0]);
});
test('no network APIs in extension code', () => {
  jsFiles.concat(walk(EXT).filter((f) => f.endsWith('.html'))).forEach((f) => {
    const src = fs.readFileSync(f, 'utf8');
    const bad = src.match(/\bfetch\s*\(|XMLHttpRequest|WebSocket|sendBeacon|EventSource|importScripts\s*\(|https?:\/\/(?!\*\.)/);
    assert.ok(!bad, path.relative(REPO, f) + ' uses ' + (bad && bad[0]));
  });
});

/* 3. profile.json round trip */
const S = require(path.join(EXT, 'shared', 'profile-schema.js'));
const exampleText = fs.readFileSync(path.join(REPO, 'templates', 'profile.example.json'), 'utf8');
const example = S.parseProfileText(exampleText);
test('import -> editor -> save keeps profile.example.json identical', () => {
  const back = S.applyFormValues(example, S.formValuesFromProfile(example));
  assert.deepStrictEqual(back, example);
  assert.deepStrictEqual(Object.keys(back), Object.keys(example), 'key order changed');
});
test('export -> import is lossless', () => {
  assert.deepStrictEqual(S.parseProfileText(S.exportProfileText(example)), example);
});
test('editing one field keeps unknown keys and types', () => {
  const v = S.formValuesFromProfile(example);
  v.scalars.city = 'Dartmouth';
  v.lists.education[0].gpa = '3.9';
  v.lists.work.splice(0, 1); // remove the first job
  v.lists.savedAnswers.push({ match: 'pronouns', answer: 'they/them' });
  const out = S.applyFormValues(example, v);
  assert.strictEqual(out.city, 'Dartmouth');
  assert.strictEqual(out.education[0].gpa, '3.9');
  assert.strictEqual(out.work.length, 1);
  assert.strictEqual(out.work[0].company, 'Bluenose Outfitters');
  assert.strictEqual(out.savedAnswers.length, 3);
  ['_comment', 'projects', 'writingStyle', 'extraRules', 'automationLevel', 'bulletFormula', 'coverLetterPolicy', 'letterStyle', 'combinedOrder']
    .forEach((k) => assert.deepStrictEqual(out[k], example[k], k + ' changed'));
  assert.strictEqual(out.resumeMaxPages, 2);
  assert.strictEqual(out.letterMaxWords, 250);
  assert.strictEqual(out.alwaysCombine, true);
  assert.strictEqual(out.yearsExperience, '2');
});
test('empty new fields are not added; numbers stay numbers', () => {
  const p = { firstName: 'Alex', yearsExperience: 3, custom: { a: 1 } };
  const out = S.applyFormValues(p, S.formValuesFromProfile(p));
  assert.deepStrictEqual(out, p);
});
test('bad imports are rejected with a message', () => {
  assert.throws(() => S.parseProfileText('[1,2]'), /one JSON object/);
  assert.throws(() => S.parseProfileText('{oops'), /not valid JSON/);
  assert.deepStrictEqual(S.parseProfileText('\uFEFF{"a":1}'), { a: 1 });
});

/* 4. rules table */
global.JobKit = {};
const T = require(path.join(EXT, 'content', 'text.js'));
global.JobKit.text = T;
const R = require(path.join(EXT, 'content', 'rules.js'));
const profile = Object.assign({}, example, {
  street: '123 Example Street', postalCode: 'B3H 0A1', gender: 'decline', race: 'white', veteranStatus: 'no',
  needsSponsorship: 'no', needsSponsorshipForInternship: 'yes'
});
function q(text, control, extra) {
  return Object.assign({ text: text, label: T.norm(text), context: '', control: control || 'text', inputType: 'text', quality: 'label' }, extra || {});
}
const CASES = [
  // [question, control, expected rule (or "left:<reason>"), extra]
  ['First Name *', 'text', 'first name'],
  ['Legal first name', 'text', 'first name'],
  ['Last name', 'text', 'last name'],
  ['Full name', 'text', 'full name'],
  ['Name', 'text', 'full name'],
  ['Preferred name', 'text', 'preferred name'],
  ['E-mail address', 'text', 'email'],
  ['Phone number', 'text', 'phone'],
  ['Country phone code', 'select', 'phone country code'],
  ['Address line 1', 'text', 'street'],
  ['Address line 2', 'text', 'left:unknown question'],
  ['City', 'text', 'city'],
  ['State/Province', 'select', 'province / state'],
  ['ZIP / Postal code', 'text', 'postal code'],
  ['Country', 'select', 'country'],
  ['Country of citizenship', 'select', 'left:unknown question'],
  ['LinkedIn profile', 'text', 'LinkedIn'],
  ['GitHub URL', 'text', 'GitHub'],
  ['School name', 'text', 'school'],
  ['Field of study', 'text', 'field of study'],
  ['Highest degree', 'select', 'degree'],
  ['Expected graduation date', 'text', 'graduation date'],
  ['Are you currently enrolled in a degree program?', 'radio', 'currently enrolled'],
  ['Years of experience', 'select', 'years of experience'],
  ['Are you legally authorized to work in Canada?', 'radio', 'work authorization'],
  ['Are you legally authorized to work in the United States?', 'radio', 'left:other-country'],
  ['Will you now or in the future require sponsorship?', 'radio', 'sponsorship'],
  ['Do you require visa sponsorship?', 'radio', 'left:ambiguous'],
  ['Will you require sponsorship for this internship?', 'radio', 'sponsorship'],
  ['Are you willing to relocate?', 'radio', 'relocation'],
  ['Is a member of your family employed by a government?', 'radio', 'government relative'],
  ['Have you worked for the government?', 'radio', 'government employee'],
  ['Are you able to work on-site three days a week?', 'radio', 'left:unknown question'],
  ['Desired salary', 'text', 'left:not in profile'],
  ['Gender', 'select', 'gender'],
  ['Race / Ethnicity', 'select', 'race / ethnicity'],
  ['Veteran status', 'select', 'veteran status'],
  ['Pronouns', 'select', 'left:not in profile'],
  ['How did you hear about us?', 'select', 'saved answer "how did you hear"'],
  ['How did you hear about us?', 'textarea', 'saved answer "how did you hear"'],
  ['Why do you want to work here?', 'textarea', 'left:open-ended'],
  ['Social Security Number', 'text', 'left:sensitive'],
  ['SIN', 'text', 'left:sensitive'],
  ['Date of birth', 'text', 'left:sensitive'],
  ['Have you been convicted of a crime?', 'radio', 'left:sensitive'],
  ['Marital status', 'select', 'left:sensitive'],
  ['Religion', 'select', 'left:sensitive'],
  ['Passport number', 'text', 'left:sensitive'],
  ['I agree to the terms and conditions', 'checkbox', 'left:consent'],
  ['I certify that my answers are true', 'checkbox', 'left:consent'],
  ['Emergency contact first name', 'text', 'left:not about you'],
  ['Resume/CV', 'file', 'resume'],
  ['Cover letter', 'file', 'left:file'],
  ['first name', 'text', 'first name', { quality: 'hint' }],
  ['salary', 'text', 'left:low confidence', { quality: 'hint' }],
  ['Start date', 'text', 'start date'],
  ['From', 'text', 'work start', { context: 'work experience' }],
  ['From', 'text', 'education start', { context: 'education' }],
  ['Are you willing to relocate?', 'radio', 'relocation', { context: 'education' }],
  ['Earliest start date', 'text', 'available from', { context: 'education and availability' }],
  ['Will you require sponsorship for this co-op work term?', 'radio', 'sponsorship']
];
CASES.forEach(([text, control, want, extra]) => {
  const d = R.decide(q(text, control, extra), profile, {});
  const got = d.ok ? d.rule : 'left:' + d.reason;
  if (got === want) ok('rule: "' + text + '" -> ' + want);
  else fail('rule: "' + text + '"', 'expected ' + want + ', got ' + got);
});
test('phone splits when the form has a country-code field', () => {
  const d = R.decide(q('Phone number'), profile, { hasPhoneCode: true });
  assert.strictEqual(d.want.text, '(902) 555-0142');
});
test('option matching: yes/no, provinces, countries, ranges, self-ID', () => {
  const o = (arr) => arr.map((t) => ({ text: t, value: t }));
  assert.strictEqual(T.pickOption(o(['Select...', 'Yes', 'No']), { matcher: (t) => T.classifyYesNo(t) === 'no' }), 2);
  assert.strictEqual(T.pickOption(o(['--', 'Ontario', 'Nova Scotia']), { text: 'NS', aliases: T.regionAliases('NS') }), 2);
  assert.strictEqual(T.pickOption(o(['United States', 'Canada']), { text: 'CA', aliases: T.countryAliases('CA') }), 1);
  assert.strictEqual(T.pickOption(o(['USA', 'UK']), { text: 'United Kingdom', aliases: T.countryAliases('United Kingdom') }), 1);
  assert.strictEqual(T.pickOption(o(['Less than 1 year', '1-2 years', '3-5 years', '5+ years']), { text: '4', number: 4 }), 2);
  assert.strictEqual(T.pickOption(o(['I am a protected veteran', 'I am not a protected veteran', 'I prefer not to say']), { matcher: T.choiceMatcher('veteranStatus', 'no') }), 1);
  assert.strictEqual(T.pickOption(o(['Male', 'Female', 'Prefer not to say']), { matcher: T.choiceMatcher('gender', 'female') }), 1);
  assert.strictEqual(T.pickOption(o(['Male', 'Female', 'Prefer not to say']), { matcher: T.choiceMatcher('gender', 'male') }), 0);
  assert.strictEqual(T.pickOption(o(['Accounting', 'Finance']), { text: 'Business Analytics' }), -1);
});
test('dates format per control', () => {
  assert.strictEqual(T.formatDate('Apr 2023', 'month'), '2023-04');
  assert.strictEqual(T.formatDate('2023-04-28', 'date'), '2023-04-28');
  assert.strictEqual(T.formatDate('Apr 2023', 'date'), '');
  assert.strictEqual(T.formatDate('Jun 2024', 'mmyyyy'), '06/2024');
  assert.strictEqual(T.formatDate('September 3, 2019', 'year'), '2019');
});

/* 5. fixtures in headless Chrome */
function findChrome() {
  const c = [process.env.CHROME_PATH,
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
    '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser',
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe'];
  return c.find((p) => p && fs.existsSync(p));
}
const chrome = !process.argv.includes('--no-browser') && findChrome();
if (!chrome) {
  console.log('skip  fixture forms (no Chrome found or --no-browser)');
} else {
  const os = require('os');
  const profileDir = fs.mkdtempSync(path.join(os.tmpdir(), 'jobkit-chrome-'));
  fs.readdirSync(__dirname).filter((f) => /^fixture-.*\.html$/.test(f)).sort().forEach((f) => {
    const url = 'file://' + path.join(__dirname, f).split(path.sep).map(encodeURIComponent).join('/').replace(/^%3A/, ':');
    const r = spawnSync(chrome, ['--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
      '--user-data-dir=' + profileDir, '--allow-file-access-from-files', '--virtual-time-budget=20000', '--dump-dom', url],
      { encoding: 'utf8', timeout: 90000 });
    const dom = r.stdout || '';
    const title = (dom.match(/<title>([^<]*)<\/title>/) || [])[1] || '(no title)';
    const pre = (dom.match(/<pre id="jk-results"[^>]*>([\s\S]*?)<\/pre>/) || [])[1] || '';
    if (/^JOBKIT-TEST PASS/.test(title)) ok('fixture ' + f + ': ' + title.replace('JOBKIT-TEST ', ''));
    else {
      fail('fixture ' + f, title);
      console.log(pre.replace(/&quot;/g, '"').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').split('\n').filter((l) => /^FAIL|error|Harness/.test(l)).map((l) => '        ' + l).join('\n'));
    }
  });
  try { fs.rmSync(profileDir, { recursive: true, force: true }); } catch (e) { /* ignore */ }
}

console.log(failures ? '\n' + failures + ' check(s) failed.' : '\nAll checks passed.');
process.exit(failures ? 1 : 0);
