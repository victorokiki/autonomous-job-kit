# Batches: a subagent for each posting

Load this when the user hands you several links or asks you to process jobs.txt. You need a subagent tool (Agent or Task; `general-purpose` type); if there isn't one, see "No subagents" at the bottom.

Principles:

- **This conversation stays lean.** Never read or fill form pages here. Your only browser actions are creating the tab group and, in Submit mode, pressing Submit.
- **Models.** Launch filling subagents on `sonnet` when the tool allows a choice. Tailoring subagents use the default model.
- **Level.** `lean`: tailoring subagents only, each also writing `answers-to-paste.md`; no filling. `assisted`: fill forms one after another yourself or with one subagent at a time, never in parallel. `full`: everything below.

## Steps

1. **Queue.** Tidy, fetch and screen as SKILL.md "Batches" shows (one call each). Drop postings already tracked. Postings screened `skip` get no subagent: `--move-skips` has already moved them under `# done` with the reason (for links given directly, log them `Skipped`). Decide each `check` yourself from its `screen_why`/`check` sentences using SKILL.md step 2, logging exclusions as `Skipped` with the reason. If not enough remain, refetch using a bigger `--limit`. Sort: earliest deadline first, then undated postings newest first.

   **Company cap: two.** Per company, add this batch's postings to its tracker rows with `date_added` in the past 5 days (from `in_tracker`; ignore `Skipped` rows). Keep no more than two, choosing the titles closest to the user's major, skills and requested role type, and the sooner deadline on ties. If a fetch failed, take the company from the jobs.txt note or the link. The others stay above `# done` with `held: 2 per company` appended to their note (once). A user request for more from one company ("every Harbourline opening") sets its own number.
2. **Tailor.** One subagent per posting using the tailoring prompt. Launch the first by itself, then all others in your next message (or all together if the tool blocks until each one returns). Postings the fetch couldn't read are read in the browser, so apply "Sharing the browser". Leave tailoring.md, overleaf.md and the master unread in this conversation.
3. **Checkpoint** (SKILL.md step 4) built from the replies, a few lines per posting. Only open a drafts file when showing its answers, never in auto mode. Add one line naming held postings (company: roles), letting the user trade one in or request all; in auto mode they stay on hold.
4. **Fill.** Send the filling prompt to a separate subagent per application, following "Sharing the browser": the first alone; in the following message, all that aren't waiting on a shared sign-in; each waiting one once the form ahead replies (or one message later if the tool waits for everything). A `NO BROWSER` reply means you fill them all yourself, as in "No subagents".
5. **Hand-off.** One message covering the batch: a line per tab (company, role, what's needed, e.g. "sign in to Workday", "attach `C:\job-uploads\Alex_Tremblay_Resume_Harbourline.pdf`"), then every form's questions, merged so one reply covers all forms asking the same thing. Before sending, test each question against profile.json yourself (all fields and `savedAnswers`, by meaning) and send those back to the subagents (step 6) rather than asking. Submit mode without auto: include the on-form written drafts as well (from each record's "Written answers"); this message goes out even if nothing else needs the user, and then you wait.
6. **Resume.** When the user is done, rerun the filling prompt for every application at once, as in step 4, including what they did and their answers. Each continues in its tab from application-record.md. Do this one more time if new steps appear.
7. **Submit** (Submit mode only, never inside a subagent). Applications that passed the check, or whose sole failure was check 3 (written answers) that the user has now approved: go to the tab, verify the review page is showing, then do "Pressing Submit" from submitting.md.
8. **Report** in a single message, a line per posting (SKILL.md step 8). Move processed links under `# done` in jobs.txt (edit in place). Held postings share one closing line ("Held, 2 per company: ...") and remain in the queue; screen skips share another ("Skipped by the screen: Company Role (reason), ..."). Any answers listed under `To save:` go into profile.json without asking (profile.md); name what you saved in one line. If profile.json changed, add: "Re-import `<folder>/profile.json` in Autonomous Autofill (options page → **Import profile.json**) so the button uses the new answers." Close with a line suggesting a new conversation for the next batch.

An obstacle the user can't clear during the hand-off (broken page, closed posting, assessment) → `Needs you`, and move on.

## Sharing the browser

- **Create the group first.** Before any browser-using subagent starts, fetch the browser tool schemas via tool search, then run `tabs_context_mcp` with `createIfEmpty: true`. Hold one tab of your own open in the group until the batch ends.
- **No concurrency limit** apart from the queueing rule, unless the user sets one.
- **One form per account at a time.** Two forms on the same Workday host (e.g. `harbourline.wd3.myworkdayjobs.com`) or the same company's careers site never run together; queue the second. Greenhouse, Lever and Ashby forms for different employers can run side by side.
- **Interference** (two subagents reporting failed screenshots, clicks that don't register, missing tabs): allow the active ones to complete, then do the rest sequentially.
- **Group lost:** running subagents reply `stopped: tab group lost`. Once all have replied, recreate the group and resend each the filling prompt with the third `Tab:` option. Never start a form over.

## Tailoring prompt

Replace the `<...>` parts; send nothing else.

```
Batch tailoring task (internship-application skill), one posting.
Use your file-reading tool (not cat) to read the posting, the profile and <skill>/SKILL.md. Carry out SKILL.md
steps 1-2 for this posting only; the tracker duplicate check is done. That means: make the job folder, save
job-posting.md, judge eligibility. If excluded, reply right away. Otherwise read <skill>/references/tailoring.md,
references/overleaf.md too for a .tex master, and the master; then step 3: tailor the resume, check it, save it,
complete changes.md, write a cover letter when tailoring.md "Cover letter" calls for one (optional fields count),
and draft written answers in <scratch>/answers/<NN>.md. Each file: one read.
Stay away from the application form and the tracker, and start no subagents.
Use only the master resume; other job folders' resumes, resume-src and changes.md are off limits.
With a .tex master, never put LaTeX in a shell command, heredoc or script; edit with Write/Edit (plain file copies are fine).
Red flags in the fetch result: report them under Problems and stop before tailoring.
- Posting: <fetched file> | <link: open your own new tab, read, close it; pass its tab id on every browser call; touch no other tab>
- Folder: <folder>  Master: <path>  Profile: <folder>/profile.json
- Scratch: <scratch>/<NN>   Today: <YYYY-MM-DD>
- Template check: <include --check-template | done already, omit it>
Reply with exactly these lines:
Folder: <job folder>
Posting: <Company> - <Role>, deadline <date | none>
Eligibility: ok | skip: <why>
Problems: <none | what needs the user>
Resume: <PDF name>; page <filled | N lines free, why>
Changes: <2-3 brief lines>
Gaps: <single line>
Cover letter: <file (and combined PDF), or none: <Cover letter line value>>
Answers: <path to drafts, or none>
```

Only the first tailoring subagent gets `--check-template`. A `skip` reply is logged `Skipped` with its reason in auto mode, otherwise shown at the checkpoint.

## Filling prompt

```
Batch filling task (internship-application skill), one application.
Read <skill>/references/filling.md (plus, outside Review mode, references/submitting.md) using your
file-reading tool (not cat), each once. SKILL.md isn't needed.
Mode: <Review | Fill all | Submit>. You never click Submit. In Submit mode, fill as Fill all, then run
submitting.md's "Final check" once on the review page and include the result.
iCIMS: no review page; every step button reads Submit but only saves, except on the final remaining step
(the current one once all others show "(Completed Step)"), whatever its number. If its heading counts forms
("(1/3)"), press Submit on each form before the last, fill the last and stop without pressing Submit. No count:
treat the visible form as the last. Review mode: stop as soon as that final step opens.
Stay on the resume step until the tailored PDF's name shows; if you can't attach it (iCIMS: Replace Resume
reveals the box), stop there for a hand-off. Any place the form takes a cover letter (optional ones too) gets it,
by upload or paste (filling.md, "Files").
The user <has | has not (auto)> seen the drafted answers.
Scope: this application only. Work in the user's browser until you reach the review page or something that
requires the user; record each page in application-record.md as it's done, and add the tracker row (filling.md,
"Tracker row"; scripts live in <skill>). Start no subagents.
Fill all you can. Before listing a question, check profile.json by meaning (all fields, all savedAnswers); only
list questions that it, the master and the posting leave open. Never edit profile.json; new answers go under To save.
Browser: use find/read_page to locate fields; click and scroll_to only by reference, never coordinates.
Screenshots: no more than one per page, always its own call, never in a batch.
- Form: <url; for icims.com add in_iframe=1>  Job folder: <folder>  Answers: <path to drafts, or none>  Resume: <PDF path>
- Letter: <letter path, cover-letter.txt path, combined PDF, or none>  Master: <path>
- Tracker: <folder>/tracker.xlsx  Profile: <folder>/profile.json
- Tab: <start in a new tab of your own | keep using tab <id>; since then the user <did what> and answered: <answers>
  | start in a new tab of your own and resume from application-record.md (group was lost)>
If the claude-in-chrome tools are deferred, fetch them with tool search first. Only if none exist afterwards,
reply with just "NO BROWSER".
Other subagents may be working in other tabs. Pass your tab id on every browser call and never switch to, close
or use another tab. Tab gone but group present: open a new tab and resume from application-record.md. Group gone
entirely: don't make a new one; reply Status: stopped: tab group lost.
Reply with exactly these lines:
Tab: <id> <url>
Status: review page | stopped: tab group lost | stopped: <reason> | needs the user
Questions: <verbatim, choices included, or none>
For the user: <single line, or none>
Agreed for you: <brief list, or none>
Written answers: <none | "in application-record.md" for ones drafted on the form>
To save: <reusable answers from the user, or none>
Submit check (Submit mode only): <passed | failed: number>
```

## No subagents

Run the same sequence yourself: tailor every posting (SKILL.md steps 1-3); a single joint checkpoint; each form filled in a tab of its own until it needs the user; a single batch-wide hand-off; then finish every form; record and log each; one report.
