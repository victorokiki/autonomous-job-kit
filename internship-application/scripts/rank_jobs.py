#!/usr/bin/env python3
"""Score how well a job posting fits the user, from 0 to 100, with the reasons behind the number.

Used by find_jobs.py and job_digest.py; it can also score postings already fetched by fetch_posting.py:
  python rank_jobs.py --folder "JOB_SEARCH_FOLDER" POSTING.md [POSTING.md ...]

The score is deliberately simple and explainable, so the user can see why a job is near the top:
  title       0-30  the title matches one of the user's tracks in search.json, weighted by that track's priority
  skills      0-30  the share of the posting's tools and skills that also appear in the master resume
  location    0-12  near home (search.json local_places) > same province/state/region > remote in the country > elsewhere
                    in the country (search.json "country": Canada, United States or United Kingdom)
  experience  0-20  years of experience the posting asks for (2 or fewer is full marks, more than 5 is none)
  recency     0-8   newer postings first

Skills come from a fixed vocabulary (VOCAB, plus search.json "extra_skills"), matched on word boundaries in the master resume and the posting.
Posting skills missing from the master are reported as gaps: never add them to a resume.
flags lists sentences worth a look before applying (citizenship or permanent residence, clearance, P.Eng.,
co-op or student-only, French); they don't change the score, because only the user's profile can settle them.
"""
import argparse
import datetime as dt
import glob
import html
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.join(_HERE, '..', '..', 'lib')):
    if os.path.isdir(os.path.join(_p, 'jobkit')):
        sys.path.insert(0, os.path.abspath(_p))
        break

VOCAB = [
    # engineering and energy
    'mechanical engineering', 'energy modelling', 'energy modeling', 'building energy modelling', 'building energy modeling',
    'designbuilder', 'energyplus', 'openstudio', 'wufi', 'retscreen', 'homer', 'pvsyst', 'helioscope', 'ies ve', 'hvac', 'ashrae',
    'bcbc', 'vbbl', 'step code', 'building science', 'building envelope', 'thermodynamics', 'heat transfer', 'fluid mechanics',
    'cfd', 'fea', 'ansys', 'autocad', 'solidworks', 'revit', 'inventor', 'matlab', 'simulink', 'solar', 'photovoltaic', 'pv',
    'battery', 'batteries', 'energy storage', 'bess', 'grid', 'distributed energy', 'der', 'microgrid', 'ieee 2030.5', 'modbus',
    'scada', 'plc', 'iot', 'inverter', 'renewable energy', 'renewables', 'wind', 'hydro', 'hydrogen', 'electrification',
    'heat pump', 'energy efficiency', 'energy audit', 'energy management', 'iso 50001', 'sustainability', 'ghg', 'carbon',
    'emissions', 'decarbonization', 'lca', 'life cycle assessment', 'esg', 'commissioning', 'preventive maintenance',
    'maintenance', 'troubleshooting', 'p.eng', 'eit', 'egbc', 'technical reporting', 'feasibility',
    # data and software
    'python', 'sql', 'excel', 'power bi', 'tableau', 'looker', 'pandas', 'numpy', 'matplotlib', 'scikit-learn', 'tensorflow',
    'pytorch', 'machine learning', 'deep learning', 'statistics', 'statistical analysis', 'data analysis', 'data analytics',
    'data cleaning', 'data validation', 'data quality', 'data governance', 'data modeling', 'data modelling', 'etl',
    'data pipelines', 'data warehouse', 'snowflake', 'dbt', 'airflow', 'spark', 'aws', 'azure', 'gcp', 'docker', 'kubernetes',
    'git', 'github', 'javascript', 'typescript', 'node.js', 'react', 'flask', 'django', 'fastapi', 'rest api', 'rest apis',
    'api', 'apis', 'java', 'c++', 'c#', 'linux', 'bash', 'sqlite', 'postgresql', 'mysql', 'mongodb', 'pytest', 'unit testing',
    'automation', 'web scraping', 'vba', 'macros', 'google sheets', 'power query', 'dax', 'kpi', 'kpis', 'dashboards',
    'dashboard', 'business intelligence', 'reporting',
    # business, governance and operations
    'governance', 'compliance', 'risk management', 'risk register', 'internal controls', 'internal audit', 'audit', 'cobit',
    'coso', 'iso 27001', 'policy', 'records management', 'regulatory', 'confidential', 'project management', 'agile', 'scrum',
    'stakeholder', 'process improvement', 'documentation', 'microsoft office', 'word', 'sharepoint', 'confluence', 'jira',
    'salesforce', 'hubspot', 'zendesk', 'servicenow', 'freshdesk', 'crm', 'sap', 'erp', 'data entry', 'customer service',
    'customer support', 'technical support', 'pos', 'inventory', 'logistics', 'shipping',
]
# Words too ambiguous to count as skills on their own in a posting ("word" as in "word of mouth")
WEAK = {'word', 'api', 'apis', 'pos', 'policy', 'documentation', 'grid', 'wind', 'hydro', 'reporting', 'maintenance', 'audit'}

SENIOR_YEARS = re.compile(r'(\d{1,2})\s*\+?\s*(?:-|–|to)?\s*(?:\d{1,2}\s*)?(?:\+\s*)?years?(?:\'|’)?\s+(?:of\s+)?'
                          r'(?:[a-z/&,-]+\s+){0,6}?(?:experience|exp\b)', re.I)
ENTRY = re.compile(r'\b(new grad|new graduate|recent graduate|entry[- ]level|junior|jr\.?|graduate engineer|engineer in training|'
                   r'eit\b|intern|internship|co-?op|student|trainee|associate|level i\b|level 1\b)', re.I)
FLAGS = [
    ('citizenship or permanent residence', re.compile(r'\b(canadian citizens?(hip)?|permanent residen\w*)\b[^.]{0,80}\b(required|must|only|eligible)\b|'
                                                     r'\b(must|required to) be (a )?(canadian citizen|permanent resident)', re.I)),
    ('U.S. work authorization', re.compile(r'\b(us|u\.s\.|united states) (citizen\w*|work authori[sz]ation|persons?)\b', re.I)),
    ('no visa sponsorship', re.compile(r'\b(unable|not able|cannot|can\'t|do not|don\'t|will not|won\'t|not)\b[^.]{0,30}\b(offer|provide|sponsor)\w*\b[^.]{0,30}\b(sponsor\w*|visas?|work permits?)\b|'
                                       r'\bno (visa )?sponsorship\b|\bsponsorship (is )?not (available|offered|provided)\b', re.I)),
    ('visa sponsorship mentioned', re.compile(r'\b(visa|skilled worker|h-?1b|work permit|lmia) sponsorship (is )?(available|offered|provided|considered)\b|'
                                              r'\b(we|will|can) (offer|provide|consider) (visa )?sponsorship\b|\bcertificate of sponsorship\b', re.I)),
    ('UK right to work', re.compile(r'\bright to work in the (uk|united kingdom)\b', re.I)),
    ('security clearance', re.compile(r'\b(secret|reliability|enhanced reliability|security) (clearance|status|screening)\b', re.I)),
    ('P.Eng. required', re.compile(r'\bp\.? ?eng\.?\b[^.]{0,60}\b(required|must|designation)\b|\b(registered|licensed) professional engineer\b', re.I)),
    ('co-op or student only', re.compile(r'\b(must be|currently) (enrolled|registered)\b|\bco-?op (program|students?|term|placement)\b|'
                                         r'\breturning to (full-time )?(school|studies)\b', re.I)),
    ('French required', re.compile(r'\b(bilingual|french)\b[^.]{0,40}\b(required|must|essential|an asset)\b', re.I)),
    ('driver\'s licence', re.compile(r'\bdriver\'?s licen[cs]e\b|\bclass 5\b', re.I)),
    # Users aiming for permanent residence often need a permanent full-time role; a temporary one is worth a look first.
    ('temporary or contract', re.compile(r'\b(temporary|fixed[- ]term|term position|\d{1,2}[- ]month (contract|term)|contract (role|position)|'
                                         r'maternity leave|parental leave|seasonal)\b', re.I)),
]


def text_of(s):
    """Plain lower-case text from HTML, LaTeX or markdown."""
    s = html.unescape(html.unescape(str(s or '')))
    s = re.sub(r'<[^>]+>', ' ', s)
    s = re.sub(r'\\[a-zA-Z]+\*?', ' ', s).replace('\\&', '&').replace('\\%', '%')
    return re.sub(r'\s+', ' ', s).lower()


def terms_in(text):
    found = set()
    for t in VOCAB:
        if re.search(r'(?<![a-z0-9])' + re.escape(t) + r'(?![a-z0-9])', text):
            found.add(t)
    # Spelling variants count once
    for a, b in (('energy modeling', 'energy modelling'), ('building energy modeling', 'building energy modelling'),
                 ('data modelling', 'data modeling'), ('rest apis', 'rest api'), ('apis', 'api'), ('kpis', 'kpi'),
                 ('dashboards', 'dashboard'), ('batteries', 'battery'), ('renewables', 'renewable energy')):
        if a in found:
            found.discard(a)
            found.add(b)
    return found


def master_text(folder):
    """The master resume's text: resume/*.tex (all files), else a .docx in resume/."""
    res = os.path.join(folder, 'resume')
    tex = glob.glob(os.path.join(res, '**', '*.tex'), recursive=True)
    if tex:
        return text_of(' '.join(open(p, encoding='utf-8', errors='replace').read() for p in tex))
    for p in glob.glob(os.path.join(res, '*.docx')):
        try:
            from docx import Document
            return text_of(' '.join(par.text for par in Document(p).paragraphs))
        except Exception:
            pass
    return ''


_FOLDER = None   # the job-search folder of the last load_search(), for the UK sponsor register cache
_SPONSORS = {}   # folder -> register dict, or an error string


def load_search(folder):
    global _FOLDER
    _FOLDER = folder
    try:
        search = json.load(open(os.path.join(folder, 'search.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    # search.json "extra_skills": the user's own tools and skills that VOCAB doesn't know yet ("figma", "quickbooks")
    for t in search.get('extra_skills') or []:
        t = str(t).strip().lower()
        if t and t not in VOCAB:
            VOCAB.append(t)
    return search


def words_in(phrase, text):
    """phrase appears in text as whole words ("der" doesn't match "order", "eit" doesn't match "reit")."""
    p = phrase.strip()
    return bool(p) and re.search(r'(?<![a-z0-9])' + re.escape(p) + r'(?![a-z0-9])', text) is not None


def best_track(title, search):
    t = re.sub(r'\s+', ' ', str(title or '').lower())
    best = (None, 0.0)
    for name, tr in (search.get('tracks') or {}).items():
        if any(words_in(k.lower(), t) for k in tr.get('titles', [])) and tr.get('priority', 0.5) > best[1]:
            best = (name, float(tr.get('priority', 0.5)))
    return best


def excluded(title, search):
    t = re.sub(r'\s+', ' ', str(title or '').lower())
    return next((w for w in search.get('exclude_titles', []) if words_in(w.lower().rstrip('.'), t)), None)


CANADA = re.compile(r'\bcanada\b|\bcanadian\b|\b(ontario|quebec|québec|british columbia|alberta|manitoba|saskatchewan|nova scotia|'
                    r'new brunswick|newfoundland|prince edward island|yukon|nunavut|northwest territories)\b|'
                    r'[,(]\s*(on|bc|qc|ab|mb|sk|ns|nb|nl|pe|yt|nu|nt)\b\)?|\b(toronto|vancouver|montreal|montréal|ottawa|'
                    r'calgary|edmonton|waterloo|burnaby|surrey|winnipeg|halifax|mississauga|markham|kelowna|kitchener|'
                    r'victoria, bc|richmond, bc|regina|saskatoon|quebec city|gatineau)\b', re.I)
US_STATE = re.compile(r',\s*(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|'
                      r'OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)\b')
ELSEWHERE = re.compile(r'\b(united states|usa|u\.s\.|uk|united kingdom|england|ireland|germany|france|netherlands|spain|portugal|'
                       r'poland|india|china|japan|singapore|australia|mexico|brazil|colombia|argentina|chile|costa rica|'
                       r'philippines|israel|emea|apac|latam|europe|london|dublin|berlin|amsterdam|paris|bangalore|bengaluru|'
                       r'sydney|tokyo|new york|san francisco|seattle|austin|chicago|boston)\b', re.I)


PROVINCE_NAMES = {'on': 'ontario', 'qc': 'quebec', 'bc': 'british columbia', 'ab': 'alberta', 'mb': 'manitoba',
                  'sk': 'saskatchewan', 'ns': 'nova scotia', 'nb': 'new brunswick', 'nl': 'newfoundland',
                  'pe': 'prince edward island', 'yt': 'yukon', 'nu': 'nunavut', 'nt': 'northwest territories'}


US_STATE_NAMES = re.compile(r'\b(alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|georgia|hawaii|'
                            r'idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|'
                            r'minnesota|mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|'
                            r'new york|north carolina|north dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|'
                            r'south carolina|south dakota|tennessee|texas|utah|vermont|virginia|washington|west virginia|'
                            r'wisconsin|wyoming|district of columbia)\b', re.I)
USA = re.compile(r'\b(united states|usa|u\.s\.a?\.?|us only|us-remote|remote,? us\b|san francisco|new york|seattle|austin|chicago|'
                 r'boston|los angeles|atlanta|denver|dallas|houston|miami|philadelphia|washington,? d\.?c\.?|bay area)\b', re.I)
UK = re.compile(r'\b(united kingdom|uk|u\.k\.|great britain|britain|england|scotland|wales|northern ireland|london|manchester|'
                r'birmingham|leeds|glasgow|edinburgh|bristol|cardiff|belfast|liverpool|newcastle|sheffield|nottingham|'
                r'cambridge|oxford|reading|milton keynes|leicester|southampton|brighton|aberdeen|coventry)\b', re.I)
US_STATE_CODES = dict(zip(
    'al ak az ar ca co ct de fl ga hi id il in ia ks ky la me md ma mi mn ms mo mt ne nv nh nj nm ny nc nd oh ok or pa ri sc sd '
    'tn tx ut vt va wa wv wi wy dc'.split(),
    ['alabama', 'alaska', 'arizona', 'arkansas', 'california', 'colorado', 'connecticut', 'delaware', 'florida', 'georgia',
     'hawaii', 'idaho', 'illinois', 'indiana', 'iowa', 'kansas', 'kentucky', 'louisiana', 'maine', 'maryland',
     'massachusetts', 'michigan', 'minnesota', 'mississippi', 'missouri', 'montana', 'nebraska', 'nevada', 'new hampshire',
     'new jersey', 'new mexico', 'new york', 'north carolina', 'north dakota', 'ohio', 'oklahoma', 'oregon', 'pennsylvania',
     'rhode island', 'south carolina', 'south dakota', 'tennessee', 'texas', 'utah', 'vermont', 'virginia', 'washington',
     'west virginia', 'wisconsin', 'wyoming', 'district of columbia']))
COUNTRIES = {
    # code: display name, the remote wording Remotive uses, SmartRecruiters' country filter, and the job-board sources that apply
    'CA': {'name': 'Canada', 'remotive': r'canada|worldwide|anywhere|north america|americas', 'sr': 'ca'},
    'US': {'name': 'the US', 'remotive': r'\busa?\b|united states|worldwide|anywhere|north america|americas', 'sr': 'us'},
    'GB': {'name': 'the UK', 'remotive': r'\buk\b|united kingdom|europe|emea|worldwide|anywhere', 'sr': 'gb'},
}
COUNTRY_ALIASES = {'canada': 'CA', 'ca': 'CA', 'united states': 'US', 'usa': 'US', 'us': 'US', 'u.s.': 'US', 'america': 'US',
                   'united kingdom': 'GB', 'uk': 'GB', 'gb': 'GB', 'great britain': 'GB', 'britain': 'GB', 'england': 'GB',
                   'scotland': 'GB', 'wales': 'GB', 'northern ireland': 'GB'}


def country_code(search):
    """search.json "country" as CA, US or GB (default CA, the kit's original setting)."""
    return COUNTRY_ALIASES.get(str(search.get('country') or 'Canada').strip().lower(), 'CA')


def in_country(code, loc):
    low = loc.lower()
    canada = bool(CANADA.search(low))
    us = bool(US_STATE.search(loc) or US_STATE_NAMES.search(low) or USA.search(low))
    if code == 'CA':
        return canada and not (us and not canada)
    if code == 'US':
        # ", CA" is California here; a Canadian province or "Canada" alone isn't the US
        return us and not (canada and not (US_STATE.search(loc) or USA.search(low)))
    if code == 'GB':
        return bool(UK.search(loc))  # case-sensitive "UK" is fine: the regex is case-insensitive anyway
    return False


def place_fit(location, search):
    """local, region, remote-country, country, remote, or None when it isn't in the search country (or doesn't say where).

    The country is search.json "country" (Canada, United States or United Kingdom). A location that lists several places
    counts by its best one in that country ("Remote, Canada; Remote, United States" is remote in Canada for a Canadian
    search). "Hybrid" or "Remote - Colombia" alone is not in the country."""
    loc = str(location or '')
    places = [p for p in re.split(r'[;|]|\s/\s', loc) if p.strip()] or [loc]
    ranks = {'local': 5, 'region': 4, 'remote-country': 3, 'country': 2, 'remote': 1}
    best = None
    for p in places:
        r = _one_place(p, search)
        if r and (best is None or ranks[r] > ranks[best]):
            best = r
    return best


def _one_place(loc, search):
    low = loc.lower()
    code = country_code(search)
    region = str(search.get('province') or search.get('state') or search.get('region') or '').lower().strip()
    inside = in_country(code, loc)
    remote = re.search(r'\b(remote|anywhere|work from home|telework|home[- ]based)\b', low)
    if inside and any(re.search(r'(?<![a-z])' + re.escape(p) + r'(?![a-z])(?! hill)', low) for p in search.get('local_places', [])):
        return 'local'
    if inside and region:
        name = {'CA': PROVINCE_NAMES, 'US': US_STATE_CODES}.get(code, {}).get(region, '')
        if (len(region) <= 3 and re.search(rf'[,(]\s*{re.escape(region)}\b', low)) or (name and name in low) \
                or (len(region) > 3 and region in low):
            return 'region'
    if inside:
        return 'remote-country' if remote else 'country'
    if remote and not ELSEWHERE.search(low) and not re.search(r'\bremote\s*[-–:,]\s*\w', low):
        return 'remote'  # "Remote" with no country; "Remote - Colombia" names another country
    return None


NOC = re.compile(r'\bnoc\b(?:\s*2021)?[^0-9]{0,25}(\d{5})\b', re.I)
MONEY = re.compile(r'(?:£|\$|us\$|c\$|cad\s?|gbp\s?|usd\s?)\s?(\d{1,3}(?:,\d{3})+|\d{2,3}(?:\.\d)?\s?k|\d{4,6})(?!\d)', re.I)


def salary_max(text):
    """The highest yearly amount the posting names ("£38,000 - £45,000" -> 45000), or None. Hourly pay is skipped."""
    vals = []
    for m in MONEY.finditer(text):
        after = text[m.end(): m.end() + 25].lower()
        if re.match(r'\s*(/|per|an|a)\s*(hour|hr|h\b|day|week|month)', after):
            continue
        raw = m.group(1).lower().replace(',', '').replace(' ', '')
        v = float(raw[:-1]) * 1000 if raw.endswith('k') else float(raw)
        if 10000 <= v <= 1000000:
            vals.append(int(v))
    return max(vals) if vals else None


def sponsor_register():
    """The UK register of licensed sponsors for the current folder, loaded once (sponsor_check.py), or an error string."""
    if _FOLDER not in _SPONSORS:
        try:
            import sponsor_check
            _SPONSORS[_FOLDER] = sponsor_check.load_register(_FOLDER or '.')
        except Exception as e:
            _SPONSORS[_FOLDER] = f'{type(e).__name__}: {str(e)[:80]}'
    return _SPONSORS[_FOLDER]


def pathway_flags(posting, desc, search):
    """Flags for the user's immigration pathway in search.json "pathway" (references/pathways.md). Checks only:
    they never change the score and never decide eligibility, which the user confirms on official sources."""
    pw = search.get('pathway') or {}
    kind = str(pw.get('type') or '').lower()
    if not kind or kind == 'none':
        return []
    out = []
    code = country_code(search)
    # NOC 2021: the second digit of the five-digit code is the TEER (21231 -> TEER 1). Job Bank postings print the code.
    m = NOC.search(desc)
    if m and code == 'CA':
        teer = int(m.group(1)[1])
        ok = teer <= 3
        note = '' if ok or not kind.startswith('ca-cec') else '; CEC counts TEER 0-3 work only'
        out.append(f'pathway: NOC {m.group(1)} is TEER {teer}{note} (from the posting; confirm on the NOC site)')
    elif code == 'CA' and kind.startswith('ca-'):
        out.append('pathway: no NOC code in the posting; Claude gives the likely NOC and TEER at the checkpoint (confirm on the NOC site)')
    if code == 'CA' and kind.startswith('ca-') and re.search(r'\bpart[- ]time\b', desc) and not re.search(r'\bfull[- ]time\b', desc):
        out.append('pathway: part-time; programs count hours, so check how this adds up for you')
    if pw.get('requireSponsor') or kind in ('uk-skilled-worker', 'us-h1b'):
        if code == 'GB' and posting.get('company'):
            reg = sponsor_register()
            if isinstance(reg, dict):
                import sponsor_check
                r = sponsor_check.check(posting['company'], reg)
                routes = sorted({e['route'] for e in r['entries']})[:3]
                if r['status'] == 'listed':
                    out.append(f'pathway: {posting["company"]} is on the UK sponsor register ({", ".join(routes)})')
                elif r['status'] == 'possible':
                    out.append(f'pathway: a similar name is on the UK sponsor register ({r["entries"][0]["name"]}): check it is this employer')
                else:
                    out.append(f'pathway: {posting["company"]} not found on the UK sponsor register (it may sponsor under another legal name: check)')
            else:
                out.append(f'pathway: couldn\'t check the UK sponsor register ({reg})')
    try:
        low_pay = int(pw.get('minSalary') or 0)
    except (TypeError, ValueError):
        low_pay = 0
    top = salary_max(desc)
    if low_pay and top and top < low_pay:
        out.append(f'pathway: posted pay tops out at {top:,}, below your minimum of {low_pay:,} (search.json pathway.minSalary)')
    elif low_pay and not top and kind == 'uk-skilled-worker':
        out.append('pathway: no yearly salary in the posting; Skilled Worker needs the salary to meet the thresholds: ask or check')
    codes = [str(c) for c in pw.get('eligibleCodes') or []]
    if codes and m and m.group(1) not in codes:
        out.append(f'pathway: NOC {m.group(1)} is not in your eligibleCodes list')
    return out


def years_required(text):
    # Dates ("Posted: 2026-09-01") would otherwise lend their last digits to "8+ years" and read as "01 ... years"
    text = re.sub(r'\b\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\b', ' ', str(text))
    nums = [int(m.group(1)) for m in SENIOR_YEARS.finditer(text) if int(m.group(1)) <= 20]
    return min(nums) if nums else None


def score(posting, master, search, today=None):
    """posting: dict with title, location, description (any of HTML/plain), posted (YYYY-MM-DD or '')."""
    today = today or dt.date.today()
    title = posting.get('title') or posting.get('role') or ''
    desc = text_of(posting.get('description', ''))
    full = text_of(title) + ' ' + desc
    parts, reasons = {}, []

    track, prio = best_track(title, search)
    parts['title'] = round(30 * prio) if track else 0
    reasons.append(f'title fits {track}' if track else 'title outside your tracks')

    master_terms = terms_in(master)
    post_terms = terms_in(full)
    strong = {t for t in post_terms if t not in WEAK}
    matched = sorted(strong & master_terms)
    gaps = sorted(strong - master_terms)
    if len(strong) >= 3:
        share = len(matched) / (len(strong) + 1.5)  # "3 of 3" is weaker evidence than "12 of 13"
        parts['skills'] = round(30 * min(1.0, share * 1.2))
        reasons.append(f'{len(matched)} of {len(strong)} skills match')
    else:
        parts['skills'] = 13  # no description, or too little to judge
        reasons.append('skills unknown (short or no description)')

    fit = place_fit(posting.get('location', ''), search)
    parts['location'] = {'local': 12, 'region': 10, 'remote-country': 9, 'country': 5, 'remote': 4}.get(fit, 0)
    cname = COUNTRIES[country_code(search)]['name']
    reasons.append({'local': 'near home', 'region': 'in your province or region', 'remote-country': f'remote in {cname}',
                    'country': f'elsewhere in {cname}', 'remote': 'remote (country unclear)'}.get(fit, f'outside {cname}'))

    yrs = years_required(desc)
    if yrs is None:
        parts['experience'] = 20 if ENTRY.search(title) else 14
    else:
        parts['experience'] = 20 if yrs <= 2 else 15 if yrs == 3 else 8 if yrs == 4 else 4 if yrs == 5 else 0
        reasons.append(f'asks for {yrs}+ years')

    try:
        age = (today - dt.date.fromisoformat(str(posting.get('posted', ''))[:10])).days
        parts['recency'] = 8 if age <= 3 else 6 if age <= 7 else 4 if age <= 14 else 2 if age <= 30 else 0
    except ValueError:
        parts['recency'] = 3

    flags = []
    if re.search(r'\bco-?op\b', title, re.I):  # co-op roles usually require enrolment in a school co-op program
        flags.append('co-op or student only: "co-op" in the title; usually needs enrolment in a school co-op program')
    for name, rx in FLAGS:
        if flags and name == 'co-op or student only' and flags[0].startswith(name):
            continue
        m = rx.search(desc)
        if m:
            s = desc[max(0, m.start() - 80): m.end() + 80].strip()
            flags.append(f'{name}: "...{s}..."')
    flags += pathway_flags(posting, desc, search)
    try:  # scam warning signs (jobkit.redflags), shown like the other flags; they don't change the score
        from jobkit.redflags import red_flags
        flags += [f"scam warning: {r['flag']}: \"{r['quote']}\"" for r in
                  red_flags(posting.get('description', ''), url=posting.get('url'), company=posting.get('company'),
                            role=title)]
    except ImportError:
        pass
    return {'score': sum(parts.values()), 'parts': parts, 'track': track, 'place': fit, 'years_required': yrs,
            'matched_skills': matched, 'gaps': gaps, 'flags': flags, 'why': '; '.join(reasons)}


def posting_from_md(path):
    """Read a job-posting.md written by fetch_posting.py."""
    t = open(path, encoding='utf-8', errors='replace').read()
    head = re.search(r'^#\s*(.+)$', t, re.M)
    def field(name):
        m = re.search(rf'^\s*[-*]?\s*\**{name}\**\s*:\s*(.+)$', t, re.M | re.I)
        return m.group(1).strip() if m else ''
    title = field('Role') or (head.group(1).split(' at ')[0] if head else '')
    company = field('Company') or (head.group(1).split(' at ', 1)[1].strip() if head and ' at ' in head.group(1) else '')
    return {'title': title, 'company': company, 'location': field('Location'), 'posted': field('Posted')[:10], 'description': t}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--folder', default='.')
    ap.add_argument('postings', nargs='+')
    a = ap.parse_args()
    folder = os.path.abspath(a.folder)
    master, search = master_text(folder), load_search(folder)
    if not master:
        print(json.dumps({'ok': False, 'error': f'no master resume in {folder}/resume'}))
        sys.exit(1)
    out = []
    for p in a.postings:
        r = score(posting_from_md(p), master, search)
        r['file'] = p
        out.append(r)
    out.sort(key=lambda r: -r['score'])
    print(json.dumps({'ok': True, 'results': out}, indent=1))


if __name__ == '__main__':
    main()
