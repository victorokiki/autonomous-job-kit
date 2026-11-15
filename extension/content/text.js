/*
 * Job Kit Autofill - text helpers (pure functions, no DOM).
 *
 * norm() turns any label or option into one canonical form: lowercase, accents removed,
 * every character other than a-z, 0-9 and "+" replaced by a space, spaces collapsed.
 * All regular expressions in rules.js are written against that form
 * ("E-mail*" -> "e mail", "She/Her" -> "she her", "Co-op term" -> "co op term").
 */
(function (root) {
  'use strict';

  function norm(s) {
    if (s === null || s === undefined) return '';
    var t = String(s);
    if (t.normalize) t = t.normalize('NFKD').replace(/[̀-ͯ]/g, '');
    t = t.toLowerCase()
      .replace(/[‘’´`]/g, "'")
      .replace(/\((required|optional)\)/g, ' ')
      .replace(/'/g, ' ')
      .replace(/[^a-z0-9+]+/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
    return t;
  }

  /* Human-readable label: whitespace collapsed, trailing required marks removed, length capped. */
  function tidy(s, max) {
    var t = String(s || '').replace(/\s+/g, ' ').replace(/\s*[*✱]+\s*$/, '').replace(/^\s*[*✱]+\s*/, '').trim();
    max = max || 140;
    return t.length > max ? t.slice(0, max - 1).trim() + '…' : t;
  }

  var PLACEHOLDER_RE = /^(|select|select one|select an option|select\.*|choose|choose one|choose an option|please select|please choose|pick one|none selected|\-+|\.\.\.|—+|select \w+)$/;

  function isPlaceholderOption(text, value) {
    var t = norm(text);
    if (PLACEHOLDER_RE.test(t)) return true;
    if ((value === '' || value === undefined || value === null) && (t === '' || /^(select|choose|please)/.test(t))) return true;
    return false;
  }

  /* ---- geography ---- */
  var COUNTRIES = [
    { code: 'CA', dial: '+1', names: ['canada', 'ca', 'can'] },
    { code: 'US', dial: '+1', names: ['united states', 'united states of america', 'usa', 'us', 'u s', 'u s a', 'america'] },
    { code: 'GB', dial: '+44', names: ['united kingdom', 'uk', 'u k', 'great britain', 'britain', 'gb', 'gbr', 'united kingdom of great britain and northern ireland'] },
    { code: 'IE', dial: '+353', names: ['ireland', 'ie', 'republic of ireland'] },
    { code: 'AU', dial: '+61', names: ['australia', 'au'] },
    { code: 'NZ', dial: '+64', names: ['new zealand', 'nz'] },
    { code: 'IN', dial: '+91', names: ['india', 'in'] },
    { code: 'CN', dial: '+86', names: ['china', 'cn', 'people s republic of china'] },
    { code: 'FR', dial: '+33', names: ['france', 'fr'] },
    { code: 'DE', dial: '+49', names: ['germany', 'de', 'deutschland'] },
    { code: 'MX', dial: '+52', names: ['mexico', 'mx'] },
    { code: 'NG', dial: '+234', names: ['nigeria', 'ng'] },
    { code: 'PK', dial: '+92', names: ['pakistan', 'pk'] },
    { code: 'PH', dial: '+63', names: ['philippines', 'ph'] },
    { code: 'VN', dial: '+84', names: ['vietnam', 'viet nam', 'vn'] },
    { code: 'BR', dial: '+55', names: ['brazil', 'br'] },
    { code: 'KR', dial: '+82', names: ['south korea', 'korea republic of', 'republic of korea', 'kr'] },
    { code: 'JP', dial: '+81', names: ['japan', 'jp'] }
  ];

  var REGIONS = [
    // Canada
    ['AB', 'alberta'], ['BC', 'british columbia'], ['MB', 'manitoba'], ['NB', 'new brunswick'],
    ['NL', 'newfoundland and labrador', 'newfoundland'], ['NS', 'nova scotia'], ['NT', 'northwest territories'],
    ['NU', 'nunavut'], ['ON', 'ontario'], ['PE', 'prince edward island', 'pei'], ['QC', 'quebec'],
    ['SK', 'saskatchewan'], ['YT', 'yukon'],
    // United States
    ['AL', 'alabama'], ['AK', 'alaska'], ['AZ', 'arizona'], ['AR', 'arkansas'], ['CA', 'california'],
    ['CO', 'colorado'], ['CT', 'connecticut'], ['DE', 'delaware'], ['DC', 'district of columbia', 'washington dc'],
    ['FL', 'florida'], ['GA', 'georgia'], ['HI', 'hawaii'], ['ID', 'idaho'], ['IL', 'illinois'], ['IN', 'indiana'],
    ['IA', 'iowa'], ['KS', 'kansas'], ['KY', 'kentucky'], ['LA', 'louisiana'], ['ME', 'maine'], ['MD', 'maryland'],
    ['MA', 'massachusetts'], ['MI', 'michigan'], ['MN', 'minnesota'], ['MS', 'mississippi'], ['MO', 'missouri'],
    ['MT', 'montana'], ['NE', 'nebraska'], ['NV', 'nevada'], ['NH', 'new hampshire'], ['NJ', 'new jersey'],
    ['NM', 'new mexico'], ['NY', 'new york'], ['NC', 'north carolina'], ['ND', 'north dakota'], ['OH', 'ohio'],
    ['OK', 'oklahoma'], ['OR', 'oregon'], ['PA', 'pennsylvania'], ['RI', 'rhode island'], ['SC', 'south carolina'],
    ['SD', 'south dakota'], ['TN', 'tennessee'], ['TX', 'texas'], ['UT', 'utah'], ['VT', 'vermont'],
    ['VA', 'virginia'], ['WA', 'washington'], ['WV', 'west virginia'], ['WI', 'wisconsin'], ['WY', 'wyoming'],
    ['PR', 'puerto rico'],
    // United Kingdom nations
    ['ENG', 'england'], ['SCT', 'scotland'], ['WLS', 'wales'], ['NIR', 'northern ireland']
  ];

  function findCountry(value) {
    var v = norm(value);
    if (!v) return null;
    for (var i = 0; i < COUNTRIES.length; i++) {
      if (COUNTRIES[i].code.toLowerCase() === v || COUNTRIES[i].names.indexOf(v) !== -1) return COUNTRIES[i];
    }
    return null;
  }

  function countryAliases(value) {
    var c = findCountry(value);
    if (!c) return [norm(value)].filter(Boolean);
    return [c.code.toLowerCase()].concat(c.names);
  }

  function regionAliases(value) {
    var v = norm(value);
    if (!v) return [];
    var out = [v];
    REGIONS.forEach(function (r) {
      var code = r[0].toLowerCase();
      var names = r.slice(1);
      if (code === v || names.indexOf(v) !== -1) {
        out.push(code);
        names.forEach(function (n) { out.push(n); });
      }
    });
    return out.filter(function (x, i) { return out.indexOf(x) === i; });
  }

  /* Names of countries mentioned in a question (used to check the work-authorization country). */
  function countriesMentioned(question) {
    var q = ' ' + norm(question) + ' ';
    var found = [];
    COUNTRIES.forEach(function (c) {
      c.names.forEach(function (n) {
        if (n.length < 3 && !/^(us|uk)$/.test(n)) return;
        if (q.indexOf(' ' + n + ' ') !== -1 && found.indexOf(c.code) === -1) found.push(c.code);
      });
    });
    return found;
  }

  /* ---- phone ---- */
  function parsePhone(phone, country) {
    var raw = String(phone || '').trim();
    if (!raw) return null;
    var dial = '';
    var national = raw;
    var m = raw.match(/^\s*(\+\d{1,3})[\s.\-]*(.*)$/);
    if (m) {
      dial = m[1];
      national = m[2];
      if (dial === '+1' || dial.length <= 3) {
        // "+1 (902) ..." -> +1; "+44 20 ..." -> +44
      }
    } else {
      var c = findCountry(country);
      dial = c ? c.dial : '';
    }
    var digits = national.replace(/\D/g, '');
    if (dial === '+44' && digits.charAt(0) !== '0' && digits.length === 10) national = '0' + digits;
    return { full: raw, dial: dial, national: national.trim(), digits: digits };
  }

  /* ---- dates ---- */
  var MONTHS = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december'];

  function monthFromWord(w) {
    w = String(w || '').toLowerCase().slice(0, 3);
    for (var i = 0; i < 12; i++) if (MONTHS[i].slice(0, 3) === w) return i + 1;
    if (w === 'sep') return 9;
    return 0;
  }

  /* Parse "2023-04-28", "2023-04", "Apr 2023", "April 28, 2023", "04/2023", "2023", "Summer 2026". */
  function parseDate(s) {
    var t = String(s || '').trim();
    if (!t || /^(present|current|now|ongoing)$/i.test(t)) return null;
    var m;
    if ((m = t.match(/^(\d{4})-(\d{1,2})(?:-(\d{1,2}))?/))) return { y: +m[1], m: +m[2], d: m[3] ? +m[3] : 0 };
    if ((m = t.match(/^(\d{1,2})\/(\d{4})$/))) return { y: +m[2], m: +m[1], d: 0 };
    if ((m = t.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/))) return { y: +m[3], m: +m[1], d: +m[2] };
    if ((m = t.match(/^([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})$/)) && monthFromWord(m[1])) return { y: +m[3], m: monthFromWord(m[1]), d: +m[2] };
    if ((m = t.match(/^([A-Za-z]{3,9})\.?,?\s+(\d{4})$/)) && monthFromWord(m[1])) return { y: +m[2], m: monthFromWord(m[1]), d: 0 };
    if ((m = t.match(/^(winter|spring|summer|fall|autumn)\s+(\d{4})$/i))) {
      var start = { winter: 1, spring: 5, summer: 5, fall: 9, autumn: 9 }[m[1].toLowerCase()];
      return { y: +m[2], m: start, d: 0, season: m[1] };
    }
    if ((m = t.match(/^(\d{4})$/))) return { y: +m[1], m: 0, d: 0 };
    return null;
  }

  function pad(n) { return (n < 10 ? '0' : '') + n; }

  /* Format a date string for a control: 'date' (YYYY-MM-DD), 'month' (YYYY-MM), 'year', 'monthName', 'monthNumber', 'text'. */
  function formatDate(value, how) {
    var p = parseDate(value);
    if (how === 'text' || !how) return String(value || '');
    if (!p) return '';
    if (how === 'year') return String(p.y);
    if (how === 'monthName') return p.m ? MONTHS[p.m - 1].charAt(0).toUpperCase() + MONTHS[p.m - 1].slice(1) : '';
    if (how === 'monthNumber') return p.m ? String(p.m) : '';
    if (how === 'month') return p.m ? p.y + '-' + pad(p.m) : '';
    if (how === 'date') return p.m && p.d ? p.y + '-' + pad(p.m) + '-' + pad(p.d) : '';
    if (how === 'mmyyyy') return p.m ? pad(p.m) + '/' + p.y : '';
    if (how === 'mmddyyyy') return p.m && p.d ? pad(p.m) + '/' + pad(p.d) + '/' + p.y : '';
    return String(value || '');
  }

  /* ---- yes / no ---- */
  var DECLINE_RE = /\b(prefer not|decline|declined|rather not|choose not|not (wish|want) to|do not wish|don t wish|do not want|don t want|not to (answer|say|disclose|self identify|identify|specify)|no answer|undisclosed|not specified|i don t know)\b/;
  var NEG_RE = /\b(not|don t|do not|am not|won t|will not|have not|haven t|doesn t|does not|never)\b/;

  function classifyYesNo(text) {
    var t = norm(text);
    if (!t) return null;
    if (DECLINE_RE.test(t)) return 'decline';
    if (/^(yes|y|true|oui)\b/.test(t)) return 'yes';
    if (/^(no|n|false|non)\b/.test(t)) return 'no';
    if (/^i (am|do|will|have|identify|can)\b/.test(t) && !NEG_RE.test(t)) return 'yes';
    if (NEG_RE.test(t) && /^i\b/.test(t)) return 'no';
    return null;
  }

  function yesNoValue(v) {
    var t = norm(v);
    if (/^(yes|y|true|1)$/.test(t)) return 'yes';
    if (/^(no|n|false|0)$/.test(t)) return 'no';
    if (t === 'decline') return 'decline';
    return '';
  }

  /* ---- self-identification option matchers: code -> function(normalizedOptionText) ---- */
  function yn(code) {
    return function (t) { return classifyYesNo(t) === code; };
  }
  function notDecline(re) {
    return function (t) { return re.test(t) && !DECLINE_RE.test(t); };
  }
  function notNeg(re) {
    return function (t) { return re.test(t) && !NEG_RE.test(t) && !DECLINE_RE.test(t); };
  }
  var CHOICES = {
    gender: {
      female: notNeg(/\b(female|woman|women)\b/),
      male: notNeg(/\b(male|man|men)\b/),
      nonbinary: notNeg(/\b(non ?binary|genderqueer|gender non ?conforming|gender diverse|gender fluid)\b/)
    },
    pronouns: {
      she: notNeg(/\bshe\b/), he: notNeg(/\bhe\b/), they: notNeg(/\bthey\b/)
    },
    hispanicLatino: {
      yes: function (t) { return classifyYesNo(t) === 'yes' || (/hispanic|latin/.test(t) && !NEG_RE.test(t) && !DECLINE_RE.test(t)); },
      no: function (t) { return classifyYesNo(t) === 'no' || /\bnot hispanic|\bnot latin/.test(t); }
    },
    race: {
      'american-indian': notDecline(/american indian|alaska n|indigenous|first nations|native american|aboriginal/),
      asian: notDecline(/\basian\b/),
      black: notDecline(/\bblack\b|african/),
      'pacific-islander': notDecline(/pacific islander|hawaiian/),
      white: notDecline(/\bwhite\b|caucasian/),
      'two-or-more': notDecline(/two or more|multiracial|multi racial|mixed/)
    },
    veteranStatus: {
      no: function (t) { return classifyYesNo(t) === 'no' || (/\bnot\b.*\bveteran|\bnot\b.*\bprotected\b|no military/.test(t) && !DECLINE_RE.test(t)); },
      protected: function (t) { return /veteran|identify as one or more/.test(t) && !NEG_RE.test(t) && !DECLINE_RE.test(t); }
    },
    disabilityStatus: {
      yes: function (t) { return classifyYesNo(t) === 'yes' || (/\b(have|had) a disability\b/.test(t) && !NEG_RE.test(t) && !DECLINE_RE.test(t)); },
      no: function (t) { return classifyYesNo(t) === 'no' || (/(do not|don t) have a disability/.test(t)); }
    },
    lgbtq: { yes: yn('yes'), no: yn('no') },
    transgender: { yes: yn('yes'), no: yn('no') },
    sexualOrientation: {
      straight: notNeg(/straight|heterosexual/), gay: notNeg(/\bgay\b/), lesbian: notNeg(/\blesbian\b/),
      bisexual: notNeg(/\bbisexual\b/), pansexual: notNeg(/\bpansexual\b/), asexual: notNeg(/\basexual\b/),
      queer: notNeg(/\bqueer\b/)
    }
  };

  function choiceMatcher(group, code) {
    if (code === 'decline') return function (t) { return DECLINE_RE.test(norm(t)); };
    var g = CHOICES[group];
    var fn = g && g[code];
    if (!fn) return null;
    return function (t) { return fn(norm(t)); };
  }

  /* ---- generic option matching ---- */
  function tokens(t) { return t.split(' ').filter(function (w) { return w.length > 1; }); }

  /* Score how well option text matches a wanted value (0-100). aliases: extra accepted forms. */
  function scoreOption(optText, optValue, wanted, aliases) {
    var t = norm(optText);
    var v = norm(optValue);
    var w = norm(wanted);
    var all = [w].concat((aliases || []).map(norm)).filter(Boolean);
    if (!t && !v) return 0;
    for (var i = 0; i < all.length; i++) {
      if (t === all[i] || (v && v === all[i])) return 100;
    }
    if (!w) return 0;
    var best = 0;
    all.forEach(function (a) {
      if (a.length >= 2 && t.length >= 2) {
        if ((' ' + t + ' ').indexOf(' ' + a + ' ') === 0 || (' ' + a + ' ').indexOf(' ' + t + ' ') === 0) best = Math.max(best, a.length >= 4 || t.length >= 4 ? 80 : 65);
        else if (a.length >= 4 && (' ' + t + ' ').indexOf(' ' + a + ' ') !== -1) best = Math.max(best, 70);
        else if (t.length >= 4 && (' ' + a + ' ').indexOf(' ' + t + ' ') !== -1) best = Math.max(best, 62);
      }
    });
    if (best) return best;
    var wt = tokens(w), ot = tokens(t);
    if (!wt.length || !ot.length) return 0;
    var common = wt.filter(function (x) { return ot.indexOf(x) !== -1; }).length;
    var ratio = common / Math.max(wt.length, ot.length);
    return ratio >= 0.5 ? Math.round(40 + ratio * 25) : 0;
  }

  /* Pick an option for a number from range labels like "0-1 years", "3 to 5", "5+", "Less than 1". */
  function numberInOption(text, n) {
    var t = norm(text);
    var m;
    if ((m = t.match(/(\d+(?:\s\d+)?)\s*(?:to|\s)\s*(\d+)/))) {
      var a = parseFloat(m[1]), b = parseFloat(m[2]);
      if (b > a) return n >= a && n <= b;
    }
    if ((m = t.match(/(\d+)\s*\+|(\d+) (?:or more|and above|plus|or over)|more than (\d+)|over (\d+)/))) {
      var lo = parseFloat(m[1] || m[2] || m[3] || m[4]);
      return /more than|over/.test(t) ? n > lo : n >= lo;
    }
    if ((m = t.match(/(less than|under|fewer than) (\d+)/))) return n < parseFloat(m[2]);
    if ((m = t.match(/^(\d+)( years?)?$/))) return n === parseFloat(m[1]);
    return false;
  }

  /*
   * Choose the best option. options: [{text, value}]. want: {text, aliases, matcher, number, prefer}.
   * prefer: words that break ties between equally good text matches (e.g. province, country).
   * Returns the index or -1. A matcher (function on option text) wins over text scoring.
   */
  function pickOption(options, want) {
    var idx = -1;
    var real = [];
    options.forEach(function (o, i) { if (!isPlaceholderOption(o.text, o.value)) real.push(i); });
    if (want.matcher) {
      for (var a = 0; a < real.length; a++) {
        if (want.matcher(options[real[a]].text)) return real[a];
      }
      return -1;
    }
    if (typeof want.number === 'number' && !isNaN(want.number)) {
      for (var b = 0; b < real.length; b++) {
        if (numberInOption(options[real[b]].text, want.number)) return real[b];
      }
    }
    var best = 0;
    var prefer = (want.prefer || []).map(norm).filter(Boolean);
    real.forEach(function (i) {
      var s = scoreOption(options[i].text, options[i].value, want.text, want.aliases);
      if (s >= 60 && prefer.length) {
        // Tie-breaker: "Halifax" + prefer [nova scotia, canada] -> "Halifax, Nova Scotia, Canada".
        var t = ' ' + norm(options[i].text) + ' ';
        s += Math.min(9, prefer.filter(function (w) { return t.indexOf(' ' + w + ' ') !== -1; }).length * 3);
      }
      if (s > best) { best = s; idx = i; }
    });
    return best >= 60 ? idx : -1;
  }

  var api = {
    norm: norm, tidy: tidy, isPlaceholderOption: isPlaceholderOption,
    COUNTRIES: COUNTRIES, REGIONS: REGIONS, findCountry: findCountry,
    countryAliases: countryAliases, regionAliases: regionAliases, countriesMentioned: countriesMentioned,
    parsePhone: parsePhone, parseDate: parseDate, formatDate: formatDate, MONTHS: MONTHS,
    classifyYesNo: classifyYesNo, yesNoValue: yesNoValue, choiceMatcher: choiceMatcher, CHOICES: CHOICES,
    scoreOption: scoreOption, pickOption: pickOption, numberInOption: numberInOption,
    DECLINE_RE: DECLINE_RE
  };
  root.JobKit = root.JobKit || {};
  root.JobKit.text = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
