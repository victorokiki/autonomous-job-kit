"""Warning signs that a job posting may be a scam, with the text that triggered each one.

    from jobkit.redflags import red_flags
    red_flags(description, url=None, company=None, role=None) -> [{"flag": "...", "quote": "..."}]

Each flag is a short plain-English label; the quote is the sentence (shortened) that matched, so the user can judge.
The rules aim for few false alarms: reassurances such as "we never ask you to pay" or "no fees" do not flag, payroll
lines like "paid by direct deposit" do not flag, and normal trade phrases like "must have a valid driver's licence"
do not flag. A flag is a reason to look closer, not proof of fraud.

Also exports split_sentences(text), used by jobkit.eligibility.
"""
import re

# ---- sentences ---------------------------------------------------------------------------------------------------

_ABBREV = re.compile(r'\b(?:U\.\s?S\.(?:\s?A\.)?|U\.\s?K\.|e\.g\.|i\.e\.|etc\.|Inc\.|Ltd\.|Co\.|Corp\.|Jr\.|Sr\.|No\.|St\.|'
                     r'approx\.|vs\.|Ph\.\s?D\.|M\.\s?Sc\.|B\.\s?Sc\.|B\.\s?S\.|M\.\s?S\.|B\.\s?A\.|M\.\s?A\.|B\.\s?Eng\.|'
                     r'M\.\s?Eng\.|Dr\.|Mr\.|Ms\.|Mrs\.)', re.I)
_DOT = '\u2024'


def split_sentences(text):
    """Sentences of a posting: every line is split at sentence ends; bullet markers are dropped. Abbreviations such
    as "U.S." or "Ph.D." don't end a sentence."""
    out = []
    for line in str(text or '').splitlines():
        line = re.sub(r'^\s*(?:[-*\u2022\u25cf\u25aa\u2013]|\d+[.)])\s+', '', line).strip()
        if not line:
            continue
        line = _ABBREV.sub(lambda m: m.group(0).replace('.', _DOT), line)
        for part in re.split(r'(?<=[.!?])\s+(?=[A-Z0-9"\'(\u201c])', line):
            part = part.replace(_DOT, '.').strip()
            if part:
                out.append(part)
    return out


def _quote(sentence, match=None, width=170):
    s = re.sub(r'\s+', ' ', sentence).strip()
    if len(s) <= width:
        return s
    if match is None:
        return s[:width - 3].rstrip() + '...'
    mid = (match.start() + match.end()) // 2
    start = max(0, min(mid - width // 2, len(s) - width))
    piece = s[start:start + width].strip()
    return ('...' if start > 0 else '') + piece + ('...' if start + width < len(s) else '')


# ---- rules -------------------------------------------------------------------------------------------------------

# A sentence that reassures rather than demands ("we will never ask you to pay", "there is no fee").
_REASSURE = re.compile(
    r"\b(never|no\s+(?:\w+\s+){0,2}(?:fees?|charges?|costs?|payments?)|not?\s+(?:be\s+)?(?:charged|required\s+to\s+pay|asked\s+to\s+pay)|"
    r"free\s+of\s+charge|at\s+no\s+(?:cost|charge)|without\s+(?:any\s+)?(?:cost|charge|fee)|do(?:es)?\s+not\s+(?:charge|ask|require)|"
    r"don'?t\s+(?:charge|ask)|will\s+not\s+(?:charge|ask)|won'?t\s+(?:charge|ask)|(?:we|company|employer)\s+(?:will\s+)?(?:cover|pay|pays|covers|reimburse\w*)|"
    r"reimburs\w*|paid\s+(?:for\s+)?by\s+(?:us|the\s+(?:company|employer))|company[- ]provided|provided\s+by\s+(?:us|the\s+company)|"
    r"scam|fraud\w*|phishing|beware|be\s+aware|legitimate\s+(?:recruiters?|employers?))\b", re.I)

_FEE = re.compile(
    r"\b(?:application|registration|processing|training|onboarding|starter|enrol(?:l)?ment|background[- ]check|screening|"
    r"equipment|kit|uniform|placement|admin(?:istration|istrative)?|certification|membership|visa\s+processing)\s+"
    r"(?:fees?|charges?|costs?|deposits?|payments?)\b", re.I)
_PAY_FOR = re.compile(
    r"\b(?:you|applicants?|candidates?|new\s+hires?)\s+(?:will\s+|must\s+|are\s+required\s+to\s+|need\s+to\s+|have\s+to\s+|should\s+)?"
    r"(?:pay|purchase|buy)\s+(?:a\s+|an\s+|the\s+|for\s+(?:the\s+|your\s+)?)?(?:\w+\s+){0,2}"
    r"(?:training|course|background\s+check|starter\s+kit|kit|equipment|software|license|certificate|application|registration|"
    r"materials|package)\b", re.I)
_REFUNDABLE = re.compile(r"\b(?:refundable|small)\s+(?:fee|deposit|payment)\b", re.I)

_CHEQUE = re.compile(
    r"(?:\b(?:cheque|check|money\s+order|funds|payment)s?\b[^.]{0,100}\b(?:equipment|supplies|workstation|home\s+office|"
    r"laptop|vendor|software|office\s+setup)\b|\b(?:equipment|supplies|workstation|home\s+office|laptop|vendor|software)\b"
    r"[^.]{0,100}\b(?:cheque|check|money\s+order)s?\b|\bdeposit\s+(?:the|a|this)\s+(?:cheque|check)\b|"
    r"\bmobile\s+deposit\b|\b(?:send|wire|transfer)\s+(?:back\s+)?(?:the\s+)?(?:remaining|remainder|balance|excess)\b)", re.I)
_PAYROLL = re.compile(r"\b(?:paycheck|paycheque|direct\s+deposit|payroll|background\s+check|reference\s+check|"
                      r"health\s+check|spell\s+check|check\s+in|check\s+out|double[- ]check)\b", re.I)

_APPS = r'(?:telegram|whats\s?app|signal\s+(?:app|messenger)|(?-i:Signal)|google\s+hangouts|hangouts|wickr|kik|wechat|viber)'
_CHAT = re.compile(
    r"\b(?:contact|text|message|reach(?:\s+out\s+to)?|chat|interview(?:ed)?|add|send|dm|apply|connect|talk|speak)\b[^.]{0,40}?"
    r"\b(?:on|via|through|using|over|at|with)\s+" + _APPS + r"\b|\b" + _APPS + r"\s*(?:id|handle|username|number|no\.?|"
    r"chat|interview)?\s*[:@+]\s*\S|\b" + _APPS + r"\s+(?:interview|chat\s+interview|only)\b", re.I)

_PERSONAL_MAIL = re.compile(
    r'\b([\w.+-]+)@(gmail|googlemail|yahoo|ymail|outlook|hotmail|live|msn|aol|icloud|me|proton(?:mail)?|gmx|mail|'
    r'yandex|zoho)\.(?:com|ca|co\.uk|me|ru|net|fr|de)\b', re.I)
_RECRUIT_LOCAL = re.compile(r'(hr|recruit|career|hiring|jobs?|talent|staffing|onboard|personnel|employ|human)', re.I)

_CRYPTO = re.compile(
    r"\b(?:paid|payment|pay|salary|compensation|wages?|remuneration|reimburs\w*)\b[^.]{0,40}\b(?:in|via|with|through|using|by)\s+"
    r"(?:bitcoin|btc|crypto(?:currenc(?:y|ies))?|usdt|tether|ethereum|eth|gift\s?cards?|itunes\s+cards?|steam\s+cards?|"
    r"google\s+play\s+cards?|amazon\s+cards?)\b|\b(?:buy|purchase|send|load)\s+(?:\w+\s+){0,3}gift\s?cards?\b|"
    r"\bgift\s?cards?\b[^.]{0,40}\b(?:as\s+payment|for\s+payment|to\s+pay)\b", re.I)

_NO_INTERVIEW = re.compile(
    r"\bno\s+(?:(?:formal|prior|phone|face[- ]to[- ]face)\s+)?interviews?\s+(?:is\s+|are\s+)?(?:needed|required|necessary)\b|"
    r"\bwithout\s+(?:an?\s+|any\s+)?interviews?\b|\b(?:get|be|are|you(?:'ll| will)\s+be)\s+hired\s+(?:immediately|instantly|"
    r"on\s+the\s+spot|today|right\s+away)\b|\bhired\s+on\s+the\s+spot\b|\binstant(?:ly)?\s+hir(?:e|ed|ing)\b|"
    r"\bguaranteed\s+(?:job|position|hire|employment|placement)\b", re.I)

_ID_ASK = re.compile(
    r"(?-i:\bSINs?\b|\bSSNs?\b)|\b(?:social\s+insurance|social\s+security|national\s+insurance)\s+(?:number|no\.?|card)\b|"
    r"\bbank\s+(?:account|details|information|info|statement|login|card)\b|\b(?:routing|account|card)\s+number\b|"
    r"\b(?:driver'?s?|driving)\s+licen[cs]e\s+(?:number|copy|photo|scan|picture)\b|\bpassport\s+(?:number|copy|photo|scan|details)\b|"
    r"\b(?:copy|photo|scan|picture)\s+of\s+(?:your\s+)?(?:id|passport|driver'?s?\s+licen[cs]e|sin\s+card|ssn\s+card|"
    r"social\s+security\s+card|photo\s+id)\b|\bdate\s+of\s+birth\b", re.I)
_ID_VERB = re.compile(r"\b(?:send|provide|submit|include|email|e-mail|attach|text|forward|share|enter|fill\s+in|required\s+"
                      r"(?:with|along)|along\s+with|together\s+with|when\s+(?:you\s+)?apply(?:ing)?|with\s+your\s+(?:application|resume|cv))\b", re.I)
_AFTER_OFFER = re.compile(r"\b(?:after|upon|once|following)\s+(?:an?\s+|the\s+|a\s+conditional\s+|you\s+(?:accept|receive)\s+(?:an?\s+)?)?"
                          r"(?:offer|hire|hired|hiring|acceptance|onboarding|start(?:ing)?|employment\s+begins|first\s+day)\b|"
                          r"\bduring\s+onboarding\b|\bform\s+i-9\b|\bi-9\b|\bpayroll\s+setup\b", re.I)

_UNSKILLED = re.compile(
    r"\b(?:data\s+entry|typist|typing|envelope\s+stuff\w*|package\s+(?:handler|forward\w*|reship\w*|inspector)|reshipp\w*|"
    r"mystery\s+shopp\w*|product\s+tester|personal\s+assistant|virtual\s+assistant|admin(?:istrative)?\s+assistant|"
    r"office\s+assistant|clerical|copy\s+paste|form\s+filling|survey\s+taker|chat\s+(?:agent|moderator)|"
    r"payment\s+processor|shipping\s+(?:clerk|coordinator)|receptionist)\b", re.I)
_ENTRY = re.compile(r"\b(?:no\s+(?:prior\s+)?experience|entry[- ]level|training\s+(?:is\s+)?provided|beginners?\s+welcome|"
                    r"no\s+skills?\s+(?:needed|required)|anyone\s+can)\b", re.I)
_MONEY = re.compile(
    r"(?P<cur>[$\u00a3\u20ac]|(?:CAD|USD|GBP|C\$|US\$)\s?)\s?(?P<num>\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)\s?(?P<k>[kK])?"
    r"(?:\s?(?:-|\u2013|to)\s?(?:[$\u00a3\u20ac]|CAD|USD|GBP)?\s?(?P<num2>\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)\s?[kK]?)?"
    r"\s?(?:/|per|an|a|each)\s?(?P<unit>hour|hr|h|day|week|wk|month)\b", re.I)
_HOURS = {'hour': 1, 'hr': 1, 'h': 1, 'day': 8, 'week': 40, 'wk': 40, 'month': 173}

_SUBSTANCE = re.compile(r"\b(?:responsib\w*|requir\w*|qualif\w*|experience|skills?|duties|tasks|you\s+will|what\s+you'?ll|"
                        r"about\s+(?:the|this)\s+(?:role|job|position)|education|degree)\b", re.I)

_URGENT = re.compile(
    r"\b(?:respond|reply|apply|answer|confirm|get\s+back|contact\s+us|act|accept)\w*\b[^.]{0,40}\bwithin\s+(?:the\s+next\s+)?"
    r"(?:1|2|3|6|12|24|48|one|two|twelve|twenty[- ]four|forty[- ]eight)\s*(?:hours?|hrs?|h)\b|"
    r"\b(?:act|apply|respond)\s+(?:now|fast|quickly|immediately)\b(?![^.]{0,30}\b(?:to\s+be\s+considered\s+for\s+our\s+fall|program)\b)|"
    r"\blimited\s+(?:spots?|slots?|positions?|seats?)\s+(?:available|left|remaining)\b|\bonly\s+\d+\s+(?:spots?|slots?|positions?|seats?)"
    r"\s+(?:left|remaining|available)\b|\b(?:offer|opportunity)\s+(?:expires|ends|closes)\s+(?:today|tonight|in\s+24)\b|"
    r"\bdon'?t\s+miss\s+(?:out|this)\b|\btoday\s+only\b|\bfirst\s+come,?\s+first\s+serve", re.I)


def _wage_per_hour(m):
    num = float(m.group('num').replace(',', ''))
    if m.group('num2'):
        num = max(num, float(m.group('num2').replace(',', '')))
    if m.group('k'):
        num *= 1000
    return num / _HOURS[m.group('unit').lower()], m.group('cur').strip().upper()


def red_flags(text, url=None, company=None, role=None, system=None):
    """List of {"flag", "quote"} for a posting's text (description, plus title and location if you like).
    `company` enables the personal-email check; `role` helps the pay check; `system` (greenhouse, lever, ...) lets a
    personal email on a big application system count even without a recruiting-style address."""
    text = str(text or '')
    found = {}

    def add(flag, sentence, match=None):
        if flag not in found:
            found[flag] = _quote(sentence, match)

    sentences = split_sentences(text)
    for s in sentences:
        reassure = _REASSURE.search(s)
        # 1. Paying to apply / train / get equipment
        m = _FEE.search(s) or _PAY_FOR.search(s) or _REFUNDABLE.search(s)
        if m and not reassure:
            add('asks you to pay (fee, training, equipment or a check)', s, m)
        # 2. Cheques / deposits to buy equipment
        m = _CHEQUE.search(s)
        if m and not reassure and not (_PAYROLL.search(s) and not re.search(r'\b(cheque|money order|equipment|vendor|supplies)\b', s, re.I)):
            add('cheque or deposit to buy equipment', s, m)
        # 3. Chat-app-only contact
        m = _CHAT.search(s)
        if m and (not re.search(r'\b(api|integrat\w*|bots?|sdk|platform|develop\w*|build\w*|experience\s+with)\b', s, re.I)
                  or re.search(r'\b(contact|text|message|reach|interview)\b', s, re.I)):
            add('contact through a chat app (Telegram/WhatsApp/Signal/Hangouts)', s, m)
        # 5. Crypto or gift cards
        m = _CRYPTO.search(s)
        if m and not reassure:
            add('payment in crypto or gift cards', s, m)
        # 6. No interview / instant hire
        m = _NO_INTERVIEW.search(s)
        if m:
            add('no interview / hired immediately', s, m)
        # 7. ID or bank details before an offer
        m = _ID_ASK.search(s)
        if m and _ID_VERB.search(s) and not reassure and not _AFTER_OFFER.search(s):
            add('asks for SIN/SSN, bank or ID details before an offer', s, m)
        # 10. Pressure
        m = _URGENT.search(s)
        if m:
            add('pressure to respond fast', s, m)

    # 4. Personal email address for a named company
    for m in _PERSONAL_MAIL.finditer(text):
        local = m.group(1)
        recruiting_style = bool(_RECRUIT_LOCAL.search(local))
        big_system = (system or '') in ('greenhouse', 'lever', 'ashby', 'workday', 'smartrecruiters', 'icims', 'oracle', 'rippling')
        if company and (recruiting_style or big_system):
            sent = next((s for s in sentences if m.group(0) in s), m.group(0))
            add(f'personal email address ({m.group(2).lower()}) used for {company} recruiting', sent)
            break
        if not company and recruiting_style:
            sent = next((s for s in sentences if m.group(0) in s), m.group(0))
            add(f'recruiting from a personal email address ({m.group(2).lower()})', sent)
            break

    # 8. Very high pay for unskilled entry-level work
    title = str(role or '')
    unskilled = _UNSKILLED.search(title) or (not title and _UNSKILLED.search(text[:400]))
    if unskilled or (_UNSKILLED.search(text) and _ENTRY.search(text) and len(text.split()) < 400):
        for s in sentences:
            for m in _MONEY.finditer(s):
                wage, cur = _wage_per_hour(m)
                limit = 30 if cur in ('\u00a3', 'GBP') else 40
                if wage > limit:
                    add('pay far above normal for unskilled entry-level work', s, m)
                    break
            if any(k.startswith('pay far above') for k in found):
                break

    # 9. Very short, vague description
    words = len(re.findall(r'\w+', text))
    if text.strip() and (words < 60 or (words < 120 and not _SUBSTANCE.search(text))):
        add('very short, vague description', f'only {words} words')

    return [{'flag': k, 'quote': v} for k, v in found.items()]
