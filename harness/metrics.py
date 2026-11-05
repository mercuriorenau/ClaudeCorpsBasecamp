"""Metrics, slices, majority outcomes, consistency and the paired bootstrap."""

import math
import random
from collections import Counter

from . import normalize as nz
from .score import (CORRECT_OUTCOMES, HALLUCINATION_OUTCOMES, SCORED_OUTCOMES,
                    SEVERITY_ORDER, critical_eligible, is_abstain_truth)


def _rate(num, den):
    return num / den if den else None


def arm_metrics(claims):
    """Metrics over a list of claim dicts (each has 'outcome', 'truth', 'is_critical_error',
    'citation_ok', 'citation_matches_truth_domain')."""
    scored = [c for c in claims if c["outcome"] in SCORED_OUTCOMES]
    n = len(scored)
    cnt = Counter(c["outcome"] for c in scored)
    halluc = sum(cnt[o] for o in HALLUCINATION_OUTCOMES)
    correct = sum(cnt[o] for o in CORRECT_OUTCOMES)
    crit = sum(1 for c in scored if c["is_critical_error"])
    abstain_q = [c for c in scored if is_abstain_truth(c["truth"])]
    value_q = [c for c in scored if not is_abstain_truth(c["truth"])]
    recent = [c for c in scored if c["truth"]["recently_changed"] == "Y"]
    cit = [c["citation_ok"] for c in claims if c["citation_ok"] is not None]
    dom = [c["citation_matches_truth_domain"] for c in claims if c["citation_matches_truth_domain"] is not None]
    return {
        "n_scored": n,
        "n_pending_review": sum(1 for c in claims if c["outcome"] == "pending_review"),
        "n_not_scoreable": sum(1 for c in claims if c["outcome"] == "not_scoreable"),
        "hallucination_rate": _rate(halluc, n),
        "accuracy": _rate(correct, n),
        "critical_error_count": crit,
        "critical_error_rate": _rate(crit, n),
        "no_answer_rate": _rate(cnt["no_answer"], n),
        "abstention_rate": _rate(cnt["correct_abstention"] + cnt["wrong_abstention"], n),
        "correct_abstention_rate": _rate(sum(1 for c in abstain_q if c["outcome"] == "correct_abstention"), len(abstain_q)),
        "wrong_abstention_rate": _rate(sum(1 for c in value_q if c["outcome"] == "wrong_abstention"), len(value_q)),
        "stale_rate": _rate(sum(1 for c in recent if c["outcome"] == "stale"), len(recent)),
        "citation_ok_rate": _rate(sum(cit), len(cit)),
        "citation_matches_truth_domain_rate": _rate(sum(dom), len(dom)),
    }


SLICE_TYPES = {
    "category": lambda t: t["category"],
    "program": lambda t: t["program"],
    "jurisdiction": lambda t: t["jurisdiction"],
    "recently_changed": lambda t: t["recently_changed"],
}


def slice_metrics(claims):
    """[(slice_type, slice_value, metrics)] sorted for stable output."""
    out = []
    for stype, key in SLICE_TYPES.items():
        groups = {}
        for c in claims:
            groups.setdefault(key(c["truth"]) or "", []).append(c)
        for value in sorted(groups):
            out.append((stype, value, arm_metrics(groups[value])))
    return out


def majority_outcome(outcomes):
    """Majority of scored outcomes; ties go to the worse outcome. None if nothing scored."""
    scored = [o for o in outcomes if o in SCORED_OUTCOMES]
    if not scored:
        return None
    cnt = Counter(scored)
    top = max(cnt.values())
    tied = [o for o in cnt if cnt[o] == top]
    return min(tied, key=SEVERITY_ORDER.index)


def normalized_answer(truth, claim):
    """A comparable form of an answer, used for consistency across runs."""
    if claim["abstained"]:
        return ("ABSTAIN",)
    ans = claim["given_answer"]
    if not ans.strip():
        return ("",)
    if truth["answer_type"] == "number":
        return ("num",) + tuple(sorted(set(nz.extract_numbers(ans))))
    if truth["answer_type"] == "yes/no":
        return ("yn",) + tuple(sorted(set(nz.yes_no_polarities(ans))))
    return ("text", nz.collapse(ans))


def consistency(claims_by_run, truth_rows):
    """Share of scoreable questions where every run gives the same normalized answer.
    None unless there are 2+ runs."""
    if len(claims_by_run) < 2:
        return None
    qs = [t for t in truth_rows if t["expected_answer"].strip()]
    if not qs:
        return None
    same = 0
    for t in qs:
        qid = t["question_id"]
        forms = {normalized_answer(t, run[qid]) for run in claims_by_run.values()}
        same += len(forms) == 1
    return same / len(qs)


def question_indicators(truth, outcome, cfg):
    """0/1 values per question for the paired comparison, from a (majority) outcome."""
    h = int(outcome in HALLUCINATION_OUTCOMES)
    return {
        "hallucination_rate": h,
        "accuracy": int(outcome in CORRECT_OUTCOMES),
        "critical_error_rate": int(bool(h) and critical_eligible(truth, cfg)),
        "no_answer_rate": int(outcome == "no_answer"),
        "wrong_abstention_rate": int(outcome == "wrong_abstention"),
        "stale_rate_recently_changed": int(outcome == "stale") if truth["recently_changed"] == "Y" else None,
    }


def bootstrap_diff(pairs, n_resamples, seed, confidence=0.95):
    """Percentile bootstrap CI of mean(complex) - mean(simple), resampling questions.
    pairs: list of (simple_value, complex_value). Returns (low, high) or (None, None) if n < 2."""
    n = len(pairs)
    if n < 2:
        return None, None
    rng = random.Random(seed)
    diffs = []
    for _ in range(n_resamples):
        s = c = 0.0
        for _ in range(n):
            a, b = pairs[rng.randrange(n)]
            s += a
            c += b
        diffs.append((c - s) / n)
    diffs.sort()
    alpha = 1 - confidence
    lo_i = max(0, int(math.floor(alpha / 2 * n_resamples)))
    hi_i = min(n_resamples - 1, int(math.ceil((1 - alpha / 2) * n_resamples)) - 1)
    return diffs[lo_i], diffs[hi_i]
