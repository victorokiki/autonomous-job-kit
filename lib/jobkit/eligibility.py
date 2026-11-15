"""Eligibility screen: does any sentence in a posting rule the user out (citizenship, visa, sponsorship, degree level)?

    from jobkit.eligibility import screen, user_status
    screen(description, profile, role='', location='') ->
        {"screen": "ok|check|skip", "why": ["<sentence> -> <rule>"], "check": ["<sentence>"], "status": {...}}

Principles
- "skip" only when a sentence plainly rules this user out; "check" when a person should judge (vague, soft or
  conditional wording, or the profile doesn't say enough); otherwise "ok". The sentences are always returned.
- Sponsorship wording alone never skips a student below their final year (internships often need no sponsorship,
  e.g. CPT in the US or a co-op work permit in Canada).
- Alternatives such as "or authorized to work", "or legally entitled to work", "or eligible" never skip.
- Equal-opportunity boilerplate ("without regard to citizenship status") is ignored.

Rules by country
- US: F-1 / OPT / CPT excluded (user on F-1); US citizenship, permanent residence / green card, "US person"
  (ITAR/EAR) or a security clearance required (user not a citizen / PR); graduate-students-only role (user is an
  undergraduate).
- Canada: Canadian citizens / permanent residents only (user is a temporary resident: study/work permit, PGWP;
  "check" when the profile doesn't say).
- UK: right to work in the UK / no visa sponsorship (user needs sponsorship: skip when explicit, else check);
  "sponsorship available" is a note only.

The user's status comes from profile.json: authCountry, workAuthorized, workAuthDetails (their own words, e.g.
"F-1 student, eligible for CPT", "Canadian citizen", "PGWP until 2027-05-01"), needsSponsorship,
needsSponsorshipForInternship, education[0].degree, classStanding, expectedGraduation, enrolled.
This is a screening aid, not legal or immigration advice.
"""
import datetime as dt
import re

from .redflags import split_sentences

# ---- the user ------------------------------------------------------------------------------------------------------

_COUNTRY_WORDS = {
    'US': r'\b(?:united\s+states|usa|u\.\s?s\.(?:\s?a\.)?|us|america|american)\b',
    'CA': r'\b(?:canada|canadian|ca)\b',
    'UK': r'\b(?:united\s+kingdom|uk|u\.\s?k\.|great\s+britain|britain|british|england|scotland|wales|gb)\b',
}


def country_code(value):
    """'US', 'CA', 'UK' or None from a country name or code."""
    v = str(value or '').strip().lower()
    if not v:
        return None
    for code, pat in _COUNTRY_WORDS.items():
        if re.fullmatch(r'\s*' + pat + r'\s*', v):
            return code
    for code, pat in _COUNTRY_WORDS.items():
        if re.search(pat, v):
            return code
    return None


def _yes_no(v):
    s = str(v if v is not None else '').strip().lower()
    if s in ('yes', 'y', 'true', '1'):
        return True
    if s in ('no', 'n', 'false', '0'):
        return False
    return None


def _date(v):
    s = str(v or '').strip()
    for fmt, n in (('%Y-%m-%d', 10), ('%Y-%m', 7), ('%Y', 4)):
        try:
            return dt.datetime.strptime(s[:n], fmt).date()
        except ValueError:
            pass
    m = re.search(r'(january|february|march|april|may|june|july|august|september|october|november|december|'
                  r'jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\w*\.?\s+(\d{4})', s, re.I)
    if m:
        try:
            return dt.datetime.strptime(m.group(1)[:3] + ' ' + m.group(2), '%b %Y').date()
        except ValueError:
            pass
    return None


def user_status(profile, today=None):
    """What the screen needs to know about the user. Unknown facts stay None."""
    p = profile or {}
    today = today or dt.date.today()
    details = str(p.get('workAuthDetails') or '')
    d = details.lower()
    auth = country_code(p.get('authCountry')) or country_code(p.get('country'))
    citizen, pr, temp = set(), set(), set()

    def named(kind_pat):
        found = set()
        for code, pat in (('US', r'(?:u\.?\s?s\.?|united states|american|us)'), ('CA', r'(?:canadian|canada)'),
                          ('UK', r'(?:british|uk|u\.k\.|united kingdom)')):
            if re.search(pat + r'\s+' + kind_pat, d) or re.search(kind_pat + r'\s+(?:of\s+(?:the\s+)?)?' + pat, d):
                found.add(code)
        return found

    if re.search(r'\bcitizen', d) and not re.search(r'\bnot\s+a\s+citizen|\bnon[- ]citizen', d):
        citizen = named(r'citizen') or ({auth} if auth else set())
    if re.search(r'permanent\s+resident|\bgreen\s+card|\bpr\b|indefinite\s+leave|\bilr\b|settled\s+status', d):
        pr = named(r'permanent\s+resident') or ({auth} if auth else set())
    if re.search(r'settled\s+status|indefinite\s+leave|\bilr\b', d):
        pr.add('UK')
    if re.search(r'green\s+card', d):
        pr.add('US')
    f1 = bool(re.search(r'\bf-?1\b|\bopt\b|\bcpt\b|stem\s+opt', d))
    if f1:
        temp.add('US')
    if re.search(r'study\s+permit|work\s+permit|\bpgwp\b|post[- ]graduat\w*\s+work|international\s+student|temporary\s+resident|'
                 r'\bvisa\b|\bh-?1b\b|\bj-?1\b|\btn\b|\biec\b|working\s+holiday|graduate\s+route|skilled\s+worker|student\s+route|'
                 r'\btier\s*[245]\b|\bbrp\b|co-?op\s+permit', d) and not (citizen or pr):
        temp.add(auth or ('US' if f1 else None))
    temp.discard(None)

    needs = _yes_no(p.get('needsSponsorship'))
    needs_intern = _yes_no(p.get('needsSponsorshipForInternship'))
    authorized = _yes_no(p.get('workAuthorized'))

    edu = (p.get('education') or [{}])
    edu0 = edu[0] if isinstance(edu, list) and edu and isinstance(edu[0], dict) else {}
    degree = str(edu0.get('degree') or '').lower()
    level = None
    if re.search(r'ph\.?\s?d|doctor|doctoral|master|\bm\.?\s?sc\b|\bm\.?\s?s\b|\bmeng\b|\bm\.?\s?eng\b|\bmba\b|\bma\b|\bm\.?\s?a\.?\b|'
                 r'\bmasc\b|\bmfa\b|\bmph\b|\bllm\b|graduate\s+(?:diploma|certificate|degree)', degree):
        level = 'graduate'
    elif re.search(r'bachelor|\bb\.?\s?sc\b|\bb\.?\s?s\b|\bb\.?\s?a\b|\bbeng\b|\bb\.?\s?eng\b|\bbcomm?\b|\bbba\b|\bbasc\b|'
                   r'\bbfa\b|undergrad|associate|diploma|\bhnd\b|\bbtech\b|\bb\.?\s?tech\b|\bbcs\b|\bbmath\b|honours|honors', degree):
        level = 'undergraduate'

    standing = str(p.get('classStanding') or '').lower()
    grad_date = _date(p.get('expectedGraduation')) or _date(edu0.get('endExact')) or _date(edu0.get('end'))
    enrolled = _yes_no(p.get('enrolled'))
    student = bool(enrolled) or bool(standing) or bool(grad_date and grad_date >= today)
    if enrolled is False:
        student = False
    final_year = None
    if student:
        if re.search(r'final|senior|last\s+year|graduating|fourth|4th|fifth|5th|year\s*[45]\b', standing):
            final_year = True
        elif grad_date:
            final_year = grad_date <= today + dt.timedelta(days=365)
        elif re.search(r'first|second|third|freshman|sophomore|junior|1st|2nd|3rd|year\s*[123]\b', standing):
            final_year = False
    return {'auth_country': auth, 'citizen_of': sorted(citizen), 'pr_of': sorted(pr), 'temporary_in': sorted(temp),
            'f1': f1, 'work_authorized': authorized, 'needs_sponsorship': needs,
            'needs_sponsorship_internship': needs_intern, 'degree_level': level, 'student': student,
            'final_year': final_year, 'details': details}


def _citizen(st, c):
    """True/False/None: is the user a citizen of country c?"""
    if c in st['citizen_of']:
        return True
    if st['citizen_of'] or st['pr_of'] or c in st['temporary_in'] or st['f1'] and c == 'US':
        return False
    return None


def _citizen_or_pr(st, c):
    if c in st['citizen_of'] or c in st['pr_of']:
        return True
    if st['citizen_of'] or st['pr_of'] or c in st['temporary_in'] or st['f1'] and c == 'US':
        return False
    return None


# ---- posting text --------------------------------------------------------------------------------------------------

_US = r'(?:(?-i:U\.?\s?S\.?(?:\s?A\.?)?)|United\s+States|American)'
_REQ = re.compile(r'\b(?:must|required|requires?|requirement|only|mandatory|need\s+to\s+be|needs\s+to\s+be|necessary|'
                  r'eligib\w*|restricted|limited\s+to|open\s+to|will\s+be\s+considered|have\s+to\s+be|is\s+a\s+condition|'
                  r'condition\s+of\s+employment|able\s+to\s+(?:obtain|maintain)|ability\s+to\s+(?:obtain|maintain)|obtain|'
                  r'possess|hold|active|current)\b', re.I)
_EEO = re.compile(r'\b(?:equal\s+(?:employment\s+)?opportunit\w*|without\s+regard|regardless\s+of|irrespective\s+of|'
                  r'protected\s+(?:veteran|characteristic|status|class)|discriminat\w*|national\s+origin|e-verify)\b', re.I)
_NOT_REQ = re.compile(r'\b(?:not|no)\b[^.]{0,25}\b(?:required|necessary|needed|a\s+requirement)\b|\bdoes\s+not\s+require\b', re.I)
_ALT = re.compile(r'\bor\b[^.;]{0,70}?\b(?:authori[sz]ed|(?<!clearance\s)eligible(?!\s+(?:to\s+obtain|for)\s+(?:an?\s+)?(?:\w+\s+)?clearance)|'
                  r'entitled|legally|valid\s+work\s+(?:permit|visa|authori[sz]ation)|work\s+permit|right\s+to\s+work|'
                  r'otherwise\s+(?:permitted|able|authori[sz]ed)|other\s+(?:work\s+)?authori[sz]ation|have\s+(?:the\s+)?(?:legal\s+)?right|'
                  r'temporary\s+residen\w*|work\s+visa)\b', re.I)
_SOFT = re.compile(r'\b(?:prefer\w*|a\s+plus|nice\s+to\s+have|desir\w*|ideal(?:ly)?|advantage\w*|bonus|priority|'
                   r'encouraged|asset)\b', re.I)
_COND = re.compile(r'\b(?:may|might|could|some\s+(?:positions|roles)|certain\s+(?:roles|positions|programs|projects)|'
                   r'if\s+(?:required|applicable|needed|selected)|depending\s+on|where\s+applicable|potential(?:ly)?)\b', re.I)

_US_CIT = re.compile(_US + r'\s*citizen(?:s|ship)?\b|\bcitizen(?:s|ship)?\s+of\s+the\s+' + _US, re.I)
_GREEN = re.compile(r'\bgreen\s+card\b|\blawful\s+permanent\s+residen\w*|' + _US + r'\s+permanent\s+residen\w*', re.I)
_PR = re.compile(r'\bpermanent\s+residen\w*', re.I)
_US_PERSON = re.compile(_US + r'\s*persons?\b|\bITAR\b|\bEAR\b(?!\w)|export[- ]control\w*|export\s+administration', re.I)
_PERSON_REQ = re.compile(r'\b(?:persons?|citizens?|permanent\s+residents?|green\s+card)\b', re.I)
_CLEAR = re.compile(r'\b(?:security|secret|top[- ]secret|ts/sci|ts|sci|public\s+trust|dod|government|federal)\s+clearance\b|'
                    r'\bclearance\s+(?:is\s+)?required\b|\b(?:active|current)\s+(?:secret|ts/sci|top\s+secret)\b|'
                    r'\bobtain\s+(?:and\s+maintain\s+)?(?:an?\s+)?(?:\w+\s+){0,2}clearance\b', re.I)
_CA_CLEAR = re.compile(r'\b(?:reliability\s+status|enhanced\s+reliability|government\s+of\s+canada|canadian\s+(?:security|government))\b', re.I)
_F1 = re.compile(r'(?-i:\bF-?1\b|\bOPT\b|\bCPT\b|\bJ-?1\b)|\bstudent\s+visas?\b|\bpractical\s+training\b', re.I)
_F1_NEG_BEFORE = re.compile(r"\b(?:not|unable|cannot|can't|won't|will\s+not|do\s+not|does\s+not|don't|no|ineligible|"
                            r"exclud\w*|not\s+eligible|not\s+accept\w*|not\s+consider\w*|not\s+(?:be\s+)?able|except)\b[^.]{0,70}$", re.I)
_F1_NEG_AFTER = re.compile(r"^[^.]{0,50}\b(?:are|is|will\s+be)\s+(?:not|ineligible)\b|^[^.]{0,30}\b(?:not\s+eligible|ineligible|"
                           r"excluded|cannot\s+be\s+considered|will\s+not\s+be\s+considered)\b", re.I)
_F1_POS = re.compile(r'^[^.]{0,40}\b(?:welcome|encouraged|eligible\s+to\s+apply|can\s+apply|may\s+apply|are\s+eligible|accepted)\b', re.I)
_GRAD = re.compile(r'\b(?:pursuing|enrolled\s+in|working\s+towards?|candidate\s+for|student\s+in|studying\s+for)\s+(?:a\s+|an\s+|your\s+)?'
                   r"(?:master'?s|masters|m\.?s\.?|m\.?sc\.?|graduate|ph\.?\s?d\.?|doctoral|doctorate|mba)\b|"
                   r"\b(?:graduate|master'?s|ph\.?\s?d\.?|doctoral|mba)\s+students?\s+only\b|\bonly\s+(?:open\s+to\s+)?(?:current\s+)?"
                   r"(?:graduate|master'?s|ph\.?\s?d\.?|doctoral|mba)\s+students\b|\bmust\s+be\s+(?:a\s+|an\s+)?(?:current\s+|currently\s+enrolled\s+)?"
                   r"(?:graduate|master'?s|ph\.?\s?d\.?|doctoral|mba)\s+student", re.I)
_UNDERGRAD = re.compile(r"\b(?:bachelor'?s?|undergrad\w*|b\.?\s?sc?\b|b\.?\s?a\b|bs/ms|b\.?\s?eng|college\s+students?|"
                        r"all\s+(?:degree\s+)?levels|any\s+level)", re.I)
_SPONSOR_NO = re.compile(r"\b(?:not|unable\s+to|cannot|can't|won't|will\s+not|do\s+not|does\s+not|don't|no\s+longer|not\s+able\s+to|"
                         r"not\s+in\s+a\s+position\s+to)\b[^.]{0,40}?\bsponsor\w*|\bno\s+(?:visa\s+|immigration\s+|work\s+permit\s+|"
                         r"employment\s+)?sponsorship\b|\bsponsorship\s+(?:is\s+|will\s+)?not\s+(?:be\s+)?(?:available|provided|offered|"
                         r"possible|supported)\b|\bwithout\s+(?:the\s+need\s+for\s+|requiring\s+|needing\s+|requiring\s+any\s+|any\s+)?"
                         r"(?:(?:current|now|or|future|visa|employer|immigration|company|work\s+permit)\s+)*sponsorship\b|"
                         r"\bnot\s+(?:offer|provide)\w*\s+(?:\w+\s+)?sponsorship\b", re.I)
_SPONSOR_Q = re.compile(r'\?\s*$|^\s*(?:will|do|are)\s+you\b', re.I)
_SPONSOR_YES = re.compile(r'\b(?:visa\s+|work\s+permit\s+|immigration\s+)?sponsorship\s+(?:is\s+|will\s+be\s+|may\s+be\s+)?'
                          r'(?:available|offered|provided|possible|considered)\b|\b(?:we|company)\s+(?:can|will|do|are\s+able\s+to)\s+'
                          r'(?:offer\s+)?sponsor\w*\b|\bopen\s+to\s+sponsor\w*|\bsponsors?\s+(?:skilled\s+worker\s+|work\s+)?visas\b|'
                          r'\bsponsor\w*\s+(?:is\s+)?available\b', re.I)
_UK_RTW = re.compile(r'\bright\s+to\s+(?:live\s+and\s+)?work\s+in\s+(?:the\s+)?(?:UK|U\.K\.|United\s+Kingdom|Britain|Great\s+Britain)\b|'
                     r'\b(?:UK|British)\s+right\s+to\s+work\b|\beligib\w*\s+to\s+work\s+in\s+the\s+(?:UK|United\s+Kingdom)\b', re.I)
_UK_EXPLICIT = re.compile(r'\b(?:already|existing|current(?:ly)?|full|unrestricted|without\s+restriction|indefinite|permanent)\b', re.I)
_CAN_CPR = re.compile(r'\bcanadian\s+citizen\w*[^.]{0,80}?permanent\s+residen\w*|\bpermanent\s+residen\w*[^.]{0,60}?canad\w*|'
                      r'\bcitizens?\s+(?:and|or|/)\s+permanent\s+residents?\s+of\s+canada', re.I)
_CAN_CIT = re.compile(r'\bcanadian\s+citizen(?:s|ship)?\b|\bcitizens?\s+of\s+canada\b', re.I)
_CAN_ALT = re.compile(r'\b(?:legally\s+entitled|entitled\s+to\s+work|authori[sz]ed\s+to\s+work|valid\s+(?:canadian\s+)?work\s+permit|'
                      r'temporary\s+residen\w*|eligible\s+to\s+work\s+in\s+canada|legally\s+eligible|work\s+permit\s+holders|'
                      r'(?:persons|those|individuals|people)\s+(?:who\s+are\s+)?legally|with\s+or\s+without\s+a\s+valid)\b', re.I)
_AUTH_REQ = re.compile(r'\b(?:legally\s+)?(?:authori[sz]ed|eligible|entitled|permitted)\s+to\s+work\s+in\s+(?:the\s+)?(?P<c>' + _US +
                       r'|US|Canada|UK|United\s+Kingdom)\b', re.I)
_GENERIC_CIT = re.compile(r'\b(?:must\s+be\s+an?\s+citizen|citizenship\s+(?:is\s+)?required|citizens\s+only|only\s+citizens)\b', re.I)
_INTERN = re.compile(r'\b(?:intern(?:ship)?s?|co-?op|placement\s+student|work\s+term|summer\s+student|student\s+(?:position|role|job))\b', re.I)


def posting_country(location='', text=''):
    """'US', 'CA', 'UK' or None, from the posting's location (then its text)."""
    loc = str(location or '')
    if re.search(r'\bcanada\b|\b(?:ontario|quebec|qu\u00e9bec|british columbia|alberta|nova scotia|new brunswick|manitoba|'
                 r'saskatchewan|newfoundland|prince edward island|yukon|nunavut|northwest territories)\b', loc, re.I) or \
            re.search(r',\s*(?:ON|BC|AB|QC|NS|NB|MB|SK|PE|PEI|NL|YT|NT|NU)\b', loc):
        return 'CA'
    if re.search(r'\b(?:united kingdom|england|scotland|wales|northern ireland|london|manchester|edinburgh|glasgow|'
                 r'birmingham|leeds|bristol|cambridge,\s*uk|oxford)\b|\bUK\b|\bGB\b', loc, re.I) and not re.search(r'london,\s*on', loc, re.I):
        return 'UK'
    if re.search(r'\b(?:united states|usa)\b|\bUS\b|,\s*[A-Z]{2}\b|\bremote\s*[-(]\s*us', loc):
        return 'US'
    t = str(text or '')[:3000]
    hits = {c: len(re.findall(p, t, re.I if c != 'US' else 0)) for c, p in
            (('CA', r'\bcanad\w*'), ('UK', r'\b(?:united kingdom|UK)\b'), ('US', r'\b(?:U\.S\.|United States|USA)\b'))}
    best = max(hits, key=hits.get)
    return best if hits[best] else None


def screen(text, profile=None, role='', location='', today=None):
    """Screen a posting against the user's status. See the module docstring for the rules."""
    st = user_status(profile or {}, today)
    has_profile = bool(profile)
    where = posting_country(location, text)
    internship = bool(_INTERN.search(str(role or ''))) or (not role and bool(_INTERN.search(str(text or '')[:500])))
    needs = st['needs_sponsorship']
    if internship and st['needs_sponsorship_internship'] is not None:
        needs = st['needs_sponsorship_internship']
    below_final = st['student'] and st['final_year'] is not True

    results = []   # (level, sentence, rule)

    def add(level, sentence, rule):
        results.append((level, re.sub(r'\s+', ' ', sentence).strip()[:300], rule))

    def decide(holds, sentence, rule, soft=False, unknown_note='profile does not say'):
        """holds: does the user meet the requirement (True/False/None)?"""
        if holds is True:
            return
        if soft or _COND.search(sentence):
            add('check', sentence, rule + (' (preferred or conditional)' if holds is False else f' ({unknown_note})'))
        elif holds is False:
            add('skip', sentence, rule)
        else:
            add('check', sentence, f'{rule} ({unknown_note})')

    for s in split_sentences(text):
        if _EEO.search(s) or _NOT_REQ.search(s):
            continue
        soft = bool(_SOFT.search(s))
        alt = bool(_ALT.search(s))
        mentions_ca = bool(re.search(r'\bcanad', s, re.I))
        mentions_uk = bool(re.search(r'\b(?:UK|U\.K\.|United Kingdom|Britain|British)\b', s))
        is_question = bool(_SPONSOR_Q.search(s))

        # --- US: F-1 / OPT / CPT excluded
        for m in _F1.finditer(s):
            before, after = s[:m.start()], s[m.end():]
            if _F1_POS.search(after):
                continue
            if _F1_NEG_BEFORE.search(before) or _F1_NEG_AFTER.search(after) or re.search(r'\bno\s+(?:CPT|OPT)', s):
                if st['f1']:
                    add('skip', s, 'excludes F-1 / OPT / CPT students and you are on F-1')
                elif not st['details'] and has_profile and needs is not False:
                    add('check', s, 'excludes F-1 / OPT / CPT students (profile does not give your visa type)')
                elif not has_profile:
                    add('check', s, 'excludes F-1 / OPT / CPT students')
                break

        # --- US citizenship / green card / US person / clearance
        us_ctx = bool(re.search(_US, s, re.I)) or (where == 'US' and not mentions_ca and not mentions_uk)
        req = bool(_REQ.search(s)) or soft
        if _US_CIT.search(s) and req and not alt:
            if _GREEN.search(s) or _PR.search(s):
                decide(_citizen_or_pr(st, 'US'), s, 'US citizenship or permanent residence required', soft)
            else:
                decide(_citizen(st, 'US'), s, 'US citizenship required', soft)
        elif (_GREEN.search(s) or (_PR.search(s) and us_ctx and not mentions_ca)) and req and not alt \
                and not _CAN_CPR.search(s):
            decide(_citizen_or_pr(st, 'US'), s, 'US permanent residence (green card) required', soft)
        elif _US_PERSON.search(s) and _PERSON_REQ.search(s) and req and not alt:
            decide(_citizen_or_pr(st, 'US'), s, '"US person" required (export control: ITAR/EAR)', soft)
        if _CLEAR.search(s) and _REQ.search(s) and not _CA_CLEAR.search(s) and not mentions_ca and \
                (us_ctx or where in (None, 'US')) and not mentions_uk:
            holds = _citizen(st, 'US')
            if holds is False and 'US' in st['pr_of']:
                add('check', s, 'security clearance required (clearances usually need US citizenship)')
            else:
                decide(holds, s, 'security clearance required (needs US citizenship)', soft)
        if _GENERIC_CIT.search(s) and not _US_CIT.search(s) and not _CAN_CIT.search(s) and not alt and where:
            decide(_citizen(st, where), s, f'{where} citizenship required', soft)

        # --- Graduate students only
        if _GRAD.search(s) and not _UNDERGRAD.search(s) and (_REQ.search(s) or re.search(r'\b(?:currently|pursuing|enrolled)\b', s, re.I)):
            if st['degree_level'] == 'undergraduate':
                if soft:
                    add('check', s, 'graduate students preferred and you are an undergraduate')
                else:
                    add('skip', s, 'graduate students only and you are an undergraduate')
            elif st['degree_level'] is None and has_profile:
                add('check', s, 'graduate students only (profile does not give your degree)')

        # --- Canada: citizens / permanent residents only
        if (_CAN_CPR.search(s) or _CAN_CIT.search(s)) and (_REQ.search(s) or soft or re.search(r'apply\s+if\s+you\s+are|accepts?\s+applications\s+from', s, re.I)) \
                and not _CAN_ALT.search(s) and not alt:
            holds = _citizen_or_pr(st, 'CA') if _CAN_CPR.search(s) else _citizen(st, 'CA')
            rule = 'Canadian citizens or permanent residents only' if _CAN_CPR.search(s) else 'Canadian citizenship required'
            if holds is False and 'CA' not in st['temporary_in'] and st['auth_country'] not in (None, 'CA'):
                decide(False, s, rule, soft)
            elif holds is False:
                decide(False, s, rule + ' and you are a temporary resident', soft)
            else:
                decide(holds, s, rule, soft)

        # --- Sponsorship (all countries) and UK right to work
        uk_rtw = bool(_UK_RTW.search(s))
        if _SPONSOR_NO.search(s) and not is_question:
            explicit = True
            rule = 'no visa sponsorship'
            if needs is False:
                pass
            elif needs is None:
                add('check', s, rule + ' (profile does not say whether you need sponsorship)')
            elif below_final:
                add('check', s, rule + ' (you are a student below your final year: sponsorship wording alone does not rule you out)')
            elif soft or _COND.search(s):
                add('check', s, rule + ' (conditional wording)')
            elif explicit:
                add('skip', s, rule + ' and you need sponsorship')
        elif uk_rtw and _REQ.search(s) and not is_question:
            rule = 'right to work in the UK required'
            if needs is False:
                pass
            elif needs is None:
                add('check', s, rule + ' (profile does not say whether you need sponsorship)')
            elif below_final:
                add('check', s, rule + ' (you are a student below your final year)')
            elif _UK_EXPLICIT.search(s) and not soft:
                add('skip', s, rule + ' (existing right, no sponsorship) and you need sponsorship')
            else:
                add('check', s, rule + ' and you need sponsorship (not explicit that they will not sponsor)')
        elif _SPONSOR_YES.search(s) and not is_question:
            add('note', s, 'sponsorship mentioned as available')

        # --- Work authorization required and the user says they aren't authorized
        m = _AUTH_REQ.search(s)
        if m and st['work_authorized'] is False and _REQ.search(s) and not _SPONSOR_NO.search(s):
            c = country_code(m.group('c'))
            if c and (st['auth_country'] in (None, c)):
                add('check', s, f'must be authorized to work in {c} and your profile says you are not')

    # one entry per sentence, strongest level wins
    order = {'skip': 0, 'check': 1, 'note': 2}
    best = {}
    for level, sentence, rule in results:
        if sentence not in best or order[level] < order[best[sentence][0]]:
            best[sentence] = (level, rule)
    levels = [lv for lv, _ in best.values()]
    verdict = 'skip' if 'skip' in levels else 'check' if 'check' in levels else 'ok'
    why = [f'{s} -> {r}' for s, (lv, r) in sorted(best.items(), key=lambda kv: order[kv[1][0]])
           if lv in ('skip', 'check')]
    why += [f'{s} -> note: {r}' for s, (lv, r) in best.items() if lv == 'note']
    check = [s for s, (lv, _) in best.items() if lv == 'check']
    return {'screen': verdict, 'why': why, 'check': check, 'country': where, 'status': st}


def short_reason(result):
    """One short line for jobs.txt / job-posting.md: the first skip (or check) rule."""
    for line in result.get('why') or []:
        if ' -> ' in line and not line.rsplit(' -> ', 1)[1].startswith('note:'):
            return line.rsplit(' -> ', 1)[1]
    return ''
