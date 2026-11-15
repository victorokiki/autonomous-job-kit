/*
 * Autonomous Job Kit Autofill - matching rules (pure functions, no DOM).
 *
 * decide(question, profile, env) returns what to put in one form control:
 *   { ok: true,  rule: 'email', want: {...} }       fill it
 *   { ok: false, rule?: '...', reason: '...' }      leave it for the user
 *
 * question = {
 *   text:     the question as shown (for the report),
 *   label:    norm(text)  (see text.js: lowercase, punctuation -> spaces),
 *   context:  norm(section heading / Workday section id), may be '',
 *   control:  'text' | 'textarea' | 'select' | 'radio' | 'checkbox' | 'checkboxGroup' | 'combobox' | 'file',
 *   inputType: input type attribute ('text', 'email', 'date', ...),
 *   quality:  'label' (real label, aria, legend, placeholder), 'near' (preceding text), 'hint' (name/id only)
 * }
 * env = { hasPhoneCode: bool }  (true when the form has a separate country-code control)
 *
 * want kinds: text {text, aliases?, number?} | yesno {value, fallbackText?} | choice {group, code, display}
 *             | date {value} | file {}
 *
 * Order of checks: sensitive (never) -> consent (never) -> saved answers -> open-ended textareas
 * (never) -> RULES table, first match wins. Rows are kept readable on purpose: one row per field.
 */
(function (root) {
  'use strict';
  var T = root.JobKit && root.JobKit.text;
  if (!T && typeof require === 'function') T = require('./text.js');

  /* Questions the extension must never answer. */
  var SENSITIVE_RE = new RegExp([
    '\\bssn\\b', 'social security', 'social insurance', '\\bsin\\b', 'national (id|identity|identification|insurance)',
    '\\bnino\\b', 'tax (id|identification|number|file)', '\\b(tin|itin)\\b', 'date of birth', 'birth ?date', '\\bdob\\b',
    'birthday', '\\bhow old\\b', '\\bbank', 'routing', 'account (number|no)', '\\biban\\b', '\\bswift\\b', 'sort code',
    'credit card', 'card number', 'passport', 'religio', 'marital', '\\bmarried\\b', 'criminal', 'convicted', 'conviction',
    'felony', 'misdemeanou?r', '\\barrest', 'offen[cs]e', 'background check', 'licen[cs]e (number|no)', 'maiden name',
    'password', 'signature', 'e sign', 'sign here', '\\binitials\\b', 'driver s licen', 'health card', 'medical'
  ].join('|'));

  /* Agreement-style questions: never ticked or answered by the extension. */
  var CONSENT_RE = new RegExp([
    '\\bi agree\\b', '\\bagree to\\b', '\\bi accept\\b', '\\bconsent', 'terms (of|and|&) (use|service|conditions)',
    '\\bterms\\b.*\\b(agree|accept|read)', '\\b(agree|accept|read)\\b.*\\bterms\\b', 'privacy (policy|notice|statement)',
    '\\bcertif(y|ication that)', '\\backnowledg', '\\battest', '\\bi confirm\\b', 'confirm that', '\\bi understand\\b',
    'true (and|,) (correct|complete|accurate)', 'accurate and complete', '\\bgdpr\\b', 'opt (in|out)', '\\bsubscribe',
    'marketing', 'text messages', '\\bsms\\b', 'future (job )?opportunities', 'talent (community|pool|network)',
    'keep me (informed|updated)', 'send me', 'newsletter', 'job alerts', 'retain my (data|information)'
  ].join('|'));

  /* Questions about someone other than the applicant (identity rules must not fire). */
  var NOT_SELF_RE = /\b(emergency|reference|referee|referr\w*|referred|manager|supervisor|parent|guardian|recruiter|spouse|relative|family member|friend|employee who)\b/;
  var NOT_SELF_CTX_RE = /\b(emergency contact|references?|referees?|referral)\b/;

  var QUESTION_RE = /^(are|do|does|did|have|has|had|will|would|can|could|is|was|were|what|which|how|why|when|where|please|if)\b/;
  var EXPERIENCE_CTX = /\b(experience|employment|work history|job history|employer|work experience|workexperience|professional history)\b/;
  var EDUCATION_CTX = /\b(education|school|university|college|degree|academic|educationsection)\b/;

  /* ---- profile helpers ---- */
  function s(v) { return v === null || v === undefined ? '' : String(v).trim(); }
  function first(p, list) { return (Array.isArray(p[list]) && p[list][0] && typeof p[list][0] === 'object') ? p[list][0] : {}; }
  function fullName(p) {
    return s(p.legalName) || [s(p.firstName), s(p.middleName), s(p.lastName)].filter(Boolean).join(' ');
  }
  function phoneParts(p) { return T.parsePhone(p.phone, p.country); }
  function placeWords(p) {
    return T.regionAliases(p.state).filter(function (a) { return a.length > 2; }).concat(T.countryAliases(p.country).filter(function (a) { return a.length > 2; }));
  }

  /* ---- want builders (return null when the profile has no value) ---- */
  function text(v, extra) {
    v = s(v);
    if (!v) return null;
    var w = { kind: 'text', text: v };
    if (extra) for (var k in extra) w[k] = extra[k];
    return w;
  }
  function yesno(v, fallbackText) {
    var y = T.yesNoValue(v);
    if (!y || y === 'decline') return null;
    return { kind: 'yesno', value: y, fallbackText: s(fallbackText) };
  }
  var DISPLAY = {
    gender: { female: 'Female', male: 'Male', nonbinary: 'Non-binary' },
    pronouns: { she: 'She/her', he: 'He/him', they: 'They/them' },
    race: { 'american-indian': 'American Indian or Alaska Native', asian: 'Asian', black: 'Black or African American',
      'pacific-islander': 'Native Hawaiian or Other Pacific Islander', white: 'White', 'two-or-more': 'Two or more races' },
    veteranStatus: { no: 'I am not a protected veteran', protected: 'I identify as a protected veteran' },
    disabilityStatus: { yes: 'Yes', no: 'No' },
    sexualOrientation: { straight: 'Straight', gay: 'Gay', lesbian: 'Lesbian', bisexual: 'Bisexual', pansexual: 'Pansexual', asexual: 'Asexual', queer: 'Queer' }
  };
  function choice(group, code) {
    code = s(code).toLowerCase();
    if (!code) return null;
    var disp = code === 'decline' ? 'Decline to answer' : ((DISPLAY[group] && DISPLAY[group][code]) || (code === 'yes' ? 'Yes' : code === 'no' ? 'No' : code));
    return { kind: 'choice', group: group, code: code, display: disp };
  }
  function date(v) { v = s(v); return v ? { kind: 'date', value: v } : null; }

  /* ---- sponsorship: two answers, one question ---- */
  function sponsorship(p, q) {
    var l = q.label;
    var future = /\b(future|now or|at any (point|time)|ever|eventually|later|long term|h ?1 ?b|green card|permanent)\b/.test(l);
    var internship = /\b(this|the|your) (internship|co op|coop|placement|work term|position|role|job)\b|\bfor (this|the) (internship|co op|term)|\bduration of\b|\bduring (the|this|your)\b/.test(l);
    var now = T.yesNoValue(p.needsSponsorship);
    var intern = T.yesNoValue(p.needsSponsorshipForInternship);
    var v;
    if (future) v = now;
    else if (internship && /\b(internship|co op|coop|placement|work term)\b/.test(l)) v = intern;
    else v = (now && now === intern) ? now : '';
    if (!v && now && intern && now !== intern) return { skip: 'ambiguous' };
    return yesno(v);
  }

  /* ---- work authorization, with a check that the question is about the user's country ---- */
  function workAuth(p, q) {
    var mentioned = T.countriesMentioned(q.text);
    var mine = T.findCountry(p.authCountry || p.country);
    if (mentioned.length && mine && mentioned.indexOf(mine.code) === -1) return { skip: 'other-country' };
    if (mentioned.length && !mine) return { skip: 'other-country' };
    return yesno(p.workAuthorized, p.workAuthDetails);
  }

  function dateOf(item, exactKey, key) { return date(s(item[exactKey]) || s(item[key])); }

  /*
   * RULES: one row per field. Columns:
   *   id     field name in the report
   *   re     question pattern (normalized text)
   *   not    exclusion pattern (optional)
   *   ctx    required section context pattern (optional)
   *   self   true when the question must be about the applicant
   *   hint   true when an id/name attribute alone is good enough evidence
   *   get    function(profile, question, env) -> want | null | {skip: reason}
   */
  var RULES = [
    // --- section-specific rows first (education / experience blocks reuse generic words) ---
    { id: 'education start', ctx: EDUCATION_CTX, re: /\b(start|from|begin|began|starting)\b/, not: /availab|earliest|desired|preferred|proposed/, get: function (p) { return dateOf(first(p, 'education'), 'startExact', 'start'); } },
    { id: 'education end', ctx: EDUCATION_CTX, re: /\b(end|to|until|finish|completion|expected end)\b/, not: /available|availability/, get: function (p) { var e = first(p, 'education'); return dateOf(e, 'endExact', 'end') || date(p.expectedGraduation); } },
    { id: 'current employer', ctx: EXPERIENCE_CTX, re: /\b(company|employer|organi[sz]ation)( name)?\b/, not: /\b(email|phone|website|url)\b/, get: function (p) { return text(first(p, 'work').company); } },
    { id: 'current title', ctx: EXPERIENCE_CTX, re: /\b(job title|title|position|role)\b/, not: /applying|apply/, get: function (p) { return text(first(p, 'work').title); } },
    { id: 'work location', ctx: EXPERIENCE_CTX, re: /\b(location|city)\b/, get: function (p) { return text(first(p, 'work').location); } },
    { id: 'work start', ctx: EXPERIENCE_CTX, re: /\b(start|from|begin)\b/, not: /availab|earliest|desired|preferred|proposed/, get: function (p) { return date(first(p, 'work').start); } },
    { id: 'work end', ctx: EXPERIENCE_CTX, re: /\b(end|to|until)\b/, not: /available|availability/, get: function (p) { var e = s(first(p, 'work').end); return /present|current/i.test(e) ? null : date(e); } },

    // --- phone ---
    { id: 'phone country code', re: /\b(country|dial(ing)?|calling|phone|mobile)\b.*\bcode\b|\bcountry code\b/, not: /\b(postal|zip|post|area)\b/, hint: true,
      get: function (p) { var ph = phoneParts(p); if (!ph || !ph.dial) return null; var c = T.findCountry(p.country); return text(ph.dial, { aliases: c ? [c.dial, c.names[0] + ' ' + c.dial, c.names[0] + ' +' + c.dial.slice(1)].concat(c.names) : [] }); } },
    { id: 'phone', self: true, hint: true, re: /\b(phone|mobile|cell|cellphone|telephone|tel|contact number|phone number)\b/, not: /\b(extension|ext|type|device|code|carrier)\b/,
      get: function (p, q, env) { var ph = phoneParts(p); if (!ph) return null; return text(env && env.hasPhoneCode ? ph.national : ph.full); } },

    // --- email ---
    { id: 'email', self: true, hint: true, re: /\be ?mail\b/, not: /\b(subscribe|newsletter|updates|alerts)\b/, get: function (p) { return text(p.email); } },

    // --- names ---
    { id: 'preferred name', self: true, hint: true, re: /\b(preferred|nick ?name|known as|chosen|goes by)\b/, not: /\b(pronoun|location|language|contact method)\b/,
      get: function (p) { return text(s(p.preferredName) || s(p.firstName)); } },
    { id: 'middle name', self: true, hint: true, re: /\bmiddle (name|initial)\b|^middle$/, get: function (p, q) { var m = s(p.middleName); if (/initial/.test(q.label)) m = m.charAt(0); return text(m); } },
    { id: 'first name', self: true, hint: true, re: /\b(first|given|fore) ?name\b|^first$|^fname$/, not: /\blast\b|\bpreferred\b/, get: function (p) { return text(p.firstName); } },
    { id: 'last name', self: true, hint: true, re: /\b(last|family|sur) ?name\b|^last$|^lname$|\bsurname\b/, get: function (p) { return text(p.lastName); } },
    { id: 'full name', self: true, hint: true, re: /^(your )?(full |legal |complete )?name( as it appears.*)?$|\b(full|legal|complete) (legal )?name\b|^name of applicant$|^applicant name$|^candidate name$/,
      not: /\b(first|last|middle|preferred|company|school|university|employer|institution|business|reference|file|user ?name)\b/, get: function (p) { return text(fullName(p)); } },

    // --- address ---
    { id: 'street', self: true, hint: true, re: /\b(street|address line 1|address 1|address1|addressline1|street address|mailing address|home address|residential address)\b|^address$|^current address$/,
      not: /\b(e ?mail|line 2|address 2|web|url|ip|city|postal|zip)\b/, get: function (p) { return text(p.street); } },
    { id: 'city', self: true, hint: true, re: /\b(city|town|municipality|locality)\b/, not: /\b(birth|state|province)\b|city and|city state/, get: function (p) { return text(p.city, { prefer: placeWords(p) }); } },
    { id: 'location', self: true, re: /^(current )?location( city)?$|\b(current|home) location\b|where are you (currently )?(located|based)|\bcity (and|,)? ?(state|province)\b|\bcity state\b|^location city$/,
      not: /\bsponsor\w*|\bvisa\b|\bwork permit\b|\bauthori[sz]\w*|\brelocat\w*|\bremain in\b/,
      get: function (p) { return text([s(p.city), s(p.state)].filter(Boolean).join(', '), { typeText: s(p.city), prefer: placeWords(p) }); } },
    { id: 'province / state', self: true, hint: true, re: /\b(state|province|region|prefecture|county|territory)\b/, not: /united states|\bstatement\b|please state|state your|state why|state the|state of birth|\bstatus\b/,
      get: function (p) { return text(p.state, { aliases: T.regionAliases(p.state) }); } },
    { id: 'postal code', self: true, hint: true, re: /\b(postal|zip|post) ?code\b|\bzip\b|\bpostcode\b|\bpostal\b/, get: function (p) { return text(p.postalCode); } },
    { id: 'country', self: true, hint: true, re: /\bcountry\b/, not: /\b(code|citizenship|authori[sz]\w*|sponsor\w*|legally|permit|born|birth|nationality|work in)\b/,
      get: function (p) { return text(p.country, { aliases: T.countryAliases(p.country) }); } },

    // --- links ---
    { id: 'LinkedIn', hint: true, re: /\blinked ?in\b/, get: function (p) { return text(p.linkedin); } },
    { id: 'GitHub', hint: true, re: /\bgit ?hub\b/, get: function (p) { return text(p.github); } },
    { id: 'portfolio', hint: true, re: /\bportfolio\b/, get: function (p) { return text(s(p.portfolio) || s(p.website)); } },
    { id: 'website', hint: true, re: /\b(website|web site|personal site|homepage|home page|personal url|blog)\b|^(other )?(url|link|links)$/, not: /\b(company|linked ?in|git ?hub|twitter|facebook|instagram)\b/,
      get: function (p) { return text(s(p.website) || s(p.portfolio)); } },

    // --- school status (before school name) ---
    { id: 'currently enrolled', re: /\b(currently|presently) (enrolled|a student|attending|studying|in school|pursuing)\b|\bare you (a |an )?(current |currently )?(student|enrolled)\b|\benrolled (full time|in a)\b/,
      get: function (p) { return yesno(p.enrolled); } },
    { id: 'returning to school', re: /\breturn(ing)? to (school|university|college|your studies|studies|campus)\b|\bcontinu(e|ing) (your )?(studies|education|degree)\b/,
      get: function (p) { return yesno(p.returningToSchool); } },
    { id: 'high school graduation', re: /\bhigh school\b.*\b(graduat\w*|year|date|complet\w*)\b/, get: function (p) { return date(p.highSchoolGraduation); } },
    { id: 'graduation date', re: /\b(expected |anticipated )?(graduation|grad)\b|\bwhen (do|will) you graduate\b|\bdegree completion\b|\bcompletion date\b/,
      not: /\b(high school|graduate (degree|program|student|school))\b/, get: function (p) { var e = first(p, 'education'); return date(s(p.expectedGraduation) || s(e.endExact) || s(e.end)); } },

    // --- education ---
    { id: 'school', hint: true, re: /\b(school|university|college|institution|alma mater)\b/, not: /\b(high school|year|date|gpa|degree|major|location|city|country|email)\b/,
      get: function (p) { return text(first(p, 'education').school); } },
    { id: 'field of study', hint: true, re: /\b(field of study|major|discipline|area of study|subject|concentration|programme? of study|specialization|specialisation|course of study|program name)\b/, not: /\bminor\b/,
      get: function (p) { return text(first(p, 'education').field); } },
    { id: 'degree', hint: true, re: /\b(degree|qualification|diploma|level of education|highest education|education level|degree type)\b/, not: /\b(field|major|discipline|subject|date|year|gpa|grade)\b/,
      get: function (p) { return text(first(p, 'education').degree); } },
    { id: 'minor', re: /\bminor\b/, get: function (p) { return text(first(p, 'education').minor); } },
    { id: 'GPA', hint: true, re: /\b(gpa|cgpa|grade point|average grade|cumulative average)\b/, not: /\b(scale|out of|max|maximum)\b/, get: function (p) { return text(first(p, 'education').gpa); } },
    { id: 'class standing', re: /\b(class standing|year of study|academic (year|standing|level)|current year|year in (school|program|university)|study year|which year|year of (your )?program|class level|student level)\b/,
      get: function (p) { return text(p.classStanding); } },
    { id: 'relevant coursework', re: /\b(relevant course ?work|course ?work|courses (taken|completed))\b/, get: function (p) { return text(p.relevantCoursework); } },
    { id: 'internship term', re: /\b(term|session|season|semester|work term|co op (term|period)|intake)\b/, not: /\b(long term|short term|terms|term of|full term)\b|sponsor|visa|authori[sz]|permit|relocat/,
      get: function (p) { return text(p.internshipTerm); } },

    // --- availability and start date ---
    { id: 'available until', re: /\bavailab\w* (until|to|through|end)\b|\b(end of|latest) (your )?availability\b|\buntil when\b|\bavailability end\b|\bavailable end date\b/, get: function (p) { return date(p.availableUntil); } },
    { id: 'available from', re: /\bavailab\w* (from|to start|start)\b|\bavailability (start|date)\b|\bearliest (start|available|date)\b|\bwhen (can|could|would) you (start|begin)\b|\bdate available\b/,
      get: function (p) { return date(s(p.availableFrom) || s(p.startDate)); } },
    { id: 'start date', re: /\b(desired |preferred |earliest |proposed |anticipated )?start(ing)? date\b/, get: function (p) { return date(s(p.startDate) || s(p.availableFrom)); } },

    // --- current job ---
    { id: 'current employer', re: /\b(current|present|most recent|latest|recent) (company|employer|organi[sz]ation|workplace)\b|^employer( name)?$/, get: function (p) { return text(first(p, 'work').company); } },
    { id: 'current title', re: /\b(current|present|most recent|latest) (job )?(title|position|role|job)\b/, get: function (p) { return text(first(p, 'work').title); } },
    { id: 'years of experience', re: /\byears (of )?(relevant |professional |work |total |related |industry )?experience\b|\bhow many years\b/,
      get: function (p) { var y = s(p.yearsExperience); return y ? text(y, { number: parseFloat(y) }) : null; } },

    // --- authorization and sponsorship ---
    { id: 'sponsorship', re: /\bsponsor\w*\b|\b(require|need)\b.*\b(visa|immigration|work permit)\b/, get: sponsorship },
    { id: 'work authorization', re: /\b(legally )?(authori[sz]ed|eligible|permitted|entitled|allowed|right) to (work|be employed)\b|\bwork authori[sz]ation\b|\bemployment eligibility\b|\bright to work\b/,
      get: workAuth },
    { id: 'permit expiry', re: /\b(permit|visa|authori[sz]ation|status)\b.*\b(expir\w*|end date|valid until|valid through)\b/, get: function (p) { return date(p.permitExpiry); } },
    { id: 'work status', re: /\b(work|immigration|visa|residency|employment|citizenship|legal) status\b|\bwork permit (type|status)\b|\bstatus in (canada|the united states|the us|the uk|the united kingdom)\b/,
      get: function (p) { return text(p.workAuthDetails); } },
    { id: 'relocation', re: /\breloca\w*\b/, get: function (p) { return yesno(p.willingToRelocate); } },
    { id: 'government relative', re: /\b(relative|family|related|household|immediate family)\b.*\b(government|public (official|servant|sector|office)|official)\b|\b(government|public official)\b.*\b(relative|family|related)\b/,
      get: function (p) { return yesno(p.governmentRelative); } },
    { id: 'government employee', re: /\b(government|public sector|public service|public official|civil serv\w*|federal employee|state employee|crown corporation)\b/, not: /\b(clearance|security|grant|funding|contract|id)\b/,
      get: function (p) { return yesno(p.governmentEmployee); } },

    // --- job details ---
    { id: 'salary', re: /\b(salary|compensation|pay (expectation|range|requirement)s?|expected (pay|wage|rate)|desired (pay|wage|rate)|hourly rate|wage)\b/, get: function (p) { return text(p.salary); } },
    { id: 'work arrangement', re: /\b(work (arrangement|preference|model|setting|style|location preference)|workplace type|remote or (on site|hybrid)|preferred work (location|arrangement|environment))\b/,
      get: function (p) { return text(p.workPreference); } },
    { id: 'skills', re: /^(key |technical |relevant )?skills$/, get: function (p) { return text(p.skills); } },

    // --- voluntary self-identification (most specific first) ---
    { id: 'transgender', re: /\btransgender\b|\btrans\b|\bgender identity\b.*\b(same|different|differ)\b|\bassigned at birth\b/, get: function (p) { return choice('transgender', p.transgender); } },
    { id: 'sexual orientation', re: /\bsexual orientation\b|\borientation\b/, get: function (p) { return choice('sexualOrientation', p.sexualOrientation); } },
    { id: 'LGBTQ+', re: /\blgbt|\b2slgbt|\bqueer community\b/, get: function (p) { return choice('lgbtq', p.lgbtq); } },
    { id: 'pronouns', re: /\bpronoun/, get: function (p) { return choice('pronouns', p.pronouns); } },
    { id: 'gender', re: /\bgender\b|\bsex\b/, get: function (p) { return choice('gender', p.gender); } },
    { id: 'Hispanic or Latino', re: /\bhispanic\b|\blatin[oaxe]\b|\blatinx\b/, get: function (p) { return choice('hispanicLatino', p.hispanicLatino); } },
    { id: 'race / ethnicity', re: /\brace\b|\bethnic\w*\b|\bracial\b/, get: function (p) { return choice('race', p.race); } },
    { id: 'veteran status', re: /\bveteran\b|\bmilitary\b|\barmed forces\b|\buniformed service\b/, get: function (p) { return choice('veteranStatus', p.veteranStatus); } },
    { id: 'disability', re: /\bdisabilit\w*\b|\bhandicap\w*\b|\bimpairment\b/, get: function (p) { return choice('disabilityStatus', p.disabilityStatus); } }
  ];

  function savedAnswerFor(label, profile) {
    var list = Array.isArray(profile.savedAnswers) ? profile.savedAnswers : [];
    var best = null;
    list.forEach(function (a) {
      if (!a || typeof a !== 'object') return;
      var m = T.norm(a.match);
      var ans = s(a.answer);
      if (m.length < 3 || !ans) return;
      if ((' ' + label + ' ').indexOf(' ' + m + ' ') !== -1 && (!best || m.length > best.m.length)) best = { m: m, answer: ans };
    });
    return best;
  }

  var RESUME_RE = /\b(resume|cv|curriculum vitae)\b/;
  var COVER_RE = /\bcover letter\b|\bcoverletter\b|\bmotivation letter\b/;

  function decide(q, profile, env) {
    profile = profile || {};
    env = env || {};
    var label = q.label || '';
    if (!label) return { ok: false, reason: 'no label' };

    if (q.control === 'file') {
      if (COVER_RE.test(label)) return { ok: false, rule: 'cover letter', reason: 'file' };
      if (RESUME_RE.test(label)) return { ok: true, rule: 'resume', want: { kind: 'file' } };
      return { ok: false, reason: 'file' };
    }
    if (SENSITIVE_RE.test(label)) return { ok: false, reason: 'sensitive' };
    if (CONSENT_RE.test(label)) return { ok: false, reason: 'consent' };

    var saved = savedAnswerFor(label, profile);
    if (saved) return { ok: true, rule: 'saved answer "' + saved.m + '"', want: { kind: 'text', text: saved.answer, saved: true } };

    if (q.control === 'textarea') return { ok: false, reason: 'open-ended' };

    for (var i = 0; i < RULES.length; i++) {
      var r = RULES[i];
      // Section rows only apply to short field labels ("From", "Company"), never to questions.
      if (r.ctx && (!r.ctx.test(q.context || '') || label.split(' ').length > 5 || QUESTION_RE.test(label))) continue;
      if (!r.re.test(label)) continue;
      if (r.not && r.not.test(label)) continue;
      if (r.self && (NOT_SELF_RE.test(label) || NOT_SELF_CTX_RE.test(q.context || ''))) return { ok: false, rule: r.id, reason: 'not about you' };
      if (q.quality === 'hint' && !r.hint) return { ok: false, rule: r.id, reason: 'low confidence' };
      var want = r.get(profile, q, env);
      if (!want) return { ok: false, rule: r.id, reason: 'not in profile' };
      if (want.skip) return { ok: false, rule: r.id, reason: want.skip };
      return { ok: true, rule: r.id, want: want };
    }
    return { ok: false, reason: 'unknown question' };
  }

  var api = { decide: decide, RULES: RULES, SENSITIVE_RE: SENSITIVE_RE, CONSENT_RE: CONSENT_RE, NOT_SELF_RE: NOT_SELF_RE, RESUME_RE: RESUME_RE, COVER_RE: COVER_RE };
  root.JobKit = root.JobKit || {};
  root.JobKit.rules = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
