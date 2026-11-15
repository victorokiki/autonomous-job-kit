# LaTeX (Overleaf) masters

The user exports their Overleaf project (Menu → Download → Source), unzips it into `resume/`, and that folder is the master. It is read-only for you. Tailor a copy in scratch; once the copy passes every check, put its PDF and its source (as `resume-src/`) in the job folder.

## Which file is main

Whichever `.tex` contains `\documentclass`. If several do, prefer `main.tex`, then a resume-like name. Files brought in by `\input` or `\include` belong to the resume and get edited in the copy as well.

## Editing rules

Templates define macros in the preamble (everything before `\begin{document}`), for example `\resumeItem{...}`, `\resumeSubheading{...}{...}{...}{...}` or `\resumeProjectHeading{...}{...}`.

- **LaTeX is written only through the Edit tool (changes) or Write (new files).** Never put LaTeX inside a shell command, heredoc or script. Shell commands that merely copy, cut or join existing files (`cat`, `cp`, `head`) are acceptable.
- **Don't touch the preamble and all `\newcommand` definitions alone.** Two exceptions: spacing numbers you're allowed to lower while squeezing (tailoring.md), and, for a pdflatex build lacking them, adding `\input{glyphtounicode}` and `\pdfgentounicode=1` to the copy.
- **Change words, not structure.** Only the text in macro arguments, and ordinary body text, may change.
- **Reorder** by moving complete items (a whole `\resumeItem{...}` line, or a heading plus its item list). **Trim** by removing complete items. Every `{` keeps its matching `}`.
- **Match the master's conventions**: how dates look (`Jan 2026 -- Present`), separator symbols (`$|$`), letter case, emphasis, quotes and dashes.
- Lines beginning with `%` are comments. Un-commenting an old bullet is allowed when it suits this posting better.

## Special characters in text you write

| Character | Write | Example |
|---|---|---|
| & | `\&` | Q\&A |
| % | `\%` | 35\% faster |
| $ | `\$` | \$2K grant |
| # | `\#` | F\# |
| _ | `\_` | user\_id |
| { } | `\{ \}` | |
| ~ | `\textasciitilde{}` | |
| ^ | `\textasciicircum{}` | |

A bare `%` silently turns the rest of the line, closing brace included, into a comment. `C++`, `/`, `-` and `.` need no escaping.

## Reading the build result

check_tailored.py compiles the copy through build_resume.py. Give `--expect` a phrase or two from your new text so the build proves it can be extracted.

| Exit | Meaning | Do |
|---|---|---|
| 0 or 2 (built) | Text overflowing the right margin | Make the newly written line shorter. |
| | `fix` says expected text isn't readable | pdflatex builds need both `\pdfgentounicode=1` and `\input{glyphtounicode}` in the copy's preamble. |
| | Digits missing from the PDF text | Follow the warning (with Carlito: `\usepackage[sfdefault,lining]{carlito}`). |
| | Margins too tight or text under 9pt | Undo the last squeeze. |
| 2 + `lines_over` | Too long | Trim (tailoring.md, "When it runs long") or squeeze; rerun. |
| `review` free lines | Too short | Add lines (tailoring.md, "When it runs short"); rerun. Leave the space only if nothing else fits, and say why in changes.md. |
| 1 | Failed to compile | Read `errors` (line and message) and `hints`. Nearly always an unescaped character or unbalanced brace in your text. Fix and rerun. Three failures in a row: roll back your most recent batch of edits, build that version, and report which changes couldn't be made. |
| 3 | No LaTeX engine here (or a package/font missing from the project, e.g. fontawesome5) | Still act on the bullet comparison and fact check, place the copy in the job folder as `resume-src/`, and have the user build it in Overleaf: zip that folder and choose New Project → Upload Project, or paste the edited lines into a duplicate of their own project. Continue the application, leave the resume upload to the user, and log the row `Needs you`, next step "build the resume in Overleaf and attach it". |

## Rebuilding and Overleaf copies

The job folder already holds the PDF and source, so an Overleaf copy is optional. Redoing a build that was already saved: build again in scratch and copy it over, after moving the old PDF and `resume-src/` into `_old/`. To open the tailored version in Overleaf: zip `resume-src`, New Project → Upload Project.
