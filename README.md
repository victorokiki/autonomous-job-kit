# Autonomous

**Paste a job link. Get a tailored CV, a cover letter and a filled-in application, ready for you to review.**

Autonomous turns Claude into your personal job-search assistant. It builds one strong master CV from the CVs
you already have, finds and ranks jobs that fit you, tailors your resume and cover letter to every posting without
inventing a single fact, fills in the application form, and checks in with you on every application until you hear back.

Made for job seekers in **Canada, the United States and the United Kingdom**, in any profession: students and new
graduates, career changers, experienced professionals, and newcomers on a route to permanent residence (Express Entry,
UK Skilled Worker, H-1B and more).

Created and maintained by [victorokiki](https://github.com/victorokiki).

## All you do: paste a job link

> https://jobs.example.com/data-analyst-12345

Claude reads the posting, checks it fits you, drafts a tailored CV and (if wanted) a cover letter from your master CV,
and logs the application in your tracker. Then, depending on the [level you chose](#choose-how-much-claude-does), it
either fills in the application form and **stops before Submit** so you can check it, or hands you the files and
answers to paste with the extension. Form filling needs
**[Claude in Chrome](https://support.claude.com/en/articles/12012173-get-started-with-claude-in-chrome)** (the browser
extension that lets Claude open pages and fill forms).

**You stay in control:** nothing is sent without you. Claude stops before Submit (or, at the lean level, hands the
form to you), and you review every application and click Submit yourself, unless you explicitly tell Claude to submit.

New here? Read [CAPABILITIES.md](CAPABILITIES.md) for a plain-words tour, or install and ask Claude **"Set me up"**.

## Choose how much Claude does

Driving the browser is what uses most of your Claude plan. Setup asks which level you want, and you can switch any time
("switch me to lean mode"):

| Level | Claude does | You do | Cost | Good | Watch out |
|---|---|---|---|---|---|
| **Lean**: Claude Code + the [Autonomous Autofill extension](extension/) | Reads the posting, tailors your CV and cover letter, writes the answers to paste, logs it | Open the form, click the extension's **Fill**, attach the files, paste the answers, submit | Lowest | Your plan goes much further; you control every field; Claude never acts in your browser; no Claude in Chrome needed | About 5–10 minutes of form work per job |
| **Assisted** | All of the above, plus fills the form in Chrome (after the extension's Fill), one at a time, stopping before Submit | Review and click Submit | Medium | Hands-off forms, and you still review each one | More usage per job; Claude works in your signed-in Chrome (close private tabs); unusual questions can be misread |
| **Full automation** | Batches of jobs, forms filled in parallel, "fill all" or "submit" when you ask | Review (unless you ask it to submit) | Highest | Fastest for volume | Can use a big share of a Pro plan's limit in one or two batches (Max suits it better); a mistake can repeat across several applications; more automated activity on job sites |

**Claude Code** with the extension is the cheapest setup; the Claude app's **Cowork** costs the most and suits full
automation.

## What it does

| Part | What it does |
|---|---|
| [`job-kit-setup`](job-kit-setup/) | First-time setup. Claude interviews you: finds your existing CVs, builds **one master CV** (flagging contradictions instead of merging them), creates your `profile.json`, captures your CV style in a style guide, and sets up your job search. |
| [`internship-application`](internship-application/) | Finds jobs (SimplifyJobs, Canada's Job Bank, company boards on Greenhouse, Lever, Ashby, SmartRecruiters and Workday, Remotive), **ranks them by fit**, tailors and fact-checks a resume per posting, writes cover letters, fills the application in Chrome and records what it entered. Daily digest of new matches. |
| [`internship-tracker`](internship-tracker/) | Tracks every application in `tracker.xlsx` and **checks in with you** about the ones with no news (submitted, assessment, interview stage, offer, accepted, rejected). Interview prep, and a clean `dashboard.html` with your pipeline and what needs updating. |
| [`extension`](extension/) | **Autonomous Autofill**, the kit's own Chrome extension: fills the predictable fields (name, contact, school, work history, yes/no and self-ID answers you chose) from your profile instantly, without using Claude, and leaves a report Claude can read. |

It never invents metrics or experience, never types passwords or solves CAPTCHAs, never automates LinkedIn, and never
deletes your files. See [CAPABILITIES.md](CAPABILITIES.md) for the full list.

## What you need

- A **paid Claude plan**: Pro, Max, Team or Enterprise (skills and Claude in Chrome aren't on the free plan).
- The [Claude desktop app](https://claude.com/download) (Cowork or Code tab) or [Claude Code](https://code.claude.com).
- Google Chrome with **[Claude in Chrome](https://support.claude.com/en/articles/12012173-get-started-with-claude-in-chrome)** for the assisted and full levels (Claude opens pages and fills forms). For the lean level, the free Autonomous Autofill extension in this repo is enough.
- Your existing CV(s): PDF, Word or Overleaf.
- For building PDFs yourself: Python 3, [Tectonic](https://tectonic-typesetting.github.io/) and Poppler (below).

## Install

### 1. Get the kit

Click **Code → Download ZIP** on this page and unzip it, or clone it:

```bash
git clone https://github.com/victorokiki/autonomous.git
```

### 2. Add the skills

**Claude Code (command line or the desktop app's Code tab):** run the installer from the kit's folder. It copies the
three skills, the templates and CAPABILITIES.md into your `.claude/skills` folder. Old copies are moved to
`.claude/skills-backup`, never deleted.

Mac or Linux:

```bash
./install.sh
```

Windows: double-click **`install.cmd`** in the kit's folder, or run this in PowerShell from that folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

**Claude app (Cowork):** run `python3 make_zips.py` (Windows: `py make_zips.py`) in the kit's folder. It makes three
ready-to-upload zips in `dist/`; upload each in **Customize → Skills**
([help](https://support.claude.com/en/articles/12512180-use-skills-in-claude)).

### Add the Autonomous Autofill extension (optional; needed for the lean level)

1. Open `chrome://extensions` (Edge: `edge://extensions`) and turn on **Developer mode** (top right).
2. Click **Load unpacked** and choose the kit's `extension` folder.
3. Pin it from the puzzle-piece menu, open its profile page and click **Import profile.json** once setup has made your
   profile (or fill the page in by hand).

On application sites a **Fill with Autonomous** button appears on the right edge. See [extension/README.md](extension/README.md).

### 3. Install the helpers

Python packages (all systems; on Windows, install Python from python.org first and tick **Add python.exe to PATH**):

```bash
pip install openpyxl pypdf python-docx
```

Tectonic and Poppler on a Mac ([Homebrew](https://brew.sh)):

```bash
brew install tectonic poppler
```

On Windows ([Scoop](https://scoop.sh)):

```powershell
scoop install tectonic poppler
```

On Linux, use your package manager for `poppler-utils` and see [Tectonic's install page](https://tectonic-typesetting.github.io/en-US/install.html).

Tectonic builds LaTeX resumes (without it, compile in Overleaf). Poppler gives `pdftotext` and `pdfunite` for PDF
checks and for merging letters with resumes.

### 4. Make a job-search folder, outside this repository

```bash
mkdir -p ~/Documents/job-search
```

Your CVs, profile, tracker and applications live there, **never inside the kit's folder**, so nothing personal can
end up on GitHub. (`.gitignore` also blocks the usual file names as a safety net.)

## First run

Open Claude in your job-search folder (Cowork: choose the folder; Claude Code: `cd ~/Documents/job-search`, then
`claude`) and say:

> Set me up

Claude explains what the kit does, finds your CVs, builds your master CV, asks only what your CV can't answer,
writes your style guide and search settings, and runs a first search so you can see ranked results.

Then:

> Find jobs that fit me

> Apply to 6 jobs

> Show my dashboard

"Apply to 6 jobs" works through the top 6 links in your `jobs.txt` in **Review mode**: a tailored resume for each
job, every form filled, and a stop before Submit. Add "fill all" to let it tick consent boxes too, or "and submit" to submit
(only when you mean it).

## Track your applications

Every application lands in `tracker.xlsx`. At the start of each job-search conversation Claude asks about the ones
with no news ("Northwind, submitted 9 days ago: any news?") and updates them: submitted, online assessment, interview
(and which stage), offer, accepted, declined, rejected or withdrawn. Ask **"show my dashboard"** for a one-page view:
your pipeline from applied to accepted, response rate, a "needs your update" list with one-click update lines to paste
back to Claude, your to-do list, every application, and the best new job matches.

## Your country, profession and immigration route

Setup asks about your situation, and the kit adapts:

- **Country:** Canada, the United States or the United Kingdom (`search.json` `country`), with your province, state
  or region and home area for location ranking. Canada also searches the government's Job Bank.
- **Profession:** you define your own job "tracks" (title words and priorities), skills and words to avoid, so it works
  for engineers, analysts, nurses, trades, admin, anything.
- **Immigration route (optional):** tell it the route you're on and it flags jobs that may not fit, with the reason:

| Route (`pathway.type`) | What the kit flags |
|---|---|
| Canada, Express Entry CEC (`ca-cec`) / PNP (`ca-pnp`) | The NOC code and **TEER** when the posting shows it (CEC counts TEER 0-3 work), part-time and temporary roles; otherwise Claude gives the *likely* NOC/TEER to confirm. |
| UK, Skilled Worker → ILR (`uk-skilled-worker`) | Whether the employer is on the Home Office **register of licensed sponsors**, "no sponsorship" wording, pay below the minimum you entered, and the *likely* SOC code to confirm on gov.uk. |
| US, OPT / H-1B / green card (`us-opt`, `us-h1b`, `us-green-card`) | "No sponsorship" or "citizens only" wording, pay below your minimum, E-Verify mentions for STEM OPT. |

These are checks, not decisions: you confirm on the official site. See
[`references/pathways.md`](internship-application/references/pathways.md) and the example settings for
[Canada](templates/search.example.json), [the UK](templates/search.uk.example.json) and [the US](templates/search.us.example.json).

## Keeping costs down

- Pick the **lean** level if you're on a Pro plan or want full control (see the table above).
- The kit itself is free. Searching, ranking, PDF building and the tracker run as local scripts and use almost no
  Claude usage; reading postings, tailoring and form-filling do.
- Apply in **batches of about 6**, and start a **new conversation for each batch**. Long conversations use far more.
- Use the strongest model for tailoring and letters, and a **cheaper model** (for example Sonnet or Haiku) with lower
  effort for form-filling and the daily digest.
- The optional Autonomous Autofill extension fills standard fields without Claude.

## Customize it

Ask Claude in plain words ("allow two-page resumes", "add Shopify's job board", "never use the word passionate"), or
edit the files in your job-search folder:

| File | Controls | Template |
|---|---|---|
| `resume/` | Your master CV, the only source of facts | [`templates/master-resume.tex`](templates/master-resume.tex) |
| `profile.json` | Your standard answers, page limit, XYZ bullets, cover-letter policy and layout, saved answers | [`templates/profile.example.json`](templates/profile.example.json) |
| `style-guide/style-guide.md` | Layout, section order, title rules, banned words, page limit, letter format | [`templates/style-guide.example.md`](templates/style-guide.example.md) |
| `search.json` | Country, province/state/region, home area, job tracks and priorities, exclusions, Job Bank searches, employers, extra skills, immigration route | [Canada](templates/search.example.json), [UK](templates/search.uk.example.json), [US](templates/search.us.example.json) |

The templates describe a **fictional** person; copy their structure, not their content. Field details:
[`references/profile.md`](internship-application/references/profile.md) and
[`references/canada.md`](internship-application/references/canada.md).

Scripts Claude runs for you:

| Script | What it does |
|---|---|
| `find_jobs.py` | Searches every source, keeps postings that fit your tracks and ranks them. `--append` queues the best in `jobs.txt`; `--add-employer <link>` follows a company's board; `--check-sources` tests your boards. |
| `rank_jobs.py` | Scores a posting 0–100 (title, shared skills, location, experience asked, recency) with reasons and skill gaps. |
| `job_digest.py` | Daily digest of new matches in `digests/`; `--queue` adds the best to `jobs.txt`. |
| `check_tailored.py` | Builds and fact-checks a tailored resume against your master; page limit from `--max-pages` or profile `resumeMaxPages`. |
| `cover_letter.py` | Builds and checks a letter: `letterStyle`, `--location`, `--subject`, `--combine` (merged PDF). |
| `sponsor_check.py` | Checks employers against the UK register of licensed sponsors (public gov.uk data, cached weekly). |
| `tracker.py checkin` | Lists applications due for a status check with you. |
| `fetch_posting.py` | Reads a posting from the job site's public data (Greenhouse, Lever, Ashby, Workday, SmartRecruiters, iCIMS, Oracle, Rippling, Job Bank and more), screens it against your eligibility and flags **scam warning signs**. |
| `email_drafts.py` (tracker) | Drafts follow-up, thank-you and offer-reply emails from your tracker. Drafts only: you send them. |
| `weekly_report.py` (tracker) | A weekly progress report: what you sent, what moved, what's next. |
| `dashboard.py` (tracker) | Writes `dashboard.html`. |

## Troubleshooting

- **Windows says "running scripts is disabled":** use `install.cmd`, or the `-ExecutionPolicy Bypass` command above.
  It applies to that one run only and doesn't change your settings.
- **`python` not found on Windows:** reinstall Python from python.org with **Add python.exe to PATH** ticked, or use `py`
  instead of `python`.
- **`CERTIFICATE_VERIFY_FAILED` on a Mac:** with Python from python.org, run **Install Certificates.command** in
  `/Applications/Python 3.x/` once.
- **Digits missing from the PDF text (tracking systems can't read your numbers):** load Carlito as
  `\usepackage[sfdefault,lining]{carlito}`. Without `lining`, its old-style digits can vanish from the text layer.
  The template and the `carlito` letter style already do this.
- **Chrome won't attach a file:** the Claude in Chrome upload tool can reject paths with spaces. The kit copies the
  PDF to a space-free folder (such as `~/job-uploads/`) before attaching; do the same if you attach by hand.
- **Job Bank returns errors, or results from the whole country:** Job Bank wants `Accept: text/html` and ignores
  free-text locations; its province filter `fprov` (your `province` in search.json) narrows results. `find_jobs.py`
  handles both.
- **An employer board fails:** run `find_jobs.py --check-sources`; renamed boards answer 404. Re-add with `--add-employer`.
- **Auto mode blocks form filling in Claude Code:** add an `autoMode` rule to `~/.claude/settings.json`
  ([how](https://code.claude.com/docs/en/auto-mode-config)). Claude can't loosen its own permissions.
- **LinkedIn:** the kit doesn't automate it (LinkedIn's terms ban automated tools). It reads one LinkedIn job page
  only when you explicitly ask, never uses Easy Apply, and looks for the same job on the company's own site instead.

## Please read: disclaimers

- **Not immigration or legal advice.** Immigration advice is regulated in Canada (licensed consultants and lawyers),
  the UK (IAA-registered advisers and solicitors) and the US (attorneys and accredited representatives). The kit only
  records what you tell it about your work authorization and route, and flags postings that may not fit. Occupation
  codes it shows (NOC/TEER, SOC) are marked "likely; confirm on the official site". Rules and salary thresholds change
  often: check [Canada.ca](https://www.canada.ca/en/immigration-refugees-citizenship.html), [the NOC site](https://noc.esdc.gc.ca/),
  [gov.uk](https://www.gov.uk/skilled-worker-visa) or [uscis.gov](https://www.uscis.gov/).
- **You review every application.** Claude can make mistakes. Check each form and document before you submit; you
  are responsible for what goes out under your name.
- **Follow each job site's terms of use.** The search scripts read public job data politely (rate-limited; one
  request every 5 seconds for Job Bank, as its robots.txt asks). Don't use the kit on sites that forbid automation.
- **Your data stays with you.** Keep your job-search folder outside this repository. Never commit CVs, profile.json,
  tracker.xlsx, digests or Applications/.
- Not affiliated with or endorsed by Anthropic, LinkedIn, the Government of Canada or any job site.

## Features at a glance

- **Onboarding** (`job-kit-setup`): finds your CVs, builds one master CV and flags contradictions, writes your profile,
  style guide and search settings.
- **Choose how much Claude does**: lean, assisted or full automation, with the cost, advantages and risks of each.
- **Jobs and internships in Canada, the US and the UK**: Canada's Job Bank, company boards (Greenhouse, Lever, Ashby,
  SmartRecruiters, Workday), SimplifyJobs and Remotive, ranked by location, province, state or region.
- **Fit ranking** (0–100 with reasons and skill gaps) and a **daily digest** of new matches.
- **Tailored resume and cover letter per posting**, fact-checked against your master CV: XYZ bullets, page limits per
  job type, your style guide, banned words, readable digits for applicant tracking systems, merged letter + resume PDFs.
- **Form filling** with Claude in Chrome and the kit's own **Autonomous Autofill** extension, always stopping before Submit
  unless you say otherwise.
- **Scam and red-flag warnings** on postings (pay-to-apply, chat-only contact, crypto, suspicious pay).
- **Immigration-route checks**: NOC/TEER for Canada's CEC and PNPs, the UK register of licensed sponsors for Skilled
  Worker, sponsorship wording and salary floors for the US and UK (checks, never advice).
- **Tracker check-ins**, a **clean dashboard**, a **weekly progress report**, and **follow-up and thank-you email
  drafts**.
- **Templates and a fictional example**, `CAPABILITIES.md`, Mac and Windows installers, Cowork zips, and
  troubleshooting for common setup problems.

## License

Autonomous © 2026 [victorokiki](https://github.com/victorokiki), released under the [MIT license](LICENSE).
