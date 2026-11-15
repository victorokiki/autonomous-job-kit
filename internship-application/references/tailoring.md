# Tailoring the resume (and the cover letter)

Goal: a page that convinces both a recruiter skimming for ten seconds and keyword-matching software (ATS) that the user has done what this role needs. You select, reorder and reword. You never add facts, and every line must be something the user could talk about in an interview.

Source of truth: the master resume only. Never open resumes, `resume-src/`, letters or changes.md from other job folders.

## Fixed: what tailoring may never change

- Job, club and research titles; organization names; dates; locations.
- Any number (GPA, users, percentages, team size, hours): no rounding up, no adding together.
- Academic details: institution, degree, program, minor, course titles, graduation date.
- The contact block, except its location: use the posting's `Your location line:` (see below).
- How big the user's role was. "Assisted with" can't turn into "led", "helped build" can't turn into "built", and coursework can't pose as a shipped product.

Anything the role asks for that the user doesn't have is recorded as a gap in changes.md and stays off the resume.

**Location line.** job-posting.md (fetched with `--profile`) has a `Your location line:` such as
`Surrey, BC · Relocating to Toronto, ON (job is in Toronto, ON)`. Put the part before the brackets where the master's
contact block shows the city, replacing only the city and province: the street, if any, is dropped for that version.
It names the job's city only when the job is on-site or hybrid outside the user's commute area and `willingToRelocate`
is `"yes"`; remote and local jobs keep the plain city. Never write the job's city as where the user lives: forms,
background checks and interviews use the real one. `relocationWording` in profile.json changes the wording
(e.g. `"Open to relocating to {city}"`). Note the change under "What changed" in changes.md.

**Honesty test:** picture the user's supervisor, instructor or teammate reading the line. Would they nod? Borrowing the posting's vocabulary for work the master documents is fine ("REST API" for endpoints the user wrote in Flask). A tool, number or responsibility absent from the master is not.

| In the master | The posting wants | Acceptable | Too far |
|---|---|---|---|
| Made a weather dashboard in Vue for a course | Front-end work | Built a weather dashboard in Vue (course project) | Shipped production Vue applications |
| Tidied lab sensor readings with pandas | Data analysis | Cleaned and summarized lab sensor data in Python (pandas) | Ran predictive models on sensor data |
| Team of 5 built a chess engine; user wrote the move generator | Algorithms | Wrote the move generator for a 5-person chess engine project | Built a chess engine |
| Library desk assistant, onboarded 4 new staff | Communication | Onboarded 4 new desk staff and answered 100+ patron questions a day | Supervised library staff |
| Took Linear Algebra | Math background | Linear Algebra, in the coursework line | Applied linear algebra professionally |

Swapping in synonyms is allowed; inflating rank, ownership, tooling or outcomes is not.

## Three passes

1. **Angle.** Jot down for yourself 3-5 criteria the hiring team will use, quoting the posting's wording (e.g. "Python services, PostgreSQL, automated tests, working with designers").
2. **Select and order.** Pick the entries that prove those things best and put the strongest first (section rules below).
3. **Rewrite every bullet you keep** for that angle.

When the check reports that most bullets (over ~50%) match the master word for word, do pass 3 again, unless the posting already uses the master's wording (say so in changes.md).

## Rewriting bullets

For each bullet you keep:

- Give it a job: which of the angle's items it proves.
- Open with the action and the posting's term for the skill, if that's true to what the user did ("Wrote Express routes" for a backend role; "Built the map view in React" for a frontend one).
- Bring forward the facts that matter here. Two bullets from the same entry may merge, or one may split, as long as every fact is in the master.
- Close with the master's outcome (users, numbers, speed) when there is one.
- Keep a bullet verbatim only when it already opens with what this posting wants.

Shape: action and skill first, result last. Before: "Was in charge of storing the ride data for our team app". After: "Designed the PostgreSQL schema storing 40,000 ride records". The 40,000 must come from the master.

**One project, four angles.** Master bullets (fictional): "Built a campus bike-share tracker in React and Node used by 450 riders"; "Wrote SQL to import 18 months of dock data into PostgreSQL"; "Added 60 Jest tests and a GitHub Actions workflow on every pull request"; "Designed the live map view and made it mobile-friendly".

| Role | Rewrite |
|---|---|
| Backend | Built the Node and PostgreSQL back end of a bike-share tracker for 450 riders, importing 18 months of dock data with SQL |
| Frontend | Designed the live React map view of a bike-share tracker used by 450 riders and made it mobile-friendly |
| QA / DevOps | Added a GitHub Actions workflow that runs 60 Jest tests per pull request on a 450-rider React/Node tracker |
| Data | Imported 18 months of bike-share dock data into PostgreSQL with SQL, the data behind a tracker used by 450 riders |

Claiming the back end requires the master to show the user did it: automatic for solo work; on a team, confirm their piece first. Each role's version should sound distinct.

### XYZ bullets (`bulletFormula: "xyz"`)

A permanent preference set by the user, taking precedence over the action-first guidance above. Template: did [X], measured by [Y], through [Z].

- Result first, then the measurable proof, then the method: "Lowered failed nightly imports by about 25% by adding schema checks to 300,000+ records."
- Only the master's numbers, unchanged ("about 25%" stays "about 25%"). Never estimate or round.
- No number in the master? Keep the real outcome and method without a figure, and put questions the user could answer under "To confirm" ("How many records a night? How much time saved?").
- First word: a vivid past-tense verb (Automated, Cut, Shipped, Reconciled, Built, Led), current role included. Ban "Helped" and "Responsible for".
- Length 1-2 lines; Canadian spelling (modelling, centre, behaviour, organize); no filler.
- Mirror the posting's keywords where true (honesty test applies).
- Write a result-first version and a shorter one. The resume gets whichever fits; changes.md gets both under "Bullet versions".
- Reread the set and flag bullets that are vague, duplicate another, or might strike a recruiter as implausible. Repair those you can and record the others in changes.md ("Flags").

## Page and order

- Length: a single, full page if the master has the material. `resumeMaxPages` lets regular jobs run to that many pages (the final one full); internships, co-ops and student positions are capped at one regardless. Below, "the page" means whatever the limit is. Margins and type size follow the master except when squeezing.
- `style-guide/style-guide.md`, when present, decides layout and section order over the list below; facts still come from the master only.
- Default order: Education first while the user is a student; then Experience or Projects, whichever proves more for this role (section headings as the master names them); then leadership/activities; Skills at the bottom. Drop a section only if none of it is relevant and space is short.

## Section rules

**Education.** Copy institution, degree, program, minor and expected graduation verbatim from the master. GPA: keep it if the master has it, never rounded (3.67 stays 3.67) or rescaled; if the posting requires a GPA that the master omits but the profile has, add it in the master's style. Coursework: four to six best-matching courses taken or in progress, most relevant first, using the master's names. In bullets under a school, don't spell out an institution's full name containing "University", "College", "Institute" or "School" (write "Representing Eastport at the 2026 ICPC regional"); honours otherwise keep their exact wording.

**Projects.** Two to four, the best matches. Headings list tools in posting-first order, naming only tools that project really used. The leading one or two projects get 3-4 bullets and others at least 2 (a single bullet only if the page is genuinely out of room); the opening bullet carries the clearest match. For team or course work, describe what the user personally built ("Implemented the scheduling algorithm for a 3-person class project") and never credit them with the group's outcome. Marking it as coursework is fine.

**Experience.** For internships, research and technical roles, sort bullets by how well they match and use the posting's terms where accurate. Research positions (RA, lab member, student researcher) appear on every version; if their work also appears under Projects, give the role one or two bullets on what the projects don't say (lab or program, duration, papers, posters, talks, awards) so no fact repeats. Side jobs such as cashier, server, tutor or help-desk shifts keep 1-2 bullets on transferable skills the posting values (communication, deadlines, training people, handling cash). A student without much else should keep them.

**Skills.** Lead with the languages and tools this posting names, keeping the master's groupings. No rating bars. Cut irrelevant ones if space is short. Never add a skill the master lacks, not even "familiar with" or "learning", unless the master says so.

**Awards and honours: lowest priority.** They never move up, never take room that relevant work could fill, and they are the first cut when over length. An award won through real work (hackathon, competition) belongs in that project's bullet ("placed 2nd at HackEastport") rather than its own line. If space remains once all relevant content is in, one Awards line may sit at the very end. A Dean's List-type note inside Education survives only when it fits on its existing line.

## When it runs long

**Large master (over about two pages): build up rather than cut down.** Seed the copy with just: header; education plus courses; the 2-4 strongest-matching projects and roles, each with its best bullets; research roles; one or two activities if they fit; skills. No awards yet. Build, then fill or trim.

**On `lines_over`,** cut roughly that number of lines in a single sweep, working down this list, and rebuild:

1. Awards, scholarships, honours, Dean's List (one may stay, placed last).
2. Any project, bullet or activity irrelevant to the posting.
3. Bullets beyond the second on weaker entries.
4. Dated or unrelated part-time and research roles, reduced to a single bullet (keep the entry).
5. All but the one or two best activities.
6. Coursework trimmed to four courses.
7. Two-line bullets compressed to one, with all facts and figures intact.

Untouchable: the header with contact details, the education entry (institution, degree, program, graduation, GPA when shown) and the single best match.

**Squeezing instead of cutting.** When the overflow is about six lines or less and the next item on the cut list is highly relevant (for instance a project built on the exact stack requested), free space another way. Rebuild after every step and stop once the page fits:

1. Tighten words: drop filler ("various", "in order to", "responsible for"); pull up a second line holding only a word or two. Keep every fact.
2. Trim spacing: a point or two off existing `\vspace`, `itemsep`, `topsep` and heading spacing. Change numbers only, inside commands already there.
3. Narrow margins, never under 0.4 inch.
4. Type size, as a last resort: the smallest reduction that works, never under 9pt (exactly 9pt is allowed). Read `smallest_text_pt` from the build rather than trusting the document class (an `11pt` class with `\small` bullets is already 10pt). The standard `article` class has no 9pt option; change the copy's class to `extarticle`, options unchanged.

If it still doesn't fit, or the page looks cramped, undo the squeeze and make the next cut. Note any squeeze in changes.md ("tightened spacing to keep the bike-share project").

## When it runs short (filling the page)

Finished once the text ends within roughly a line of the bottom margin, or the master has nothing more that suits this role. With `free_lines` of 2 or more, add about that many lines (two-line bullets count as two), drawing from this list in order, then rebuild:

1. Extra bullets on entries already present, best first, until the lead projects and main internship have 3-4 and everything else has 2 or more.
2. Split apart bullets that were merged just for space.
3. The strongest omitted project or role.
4. Real keywords: additional courses, or skills listed by the ATS check under `in_master_not_resume`.
5. Another activity, only if it demonstrates a quality the role mentions (leadership, collaboration, communication).
6. A single award line at the end.

Each addition goes through the rewrite pass. Spilling onto a second page means undoing the latest addition or shortening something. No filler, no repeated facts, no inflated spacing. Stopping with two or more empty lines requires a reason on the Page line of changes.md.

## Staying ATS-readable

- One column only. Never introduce tables, multi-column blocks, text boxes, graphics, icons, or page headers/footers that hold important details; right-aligned dates from the template are acceptable.
- Conventional headings such as Skills, Projects, Experience, Education.
- Name followed by contact info as ordinary text, URLs written in full (github.com/...).
- Dates in the master's format, consistent throughout.
- No hidden keywords in white or tiny text.

`ats_check.py` (run inside check_tailored) reports posting keywords present, ones in the master but missing here (restore where they fit), and ones the user lacks (gaps: never add, not even to Skills). Use the posting's exact term where the user truly has the skill ("data visualization", "SQL"). It also flags an unreadable name, ligatures (a fused "ffi" won't match "efficient"), glued words, two-column layout and unembedded fonts: resolve them before saving. When the page really is a single column, a two-column warning is spurious: mention it in changes.md and leave the page alone. Removing content only to silence a layout warning is never acceptable. A master built on a two-column or icon-laden template keeps that design; just let the user know once that single-column layouts are read more dependably.

## changes.md

The check saves a draft next to the PDF with the title, Page line and Reworded pairs filled in. Use Edit to replace each `<...>` slot (angle, what changed, requirements covered, ATS keywords, gaps) and leave the rest. Draw keywords from the check's `keywords` output, limited to skills and technical vocabulary (no perks, locations or application-form words).

```
# Tailoring notes: <Role> at <Company>

## Angle
<three to five things this posting judges, in its wording>

## What changed
- Coursework: <courses first> (for <requirement>).
- Projects: <moved up / dropped for space>.
- Experience: <kept>; <trimmed or dropped>, because <reason>.
- Skills: <tools first>.
- Page: filled. (Or: <N> lines free because <reason>.)

## Reworded
- <original> → <new>
- <original A> + <original B> → <combined>

## Requirements covered
- <requirement>: <section or bullet that shows it>

## ATS keywords
- Covered: <terms on the page>
- Gaps: <terms the user lacks>

## Gaps
- <requirement>: not on the resume. Ways to address it: <letter line, interview story, short course or project>.
```

Also add one line with the posting's class-year or graduation range and any sponsorship note (SKILL.md step 2), and a "Pathway check" when pathways.md applies.

With `bulletFormula: xyz`, add after "Reworded" (the draft lacks these):

```
## Bullet versions
- Result-first: <bullet>
  Shorter: <one-line version>

## To confirm
- <short form of bullet>: <what to ask the user to get a true figure>

## Flags
- <bullet, shortened>: <vague | duplicates "<other>" | may sound implausible because ...> (or "none")
```

With `style-guide/style-guide.md`, end with:

```
## Keywords
- Used: <posting terms and the job title, where accurate>
- Missing: <posting terms absent from the master>

## Likely NOC and TEER
- <code and title, NOC 2021>, TEER <n>: likely only, the user should verify it on the official NOC site. Reason: <one line>

## Checks before saving
- Corrected: <typos, tense, date/title formatting>
- Unverified: <items not traceable to the master, or "none">
```

Aim for a short file.

## Cover letter

**When to write one.** By the posting's `Cover letter:` line: `required`, `optional`, `asked` or `unknown` → write; `none` or `not wanted` → don't. Postings read in the browser get one too, except Workday postings that don't ask for one. With profile.json `coverLetterPolicy: required-or-asked`, a letter is written only for `required` or `asked` or on the user's request; `optional`/`unknown` get none, and optional letter fields remain blank. A style guide that describes letters (length, paragraphs) takes precedence on form.

**Content.**

- Plain text from the greeting ("Dear Harbourline hiring team,") to the sign-off ("Sincerely," then the user's name on its own line), blank lines between paragraphs. No header: the build adds name, contact line, date and company.
- Under the word limit (`letterMaxWords`, default 250).
- 3-4 brief paragraphs: which role and what draws the user to this team (echoing the posting); a proof point or two drawn from the master, with the user's personal contribution and its real figures; what they want to learn; when they're free (`availableFrom`-`availableUntil`).
- When the location line says the user is relocating, one sentence in the first or last paragraph says so, e.g. "I am relocating to Toronto and can start in person from <availableFrom>"; add "at my own cost" only when the saved answer for relocation assistance is No. cover_letter.py puts the same line in the letter's contact line.
- Do whatever the posting asks of the letter (the quote on the `Cover letter:` line), e.g. name the role or answer its questions.
- Same factual limits as the resume: master and profile only. Skills the posting wants but the master lacks are not mentioned as the user's.
- Voice from `writingStyle`; every `extraRules` line applies.

**Build and check.** Save the text via the Write tool to `<scratch>/cover-letter.txt` and run:

```
python scripts/cover_letter.py "<scratch>/cover-letter.txt" --profile "<folder>/profile.json" --master "<master>" --company "<Company>" --role "<Role>" --posting "<job folder>/job-posting.md" --out "<scratch>/Firstname_Lastname_Cover_Letter_Company.pdf" [--combine "<scratch>/Firstname_Lastname_Resume_Company.pdf"]
```

- Resolve every `fix` item; handle each `review` item (a posting term may describe the employer's work, never the user's skill). Rerun until `fix` is empty.
- `--combine` plus the verified resume PDF also produces the merged `*_Resume_and_Cover_Letter_*.pdf` for forms with one upload slot. Use it for `asked` letters, and for every letter when `alwaysCombine` is true. Order is resume first unless `combinedOrder` is `letter-first`.
- `letterStyle: carlito` switches to the Carlito single-column layout with a bold "Re:" line (`--subject` overrides the role; `--location` fills the address block).
- Exit 3 (no LaTeX): build an identical `.docx` letter using the docx skill.
- Copy the PDF, any merged PDF and `cover-letter.txt` to the job folder (the script moves an older letter to `_old/`; move any older copies there yourself when copying by hand).
