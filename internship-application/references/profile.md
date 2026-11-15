# profile.json reference

profile.json, in the job-search folder, stores the user's reusable answers. The scripts and the Autonomous Autofill extension read keys by name, so spell them exactly as in `profile-template.json`. Every key is optional.

The extension keeps its own copy: the user loads this file with **Import profile.json** on the extension's options page and can export changes with **Download profile.json** (same schema; unknown keys survive the round trip).

## Housekeeping

- Edit it in place; never delete it.
- Invalid JSON: move the broken file into `_old/` with a date-time stamp, then save a repaired version.

## Making a new one

Only when the folder has none.

1. Start from `references/profile-template.json`: copy it into the folder under the name `profile.json`.
2. Copy over what the master resume states, word for word: names, contact details, location, links, schooling (most recent first), jobs, projects, skills, courses, graduation date. Leave everything else blank; never guess.
3. In a single message, ask only what the resume can't tell you, marking which questions are optional:
   - work authorization (`workAuthorized`, `authCountry`) and, in their own words, `workAuthDetails`;
   - sponsorship as two separate questions: now or in the future (`needsSponsorship`) and for the internship itself (`needsSponsorshipForInternship`); never decide these for them;
   - class standing, internship term, available dates, currently enrolled, returning to school after, willing to relocate, work preference;
   - government ties: has the user ever held a government job or office (`governmentEmployee`); is a close relative one (`governmentRelative`);
   - optional self-identification (gender, pronouns, Hispanic/Latino, race, veteran, disability, LGBTQ+, transgender, sexual orientation): each an answer, "decline", or blank so the user answers per form; never deduce these from appearance, name or any other clue;
   - optional: a `writingStyle` and `extraRules` to shape drafted answers;
   - `legalName` if their legal name differs from first + last (used for signatures).
4. Save it and say once: "profile.json is ready. In Autonomous Autofill, open the options page, click **Import profile.json** and pick this file so the Fill with Autonomous button uses the same answers."

## Keys and allowed values

**Identity and contact:** `firstName`, `middleName`, `lastName`, `preferredName`, `legalName` (signatures and "legal name" fields), `resumeName` (the name exactly as printed on resumes and letters, e.g. "Alex Morgan Tremblay"; cover_letter.py uses it and it goes to check_tailored.py as `--name`), `email`, `phone`, `street`, `city`, `state` (province/state/region code), `postalCode`, `country`, `linkedin`, `github`, `portfolio`, `website`.

**History (lists):**

- `education`: `{school, degree, field, minor, start, end, startExact, endExact, gpa}`. `start`/`end` as on the resume; `startExact`/`endExact` as YYYY-MM-DD for forms wanting exact dates; GPA verbatim.
- `projects`: `{name, tools, link, highlights}`.
- `work`: `{title, company, location, start, end, highlights}`; `highlights` holds a line per point.

**Student:** `expectedGraduation` ("May 2028"), `classStanding` ("Sophomore"), `enrolled`, `returningToSchool`, `relevantCoursework`, `internshipTerm` ("Summer 2027"), `availableFrom`/`availableUntil` ("June 1, 2027"), `highSchoolGraduation`.

**Authorization:** `workAuthorized`, `authCountry`, `workAuthDetails` (the user's words, e.g. "Open work permit until 2027-05-01"; used for written answers and fetch_posting's eligibility screen), `needsSponsorship`, `needsSponsorshipForInternship`, `permitExpiry` (YYYY-MM-DD), `willingToRelocate`, `governmentEmployee`, `governmentRelative`.

**Job:** `salary`, `startDate`, `workPreference`, `yearsExperience`, `summary`, `skills`.

**Yes/no keys** (`"yes"`, `"no"`, or `""` for unset): `workAuthorized`, `needsSponsorship`, `needsSponsorshipForInternship`, `enrolled`, `returningToSchool`, `willingToRelocate`, `governmentEmployee`, `governmentRelative`.

**Self-identification codes** (`""` leaves the question for the user on each form):

| Key | Codes |
|---|---|
| `gender` | `female`, `male`, `nonbinary`, `decline` |
| `pronouns` | `she`, `he`, `they`, `decline` (other pronouns: leave blank) |
| `race` | `asian`, `black`, `white`, `american-indian`, `pacific-islander`, `two-or-more`, `decline` |
| `hispanicLatino`, `disabilityStatus`, `lgbtq`, `transgender` | `yes`, `no`, `decline` |
| `veteranStatus` | `protected`, `no`, `decline` |
| `sexualOrientation` | `decline`, `straight`, `gay`, `lesbian`, `bisexual`, `pansexual`, `asexual`, `queer` |

**Answers and voice:** `savedAnswers` (`[{match, answer}]`: any question containing the short lowercase `match` phrase gets `answer`), `writingStyle`, `extraRules` (one rule per line).

**Kit settings** (set only from the user's choices):

| Key | Effect |
|---|---|
| `automationLevel` | `lean`, `assisted` or `full` (automation-levels.md). |
| `resumeMaxPages` | Maximum pages for non-student jobs (default 1); never applies to internships, co-ops or student roles, which get one page. |
| `bulletFormula` | `xyz`: XYZ bullets, two versions each, plus "To confirm" and "Flags" in changes.md (tailoring.md). |
| `coverLetterPolicy` | `required-or-asked`: letters only when required or requested; optional letter fields stay empty. |
| `letterStyle` | `carlito`: single-column Carlito letter with capitalised name, one contact line, address block and bold "Re:" line. Blank = default layout. |
| `letterMaxWords` | Letter word limit, default 250. |
| `alwaysCombine` | `true`: every letter also gets a merged `*_Resume_and_Cover_Letter_*.pdf` for one-upload forms. |
| `combinedOrder` | `letter-first` = letter, then resume; anything else = resume, then letter. |
| `weeklyGoal` | Applications per week; weekly_report.py tracks progress against it. |

## Saving new answers

A new answer from the user that is likely to be needed again gets stored right away, no permission needed; mention it in a single line. Use the matching key if one exists; otherwise add to `savedAnswers` an entry `{"match": "<key phrase>", "answer": "<the user's reply>"}`. Skip answers tied to one employer ("Why this company?").

Whenever profile.json changed during a run, end the report with: "In Autonomous Autofill, open the options page, click **Import profile.json** and choose `<folder>/profile.json` so the button uses the new answers." When the user changed answers in the extension itself, have them press **Download profile.json** and place the file in the job-search folder.
