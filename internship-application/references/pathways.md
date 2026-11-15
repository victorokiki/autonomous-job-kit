# Country and immigration pathway settings

Read this when search.json has a `"pathway"` other than `none`, or when the user asks how the kit handles visas,
sponsorship or permanent residence. It adds to SKILL.md and canada.md.

**This is not immigration advice.** Immigration advice is regulated in all three countries (in Canada by the CICC,
in the UK by the IAA, in the US only lawyers and accredited representatives may give it). Rules, salary thresholds and
occupation lists change often. The kit only:

- records the pathway the **user** chose and the facts the **user** gave (in their own words),
- flags postings that may not fit that pathway, with the reason and the sentence from the posting,
- shows *likely* occupation codes, always marked "likely; confirm on the official site".

It never tells the user they are or aren't eligible, never works out their status, and never skips a job for a
pathway reason without saying so. When something matters for their status, point them to the official page and,
for anything uncertain, a licensed adviser.

## Settings (search.json)

```json
"country": "United Kingdom",
"region": "london",
"pathway": {
  "type": "uk-skilled-worker",
  "goal": "Skilled Worker visa, then settlement (ILR)",
  "requireSponsor": true,
  "minSalary": 41700,
  "avoidTemporary": true,
  "eligibleCodes": []
}
```

- `country`: `Canada`, `United States` or `United Kingdom` (job search, location ranking, Job Bank on or off).
  Region key: `province` (Canada, two-letter code), `state` (US, two-letter code) or `region` (UK, a name such as
  `london` or `scotland`).
- `type`: one of the types below, or `none` (default: no pathway checks).
- `goal`: the user's own words, shown in the digest and checkpoints.
- `requireSponsor`: the user needs the employer to sponsor a visa.
- `minSalary`: the yearly amount (in the posting's currency) the **user** says their route needs. The user looks it up
  on the official site and enters it; Claude doesn't supply the number. Postings whose top pay is below it get a flag.
- `avoidTemporary`: the user wants permanent, full-time roles (the kit flags temporary, contract and part-time work).
- `eligibleCodes`: occupation codes the user has confirmed fit their route (NOC 2021 for Canada, SOC 2020 for the UK).

Ask about these in setup (job-kit-setup step 6). Never fill them by guessing.

## Pathway types and what the kit checks

| type | Country | What the kit flags |
|---|---|---|
| `ca-cec` | Canada: Express Entry, Canadian Experience Class | The NOC code when the posting prints one (Job Bank does) and its TEER (the code's second digit: 21223 → TEER 1); "CEC counts TEER 0-3 work only" for TEER 4-5; part-time; temporary/contract with `avoidTemporary`. Without a code, Claude gives the likely NOC and TEER at the checkpoint and in changes.md. |
| `ca-pnp` | Canada: a Provincial Nominee Program | As `ca-cec`, plus the province: PNP job offers are usually full-time, indefinite and in the nominating province. The user names their stream in `goal`. |
| `ca-other` | Canada: another route (Atlantic Immigration Program, a work permit) | NOC/TEER and temporary flags only. |
| `uk-skilled-worker` | UK: Skilled Worker visa, often aiming for Indefinite Leave to Remain (ILR) | Whether the employer is on the Home Office **register of licensed sponsors** (sponsor_check.py; "not found" may just be a different legal name); "no sponsorship" wording; posted pay below `minSalary`; no yearly salary in the posting. Claude gives the likely SOC 2020 code at the checkpoint ("likely; confirm on gov.uk"). |
| `uk-graduate` | UK: Graduate visa (no sponsor needed) | Temporary/contract flags only. Mention once, at setup, that the user should check on gov.uk how their time on this visa counts towards later routes. |
| `uk-other` | UK: Global Talent, Health and Care Worker, family routes | "no sponsorship" wording and salary only. |
| `us-h1b` | US: H-1B or another employer-sponsored visa | "no sponsorship" and "must be a US citizen / authorized without sponsorship" wording; posted pay below `minSalary`. |
| `us-opt` | US: F-1 OPT or STEM OPT | "no sponsorship" wording; E-Verify mentions. STEM OPT needs an E-Verify employer: tell the user they can check it on e-verify.gov. |
| `us-green-card` | US: employer-sponsored permanent residence (PERM) | As `us-h1b`. |

Every flag starts with `pathway:` in rank_jobs.py's output, find_jobs.py's results and the daily digest. They never
change the fit score.

## UK sponsor register

```
python scripts/sponsor_check.py --folder "<folder>" "Company A" "Company B"
```

Downloads the public register from gov.uk into `.cache/` (refreshed weekly) and reports `listed`, `possible` or
`not found` with the routes. rank_jobs.py runs it for every UK posting when `requireSponsor` is set.

## At the checkpoint and in changes.md

With a pathway set, add one line per posting to the checkpoint and a section at the end of changes.md:

```
## Pathway check (not immigration advice)
- Goal: <pathway.goal>
- Likely occupation code: <NOC 2021 code and title, TEER n | SOC 2020 code and title> (likely; confirm on <the NOC site | gov.uk>)
- Flags: <the pathway flags from the ranking, or "none">
- To check yourself: <for example "salary against the going rate for this SOC code on gov.uk", "whether this employer will sponsor">
```

Official places to confirm (give the user the name, not advice):
Canada, the NOC site (noc.esdc.gc.ca) and IRCC's Express Entry and PNP pages; UK, gov.uk's Skilled Worker visa pages,
"Skilled Worker visa: eligible occupations" and the register of licensed sponsors; US, uscis.gov and e-verify.gov.

## Applications and forms

Work authorization answers still come only from profile.json (`workAuthorized`, `needsSponsorship`,
`workAuthDetails`). A pathway doesn't change how a form question is answered.
