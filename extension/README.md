# Autonomous Autofill

A Chrome / Edge extension (Manifest V3) that fills job application forms from your
Autonomous `profile.json`. It never submits a form, never clicks Next, and never changes
a field that already has an answer.

## Install (Load unpacked)

1. Open `chrome://extensions` (Edge: `edge://extensions`).
2. Turn on **Developer mode** (top right).
3. Click **Load unpacked** and choose this `extension` folder.
4. The profile page opens. Click **Import profile.json** and pick the `profile.json` from your
   job-search folder. Optionally add your resume PDF (up to 5 MB).

A Chrome Web Store listing may come later; until then, Load unpacked is the way to install.
After updating the files, press the reload icon on the extension's card in `chrome://extensions`.

## Using it

- **Page button**: on supported application sites a small **Fill with Autonomous** button appears
  on the right edge when the page has a form. Only a real click starts a fill.
- **Toolbar menu**: *Fill this page* (works on any site, injected on demand) and *Edit profile*.
- **Shortcut**: `Alt+Shift+F` fills the current page (change it at `chrome://extensions/shortcuts`).

After a fill, a panel lists what was **filled**, **already filled** and **left for you**. Filled
fields get a solid green outline; empty fields left for you get a dashed amber outline. Multi-page
forms (Workday and others): fill each page, check it, then click Next yourself.

### What Claude reads

The extension also writes a visually hidden text block at the top of the form, for Claude in
Chrome (`get_page_text`):

```
Autonomous report: filled 14, already filled 2, left 3. Left: Why do you want to work here? (textarea,
required, open question); Cover letter (file); ... Filled: First Name; ... Nothing was submitted.
Review every answer before continuing. Profile: imported 2026-11-14, 2 saved answers.
```

While a fill is running it reads `Autonomous report: busy filling this page. Check back in about 5 seconds.` The final `Profile:` part says when the profile was last imported or saved
here, so an out-of-date profile is easy to spot.

## What it fills and what it never touches

Fills: name parts, preferred and legal name, email, phone (split when the form has a separate
country-code field), address, location, links, school, degree, field, GPA, education and work
dates, graduation date, class standing, term, availability and start dates, current employer and
title, years of experience, work authorization (only for the country in your profile), the two
sponsorship answers, relocation, government ties, salary, voluntary self-identification (only
answers you set; "Not set" leaves the question), saved answers (phrase match, also for text boxes),
and your stored resume PDF in Resume/CV upload fields when you fill from the popup or Alt+Shift+F. The
page button leaves the resume upload empty, because Claude attaches the resume it tailored for that job.

Never: submit or click Next/Submit; tick consent, terms, certification or "I agree" boxes; fill
open-ended text boxes (unless a saved answer matches); fill SSN/SIN/national ID, date of birth,
bank or card details, passport numbers, religion, marital status or criminal-record questions;
answer a question about someone else (emergency contact, references); guess when unsure. A
question like "Do you require sponsorship?" that does not say *now/future* or *this internship*
is filled only when both sponsorship answers agree.

## Files

| Path | Purpose |
| --- | --- |
| `manifest.json` | MV3 manifest: permissions `storage`, `activeTab`, `scripting`; host access only for the listed application systems |
| `background.js` | Service worker: shortcut, popup fill request, on-demand injection, badge |
| `content/text.js` | Text normalising, provinces/states/countries, phone and date parsing, option matching |
| `content/rules.js` | The matching rules table (one row per field) and the never-fill lists |
| `content/labels.js` | Finds controls (including open shadow roots) and the question each one asks |
| `content/setters.js` | React/Angular-safe value setting, selects, radios, checkboxes, custom dropdowns, file upload |
| `content/ui.js` | Page button, result panel, hidden report block, outlines |
| `content/engine.js` | One fill run |
| `content/main.js` | Content-script entry point |
| `shared/profile-schema.js` | Profile fields for the editor and the lossless profile.json round trip |
| `options/` | Profile editor |
| `popup/` | Toolbar menu |

Supported sites (content script and button): greenhouse.io, lever.co, ashbyhq.com,
myworkdayjobs.com, myworkday.com, myworkdaysite.com, smartrecruiters.com, workable.com, icims.com,
jobvite.com, bamboohr.com, oraclecloud.com (`/hcmUI/` recruiting pages), rippling.com, breezy.hr,
recruitee.com, teamtailor.com, jobbank.gc.ca. Elsewhere use the toolbar menu or the shortcut.

## Developing and testing

```
node tests/extension/check.js          # manifest, syntax, round trip, rules, fixtures in headless Chrome
python3 tests/extension/make_icons.py  # regenerate the icons
```

`tests/extension/fixture-*.html` are sample forms (Greenhouse-, Lever-, Workday-like and generic)
that load the real content scripts with a stub `chrome` object and a made-up profile; open one in
Chrome (served over `http://localhost` or with file access) to watch a fill and see the checks.

See [PRIVACY.md](PRIVACY.md) for what is stored and where.
