"""Deterministic, offline scoring: one outcome per (arm, run, question)."""

import re

from . import normalize as nz

HALLUCINATION_OUTCOMES = {"wrong_value", "stale", "should_have_abstained"}
CORRECT_OUTCOMES = {"correct", "correct_abstention"}
UNSCORED_OUTCOMES = {"pending_review", "not_scoreable"}
SCORED_OUTCOMES = {
    "correct", "wrong_value", "stale", "correct_abstention",
    "should_have_abstained", "wrong_abstention", "no_answer",
}
# Worst first; used for tie-breaking the majority outcome and for deterministic ordering.
SEVERITY_ORDER = [
    "should_have_abstained", "wrong_value", "stale", "wrong_abstention",
    "no_answer", "correct", "correct_abstention",
]


def is_abstain_truth(truth):
    return truth["answer_type"] == "abstain" or truth["expected_answer"].strip().upper() == "ABSTAIN"


def critical_eligible(truth, cfg):
    """True if a hallucination on this question would count as a critical error."""
    rule = cfg["critical_error"]
    cat = truth["category"].lower()
    if cat in {c.lower() for c in rule.get("always_categories", [])}:
        return True
    for c, pattern in rule.get("categories_if_question_matches", {}).items():
        if cat == c.lower() and re.search(pattern, truth["question"], re.IGNORECASE):
            return True
    return False


def _has_value(answer, answer_type):
    """Can a clear value be extracted for this answer type?"""
    if answer_type == "number":
        return bool(nz.extract_numbers(answer))
    if answer_type == "yes/no":
        return bool(nz.yes_no_polarities(answer))
    return False


def detect_abstention(answer, abstain_flag, answer_type, cfg):
    """(abstained: bool, reason: str). Phrase matches count only when no value can be extracted,
    so 'No, the credit is not available for 2026' is a 'no', not an abstention."""
    if abstain_flag:
        return True, "abstain flag is true"
    if nz.is_abstention_marker(answer, cfg["abstention_markers"]):
        return True, "answer is blank or an abstention marker"
    phrase = nz.contains_phrase(answer, cfg["abstention_phrases"])
    if phrase:
        if answer_type in ("number", "yes/no") and _has_value(answer, answer_type):
            return False, ""
        if answer_type in ("text", "date"):
            return False, f"possible abstention phrase '{phrase}'"
        return True, f"abstention phrase '{phrase}'"
    return False, ""


def _unit_basis(text, cfg):
    t = nz.collapse(text)
    month = any(w in t for w in cfg["per_month_words"])
    year = any(w in t for w in cfg["per_year_words"])
    if month and not year:
        return "month"
    if year and not month:
        return "year"
    return None


def _truth_basis(unit):
    u = (unit or "").lower()
    if "per month" in u:
        return "month"
    if "per year" in u:
        return "year"
    return None


def score_number(truth, answer, stale, cfg):
    """Returns (outcome, reason)."""
    expected = nz.extract_numbers(truth["expected_answer"])
    if not expected:
        return "pending_review", "expected answer has no number"
    given = nz.extract_numbers(answer)
    if not given:
        return "pending_review", "no number found in answer"

    stale_nums = {}
    for s in stale:
        for n in nz.extract_numbers(s["value"]):
            stale_nums[n] = s
    question_nums = set(nz.extract_numbers(truth["question"]))
    lo, hi = cfg["competing_number_ratio"]

    truth_basis, given_basis = _truth_basis(truth["unit"]), _unit_basis(answer, cfg)
    unit_mismatch = truth_basis and given_basis and truth_basis != given_basis

    if all(e in given for e in expected):
        others = [n for n in given if n not in expected]
        stale_hits = [n for n in others if n in stale_nums]
        if stale_hits:
            return "pending_review", f"answer has the expected value and also known stale/alternate value {_fmt(stale_hits[0])}"
        competing = [
            n for n in others
            if n not in question_nums and not nz.is_year(n, cfg["year_range"])
            and any(lo * e <= n <= hi * e for e in expected)
        ]
        if competing:
            return "pending_review", f"answer has the expected value and also competing number {_fmt(competing[0])}"
        if unit_mismatch:
            return "wrong_value", f"unit basis differs: expected per {truth_basis}, answer says per {given_basis}"
        return "correct", ""

    hits = [stale_nums[n] for n in given if n in stale_nums]
    if hits:
        if any(h["rule"] == "review" for h in hits):
            h = next(h for h in hits if h["rule"] == "review")
            return "pending_review", f"matches review-rule value {h['value']}: {h['reason']}"
        return "stale", f"matches known stale value {hits[0]['value']}: {hits[0]['reason']}"
    if unit_mismatch:
        return "wrong_value", f"unit basis differs: expected per {truth_basis}, answer says per {given_basis}"
    return "wrong_value", f"expected {truth['expected_answer']}, got numbers {', '.join(_fmt(n) for n in given)}"


def score_yes_no(truth, answer, stale, cfg):
    hedge = nz.contains_phrase(answer, cfg["hedge_phrases"])
    if hedge:
        return "pending_review", f"hedged answer ('{hedge}')"
    pols = set(nz.yes_no_polarities(answer))
    if not pols:
        return "pending_review", "no clear yes/no in answer"
    if len(pols) > 1:
        return "pending_review", "answer contains both yes and no"
    given = pols.pop()
    expected = nz.first_polarity(truth["expected_answer"])
    if expected is None:
        return "pending_review", "expected answer has no yes/no"
    if given == expected:
        return "correct", ""
    for s in stale:
        if nz.first_polarity(s["value"]) == given:
            if s["rule"] == "review":
                return "pending_review", f"matches review-rule value {s['value']}: {s['reason']}"
            return "stale", f"matches known stale value {s['value']}: {s['reason']}"
    return "wrong_value", f"expected {expected}, got {given}"


def suggest_text_label(truth, answer, cfg):
    cov = nz.term_coverage(truth["expected_answer"], answer, cfg["stopwords"])
    if cov is None:
        return "", "key-term coverage not computable"
    label = "correct" if cov >= cfg["suggested_correct_coverage"] else "wrong_value"
    return label, f"key-term coverage {cov:.2f}"


def citation_checks(truth, answer_row, answered, cfg):
    """(citation_ok, citation_matches_truth_domain) as True/False/None (None = not applicable)."""
    if not answer_row or not answered:
        return None, None
    host = nz.url_host(answer_row["source_url"])
    ok = bool(host) and nz.is_gov_host(host, cfg["gov_domain_suffixes"])
    truth_host = nz.url_host(truth["official_source_url"])
    if not truth_host:
        return ok, None
    if not host:
        return ok, False
    sufs = cfg["multi_label_suffixes"]
    return ok, nz.registrable_domain(host, sufs) == nz.registrable_domain(truth_host, sufs)


def score_claim(truth, answer_row, stale, manual_label, cfg):
    """Score one claim. Returns a dict of fields used by claim_scores.csv / needs_review.csv."""
    atype = truth["answer_type"]
    answer = answer_row["answer"] if answer_row else ""
    flag = answer_row["abstain"] if answer_row else False

    abstained, abst_reason = (False, "")
    if answer_row and (answer.strip() or flag):
        abstained, abst_reason = detect_abstention(answer, flag, atype, cfg)
    answered = bool(answer_row) and bool(answer.strip()) and not abstained

    res = {
        "outcome": "", "reason": "", "suggested_label": "", "review_source": "auto",
        "abstained": abstained if answer_row else None,
        "answered": answered,
        "given_answer": answer,
        "given_source_url": answer_row["source_url"] if answer_row else "",
        "supporting_quote": answer_row["supporting_quote"] if answer_row else "",
    }
    res["citation_ok"], res["citation_matches_truth_domain"] = citation_checks(truth, answer_row, answered, cfg)

    if not truth["expected_answer"].strip():
        res.update(outcome="not_scoreable", reason="truth row has no expected answer", review_source="")
    elif manual_label:
        res.update(outcome=manual_label["label"], review_source="manual",
                   reason=f"manual label by {manual_label.get('labeled_by', '')}".strip())
    elif not answer_row or (not answer.strip() and not flag):
        res.update(outcome="no_answer", reason="question missing from run" if not answer_row else "blank answer")
    elif is_abstain_truth(truth):
        res.update(outcome="correct_abstention" if abstained else "should_have_abstained", reason=abst_reason)
    elif abstained:
        res.update(outcome="wrong_abstention", reason=abst_reason)
    elif atype == "number":
        res["outcome"], res["reason"] = score_number(truth, answer, stale, cfg)
    elif atype == "yes/no":
        res["outcome"], res["reason"] = score_yes_no(truth, answer, stale, cfg)
    else:  # text, date, or anything unexpected
        label, why = suggest_text_label(truth, answer, cfg)
        if abst_reason:
            label, why = "wrong_abstention", f"{abst_reason}; {why}"
        res.update(outcome="pending_review", suggested_label=label,
                   reason=f"{atype or 'unknown'} answers need a human label; {why}")

    out = res["outcome"]
    if out in UNSCORED_OUTCOMES:
        res["is_correct"] = res["is_hallucination"] = res["is_critical_error"] = None
    else:
        res["is_correct"] = out in CORRECT_OUTCOMES
        res["is_hallucination"] = out in HALLUCINATION_OUTCOMES
        res["is_critical_error"] = res["is_hallucination"] and critical_eligible(truth, cfg)
    return res


def trace_details(truth, answer_row, stale, cfg):
    """What the scorer saw, for claim_trace.csv. Read-only: uses the same helpers as score_claim
    and never changes an outcome."""
    atype = truth["answer_type"]
    answer = answer_row["answer"] if answer_row else ""
    out = {"extracted_numbers": "", "expected_numbers": "", "yes_no_tokens": "",
           "abstention_detected": None, "abstention_reason": "", "stale_matches": ""}
    if not answer_row:
        return out
    flag = answer_row["abstain"]
    if answer.strip() or flag:
        out["abstention_detected"], out["abstention_reason"] = detect_abstention(answer, flag, atype, cfg)
    else:
        out["abstention_detected"] = False
    matches = []
    if atype == "number":
        given = nz.extract_numbers(answer)
        out["extracted_numbers"] = "; ".join(_fmt(n) for n in given)
        out["expected_numbers"] = "; ".join(_fmt(n) for n in nz.extract_numbers(truth["expected_answer"]))
        for s in stale:
            if any(n in given for n in nz.extract_numbers(s["value"])):
                matches.append(f"{s['value']} ({s['rule']})")
    elif atype == "yes/no":
        tokens = nz.yes_no_polarities(answer)
        out["yes_no_tokens"] = "; ".join(tokens)
        for s in stale:
            if tokens and nz.first_polarity(s["value"]) in tokens:
                matches.append(f"{s['value']} ({s['rule']})")
    out["stale_matches"] = "; ".join(matches)
    return out


def _fmt(n):
    return str(int(n)) if float(n).is_integer() else f"{n:.2f}"
