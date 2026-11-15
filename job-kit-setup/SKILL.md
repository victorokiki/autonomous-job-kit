---
name: job-kit-setup
description: "First-time setup for the job and internship kit: find my existing CVs, build one master resume, create profile.json, capture my CV style in a style guide, set up my job search (country, region, roles, employers, immigration route), choose how much Claude automates (lean, assisted or full) and explain what it costs. Use when I say set me up, get started, onboard me, what can this do, or when the job-search folder has no profile.json or master resume yet."
---

# Autonomous Job Kit setup

Interview a new user and leave them with a working job-search folder: one master resume, `profile.json`,
`style-guide/style-guide.md` and `search.json`. Then hand over to the `internship-application` and
`internship-tracker` skills.

When the user asks what the kit can do, what it costs or how to customize it, answer in plain words from
`../CAPABILITIES.md` (beside the skill folders; if it's missing, use the summary in step 1 below).

## Ground rules

- **Privacy first.** Everything personal lives in the user's job-search folder, which must be **outside** the kit's
  repository folder (never inside a git clone). If they pick a folder inside it, say why that's risky and suggest a
  sibling folder instead. Never upload, publish or commit their CVs, profile, tracker or digests.
- **Never invent anything.** No metrics, dates, titles, tools, employers or degrees that aren't in the user's own
  documents or words. A missing number stays missing and goes on a "To confirm" list.
- **Contradictions are flagged, never merged.** When two CVs disagree (dates, titles, employers, numbers, degree names),
  don't pick one silently and don't blend them: list each one and ask.
- **Never delete** the user's files. To replace a file you wrote, move the old one into `_old/` with the date and time.
- **Immigration and eligibility are the user's to state.** Record what they say about work authorization; never work
  out their status, permit conditions or eligibility yourself. This kit gives no immigration advice.
- Ask questions in **one batched message per step**, mark optional ones, and offer sensible defaults.

## Templates

Use the files in `templates/` beside this SKILL.md, or `../templates/` in the repository:
`profile.example.json`, `search.example.json`, `style-guide.example.md`, `master-resume.tex`. They are a fictional
person: copy their **structure**, never their content. The blank profile is
`../internship-application/references/profile-template.json`; field meanings are in
`../internship-application/references/profile.md` (read it before writing profile.json).

## Steps

### 1. Welcome and explain (short)

In five or six lines: what the kit does. The everyday use is just pasting a job link: Claude reads the posting in
Chrome, drafts the tailored CV and cover letter, fills the application and stops before Submit (Claude in Chrome must
be installed for that). It also finds and ranks jobs, tailors a resume and cover letter per posting from one
master, fills application forms in Chrome and stops before Submit, tracks everything, asks for status updates and builds a dashboard. Then say that the
user reviews and submits every application themselves unless they explicitly say "submit", and roughly what it costs
(step 7). Ask whether to continue.

### 2. The job-search folder

Ask where it should live (suggest `~/Documents/job-search`), or use the folder Cowork/Claude Code was opened in if it
isn't inside the kit's repository. Create:

```
job-search/
  resume/          the master resume (made in step 3)
  style-guide/     style-guide.md, plus any old CVs and letters the user wants as style examples
  source/          the user's original CVs, copied as-is (never edited)
```

The kit later adds `profile.json`, `search.json`, `jobs.txt`, `Applications/`, `tracker.xlsx`, `digests/`, `.cache/`
and `dashboard.html`.

### 3. Find the CVs and build one master

1. Ask where their CVs are. If they don't know, offer to look (with their OK) in Desktop, Documents and Downloads for
   files named like resume/CV/curriculum (`.pdf`, `.docx`, `.tex`, `.doc`, Overleaf zips). List what you find with the
   modified date and page count; let them choose. Copy the chosen ones into `source/`.
2. Read them all (pdftotext or the pdf/docx skills). Pick as the **base** the most recent CV that is internally
   consistent and most complete. Tell the user which one and why in one line.
3. Add facts from the other CVs only when they don't conflict with the base (an extra project, an older job, a
   certification). Every fact must exist in at least one of the user's documents.
4. **Contradictions:** write `resume/master-notes.md` with a "Contradictions to resolve" list, each as
   `<fact>: "<version A>" (<file>) vs "<version B>" (<file>)`, plus "To confirm" (bullets with no number that could
   have one). Ask the user to resolve them in one message; apply only their answers. Until resolved, the master keeps
   the base CV's version and the note stays open.
5. Write the master:
   - If they already work in **Overleaf**, keep their project: put the unzipped source in `resume/` and only fix facts.
     Tell them about the Carlito `lining` fix (README troubleshooting) if their template uses Carlito.
   - If they have a **Word** CV they like, keep the `.docx` in `resume/`.
   - Otherwise build `resume/master.tex` from `templates/master-resume.tex` (single column, Carlito with lining
     digits). The master may run past the page limit: it holds every fact; tailored copies are cut down.
6. Build and check it (needs Tectonic; otherwise ask them to compile in Overleaf):
   ```
   python ../internship-application/scripts/build_resume.py "<folder>/resume/master.tex" --out "<scratch>/master.pdf" --max-pages 0
   pdftotext "<scratch>/master.pdf" - | head -40
   ```
   Check that every digit and the name are in the text layer, then show the user the PDF.

### 4. profile.json

Copy `profile-template.json` to `<folder>/profile.json`, fill what the master says exactly as written, and ask in one
message only what the CV can't answer (profile.md "What to ask"), plus:

- Country they're applying in (`authCountry`) and, in their own words, their work authorization (`workAuthDetails`:
  e.g. "Canadian citizen", "Permanent resident", "Open work permit until 2027-05-01", "Study permit, eligible for
  PGWP"). `permitExpiry` only if they want it recorded. Never guess.
- Name as written on resumes (`resumeName`) if it differs from the legal first and last name; `legalName` for
  signatures.
- Page limit for regular jobs (`resumeMaxPages`, default 1; internships always 1), XYZ bullets (`bulletFormula: "xyz"`),
  cover letters always or only when required (`coverLetterPolicy`), letter layout (`letterStyle`), merged
  letter+resume PDF (`alwaysCombine`, `combinedOrder`).
- Self-identification is optional; every field may stay empty or "decline". Never infer it.
- The common screening questions, asked once in two or three short rounds (multiple choice where possible) and saved so
  they never need re-answering. Use the checklist in profile.md, "Common screening questions".

Tell them `savedAnswers` grows as they apply: when they answer a new repeat question, Claude saves it.

### 5. style-guide/style-guide.md

Infer from their CVs (and any letters), then confirm with the user. Follow `templates/style-guide.example.md`'s
headings:

- **Layout**: columns, font, margins, header format, date format, spelling (Canadian, US, UK).
- **Section order** exactly as they like it.
- **Title rules**: job titles exactly as held, never upgraded to match a posting; how the headline may name the target role.
- **Banned words**: start from the example list; ask what they hate.
- **Bullets**: XYZ or not; verb tense; line length; never invented metrics.
- **Page limit**: regular jobs vs internships and co-ops.
- **Cover letter**: when, length, paragraphs, sign-off.

Show the draft, apply their edits, save it.

### 6. search.json

Ask in one message, then write `<folder>/search.json` from the matching template: `templates/search.example.json`
(Canada), `search.uk.example.json` (UK) or `search.us.example.json` (US):

- Country: **Canada, United States or United Kingdom**; their province (`province`, e.g. "ON"), state (`state`,
  e.g. "TX") or region (`region`, e.g. "london"); home city and nearby places (`local_places`). Job Bank is used
  only for Canada.
- **Their situation and goal**, in their own words: a student, a new graduate, changing careers, already allowed to
  work there, or on a visa and aiming for permanent residence. If they have an immigration goal, ask which route
  they're on (they choose it; you don't) and set `pathway` (read `../internship-application/references/pathways.md`):
  for example `ca-cec` (Express Entry, Canadian Experience Class: TEER 0-3 work), `ca-pnp`, `uk-skilled-worker`
  (licensed sponsor, eligible occupation, salary thresholds, then ILR), `uk-graduate`, `us-opt`, `us-h1b`. Ask
  whether they need sponsorship, want only permanent full-time roles, and the minimum salary their route needs as
  they found it on the official site (`minSalary`; leave it 0 if they don't know). Say once, plainly: "I'll flag
  jobs that may not fit your route, but I can't give immigration advice. Confirm anything that matters on the
  official site or with a licensed adviser."
- Target roles as **tracks** (2–5), each with title words and a priority from 1.0 down. Words to exclude (senior,
  manager, languages they don't speak).
- Job Bank searches (`jobbank_queries`, 3–8 short job titles), Remotive categories if they want remote work.
- Skills the ranking vocabulary may not know (`extra_skills`).
- Employers to follow: for each company they name, find its careers board and run
  ```
  python ../internship-application/scripts/find_jobs.py --folder "<folder>" --add-employer "<link to the board or a posting>"
  ```
  (works for Greenhouse, Lever, Ashby, SmartRecruiters, Workday; other sites go through Job Bank or the browser).
  Then `--check-sources` once and fix any board that fails.

Run one search without `--append` and show the top 10 with their fit scores and reasons, so they see it works. Ask
before queueing anything in `jobs.txt`.

Tell them how updates work: at the start of each job-search conversation Claude asks about applications with no
news for a week (submitted, assessment, interview stage, offer, accepted, rejected), and `dashboard.html` shows the
same list with buttons that copy an update to paste back.

### 7. Choose how much Claude does (cost vs effort)

Explain that the biggest cost is Claude driving the browser, then offer the three levels from
`../internship-application/references/automation-levels.md` in one message, each with what it costs, what the user
still does, and the risks. Keep it to this shape:

> **1. Lean: Claude Code + the Autonomous Job Kit Autofill extension (lowest cost).** I read the posting, tailor your CV and cover
> letter, and write the answers to paste. You open the form, click the extension's Fill button, attach the files and
> submit. *Good:* uses the least of your plan; you control every field; I never act in your browser. *Watch out:* you
> do 5–10 minutes of form work per job.
>
> **2. Assisted: I fill one form at a time (medium cost).** The extension fills the standard fields, I fill the rest
> in Chrome and stop before Submit. *Good:* hands-off, and you still review. *Watch out:* more usage per job; I work in
> your signed-in Chrome, so close private tabs; unusual questions can be misread.
>
> **3. Full automation (highest cost).** Batches of jobs, forms filled in parallel, and "fill all" or "submit" when
> you ask. *Good:* fastest for volume. *Watch out:* can use a large share of a Pro plan's limit in one or two batches
> (Max suits it better); a mistake can repeat across several applications; more automated activity on job sites.

Recommend from their answers, briefly: **lean** for a Pro plan or anyone who wants full control, **assisted** for most
people who want the forms done, **full** for a Max plan and a high volume. Save the choice as profile.json
`automationLevel` and tell them they can switch any time ("switch me to lean mode"). For lean or assisted, help them
install the Autonomous Job Kit Autofill extension and load it unpacked (extension/README.md) and import profile.json on its profile page; for assisted or full,
check Claude in Chrome is installed.

Then the general cost tips, plainly:

- The kit is free (MIT). It needs a **paid Claude plan** (Pro or higher). Searching, ranking, building PDFs and the
  tracker run locally as Python scripts and use almost no Claude usage; reading postings, tailoring and especially
  browser work do.
- **Claude Code** with the extension is the cheapest way to run it; the Claude app's **Cowork** costs the most and
  suits full automation.
- Work in **batches of about 6 applications**, and start a **new conversation for each batch**: long conversations
  re-read everything and burn through usage limits.
- Use the strongest model for tailoring and letters; a **cheaper, faster model** (for example Sonnet or Haiku) is
  usually fine for form-filling and the daily digest. Lower effort for routine runs.

### 8. Wrap up

List what now exists in their folder and what's still open (contradictions, "To confirm" items). Then give the next
requests they can type:

- "Find jobs that fit me" / "What's new today?" (daily digest)
- Paste a job link (at their automation level)
- "Apply to 6 jobs" (lean: CVs, letters and answers ready to paste; assisted/full: forms filled, stopped before Submit)
- "Show my dashboard"
- "What can this kit do?"

Remind them once: Claude never submits without their explicit "submit", never types passwords or solves CAPTCHAs, and
leaves consent boxes to them unless they ask for "fill all".
