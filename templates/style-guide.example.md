# Style guide: Alex's CV brief (FICTIONAL example)

Copy this to `<your job-search folder>/style-guide/style-guide.md` and make it yours, or let the `job-kit-setup`
skill write it from your existing CVs. Claude reads it before every tailoring and cover letter. It controls **how**
things look and sound. **Facts only ever come from your master resume**, never from this file or old PDFs.

## Who the user is

- Target roles: data analyst, business analyst, reporting and operations analyst. Second choice: operations coordinator.
- Level: early career, about two years of full-time experience. Not a student.
- Location: Halifax, NS. Open to hybrid or remote in Canada.

## Format

- ATS-friendly: single column, plain headings, no tables, icons, photos or text boxes.
- **Page limit: up to 2 pages for regular jobs, 1 page for internships and co-ops** (profile.json `resumeMaxPages: 2`).
  Fill the last page.
- **Section order:** Header, Professional Summary, Core Skills, Experience, Selected Projects, Education, Certifications.
- Header: name centred in capitals (profile.json `resumeName`), a headline of three focus areas in the posting's words
  separated by " | ", then City, Province | phone | email | LinkedIn.
- Font: Carlito, loaded as `\usepackage[sfdefault,lining]{carlito}` (without `lining`, digits can vanish from the PDF
  text that tracking systems read). Capitalised section headings with a rule.
- Entries: bold title line, then an italic line "Employer | City | Type | Mon YYYY – Mon YYYY". Most relevant role first.
- Dates as "Mon YYYY – Mon YYYY"; current role ends "Present".
- Spelling: Canadian (modelling, organization, behaviour, centre, licence).
- Certifications as a bullet list, one per bullet.

## Job titles

- Use each job title exactly as it was held. Never upgrade a title to match a posting ("Operations Assistant" stays
  "Operations Assistant", never "Operations Analyst").
- The headline and summary may name the target role ("Data analyst with ...") when it is true.

## Summary

- 3–4 lines. Lead with the target role, then the two or three strongest proof points with real numbers from the master.
- No filler or self-praise.

## Bullets

- Google's XYZ formula: "Accomplished [X], as measured by [Y], by doing [Z]." Result first (profile.json `bulletFormula: xyz`).
- Only facts and numbers in the master. **Never invent, estimate or round up a metric**, tool, title or date. If a number
  is missing, state the real outcome and method and list what to confirm in changes.md ("To confirm").
- Strong past-tense verb first; 1–2 lines each. Two versions of each bullet in changes.md (result-first and shorter).

## Banned words and phrases

passionate, team player, hard-working, quick learner, results-driven, synergy, go-getter, "responsible for", "helped with",
"various", "etc."

## Tailoring

- Mirror the posting's exact keywords and job title where they are true for the user.
- changes.md ends with: keywords used, keywords missing, and the likely NOC 2021 code and TEER for the role, marked
  "likely; confirm on the NOC site" (Canada only; this is not immigration advice).

## Cover letter (only when the posting requires one or the user asks)

- One page, three short paragraphs: why this role; the two strongest matching proofs; a plain close. At most 250 words
  (profile.json `letterMaxWords`).
- Layout: profile.json `letterStyle: carlito`. Pass `--location` and `--subject "<Role> (Job ID <id>)"` to cover_letter.py.
- Sign off "Sincerely," and the name exactly as on the resume.

## Check before saving

Typos, tense, date gaps, inconsistent date and title formats, anything not traceable to the master. In changes.md, say
what you changed and what you couldn't confirm.
