"""Load the answer key, the known stale values and the manual labels (all read-only)."""

import csv
import hashlib
from pathlib import Path

from .normalize import collapse

TRUTH_COLUMNS = [
    "question_id", "program", "jurisdiction", "mfb_screener_status", "category", "question",
    "answer_type", "unit", "expected_answer", "supporting_quote", "effective_date",
    "recently_changed", "official_source_url", "source_check", "date_verified", "verified_by",
    "second_check_by", "status", "notes", "preparer_note",
]
REQUIRED_TRUTH_COLUMNS = ["question_id", "category", "question", "answer_type", "expected_answer"]

STALE_COLUMNS = ["question_id", "value", "rule", "reason", "source_note"]
MANUAL_LABEL_COLUMNS = ["arm", "run_id", "question_id", "label", "labeled_by", "labeled_on", "note"]
VALID_MANUAL_LABELS = {
    "correct", "wrong_value", "stale", "should_have_abstained",
    "correct_abstention", "wrong_abstention",
}

ARM_ALIASES = {
    "simple": "simple", "simple-discovery": "simple", "simplediscovery": "simple",
    "complex": "complex", "complex-discovery": "complex", "complexdiscovery": "complex",
}


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_dicts(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        header = [(h or "").strip().lower() for h in (reader.fieldnames or [])]
        rows = []
        for raw in reader:
            row = {}
            for k, v in raw.items():
                if k is None:  # extra cells beyond the header
                    continue
                row[k.strip().lower()] = (v or "").strip() if isinstance(v, str) else ""
            if any(row.values()):
                rows.append(row)
    return header, rows


def load_truth(path):
    """Return (rows, problems). Each row has every TRUTH_COLUMNS key plus `_question_norm`."""
    header, raw_rows = _read_dicts(path)
    missing = [c for c in REQUIRED_TRUTH_COLUMNS if c not in header]
    if missing:
        raise ValueError(f"Truth file {path} is missing required columns: {', '.join(missing)}")
    problems = []
    rows, seen = [], set()
    for r in raw_rows:
        qid = r.get("question_id", "")
        if not qid:
            problems.append(("truth row without question_id", r.get("question", "")[:80]))
            continue
        if qid.upper() in seen:
            problems.append(("duplicate question_id in truth file; kept the first", qid))
            continue
        seen.add(qid.upper())
        row = {c: r.get(c, "") for c in TRUTH_COLUMNS}
        row["answer_type"] = row["answer_type"].lower()
        row["category"] = row["category"].lower()
        row["recently_changed"] = "Y" if row["recently_changed"].upper().startswith("Y") else "N"
        row["_question_norm"] = collapse(row["question"])
        rows.append(row)
    return rows, problems


def load_stale_values(path):
    """{QUESTION_ID_UPPER: [ {value, rule, reason, source_note}, ... ]} and a list of problems."""
    out, problems = {}, []
    if not path or not Path(path).exists():
        return out, [("known stale values file not found", str(path))]
    _, rows = _read_dicts(path)
    for r in rows:
        qid, rule = r.get("question_id", ""), r.get("rule", "").lower()
        if not qid or not r.get("value"):
            continue
        if rule not in ("stale", "review"):
            problems.append(("stale value has unknown rule; treated as review", f"{qid}={r.get('value')} rule={rule}"))
            rule = "review"
        out.setdefault(qid.upper(), []).append({
            "value": r["value"], "rule": rule,
            "reason": r.get("reason", ""), "source_note": r.get("source_note", ""),
        })
    return out, problems


def load_manual_labels(path):
    """{(arm, run_id, QUESTION_ID_UPPER): label_row} and a list of problems."""
    out, problems = {}, []
    if not path or not Path(path).exists():
        return out, problems
    _, rows = _read_dicts(path)
    for r in rows:
        arm = ARM_ALIASES.get(r.get("arm", "").lower())
        label = r.get("label", "").lower()
        qid = r.get("question_id", "")
        run_id = r.get("run_id", "")
        desc = f"arm={r.get('arm')} run_id={run_id} question_id={qid} label={r.get('label')}"
        if not arm or not run_id or not qid:
            problems.append(("manual label missing arm/run_id/question_id; ignored", desc))
            continue
        if label not in VALID_MANUAL_LABELS:
            problems.append(("manual label is not a valid label; ignored", desc))
            continue
        key = (arm, run_id, qid.upper())
        if key in out:
            problems.append(("duplicate manual label; kept the first", desc))
            continue
        out[key] = dict(r, label=label, arm=arm)
    return out, problems
