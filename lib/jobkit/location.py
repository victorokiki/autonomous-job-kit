"""Matching the location on the resume and letter to where the job is.

When a posting is on-site or hybrid in another city and the user is willing to relocate, the resume's contact line
and the letter's contact line read "Surrey, BC · Relocating to Toronto, ON" instead of only the user's own city. The
user's real city always stays (forms, background checks and interviews use it); remote jobs, jobs in the user's own
metro area and users who won't relocate keep the plain city line.

Profile keys: city, state (province or state), willingToRelocate ("yes"/"no"), and optionally relocationWording, a
pattern with {city} (default "Relocating to {city}"), e.g. "Open to relocating to {city}".
"""
import re

from .text import norm

PROVINCES = {
    'alberta': 'AB', 'british columbia': 'BC', 'manitoba': 'MB', 'new brunswick': 'NB',
    'newfoundland and labrador': 'NL', 'newfoundland': 'NL', 'nova scotia': 'NS', 'ontario': 'ON',
    'prince edward island': 'PE', 'quebec': 'QC', 'québec': 'QC', 'saskatchewan': 'SK',
    'northwest territories': 'NT', 'nunavut': 'NU', 'yukon': 'YT',
}
STATES = {
    'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR', 'california': 'CA', 'colorado': 'CO',
    'connecticut': 'CT', 'delaware': 'DE', 'florida': 'FL', 'georgia': 'GA', 'hawaii': 'HI', 'idaho': 'ID',
    'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA', 'kansas': 'KS', 'kentucky': 'KY', 'louisiana': 'LA',
    'maine': 'ME', 'maryland': 'MD', 'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN',
    'mississippi': 'MS', 'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV',
    'new hampshire': 'NH', 'new jersey': 'NJ', 'new mexico': 'NM', 'new york': 'NY', 'north carolina': 'NC',
    'north dakota': 'ND', 'ohio': 'OH', 'oklahoma': 'OK', 'oregon': 'OR', 'pennsylvania': 'PA',
    'rhode island': 'RI', 'south carolina': 'SC', 'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX',
    'utah': 'UT', 'vermont': 'VT', 'virginia': 'VA', 'washington': 'WA', 'west virginia': 'WV',
    'wisconsin': 'WI', 'wyoming': 'WY', 'district of columbia': 'DC',
}
REGIONS = {**STATES, **PROVINCES}
CODES = set(REGIONS.values())

# Cities a recruiter treats as one commute area. A job anywhere in the user's group needs no relocation line.
METROS = [
    {'vancouver', 'surrey', 'burnaby', 'richmond', 'coquitlam', 'port coquitlam', 'port moody', 'new westminster',
     'north vancouver', 'west vancouver', 'delta', 'langley', 'white rock', 'maple ridge', 'pitt meadows',
     'abbotsford', 'metro vancouver', 'greater vancouver', 'lower mainland'},
    {'toronto', 'mississauga', 'brampton', 'markham', 'vaughan', 'richmond hill', 'oakville', 'scarborough',
     'north york', 'etobicoke', 'pickering', 'ajax', 'whitby', 'oshawa', 'burlington', 'milton', 'newmarket',
     'aurora', 'concord', 'gta', 'greater toronto area'},
    {'montreal', 'montréal', 'laval', 'longueuil', 'brossard', 'pointe claire', 'dorval', 'saint laurent',
     'greater montreal'},
    {'ottawa', 'gatineau', 'kanata', 'nepean', 'orleans'},
    {'calgary', 'airdrie', 'cochrane', 'okotoks'},
    {'edmonton', 'st albert', 'sherwood park', 'leduc', 'spruce grove', 'nisku'},
    {'winnipeg', 'steinbach', 'selkirk'},
    {'kitchener', 'waterloo', 'cambridge', 'guelph'},
    {'victoria', 'saanich', 'langford', 'esquimalt', 'colwood', 'sidney'},
    {'halifax', 'dartmouth', 'bedford'},
    {'quebec city', 'ville de quebec', 'levis', 'lévis'},
    {'hamilton', 'stoney creek', 'ancaster', 'dundas'},
    {'seattle', 'bellevue', 'redmond', 'kirkland', 'tacoma', 'everett'},
    {'san francisco', 'oakland', 'san jose', 'palo alto', 'mountain view', 'sunnyvale', 'menlo park',
     'santa clara', 'cupertino', 'redwood city', 'bay area', 'san francisco bay area'},
    {'new york', 'new york city', 'nyc', 'brooklyn', 'manhattan', 'jersey city', 'hoboken'},
    {'london', 'greater london'},
]

_REMOTE = re.compile(r'\b(remote|work from home|wfh|anywhere|telecommut\w*|virtual)\b', re.I)
_ONSITE_HINT = re.compile(r'\b(on[- ]?site|hybrid|in[- ]office)\b', re.I)
_COUNTRY = re.compile(r'^(canada|ca|can|united states|usa|us|united kingdom|uk|gb|england|scotland|wales)$', re.I)


def _region_code(word):
    w = (word or '').strip().rstrip('.')
    if w.upper() in CODES and len(w) == 2:
        return w.upper()
    return REGIONS.get(norm(w), '') or REGIONS.get(w.lower(), '')


def parse_place(location):
    """First place in a posting's location text as {"city", "region", "remote", "label"}.

    "Toronto, ON, Canada (hybrid)" -> city Toronto, region ON. "Remote - Canada" -> remote. A location that names
    both an office and remote ("Toronto, ON or Remote") counts as remote. Unreadable text gives city "".
    """
    raw = str(location or '').strip()
    out = {'city': '', 'region': '', 'remote': False, 'label': ''}
    if not raw or raw.lower() in ('not stated', 'unknown'):
        return out
    first = re.split(r';|\bor\b|/|\|', raw, maxsplit=1)[0]
    mode = re.search(r'\(([^)]*)\)', raw)
    if _REMOTE.search(raw) and not (mode and _ONSITE_HINT.search(mode.group(1)) and not _REMOTE.search(mode.group(1))):
        if not _ONSITE_HINT.search(raw) or _REMOTE.search(first):
            out['remote'] = True
            return out
    first = re.sub(r'\([^)]*\)', ' ', first)
    parts = [p.strip() for p in re.split(r',|\s+-\s+', first) if p.strip()]
    parts = [p for p in parts if not _COUNTRY.match(p) and not re.fullmatch(r'(on[- ]?site|hybrid|in[- ]office|office)', p, re.I)]
    if not parts:
        return out
    city, region = parts[0], ''
    for p in parts[1:]:
        code = _region_code(p)
        if code:
            region = code
            break
    if not region:
        m = re.match(r'^(.*?)\s+([A-Z]{2})$', city)
        if m and m.group(2) in CODES:
            city, region = m.group(1).strip(), m.group(2)
    if _region_code(city) and not region:
        return out
    city = re.sub(r'\s+', ' ', city).strip(' .')
    out.update(city=city, region=region, label=', '.join(x for x in (city, region) if x))
    return out


def _metro(city):
    c = norm(city)
    for group in METROS:
        if c in {norm(x) for x in group}:
            return group
    return None


def same_area(home_city, home_region, job_city, job_region):
    """True when the job is in the user's city or its commute area (metro list above)."""
    if not job_city:
        return True
    if norm(home_city) == norm(job_city):
        return not (home_region and job_region and _region_code(home_region) != job_region)
    g = _metro(home_city)
    return bool(g and _metro(job_city) is g)


def home_line(profile):
    """The user's own "City, ST" (state or province shortened when it is a known one)."""
    city = (profile.get('city') or '').strip()
    region = (profile.get('state') or '').strip()
    region = _region_code(region) or region
    return ', '.join(x for x in (city, region) if x)


def location_line(profile, posting_location):
    """{"line", "relocating", "job_city", "why"} for the resume's and letter's contact line.

    line is "Surrey, BC · Relocating to Toronto, ON" when the job is on-site or hybrid outside the user's area and
    willingToRelocate is "yes"; otherwise the user's own "City, ST".
    """
    profile = profile or {}
    home = home_line(profile)
    place = parse_place(posting_location)
    base = {'line': home, 'relocating': False, 'job_city': place['label'], 'why': ''}
    if place['remote']:
        return {**base, 'why': 'remote job'}
    if not place['city']:
        return {**base, 'why': 'job location not stated'}
    if same_area(profile.get('city'), profile.get('state'), place['city'], place['region']):
        return {**base, 'why': 'job is in your area'}
    if str(profile.get('willingToRelocate') or '').strip().lower() not in ('yes', 'y', 'true'):
        return {**base, 'why': 'willingToRelocate is not "yes"'}
    pattern = (profile.get('relocationWording') or '').strip() or 'Relocating to {city}'
    if '{city}' not in pattern:
        pattern += ' {city}'
    note = pattern.replace('{city}', place['label'])
    line = f'{home} · {note}' if home else note
    return {**base, 'line': line, 'relocating': True, 'why': f'job is in {place["label"]}'}
