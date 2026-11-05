"""Entry point: python run_eval.py [--label NAME] [--only-verified] [--truth PATH] [--simple DIR] [--complex DIR]"""

import argparse
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from . import __version__, schema
from .config import PROJECT_ROOT, load_config
from .ingest import discover_runs, read_run
from .metrics import (arm_metrics, bootstrap_diff, consistency, majority_outcome,
                      question_indicators, slice_metrics)
from .outputs import append_history, refresh_latest, write_csv, write_json, write_schema
from .score import CORRECT_OUTCOMES, SCORED_OUTCOMES, score_claim, trace_details
from .truth import load_manual_labels, load_stale_values, load_truth, sha256_of

ARMS = ["simple", "complex"]
COMPARISON_METRICS = [
    "hallucination_rate", "accuracy", "critical_error_rate",
    "no_answer_rate", "wrong_abstention_rate", "stale_rate_recently_changed",
]


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Score simple vs complex discovery runs against the Colorado truth set (offline).")
    p.add_argument("--label", default="", help="name for this eval run (appended to eval_run_id)")
    p.add_argument("--only-verified", action="store_true",
                   help="score only truth rows whose status is answered or second-checked")
    p.add_argument("--truth", default=str(PROJECT_ROOT / "truth" / "colorado_truth_set.csv"))
    p.add_argument("--simple", default=None, help="folder of simple-arm CSVs (default: simple-discovery/)")
    p.add_argument("--complex", default=None, help="folder of complex-arm CSVs (default: complex-discovery/)")
    p.add_argument("--stale", default=None, help="known stale values CSV (default: next to the truth file)")
    p.add_argument("--labels", default=None, help="manual labels CSV (default: next to the truth file)")
    p.add_argument("--config", default=None, help="config.json path")
    p.add_argument("--results", default=str(PROJECT_ROOT / "results"), help="results folder")
    return p.parse_args(argv)


def _issue(arm, run_id, file, kind, detail):
    return {"arm": arm, "run_id": run_id, "file": str(file), "issue": kind, "detail": detail}


def _make_run_dir(results_dir, now, label):
    base = now.strftime("%Y%m%d-%H%M%S")
    label = re.sub(r"[^A-Za-z0-9_-]+", "-", label or "").strip("-")
    eval_run_id = f"{base}-{label}" if label else base
    candidate, i = eval_run_id, 2
    while (Path(results_dir) / candidate).exists():
        candidate = f"{eval_run_id}-{i}"
        i += 1
    run_dir = Path(results_dir) / candidate
    run_dir.mkdir(parents=True)
    return candidate, run_dir, label


def main(argv=None):
    args = parse_args(argv)
    cfg = load_config(args.config)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    scored_at = now.isoformat().replace("+00:00", "Z")

    truth_path = Path(args.truth)
    if not truth_path.exists():
        print(f"ERROR: truth file not found: {truth_path}", file=sys.stderr)
        return 2
    truth_dir = truth_path.parent
    stale_path = Path(args.stale) if args.stale else truth_dir / "known_stale_values.csv"
    labels_path = Path(args.labels) if args.labels else truth_dir / "manual_labels.csv"
    arm_dirs = {
        "simple": Path(args.simple) if args.simple else PROJECT_ROOT / cfg["arm_folders"]["simple"],
        "complex": Path(args.complex) if args.complex else PROJECT_ROOT / cfg["arm_folders"]["complex"],
    }

    results_dir = Path(args.results)
    results_dir.mkdir(parents=True, exist_ok=True)
    eval_run_id, run_dir, label = _make_run_dir(results_dir, now, args.label)

    issues, warnings = [], []

    # ---- truth, stale values, manual labels
    all_truth, truth_problems = load_truth(truth_path)
    for kind, detail in truth_problems:
        issues.append(_issue("", "", truth_path, kind, detail))
    status_counts = dict(sorted(Counter(t["status"] for t in all_truth).items()))
    if args.only_verified:
        verified = {s.lower() for s in cfg["verified_statuses"]}
        truth_rows = [t for t in all_truth if t["status"].lower() in verified]
        if not truth_rows:
            warnings.append("--only-verified is on but no truth row has status "
                            f"{' or '.join(cfg['verified_statuses'])}; nothing was scored.")
    else:
        truth_rows = all_truth
    truth_by_qid = {t["question_id"].upper(): t for t in truth_rows}

    stale, stale_problems = load_stale_values(stale_path)
    for kind, detail in stale_problems:
        issues.append(_issue("", "", stale_path, kind, detail))
    labels, label_problems = load_manual_labels(labels_path)
    for kind, detail in label_problems:
        issues.append(_issue("", "", labels_path, kind, detail))

    # ---- ingest + score
    claims = []
    arm_runs = {a: {} for a in ARMS}     # arm -> run_id -> qid -> claim
    inputs_meta = {}
    used_labels = set()
    for arm in ARMS:
        folder = arm_dirs[arm]
        files = discover_runs(folder)
        inputs_meta[arm] = {"folder": str(folder), "folder_exists": folder.is_dir(), "files": []}
        if not folder.is_dir():
            issues.append(_issue(arm, "", folder, "input folder missing", ""))
            warnings.append(f"{arm} arm: folder {folder} is missing; comparison is incomplete.")
        elif not files:
            issues.append(_issue(arm, "", folder, "input folder has no .csv files", ""))
            warnings.append(f"{arm} arm: no .csv files in {folder}; comparison is incomplete.")
        for f in files:
            run_id = f.stem
            if run_id in arm_runs[arm]:
                issues.append(_issue(arm, run_id, f, "two files with the same run_id; second ignored", ""))
                continue
            answers, run_issues, stats = read_run(f, arm, truth_rows)
            issues.extend(run_issues)
            inputs_meta[arm]["files"].append({"file": str(f), "run_id": run_id, **stats})
            per_q = {}
            for t in truth_rows:
                qkey = t["question_id"].upper()
                lkey = (arm, run_id, qkey)
                label_row = labels.get(lkey) if t["expected_answer"].strip() else None
                if label_row:
                    used_labels.add(lkey)
                ans_row, st = answers.get(qkey), stale.get(qkey, [])
                res = score_claim(t, ans_row, st, label_row, cfg)
                claim = {"arm": arm, "run_id": run_id, "question_id": t["question_id"], "truth": t, **res,
                         "source_file": str(f), "answer_row": ans_row, "label_row": label_row,
                         "trace": trace_details(t, ans_row, st, cfg)}
                claims.append(claim)
                per_q[t["question_id"]] = claim
            arm_runs[arm][run_id] = per_q

    for key, row in labels.items():
        if key not in used_labels:
            arm, run_id, qid = key
            why = "no such arm/run/question in this eval run" if qid in truth_by_qid else "question_id not in truth set (or filtered out)"
            issues.append(_issue(arm, run_id, labels_path, "manual label not applied", f"{qid}: {why}"))

    present_arms = [a for a in ARMS if arm_runs[a]]
    comparison_complete = len(present_arms) == 2

    # ---- claim_scores.csv
    claim_rows = []
    for c in claims:
        t = c["truth"]
        claim_rows.append({
            "eval_run_id": eval_run_id, "scored_at": scored_at, "arm": c["arm"], "run_id": c["run_id"],
            "question_id": t["question_id"], "program": t["program"], "jurisdiction": t["jurisdiction"],
            "category": t["category"], "answer_type": t["answer_type"], "unit": t["unit"],
            "recently_changed": t["recently_changed"], "effective_date": t["effective_date"],
            "truth_status": t["status"], "expected_answer": t["expected_answer"],
            "given_answer": c["given_answer"], "given_source_url": c["given_source_url"],
            "outcome": c["outcome"], "is_correct": c["is_correct"], "is_hallucination": c["is_hallucination"],
            "is_critical_error": c["is_critical_error"], "answered": c["answered"], "abstained": c["abstained"],
            "citation_ok": c["citation_ok"], "citation_matches_truth_domain": c["citation_matches_truth_domain"],
            "review_source": c["review_source"],
        })
    write_csv(run_dir / "claim_scores.csv", schema.columns("claim_scores.csv"), claim_rows)

    # ---- claim_trace.csv: provenance of every claim (input row -> parsing -> rule -> outcome)
    trace_rows = []
    for c in claims:
        t, a, lab, tr = c["truth"], c["answer_row"], c["label_row"], c["trace"]
        trace_rows.append({
            "eval_run_id": eval_run_id, "arm": c["arm"], "run_id": c["run_id"], "question_id": t["question_id"],
            "source_file": c["source_file"],
            "source_line": a["line"] if a else None,
            "matched_by": a["matched_by"] if a else "missing",
            "raw_answer": a["answer"] if a else "", "raw_source_url": a["source_url"] if a else "",
            "raw_supporting_quote": a["supporting_quote"] if a else "", "raw_abstain": a["abstain_raw"] if a else "",
            "raw_confidence": a["confidence"] if a else "",
            "answer_type": t["answer_type"], "unit": t["unit"], "expected_answer": t["expected_answer"],
            **tr,
            "outcome": c["outcome"], "review_source": c["review_source"],
            "scoring_reason": c["reason"], "suggested_label": c["suggested_label"],
            "manual_labeled_by": lab.get("labeled_by", "") if lab else "",
            "manual_labeled_on": lab.get("labeled_on", "") if lab else "",
            "manual_note": lab.get("note", "") if lab else "",
            "truth_supporting_quote": t["supporting_quote"], "truth_source_url": t["official_source_url"],
            "truth_status": t["status"],
        })
    write_csv(run_dir / "claim_trace.csv", schema.columns("claim_trace.csv"), trace_rows)

    # ---- summaries
    arm_summary, run_summary, slice_rows = {}, [], []
    for arm in present_arms:
        arm_claims = [c for c in claims if c["arm"] == arm]
        m = arm_metrics(arm_claims)
        m.update(eval_run_id=eval_run_id, arm=arm, n_runs=len(arm_runs[arm]), n_questions=len(truth_rows),
                 consistency=consistency(arm_runs[arm], truth_rows))
        arm_summary[arm] = m
        for run_id in sorted(arm_runs[arm]):
            rm = arm_metrics(list(arm_runs[arm][run_id].values()))
            rm.update(eval_run_id=eval_run_id, arm=arm, run_id=run_id)
            run_summary.append(rm)
        for stype, svalue, sm in slice_metrics(arm_claims):
            slice_rows.append({"eval_run_id": eval_run_id, "arm": arm, "slice_type": stype,
                               "slice_value": svalue, **sm})
    write_csv(run_dir / "summary_by_arm.csv", schema.columns("summary_by_arm.csv"), [arm_summary[a] for a in present_arms])
    write_csv(run_dir / "summary_by_run.csv", schema.columns("summary_by_run.csv"), run_summary)
    write_csv(run_dir / "summary_by_slice.csv", schema.columns("summary_by_slice.csv"), slice_rows)

    # ---- per-question comparison (majority outcome across runs)
    majority, per_q_rows = {a: {} for a in ARMS}, []
    for t in truth_rows:
        qid = t["question_id"]
        row = {"eval_run_id": eval_run_id, "question_id": qid, "program": t["program"],
               "category": t["category"], "recently_changed": t["recently_changed"],
               "expected_answer": t["expected_answer"]}
        rates = {}
        for arm in ARMS:
            runs = [arm_runs[arm][r][qid] for r in sorted(arm_runs[arm])]
            if not runs:
                row[f"{arm}_outcome"] = row[f"{arm}_given_answer"] = row[f"{arm}_correct_rate"] = None
                rates[arm] = None
                continue
            maj = majority_outcome([c["outcome"] for c in runs])
            majority[arm][qid] = maj
            scored = [c for c in runs if c["outcome"] in SCORED_OUTCOMES]
            rates[arm] = sum(c["outcome"] in CORRECT_OUTCOMES for c in scored) / len(scored) if scored else None
            if maj:
                row[f"{arm}_outcome"] = maj
                pick = next(c for c in runs if c["outcome"] == maj)
            else:
                row[f"{arm}_outcome"] = "not_scoreable" if any(c["outcome"] == "not_scoreable" for c in runs) else "pending_review"
                pick = runs[0]
            row[f"{arm}_given_answer"] = pick["given_answer"]
            row[f"{arm}_correct_rate"] = rates[arm]
        if rates["simple"] is None or rates["complex"] is None:
            row["difference"], row["winner"] = None, "n/a"
        else:
            d = rates["complex"] - rates["simple"]
            row["difference"] = d
            row["winner"] = "complex" if d > 0 else "simple" if d < 0 else "tie"
        per_q_rows.append(row)
    write_csv(run_dir / "comparison_by_question.csv", schema.columns("comparison_by_question.csv"), per_q_rows)

    # ---- overall comparison with bootstrap
    bs = cfg["bootstrap"]
    overall_rows = []
    for metric in COMPARISON_METRICS:
        row = {"eval_run_id": eval_run_id, "metric": metric}
        if comparison_complete:
            pairs = []
            for t in truth_rows:
                qid = t["question_id"]
                ms, mc = majority["simple"].get(qid), majority["complex"].get(qid)
                if not ms or not mc:
                    continue
                vs = question_indicators(t, ms, cfg)[metric]
                vc = question_indicators(t, mc, cfg)[metric]
                if vs is not None and vc is not None:
                    pairs.append((vs, vc))
            n = len(pairs)
            if n:
                s = sum(p[0] for p in pairs) / n
                c = sum(p[1] for p in pairs) / n
                lo, hi = bootstrap_diff(pairs, bs["n_resamples"], bs["seed"], bs["confidence"])
                row.update(simple=s, complex=c, difference_complex_minus_simple=c - s, ci_low=lo, ci_high=hi)
            row["n_questions"] = n
            row["note"] = _comparison_note(metric, n, row.get("ci_low"), row.get("ci_high"), bs)
        else:
            for arm in present_arms:
                vals = [question_indicators(t, majority[arm][t["question_id"]], cfg)[metric]
                        for t in truth_rows if majority[arm].get(t["question_id"])]
                vals = [v for v in vals if v is not None]
                row[arm] = sum(vals) / len(vals) if vals else None
            row["n_questions"] = 0
            missing = [a for a in ARMS if a not in present_arms]
            row["note"] = f"comparison incomplete: no runs for the {' and '.join(missing)} arm; no difference reported"
        overall_rows.append(row)
    write_csv(run_dir / "overall_comparison.csv", schema.columns("overall_comparison.csv"), overall_rows)

    # ---- review loop output
    review_rows = []
    for c in claims:
        if c["outcome"] == "pending_review":
            t = c["truth"]
            review_rows.append({
                "eval_run_id": eval_run_id, "arm": c["arm"], "run_id": c["run_id"], "question_id": t["question_id"],
                "question": t["question"], "expected_answer": t["expected_answer"], "given_answer": c["given_answer"],
                "supporting_quote": c["supporting_quote"], "suggested_label": c["suggested_label"], "reason": c["reason"],
            })
    write_csv(run_dir / "needs_review.csv", schema.columns("needs_review.csv"), review_rows)

    # ---- warnings
    n_pending = len(review_rows)
    n_not_scoreable = sum(1 for c in claims if c["outcome"] == "not_scoreable")
    n_unmatched = sum(1 for i in issues if i["issue"] == "unmatched row")
    if n_unmatched:
        warnings.append(f"{n_unmatched} input row(s) could not be matched to a truth question (see ingestion_report.csv).")
    if n_pending:
        warnings.append(f"{n_pending} claim(s) are pending human review; rates exclude them until labeled "
                        f"in {labels_path.name} (see needs_review.csv).")
    if n_not_scoreable:
        warnings.append(f"{n_not_scoreable} claim(s) are not scoreable because the truth row has no expected answer.")
    if not present_arms:
        warnings.append("No runs found in either arm; nothing was scored.")
    elif not comparison_complete:
        warnings.append("Comparison is incomplete: only the " + present_arms[0] + " arm has runs.")

    for i in issues:
        i["eval_run_id"] = eval_run_id
    write_csv(run_dir / "ingestion_report.csv", schema.columns("ingestion_report.csv"), issues)

    # ---- metadata
    meta = {
        "eval_run_id": eval_run_id,
        "scored_at": scored_at,
        "label": label,
        "harness_version": __version__,
        "only_verified": bool(args.only_verified),
        "comparison_complete": comparison_complete,
        "arms_present": present_arms,
        "truth": {
            "path": str(truth_path), "file_name": truth_path.name, "sha256": sha256_of(truth_path),
            "n_rows": len(all_truth), "n_rows_in_scope": len(truth_rows), "status_counts": status_counts,
        },
        "known_stale_values": {"path": str(stale_path), "sha256": sha256_of(stale_path) if stale_path.exists() else None,
                               "n_rows": sum(len(v) for v in stale.values())},
        "manual_labels": {"path": str(labels_path), "n_rows_valid": len(labels), "n_applied": len(used_labels)},
        "inputs": inputs_meta,
        "counts": {
            "n_claims": len(claims), "n_pending_review": n_pending, "n_not_scoreable": n_not_scoreable,
            "n_unmatched_rows": n_unmatched, "n_ingestion_issues": len(issues),
            "outcomes": dict(sorted(Counter(c["outcome"] for c in claims).items())),
        },
        "config": cfg,
        "warnings": warnings,
    }
    write_json(run_dir / "run_metadata.json", meta)

    # ---- latest, history, schema
    refresh_latest(run_dir, results_dir / "latest")
    hist = []
    for arm in present_arms:
        m = arm_summary[arm]
        for metric in schema.HISTORY_ARM_METRICS:
            hist.append({"arm": arm, "metric": metric, "value": m.get(metric), "n_scored": m["n_scored"]})
    for r in overall_rows:
        if r.get("difference_complex_minus_simple") is not None:
            hist.append({"arm": "", "metric": f"complex_minus_simple_{r['metric']}",
                         "value": r["difference_complex_minus_simple"], "ci_low": r.get("ci_low"),
                         "ci_high": r.get("ci_high"), "n_scored": r["n_questions"]})
    for h in hist:
        h.update(eval_run_id=eval_run_id, scored_at=scored_at, label=label,
                 truth_sha256=meta["truth"]["sha256"], comparison_complete=comparison_complete)
    append_history(results_dir / "history.csv", hist)
    write_schema(results_dir)

    _print_summary(eval_run_id, run_dir, results_dir, labels_path, arm_summary, present_arms, overall_rows,
                   n_pending, len(used_labels), warnings, comparison_complete)
    return 0


def _comparison_note(metric, n, lo, hi, bs):
    if n == 0:
        return "no questions scored in both arms for this metric; nothing to compare"
    parts = [f"paired over {n} questions scored in both arms (majority outcome per question)"]
    if metric == "stale_rate_recently_changed":
        parts[0] += ", recently_changed = Y only"
    parts.append(f"{int(bs['confidence'] * 100)}% bootstrap CI resampling questions "
                 f"({bs['n_resamples']} resamples, seed {bs['seed']})")
    if lo is None:
        parts.append("too few questions for an interval")
    else:
        if n < 100:
            parts.append(f"with only {n} questions the interval is wide")
        parts.append("CI includes 0: no clear difference" if lo <= 0 <= hi else "CI excludes 0")
    parts.append("can differ from summary_by_arm.csv, which pools all scored claims")
    return "; ".join(parts)


def _pct(x):
    return "n/a" if x is None else f"{x * 100:.1f}%"


def _print_summary(eval_run_id, run_dir, results_dir, labels_path, arm_summary, present_arms, overall_rows,
                   n_pending, n_labels, warnings, complete):
    print()
    print(f"Eval run {eval_run_id}")
    print(f"Results: {run_dir}  (copied to {results_dir / 'latest'})")
    print()
    for arm in present_arms:
        m = arm_summary[arm]
        print(f"  {arm:<8} hallucination {_pct(m['hallucination_rate']):>7}   accuracy {_pct(m['accuracy']):>7}   "
              f"critical errors {m['critical_error_count']}   scored {m['n_scored']}   pending {m['n_pending_review']}")
    if complete:
        h = next(r for r in overall_rows if r["metric"] == "hallucination_rate")
        if h.get("difference_complex_minus_simple") is not None:
            ci = (f"95% CI [{h['ci_low'] * 100:+.1f}, {h['ci_high'] * 100:+.1f}] pts"
                  if h.get("ci_low") is not None else "no CI (too few questions)")
            print(f"\n  hallucination rate, complex - simple: {h['difference_complex_minus_simple'] * 100:+.1f} pts, "
                  f"{ci}, n={h['n_questions']} paired questions")
    print(f"\n  manual labels applied: {n_labels}")
    if n_pending:
        bar = "!" * 72
        print(f"\n{bar}\n  WARNING: {n_pending} claim(s) PENDING HUMAN REVIEW. Rates exclude them.\n"
              f"  Label them in {labels_path} (see {run_dir / 'needs_review.csv'}) and re-run.\n{bar}")
    others = [w for w in warnings if "pending human review" not in w]
    if others:
        print("\nWarnings:")
        for w in others:
            print(f"  - {w}")
    print()
