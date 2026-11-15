/*
 * Autonomous Autofill - profile schema and profile.json round-trip helpers.
 *
 * Shared by the options page (to build the editor) and by the Node check script in
 * tests/extension/. It has no DOM or chrome.* dependencies.
 *
 * Round-trip rule: the stored profile is the user's whole profile.json object. The editor
 * only changes the keys it knows about; every other key (kit settings such as
 * automationLevel, letterMaxWords, projects, ...) is carried through untouched, and a value
 * whose text did not change keeps its original JSON type (so 2 stays 2, not "2").
 */
(function (root) {
  'use strict';

  var YES_NO = [
    { value: '', label: 'Not set' },
    { value: 'yes', label: 'Yes' },
    { value: 'no', label: 'No' }
  ];

  function decline(list) {
    return [{ value: '', label: 'Not set (leave for me)' }].concat(list, [{ value: 'decline', label: 'Decline to answer' }]);
  }

  var SELF_ID = {
    gender: decline([
      { value: 'female', label: 'Female / woman' },
      { value: 'male', label: 'Male / man' },
      { value: 'nonbinary', label: 'Non-binary' }
    ]),
    pronouns: decline([
      { value: 'she', label: 'She / her' },
      { value: 'he', label: 'He / him' },
      { value: 'they', label: 'They / them' }
    ]),
    hispanicLatino: decline([
      { value: 'yes', label: 'Yes' },
      { value: 'no', label: 'No' }
    ]),
    race: decline([
      { value: 'american-indian', label: 'American Indian, Alaska Native or Indigenous' },
      { value: 'asian', label: 'Asian' },
      { value: 'black', label: 'Black or African American' },
      { value: 'pacific-islander', label: 'Native Hawaiian or Pacific Islander' },
      { value: 'white', label: 'White' },
      { value: 'two-or-more', label: 'Two or more races' }
    ]),
    veteranStatus: decline([
      { value: 'no', label: 'Not a veteran' },
      { value: 'protected', label: 'Protected veteran' }
    ]),
    disabilityStatus: decline([
      { value: 'yes', label: 'Yes, I have a disability' },
      { value: 'no', label: 'No disability' }
    ]),
    lgbtq: decline([
      { value: 'yes', label: 'Yes' },
      { value: 'no', label: 'No' }
    ]),
    transgender: decline([
      { value: 'yes', label: 'Yes' },
      { value: 'no', label: 'No' }
    ]),
    sexualOrientation: decline([
      { value: 'straight', label: 'Straight / heterosexual' },
      { value: 'gay', label: 'Gay' },
      { value: 'lesbian', label: 'Lesbian' },
      { value: 'bisexual', label: 'Bisexual' },
      { value: 'pansexual', label: 'Pansexual' },
      { value: 'asexual', label: 'Asexual' },
      { value: 'queer', label: 'Queer' }
    ])
  };

  /* Field definition: key, label, type (text|email|tel|url|date|textarea|select), help, choices, auto (autocomplete). */
  var SECTIONS = [
    {
      id: 'contact', title: 'Name and contact',
      fields: [
        { key: 'firstName', label: 'First name', auto: 'given-name' },
        { key: 'middleName', label: 'Middle name', auto: 'additional-name' },
        { key: 'lastName', label: 'Last name', auto: 'family-name' },
        { key: 'preferredName', label: 'Preferred name', help: 'Used for "preferred name" questions. Empty means your first name.' },
        { key: 'legalName', label: 'Legal full name', help: 'Used for "full legal name" questions.' },
        { key: 'resumeName', label: 'Name as printed on your resume' },
        { key: 'email', label: 'Email', type: 'email', auto: 'email' },
        { key: 'phone', label: 'Phone', type: 'tel', auto: 'tel', help: 'Include the country code, e.g. +1 (902) 555-0142.' }
      ]
    },
    {
      id: 'address', title: 'Address',
      fields: [
        { key: 'street', label: 'Street address', auto: 'address-line1' },
        { key: 'city', label: 'City', auto: 'address-level2' },
        { key: 'state', label: 'Province / state / region', help: 'Code or name, e.g. NS or Nova Scotia.' },
        { key: 'postalCode', label: 'Postal / ZIP code', auto: 'postal-code' },
        { key: 'country', label: 'Country', auto: 'country-name' }
      ]
    },
    {
      id: 'links', title: 'Links',
      fields: [
        { key: 'linkedin', label: 'LinkedIn', type: 'url' },
        { key: 'github', label: 'GitHub', type: 'url' },
        { key: 'portfolio', label: 'Portfolio', type: 'url' },
        { key: 'website', label: 'Personal website', type: 'url' }
      ]
    },
    { id: 'education', title: 'Education', list: 'education' },
    { id: 'work', title: 'Work experience', list: 'work' },
    {
      id: 'student', title: 'Student details',
      fields: [
        { key: 'expectedGraduation', label: 'Expected graduation', help: 'e.g. Apr 2027 or 2027-04-30.' },
        { key: 'classStanding', label: 'Class standing / year of study', help: 'e.g. Third year, Junior, Graduate.' },
        { key: 'enrolled', label: 'Currently enrolled', type: 'select', choices: YES_NO },
        { key: 'returningToSchool', label: 'Returning to school after the work term', type: 'select', choices: YES_NO },
        { key: 'relevantCoursework', label: 'Relevant coursework' },
        { key: 'internshipTerm', label: 'Internship / co-op term', help: 'e.g. Summer 2026.' },
        { key: 'availableFrom', label: 'Available from' },
        { key: 'availableUntil', label: 'Available until' },
        { key: 'highSchoolGraduation', label: 'High school graduation' }
      ]
    },
    {
      id: 'authorization', title: 'Work authorization',
      fields: [
        { key: 'workAuthorized', label: 'Legally allowed to work', type: 'select', choices: YES_NO },
        { key: 'authCountry', label: 'Country that answer applies to', help: 'Questions about another country are left for you.' },
        { key: 'workAuthDetails', label: 'Status in your own words', help: 'e.g. Canadian citizen, Open work permit until 2027-05-01.' },
        { key: 'needsSponsorship', label: 'Need sponsorship now or in the future', type: 'select', choices: YES_NO },
        { key: 'needsSponsorshipForInternship', label: 'Need sponsorship for this internship / co-op', type: 'select', choices: YES_NO,
          help: 'A question that does not say which one is filled only when both answers agree.' },
        { key: 'permitExpiry', label: 'Permit expiry date' },
        { key: 'willingToRelocate', label: 'Willing to relocate', type: 'select', choices: YES_NO },
        { key: 'governmentEmployee', label: 'Current or former government employee', type: 'select', choices: YES_NO },
        { key: 'governmentRelative', label: 'Relative works for the government', type: 'select', choices: YES_NO }
      ]
    },
    {
      id: 'job', title: 'Job preferences',
      fields: [
        { key: 'salary', label: 'Salary expectation' },
        { key: 'startDate', label: 'Earliest start date' },
        { key: 'workPreference', label: 'Work arrangement preference', help: 'e.g. Hybrid or remote.' },
        { key: 'yearsExperience', label: 'Years of experience' },
        { key: 'skills', label: 'Skills', help: 'Comma-separated.' },
        { key: 'summary', label: 'Short summary', type: 'textarea' }
      ]
    },
    {
      id: 'selfid', title: 'Voluntary self-identification',
      intro: '"Not set" leaves the question for you. "Decline to answer" picks the decline option when the form has one.',
      fields: [
        { key: 'gender', label: 'Gender', type: 'select', choices: SELF_ID.gender },
        { key: 'pronouns', label: 'Pronouns', type: 'select', choices: SELF_ID.pronouns },
        { key: 'hispanicLatino', label: 'Hispanic or Latino', type: 'select', choices: SELF_ID.hispanicLatino },
        { key: 'race', label: 'Race / ethnicity', type: 'select', choices: SELF_ID.race },
        { key: 'veteranStatus', label: 'Veteran status', type: 'select', choices: SELF_ID.veteranStatus },
        { key: 'disabilityStatus', label: 'Disability', type: 'select', choices: SELF_ID.disabilityStatus },
        { key: 'lgbtq', label: 'LGBTQ+', type: 'select', choices: SELF_ID.lgbtq },
        { key: 'transgender', label: 'Transgender', type: 'select', choices: SELF_ID.transgender },
        { key: 'sexualOrientation', label: 'Sexual orientation', type: 'select', choices: SELF_ID.sexualOrientation }
      ]
    },
    { id: 'answers', title: 'Saved answers', list: 'savedAnswers' }
  ];

  var LISTS = {
    education: {
      itemTitle: 'Education',
      fields: [
        { key: 'school', label: 'School' },
        { key: 'degree', label: 'Degree' },
        { key: 'field', label: 'Field of study' },
        { key: 'minor', label: 'Minor' },
        { key: 'start', label: 'Start', help: 'e.g. Sep 2022' },
        { key: 'end', label: 'End', help: 'e.g. Apr 2026 or Present' },
        { key: 'startExact', label: 'Exact start date', type: 'date' },
        { key: 'endExact', label: 'Exact end date', type: 'date' },
        { key: 'gpa', label: 'GPA' }
      ]
    },
    work: {
      itemTitle: 'Job',
      fields: [
        { key: 'title', label: 'Job title' },
        { key: 'company', label: 'Company' },
        { key: 'location', label: 'Location' },
        { key: 'start', label: 'Start' },
        { key: 'end', label: 'End' },
        { key: 'highlights', label: 'Highlights (one per line)', type: 'textarea' }
      ]
    },
    savedAnswers: {
      itemTitle: 'Answer',
      intro: 'When a question contains the phrase, the answer is used (also for open text boxes). Example: "how did you hear" → "Company careers page".',
      fields: [
        { key: 'match', label: 'Question contains', help: 'Short lowercase phrase.' },
        { key: 'answer', label: 'Answer', type: 'textarea' }
      ]
    }
  };

  var MAX_RESUME_BYTES = 5 * 1024 * 1024;

  function isPlainObject(v) {
    return v !== null && typeof v === 'object' && !Array.isArray(v);
  }

  function clone(v) {
    return JSON.parse(JSON.stringify(v));
  }

  function asText(v) {
    if (v === null || v === undefined) return '';
    if (typeof v === 'string') return v;
    if (typeof v === 'number' || typeof v === 'boolean') return String(v);
    return '';
  }

  function scalarFields() {
    var out = [];
    SECTIONS.forEach(function (s) { (s.fields || []).forEach(function (f) { out.push(f); }); });
    return out;
  }

  /* Values the editor shows: {scalars: {key: text}, lists: {name: [{_origin, key: text}]}}. */
  function formValuesFromProfile(profile) {
    profile = isPlainObject(profile) ? profile : {};
    var scalars = {};
    scalarFields().forEach(function (f) { scalars[f.key] = asText(profile[f.key]); });
    var lists = {};
    Object.keys(LISTS).forEach(function (name) {
      var src = Array.isArray(profile[name]) ? profile[name] : [];
      lists[name] = src.map(function (item, i) {
        var row = { _origin: i };
        LISTS[name].fields.forEach(function (f) { row[f.key] = isPlainObject(item) ? asText(item[f.key]) : ''; });
        return row;
      });
    });
    return { scalars: scalars, lists: lists };
  }

  /* Write one edited text value onto target[key] without disturbing untouched values or types. */
  function putValue(target, original, key, text) {
    text = text === undefined || text === null ? '' : String(text);
    if (Object.prototype.hasOwnProperty.call(original, key)) {
      if (asText(original[key]) === text && (typeof original[key] !== 'object' || original[key] === null)) {
        target[key] = original[key];
      } else {
        target[key] = text;
      }
    } else if (text !== '') {
      target[key] = text;
    }
  }

  /* Merge editor values back into the original profile and return a new object. */
  function applyFormValues(original, values) {
    original = isPlainObject(original) ? original : {};
    var out = clone(original);
    var scalars = (values && values.scalars) || {};
    scalarFields().forEach(function (f) {
      if (Object.prototype.hasOwnProperty.call(scalars, f.key)) putValue(out, original, f.key, scalars[f.key]);
    });
    var lists = (values && values.lists) || {};
    Object.keys(LISTS).forEach(function (name) {
      if (!Object.prototype.hasOwnProperty.call(lists, name)) return;
      var rows = lists[name] || [];
      var srcList = Array.isArray(original[name]) ? original[name] : [];
      if (!Object.prototype.hasOwnProperty.call(original, name) && rows.length === 0) return;
      out[name] = rows.map(function (row) {
        var origItem = (typeof row._origin === 'number' && isPlainObject(srcList[row._origin])) ? srcList[row._origin] : {};
        var item = clone(origItem);
        LISTS[name].fields.forEach(function (f) { putValue(item, origItem, f.key, row[f.key]); });
        return item;
      });
    });
    return out;
  }

  /* Parse an imported profile.json; throws Error with a readable message. */
  function parseProfileText(text) {
    var data;
    try {
      data = JSON.parse(String(text).replace(/^﻿/, ''));
    } catch (e) {
      throw new Error('This file is not valid JSON: ' + e.message);
    }
    if (!isPlainObject(data)) throw new Error('profile.json must contain one JSON object ({ ... }).');
    return data;
  }

  function exportProfileText(profile) {
    return JSON.stringify(isPlainObject(profile) ? profile : {}, null, 2) + '\n';
  }

  var api = {
    SECTIONS: SECTIONS,
    LISTS: LISTS,
    SELF_ID: SELF_ID,
    YES_NO: YES_NO,
    MAX_RESUME_BYTES: MAX_RESUME_BYTES,
    scalarFields: scalarFields,
    formValuesFromProfile: formValuesFromProfile,
    applyFormValues: applyFormValues,
    parseProfileText: parseProfileText,
    exportProfileText: exportProfileText,
    asText: asText
  };

  root.JobKit = root.JobKit || {};
  root.JobKit.schema = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
