# Automation levels: how much Claude does, and what it costs

profile.json `automationLevel` decides how much of each application Claude does itself. It's the user's choice,
made in setup (job-kit-setup step 7) and changeable any time ("switch me to lean mode"). It's separate from the
Review / Fill all / Submit modes in SKILL.md, which only matter when Claude fills forms.

The biggest cost in this kit is **driving the browser**: every page Claude reads or fills in Chrome uses a lot of
usage, and batches that fill several forms at once multiply it. Reading postings, tailoring and the local Python
scripts (search, ranking, PDFs, tracker) use far less.

## The three levels

### `lean`: Claude Code + the Autonomous Job Kit Autofill extension (lowest cost)

Claude prepares everything; the user fills and submits the form themselves with the extension's help.

- **Posting:** `fetch_posting.py` reads it without a browser. If it can't, ask the user to paste the job description.
  Don't open Chrome.
- **Tailoring:** as usual: tailored resume, cover letter when wanted, written answers, changes.md.
- **Instead of filling:** write `answers-to-paste.md` in the job folder (format below), copy the PDFs into the
  space-free uploads folder (filling.md, "Paths with spaces"), log the tracker row as `Ready to submit` with next step
  "Apply yourself: open the link, click Fill with Autonomous, attach the files, paste the answers", and report the link
  and the steps.
- The user tells Claude "I submitted Northwind" afterwards (tracker skill), or the next check-in asks.
- **Never** drive the browser in this level unless the user asks for that one application ("fill this one for me");
  then fill it as in `assisted`, for that application only, and go back to lean.
- Fill all and Submit modes don't apply: the user always fills and submits. Say so once if they ask for them.

Advantages: the lowest usage by far, so a Pro plan goes much further; the user sees and controls every field; Claude
never acts in the user's signed-in browser; works without Claude in Chrome.
Risks and limits: the user does the form (often 5–10 minutes each); the extension fills only predictable fields
(name, contact, school, links, yes/no and self-ID answers they saved), so they attach files and paste the rest;
applications they forget to report stay `Ready to submit` until the next check-in.

`answers-to-paste.md`:

```
# <Company>, <Role>: answers to paste
Link: <application URL>
Files: <uploads folder path>/<Resume PDF>, <Cover letter PDF or "none">

## Before you start
1. Open the link, sign in if asked, then click **Fill with Autonomous** (extension) on each page.
2. Attach the files above (resume, and the letter if there's a field for it).
3. Paste the answers below where the extension left blanks. Leave anything marked "yours" for you to decide.

## Answers
- <question as the form or posting words it>: <answer from profile.json / savedAnswers>
- <written question>: <drafted answer>
- <question the profile doesn't answer>: yours

## After you submit
Tell Claude: "I submitted <Company>".
```

### `assisted`: Claude fills one form at a time (medium cost)

- Claude in Chrome opens the form. Press the Autonomous Job Kit Autofill button ("Fill with Autonomous") first (it does the standard fields for free),
  then Claude fills only what's left, attaches the files, and stops before Submit (Review mode unless the user says
  otherwise).
- **One application at a time.** In a batch, tailor all of them first, then fill the forms one after another, never
  in parallel subagents.
- Keep browser work cheap (filling.md, "Keep browser work cheap"): `find` and `form_input`, not screenshots.

Advantages: hands-off form filling with the user reviewing before Submit; much cheaper than full batches because forms
are filled one by one, with the extension doing the predictable fields.
Risks and limits: still uses noticeably more usage per application than lean; Claude acts in the user's signed-in
Chrome (close tabs with banking or private email first); it can misread unusual dropdowns or questions, so the review
before Submit matters; some sites show CAPTCHAs or block automated input, and those stay with the user.

### `full`: full automation (highest cost)

- Everything in SKILL.md and batch.md as written: batches of several jobs, forms filled in parallel by subagents,
  search, digest and queue, and the Fill all and Submit modes when the user asks for them.

Advantages: the fastest way to send many applications; almost no manual steps.
Risks and limits: uses usage limits fastest (one or two batches can take a large share of a Pro plan's limit; a Max
plan suits this level better); a mistake can repeat across several applications before anyone sees it; more
automated activity on job sites; with Submit mode, applications go out without the user's final look. Batches of
about 6 and a new conversation per batch keep it manageable.

## Where to run it

- **Claude Code** (terminal or the desktop app's Code tab) with the extension suits `lean` and `assisted`.
- **Cowork** in the Claude app suits `full`, and costs the most.
- A cheaper model (Sonnet or Haiku) is usually fine for form filling and digests; use the strongest model for
  tailoring and letters.

## No level set

If profile.json has no `automationLevel`, use `assisted` for a single posting, and before the first batch ask once
which level they want (one line on each: cost, effort, risk), then save their answer to profile.json.
