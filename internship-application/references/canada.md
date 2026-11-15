# Job search in Canada, and roles beyond internships

Read this when the job-search folder's `search.json` says `"country": "Canada"`, or profile.json's `authCountry` is Canada. It adds to SKILL.md, filling.md and tailoring.md and wins where they differ.

## Finding jobs

Use `find_jobs.py`, not `find_internships.py` (that one drops everything outside the U.S. for a U.S. profile and only knows internships):

```
python scripts/find_jobs.py --folder "<folder>" [--source jobbank --source greenhouse ...] [--days 30] [--append]
```

It searches SimplifyJobs (internships and new-grad, Canadian locations only), the Government of Canada Job Bank (one search per `jobbank_queries` entry, filtered to `province`), employer boards listed in `search.json` (Greenhouse, Lever, Ashby, SmartRecruiters, Workday) and Remotive (remote jobs open to Canada). It keeps postings whose title fits a track in `search.json`, scores each 0 to 100 with `rank_jobs.py`, and shows why. `--append` queues the best (at least `min_score_to_queue`) in jobs.txt with the score in the note. Co-op and student-only roles are shown but not queued unless profile.json says `enrolled` and `returningToSchool` are both yes.

- To follow a company, run `--add-employer "<any link to its careers board or a posting>"`. It works for Greenhouse, Lever, Ashby, SmartRecruiters and Workday, tries the board once and saves it to search.json. For other sites, add a Job Bank query or open the careers page in the browser.
- `--check-sources` tries every board in search.json and lists the ones that fail (a renamed board answers 404). Remove or fix those.
- Work the queue in fit order: the highest score first, then the earliest deadline.

## Eligibility in Canada

From the profile only (`workAuthorized`, `workAuthDetails`, `needsSponsorship`). Never work out immigration status, permit conditions or off-campus work limits yourself. If the profile doesn't say, the question is the user's.

- "Legally entitled to work in Canada?" is `workAuthorized`.
- "Will you now or in the future require sponsorship (a work permit or LMIA)?" is `needsSponsorship`.
- `fetch_posting.py --profile` screens Canadian rules too: "must be a Canadian citizen (or permanent resident)" is a skip for a temporary resident (study permit, work permit, PGWP in `workAuthDetails`) and a check when the profile doesn't say. "Citizens, permanent residents, or those legally entitled to work in Canada" rules no one out.
- Security screening ("Reliability status", "Secret clearance") on federal jobs: a check, not a skip; some need years of residence history the profile doesn't record.
- **Co-op and student programs** usually need current enrolment and a return to school after the term. Apply only when profile.json says `enrolled` and `returningToSchool` are yes; otherwise skip with that reason.
- **P.Eng. or EIT** (the provincial engineering regulator, such as Engineers and Geoscientists BC or PEO in Ontario): never claim either unless the master or profile says so. "P.Eng. required" rules the user out; "EIT or eligible for EIT" is a check for the user.
- **French**: "bilingual (English and French) required" is a skip unless the master shows French; "an asset" is fine.

## Regular jobs (not internships)

- Class year and graduation window rules in SKILL.md step 2 are for internships. For a regular job, check the years of experience asked for against the master's dates: up to about two years beyond is fine (mention it at the checkpoint); more is weak fit, not a stop.
- Tailoring: if the posting is not an internship, co-op or new-grad role and the user's relevant work experience is stronger than their schooling, put Experience above Education. Everything else in tailoring.md stands, including one page and never adding facts.
- Salary questions: use `salary` from the profile, in the form's unit (hourly or yearly, CAD). If it's empty, leave it for the user.

## Canadian application conventions

- Never put a photo, date of birth, marital status, Social Insurance Number (SIN) or citizenship on a resume or cover letter. A form that asks for a SIN or date of birth is the user's to fill.
- Use the posting's spelling (Canadian "modelling", "behaviour", "centre" when the posting uses it) in written answers and cover letters.
- **Voluntary self-identification in Canada** follows employment equity groups (women, Indigenous peoples, persons with disabilities, members of visible minorities). Answer only from the profile's self-identification fields or a matching `savedAnswers` entry ("indigenous", "visible minority"). Never infer; otherwise leave it.

## Job Bank postings

Job Bank lists how to apply: "Direct Apply" (a Job Bank form), by email, online at the employer's site, by mail or in person.

- Online at the employer's site: follow the link and fill that form as usual.
- **By email**: never send email for the user. Write `email-to-employer.md` in the job folder (To, Subject with the job title and Job Bank number, a short body built like the cover letter, the files to attach), log the row as `Needs you` with next step "Send the application email", and give the user the address in the report.
- Direct Apply needs the user's Job Bank account: hand over the sign-in like any other.
- By mail or in person: prepare the files and log `Needs you`.

## Daily digest

`python scripts/job_digest.py --folder "<folder>" [--queue]` runs the same search, writes `digests/YYYY-MM-DD.md` with the best new matches, flags and recurring skill gaps, and with `--queue` adds the best new ones to jobs.txt. It never applies or contacts anyone. The tracker skill's `dashboard.py` shows the latest matches next to the applications.
