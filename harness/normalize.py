"""Text normalization helpers: numbers, yes/no, abstention, key terms, domains."""

import re
from urllib.parse import urlparse

# A number with thousands separators (1,234 / 12,345.00) or a plain number (1234 / 1234.00 / 0.5).
_NUM_RE = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(?![\d])")

_MONTHS = {
    "january": "jan", "february": "feb", "march": "mar", "april": "apr", "june": "jun",
    "july": "jul", "august": "aug", "september": "sep", "sept": "sep", "october": "oct",
    "november": "nov", "december": "dec",
}


def collapse(text):
    """Lowercase and collapse whitespace."""
    return re.sub(r"\s+", " ", (text or "").strip()).lower()


def extract_numbers(text):
    """Every number in the text, as floats rounded to 2 decimals, in order of appearance.

    '$1,234' -> [1234.0]; '1234.00' -> [1234.0]; '150%' -> [150.0];
    '100 (single); 200 (couple)' -> [100.0, 200.0]
    """
    if not text:
        return []
    return [round(float(m.replace(",", "")), 2) for m in _NUM_RE.findall(text)]


def is_year(value, year_range):
    lo, hi = year_range
    return float(value).is_integer() and lo <= value <= hi


def contains_phrase(text, phrases):
    """First phrase from `phrases` found in text (word-boundary match), or None."""
    t = collapse(text)
    for p in phrases:
        p = p.strip().lower()
        if not p:
            continue
        if re.search(r"(?<!\w)" + re.escape(p) + r"(?!\w)", t):
            return p
    return None


def yes_no_polarities(text):
    """Set of yes/no answers expressed in the text, as {'yes', 'no'}.

    'yes', 'true' -> yes; 'false' -> no. 'no' only counts when it stands as an answer
    (start of text or of a clause after ; : . ! ?, or followed by punctuation / end), so
    'workers with no qualifying children' does not count as a 'no'.
    """
    t = collapse(text)
    found = []
    for m in re.finditer(r"\b(yes|true|false|no)\b", t):
        word = m.group(1)
        if word == "no":
            at_start = m.start() == 0 or not re.search(r"\w", t[: m.start()])
            new_clause = re.search(r"[;:.!?]\s*$", t[: m.start()])
            followed = re.match(r"\s*([,.;:!)]|$)", t[m.end():])
            if not (at_start or new_clause or followed):
                continue
        found.append("yes" if word in ("yes", "true") else "no")
    return found


def first_polarity(text):
    p = yes_no_polarities(text)
    return p[0] if p else None


def is_abstention_marker(answer, markers):
    return collapse(answer) in {m.strip().lower() for m in markers}


def key_terms(text, stopwords):
    """Significant lowercase terms: numbers, and words of 3+ letters that are not stopwords.
    Month names are shortened to 3 letters."""
    t = (text or "").lower()
    t = re.sub(r"(?<=\d),(?=\d{3})", "", t)  # 12,345 -> 12345
    stop = {s.lower() for s in stopwords}
    terms = []
    for tok in re.findall(r"[a-z]+|\d+(?:\.\d+)?", t):
        tok = _MONTHS.get(tok, tok)
        if tok[0].isdigit():
            terms.append(tok)
        elif len(tok) >= 3 and tok not in stop:
            terms.append(tok)
    # keep order, drop duplicates
    seen, out = set(), []
    for x in terms:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def term_coverage(expected, given, stopwords):
    """Share of the expected answer's key terms found in the given answer (5-char prefix match
    for words, exact match for numbers). Returns None when expected has no key terms."""
    exp = key_terms(expected, stopwords)
    if not exp:
        return None
    giv = key_terms(given, stopwords)
    giv_words = {g[:5] for g in giv if not g[0].isdigit()}
    giv_nums = {float(g) for g in giv if g[0].isdigit()}
    hit = 0
    for e in exp:
        if e[0].isdigit():
            hit += float(e) in giv_nums
        else:
            hit += e[:5] in giv_words
    return hit / len(exp)


def url_host(url):
    url = (url or "").strip()
    if not url:
        return None
    try:
        p = urlparse(url)
    except ValueError:
        return None
    if p.scheme not in ("http", "https") or not p.hostname or "." not in p.hostname:
        return None
    return p.hostname.lower().rstrip(".")


def registrable_domain(host, multi_label_suffixes):
    """Approximate registrable domain without a public-suffix list:
    one label plus the longest matching multi-label suffix, else the last two labels."""
    if not host:
        return None
    labels = host.split(".")
    best = None
    for suf in multi_label_suffixes:
        suf = suf.lower().strip(".")
        if host.endswith("." + suf) and (best is None or len(suf) > len(best)):
            best = suf
    if best:
        n = len(best.split(".")) + 1
        return ".".join(labels[-n:])
    return ".".join(labels[-2:])


def is_gov_host(host, suffixes):
    if not host:
        return False
    return any(host.endswith(s.lower()) for s in suffixes)
