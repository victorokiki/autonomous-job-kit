# Autonomous Job Kit Autofill privacy notice

**Short version: your data stays in your browser. The extension makes no network requests.**

## What is stored

- Your profile (the contents of the `profile.json` you import or edit), the date it was last
  imported or saved, your resume PDF if you add one, and the "show page button" setting.
- Everything is kept in `chrome.storage.local` on this computer, in this browser profile only.
  It is not synced to your Google or Microsoft account.

## What is sent anywhere

Nothing. The extension contains no analytics, no tracking, no remote code and no network calls.
It only reads your stored profile and writes answers into the form on the page you are viewing.
Your answers reach an employer only when **you** submit their form.

## Permissions and why

| Permission | Why |
| --- | --- |
| `storage` | Keep your profile, resume PDF and settings on this computer |
| `activeTab` + `scripting` | Fill the current tab when you click *Fill this page* or press Alt+Shift+F on a site outside the built-in list |
| Host access to application systems (Greenhouse, Lever, Workday, ...) | Show the page button and fill forms on those sites, including forms embedded in frames |

## Sensitive questions

The extension never fills social security / social insurance / national ID numbers, date of
birth, bank or card details, passport numbers, religion, marital status or criminal-record
questions, and never ticks consent or certification boxes. Voluntary self-identification answers
are filled only for the questions where you chose an answer; "Not set" leaves them for you.

## Removing your data

Open the profile page, remove the resume, or uninstall the extension from `chrome://extensions`;
uninstalling deletes everything it stored.
