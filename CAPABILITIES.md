# What Autonomous Job Kit can do

A plain-words guide for people using the kit, and for Claude to answer "what can you do?" and "how do I change X?".

New here? Install it with the [Quick start](README.md#quick-start), open Claude in your job-search folder and say
**"Set me up"**. Claude finds your CVs, builds your master CV, asks only what your CV
can't answer, and helps you choose how much it automates.

## In one paragraph

You keep one **master resume** with every fact about you. The kit finds jobs and internships, ranks them by how well
they fit you, writes a **tailored resume** (and a cover letter when one is wanted) for each posting using only facts
from your master, fills in the application form in Chrome, and **stops before Submit** so you can check it. Every
application is recorded, and a tracker spreadsheet and dashboard show where everything stands.

## The everyday use: paste a job link

Paste a posting's link to Claude. Claude reads it, checks it fits you (and your immigration route, if you set one) and
drafts the tailored CV and cover letter. At the assisted and full levels (with **Claude in Chrome**) it fills the
application and stops before Submit; at the lean level it hands you the files and answers to paste with the extension. Then it logs the application and, in later conversations, asks you how it's going.

## Choose how much Claude does

| Level | Claude does | You do | Cost |
|---|---|---|---|
| **Lean** (Claude Code + Autonomous Job Kit Autofill extension) | Reads the posting, tailors CV and letter, writes answers to paste, logs it | Fill the form with the extension's Fill button, attach files, paste answers, submit | Lowest |
| **Assisted** | Also fills the form in Chrome, one at a time, stops before Submit | Review and submit | Medium |
| **Full** | Batches, parallel form filling, "fill all" / "submit" on request | Review | Highest |

Lean: least usage, full control, Claude never touches your browser, but 5–10 minutes of form work per job. Assisted:
hands-off forms you still review, more usage, Claude works in your signed-in Chrome. Full: fastest for volume, but uses
plan limits fastest and a mistake can repeat across applications. Say "switch me to lean mode" (or assisted, or full)
any time; it's saved as `automationLevel` in profile.json.

## The four parts

| Part | What it does | Ask Claude |
|---|---|---|
| `job-kit-setup` skill | First-time setup: finds your CVs, builds one master, creates your profile, captures your CV style, sets up your search. | "Set me up", "Get started" |
| `internship-application` skill | Finds and ranks jobs, tailors resumes and letters, fills forms, records what was entered. | "Find jobs that fit me", "Apply to 6 jobs", "What's new today?" |
| `internship-tracker` skill | Tracker spreadsheet, check-ins asking how each application is going, follow-up and thank-you email drafts, interview prep, weekly report, dashboard. | "Show my dashboard", "Check in", "Draft a follow-up to Northwind", "Weekly report", "I got an interview at X" |
| `extension` (Autonomous Job Kit Autofill, optional) | Fills the predictable form fields instantly from your saved profile, without using Claude. Green outline = filled, amber = left for you. | Click **Fill with Autonomous** on the page or press Alt+Shift+F (or let Claude press it) |

## What it does, step by step

1. **Finds jobs** in Canada, the US or the UK from SimplifyJobs (internships and new-grad), Canada's Job Bank, company
   boards on Greenhouse, Lever, Ashby, SmartRecruiters and Workday, and Remotive (remote jobs open to your country).
2. **Ranks** each one from 0 to 100 (title fit, skills you share, location, experience asked, how recent) and says
   why. It lists skill gaps; it never adds them to your resume.
3. **Screens eligibility and your route** from what you told it: "Canadian citizens only" is flagged for a temporary
   resident; with a route set, it flags NOC/TEER for Canada's CEC, whether a UK employer is a licensed sponsor, "no
   sponsorship" wording and pay below the minimum you entered. It never decides your immigration status for you.
4. **Tailors your resume** in three passes (the posting's angle, choose and order, rewrite every kept bullet) and
   fact-checks it against your master: new numbers, tools or titles that aren't in your master are flagged.
   For an on-site or hybrid job in another city, the header reads "Surrey, BC · Relocating to Toronto, ON" (your
   city, then the job's), and the cover letter says you're relocating. Remote and local jobs keep just your city.
5. **Writes a cover letter** when the posting wants one (or always, if you prefer), and can merge it with the resume
   into one PDF for forms with a single upload box.
6. **Fills the form** in Chrome (Claude in Chrome), attaches the files, answers from your profile and saved answers,
   and stops on the last page before Submit. At the lean level it writes `answers-to-paste.md` instead, so you fill
   the form yourself with the extension.
7. **Records** every field and answer it entered (`application-record.md`), what it changed in the resume
   (`changes.md`), and a tracker row.
8. **Daily digest**: what's new since yesterday, best first.
9. **Check-ins**: asks about applications with no news for a week and records submitted, assessment, interview stage,
   offer, accepted, declined or rejected.
10. **Dashboard**: one clean page with your pipeline (applied → interview → offer → accepted), a "needs your update"
   list, a to-do list, every application and the latest matches.
11. **Scam warnings**: flags postings that ask you to pay, want to chat only on Telegram or WhatsApp, offer a cheque to
   buy equipment, promise pay far above normal for entry-level work, or skip the interview.
12. **Email drafts**: follow-up after a quiet week or two, thank-you after an interview, and replies to accept, decline
   or withdraw. Drafts only: you send them.
13. **Weekly report**: what you sent, what moved, interviews coming up, and progress toward your weekly goal.
14. **Interview prep**: say "prep me for my Harbourline interview" and Claude writes `interview-prep.md` in that job's
   folder: the role and company, exactly what they already have from you (the resume and your written answers word
   for word), a 30-second intro, 4–6 true stories for likely questions, each project on your resume in depth, a
   technical review with practice ideas, honest answers for your skill gaps, questions to ask them, and a day-of
   checklist. Nothing is invented: details only you know are left as `[Fill in: ...]`. Afterwards it offers a mock
   interview in chat and a thank-you email draft.
15. **Memory of what you sent**: "Which resume went to Acme?" or "What did I tell them about salary?" is answered from
   the job's own records, word for word.

## Things you can say

| You want to | Say |
|---|---|
| Apply to one job | *paste the job link* |
| Find jobs | "Find jobs that fit me" · "What's new today?" · "Add Shopify's job board" |
| Apply to several | "Apply to 6 jobs" · "Apply to the top 3 and fill all" |
| Check a job first | "Is this a good fit?" · "Does this work for my CEC route?" · "Is this posting legit?" |
| Report news | "I submitted Northwind" · "Interview with Harbourline on Thursday" · "Rejected by Acme" · "I got the offer!" |
| See where things stand | "Show my dashboard" · "Where do things stand?" · "What should I do this week?" · "Weekly report" |
| Prepare and follow up | "Prep me for my Harbourline interview" · "Draft a follow-up for Northwind" · "Draft a thank-you email" |
| Change settings | "Switch me to lean mode" · "Allow two-page resumes" · "Stop writing cover letters unless required" |

## What it never does

- Submit an application unless you explicitly say "submit".
- Invent metrics, titles, dates, tools or degrees. Missing numbers go on a "To confirm" list for you.
- Type passwords, solve CAPTCHAs, create accounts, or enter ID numbers, date of birth or bank details.
- Tick consent or certification boxes, unless you ask for "fill all".
- Send emails for you (for apply-by-email jobs it drafts the email; you send it).
- Automate LinkedIn. No Easy Apply. It reads one LinkedIn job page only if you explicitly ask it to.
- Delete your files.
- Give immigration or legal advice. NOC/TEER codes it shows are "likely; confirm on the NOC site".

## Modes

| Say | What happens |
|---|---|
| "Apply to 6 jobs" | **Review** (default): fills each form, leaves consent boxes and unknown questions to you, stops before Submit. |
| "Apply to 6 jobs fill all" | **Fill all**: also ticks consent boxes and signs, and asks you once for anything unknown. Still stops before Submit. |
| "Apply to 6 jobs and submit" | **Submit**: fill all, then submits each application that passes the final check. Only when you say so. |

## How to customize it

Everything personal lives in **your own job-search folder** (never inside this repository):

| File | What it controls | Example settings |
|---|---|---|
| `resume/` | Your master resume (Overleaf/LaTeX or Word). The only source of facts. | |
| `profile.json` | Your standard answers and preferences. | `resumeMaxPages: 2`, `bulletFormula: "xyz"`, `coverLetterPolicy: "required-or-asked"`, `letterStyle: "carlito"`, `alwaysCombine: true`, `savedAnswers` |
| `style-guide/style-guide.md` | How your resume looks and sounds: layout, section order, title rules, banned words, page limit, letter format. | See `templates/style-guide.example.md` |
| `search.json` | What and where to search: country (Canada, US, UK), province/state/region, home area, job tracks with priorities, words to exclude, Job Bank searches, employers to follow, extra skills, and your immigration route (`pathway`). | `templates/search.example.json`, `search.uk.example.json`, `search.us.example.json` |
| `jobs.txt` | Your queue of posting links, one per line. Links below `# done` are finished. | |

The kit also keeps, in the same folder: `Applications/` (one folder per job with its resume, letter and records),
`tracker.xlsx`, `dashboard.html`, `digests/` and `reports/`. Open any of them yourself. Nothing is deleted: replaced
files move into an `_old/` folder beside them.

Common changes, just ask Claude:

- "Add Shopify's job board" → `find_jobs.py --add-employer <link>`.
- "Also look for project coordinator roles" → a new track in search.json.
- "Allow two-page resumes for regular jobs" → `resumeMaxPages: 2`.
- "Only write cover letters when they're required" → `coverLetterPolicy: "required-or-asked"`.
- "Never use the word 'passionate'" → banned words in style-guide.md.
- "Put Education after Projects" → section order in style-guide.md.
- "Remember that my notice period is two weeks" → a saved answer.
- "Switch me to lean mode" → `automationLevel: "lean"` (Claude prepares, you fill with the extension).
- "I'm on the UK Skilled Worker route and need sponsorship" → `pathway` in search.json (sponsor register checks).
- "I'm aiming for CEC" → `pathway: ca-cec` (TEER flags).

## What it costs

- The kit is free and open source (MIT).
- You need a **paid Claude plan** (Pro or higher) for skills and Claude in Chrome.
- Searching, ranking, PDF building and the tracker are local Python scripts: they use almost no Claude usage.
  Reading postings, tailoring and form-filling do.
- The **automation level** matters most: lean uses the least, full the most.
- To stretch your plan: batches of **about 6** applications, a **new conversation for each batch**, the strongest model
  for tailoring and a **cheaper model** (for example Sonnet or Haiku) for form-filling and digests.

## Where it works best

- Job search scripts: **Canada, the United States and the United Kingdom**.
- Application systems: Greenhouse, Lever, Ashby, Workday, SmartRecruiters, iCIMS and most company career sites.
- Resumes: Overleaf/LaTeX (best: Claude builds and checks the PDF itself with Tectonic) or Word.

## Updating

Download the new version (or `git pull`) and run the installer again; your job-search folder isn't touched. Reload the
extension in `chrome://extensions`. Details and uninstall steps: [README](README.md#update-or-uninstall).
