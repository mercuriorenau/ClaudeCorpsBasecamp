"""Read the prompt-output CSVs tolerantly. Never raises on bad input; logs issues instead."""

import csv
import io
import re
from pathlib import Path

from .normalize import collapse

# normalized header key -> canonical column
ALIASES = {
    "questionid": "question_id", "id": "question_id", "qid": "question_id",
    "answer": "answer", "response": "answer", "finalanswer": "answer", "value": "answer",
    "sourceurl": "source_url", "url": "source_url", "source": "source_url", "citation": "source_url",
    "supportingquote": "supporting_quote", "quote": "supporting_quote", "evidence": "supporting_quote",
    "abstain": "abstain", "confidence": "confidence", "question": "question",
}
TRUE_WORDS = {"true", "t", "yes", "y", "1"}


def header_key(name):
    return re.sub(r"[\s_\-]+", "", (name or "").strip().lower())


def discover_runs(folder):
    """Sorted list of .csv files in folder (empty list if the folder is missing)."""
    p = Path(folder)
    if not p.is_dir():
        return []
    return sorted(f for f in p.iterdir() if f.is_file() and f.suffix.lower() == ".csv")


def _read_text(path, issue):
    data = Path(path).read_bytes()
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        issue("file is not valid UTF-8; decoded as latin-1", "")
        return data.decode("latin-1")


def read_run(path, arm, truth_rows):
    """Parse one run file.

    Returns (answers, issues, stats):
      answers: {QUESTION_ID_UPPER: {answer, source_url, supporting_quote, abstain, abstain_raw, confidence,
                                    line, matched_by}}   # line = 1-based line in the CSV (header is line 1)
      issues:  list of dicts with arm, run_id, file, issue, detail
      stats:   {rows_read, rows_matched}
    """
    path = Path(path)
    run_id = path.stem
    issues = []

    def issue(kind, detail):
        issues.append({"arm": arm, "run_id": run_id, "file": str(path), "issue": kind, "detail": detail})

    by_qid = {t["question_id"].upper(): t for t in truth_rows}
    by_text = {}
    for t in truth_rows:
        by_text.setdefault(t["_question_norm"], t["question_id"].upper())

    answers, stats = {}, {"rows_read": 0, "rows_matched": 0}
    try:
        text = _read_text(path, issue)
    except OSError as e:
        issue("could not read file", str(e))
        return answers, issues, stats

    try:
        reader = csv.reader(io.StringIO(text, newline=""))
        header = next(reader, None)
        if not header:
            issue("file is empty", "")
            return answers, issues, stats

        colmap = {}  # index -> canonical
        for i, name in enumerate(header):
            canon = ALIASES.get(header_key(name))
            if canon is None:
                if name.strip():
                    issue("unrecognized column ignored", name)
                continue
            if canon in colmap.values():
                issue("second column maps to the same field; ignored", f"{name} -> {canon}")
                continue
            if header_key(name) != header_key(canon):
                issue("column alias used", f"{name} -> {canon}")
            colmap[i] = canon
        present = set(colmap.values())
        if "answer" not in present:
            issue("no answer column found; every question counts as no_answer", ",".join(header))
        if "question_id" not in present and "question" not in present:
            issue("no question_id or question column; rows cannot be matched", ",".join(header))

        prev_line = reader.line_num  # physical lines consumed so far (the header)
        for cells in reader:
            # first physical line of this record; differs from the record count when a quoted cell has a newline
            line_no, prev_line = prev_line + 1, reader.line_num
            if not any(c.strip() for c in cells):
                continue
            stats["rows_read"] += 1
            if len(cells) > len(header):
                issue("row has more cells than the header; extras ignored", f"line {line_no}")
            row = {canon: (cells[i].strip() if i < len(cells) else "") for i, canon in colmap.items()}

            qid = row.get("question_id", "").upper()
            matched = qid if qid in by_qid else None
            matched_by = "question_id"
            if not matched:
                qnorm = collapse(row.get("question", ""))
                if qnorm and qnorm in by_text:
                    matched = by_text[qnorm]
                    matched_by = "question_text"
                    issue("matched by question text", f"line {line_no}: question_id='{row.get('question_id', '')}' -> {matched}")
            if not matched:
                issue("unmatched row", f"line {line_no}: question_id='{row.get('question_id', '')}' question='{row.get('question', '')[:80]}'")
                continue
            if matched in answers:
                issue("duplicate question_id; kept the first", f"line {line_no}: {matched}")
                continue
            answers[matched] = {
                "answer": row.get("answer", ""),
                "source_url": row.get("source_url", ""),
                "supporting_quote": row.get("supporting_quote", ""),
                "abstain": row.get("abstain", "").strip().lower() in TRUE_WORDS,
                "abstain_raw": row.get("abstain", ""),
                "confidence": row.get("confidence", ""),
                # provenance, for claim_trace.csv
                "line": line_no,
                "matched_by": matched_by,
            }
            stats["rows_matched"] += 1
    except csv.Error as e:
        issue("CSV parse error; rows after this point were skipped", str(e))

    missing = [t["question_id"] for t in truth_rows if t["question_id"].upper() not in answers]
    if missing:
        issue("questions missing from run (scored as no_answer)", ";".join(missing))
    return answers, issues, stats
