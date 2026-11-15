# Interview prep

Goal: the user walks in knowing exactly what the employer has already seen from them, with true stories ready for the likely questions.

## Gather

1. Job folder contents: the posting file, the application record (with its pre-submission edits and timeline), the tailoring notes, the resume that went out (PDF or `resume-src/`), and the letter if one was sent.
2. profile.json and the master, which hold details the one-page version dropped.
3. What the user told you about the interview: when (with time zone), how (call, video, in person), with whom, and which round (recruiter screen, technical, behavioural, final). If the round isn't known, prepare for several kinds and note that up front.
4. With web search: a quick scan of the employer and team (products, a recent headline or two), citing links. No search tool: leave this out instead of guessing.

## Rules

- **Nothing invented.** Every story, figure, tool and result must trace to the submitted resume, the master, profile.json or the application record. Details only the user can supply become `[Fill in: ...]` placeholders.
- Quote the user's submitted written answers verbatim so they can stay consistent.
- Every line on the resume sent needs a ready answer behind it.
- Readable in about 15 minutes.

## Check, then save

Write the draft in scratch, then run the fact check, whitelisting the employer, the job title and interviewer names:

```
python scripts/check_resume.py "<master resume>" "<scratch>/interview-prep.md" --known "<folder>/profile.json" --known "<job folder>/application-record.md" --allow "<Company>" --allow "<Role>" --allow "<Interviewer>"
```

Research naturally adds new names and figures. Go through each flag raised in the intro and stories and drop whatever the user didn't actually do. Store the result in the job folder as `interview-prep.md`; any previous copy goes to `_old/` first.

## Template

```
# Interview prep: <Role> at <Company>

**When and how:** <date, time, time zone> · <format> · <interviewers> · <round>

## The role
3-5 bullets: the team's work, what the hire will do, the posting's key requirements.

## The company
2-4 bullets; link anything taken from the web.

## What they already have from you
- Resume: <file name>. Most likely talking points: <3-5 lines that best match the posting>.
- Written answers: <each question, then the answer verbatim>.
- Cover letter: <main points, or "none">.

## 30-second intro
Written as the user would say it: study year, institution, program, a relevant project or job or two, and what draws them to this role. Only true facts.

## Stories
4-6, each tied to a theme the posting or round suggests (common ones: a project you're proud of, teamwork or disagreement, a setback or mistake, learning fast, why this employer).

### <Theme>: <project, job or activity used>
- **Context:** ...
- **Your part:** ... (only what the user did in group work)
- **Outcome:** ... (from the resume, or [Fill in: ...])
- **Follow-ups:** [Fill in: hardest part, what you'd change]

## Projects, in depth
One block per project listed on the submitted resume: purpose, the user's contribution, the tech used and the reason for it (or [Fill in: why]), a tough problem solved, and what they'd build next.

## Technical review
Concrete subtopics drawn from the posting and the resume's tools, each with one way to practise (e.g. SQL: joins, GROUP BY, window functions; write three queries on a sample dataset). If a coding round is expected, state it directly and recommend practice on core data structures and easy/medium problems, using the posting's first-listed language.

## Gaps, answered honestly
Take each gap from changes.md that might come up and prepare an honest response: point to the nearest genuine experience and express eagerness to pick it up. The user must never claim to have it.

## Questions for them
4-6 tailored to the team and position (what new hires usually start on, what good performance looks like, the team's working rhythm), skipping anything the posting covers.

## Day of, and after
- Confirm the time zone and the link or address; have the submitted resume open.
- Within 24 hours: a short thank-you. Offer a draft (`email_drafts.py --kind thankyou`), mentioning one specific moment from the conversation.
```

When done, give the user the file's location, how many `[Fill in: ...]` spots need them, and offer a short mock interview in chat.
