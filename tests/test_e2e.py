"""End-to-end on FAKE fixtures. Column lists are copied from the brief (section 8) on purpose,
independent of harness/schema.py, so any drift in the writers fails this test."""

import contextlib
import csv
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from harness.cli import main
from tests.helpers import FIXTURES

EXPECTED_COLUMNS = {
    "claim_scores.csv": "eval_run_id, scored_at, arm, run_id, question_id, program, jurisdiction, category, answer_type, unit, recently_changed, effective_date, truth_status, expected_answer, given_answer, given_source_url, outcome, is_correct, is_hallucination, is_critical_error, answered, abstained, citation_ok, citation_matches_truth_domain, review_source",
    "summary_by_arm.csv": "eval_run_id, arm, n_runs, n_questions, n_scored, n_pending_review, n_not_scoreable, hallucination_rate, accuracy, critical_error_count, critical_error_rate, no_answer_rate, abstention_rate, correct_abstention_rate, wrong_abstention_rate, citation_ok_rate, citation_matches_truth_domain_rate, consistency",
    "summary_by_slice.csv": "eval_run_id, arm, slice_type, slice_value, n_scored, hallucination_rate, accuracy, critical_error_count, stale_rate",
    "comparison_by_question.csv": "eval_run_id, question_id, program, category, recently_changed, expected_answer, simple_given_answer, complex_given_answer, simple_outcome, complex_outcome, simple_correct_rate, complex_correct_rate, difference, winner",
    "overall_comparison.csv": "eval_run_id, metric, simple, complex, difference_complex_minus_simple, ci_low, ci_high, n_questions, note",
    # Sections 3.2 / 7 columns, prefixed with eval_run_id ("every file carries eval_run_id").
    "needs_review.csv": "eval_run_id, arm, run_id, question_id, question, expected_answer, given_answer, supporting_quote, suggested_label, reason",
    "ingestion_report.csv": "eval_run_id, arm, run_id, file, issue, detail",
}


def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def header(path):
    with open(path, encoding="utf-8", newline="") as f:
        return next(csv.reader(f))


class EndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        # Copy the fake truth folder so the review-loop test can write labels without touching fixtures.
        shutil.copytree(FIXTURES / "truth", self.tmp / "truth")
        self.results = self.tmp / "results"

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_eval(self, *extra, simple=None, complex_=None, label="test"):
        argv = ["--truth", str(self.tmp / "truth" / "fake_truth_set.csv"),
                "--simple", str(simple or FIXTURES / "simple-discovery"),
                "--complex", str(complex_ or FIXTURES / "complex-discovery"),
                "--results", str(self.results), "--label", label, *extra]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(argv), 0)
        return self.results / "latest"

    def test_outputs_and_columns(self):
        latest = self.run_eval()
        for name, cols in EXPECTED_COLUMNS.items():
            self.assertTrue((latest / name).exists(), name)
            self.assertEqual(header(latest / name), [c.strip() for c in cols.split(",")], name)
        meta = json.loads((latest / "run_metadata.json").read_text())
        for key in ["eval_run_id", "scored_at", "label", "inputs", "truth", "config", "only_verified", "warnings"]:
            self.assertIn(key, meta)
        self.assertEqual(len(meta["truth"]["sha256"]), 64)
        self.assertTrue(meta["comparison_complete"])
        self.assertTrue((self.results / "SCHEMA.md").exists())
        self.assertTrue((self.results / "history.csv").exists())
        run_dirs = [p for p in self.results.iterdir() if p.is_dir() and p.name != "latest"]
        self.assertEqual(len(run_dirs), 1)

        claims = read(latest / "claim_scores.csv")
        self.assertEqual(len(claims), 24)  # 12 fake questions x 2 arms
        self.assertEqual({c["arm"] for c in claims}, {"simple", "complex"})
        by = {(c["arm"], c["question_id"]): c for c in claims}
        self.assertEqual(by[("simple", "FAKE-ALPHA-03")]["outcome"], "wrong_value")
        self.assertEqual(by[("simple", "FAKE-DELTA-01")]["outcome"], "stale")
        self.assertEqual(by[("simple", "FAKE-BETA-03")]["outcome"], "stale")
        self.assertEqual(by[("simple", "FAKE-GAMMA-02")]["outcome"], "no_answer")
        self.assertEqual(by[("simple", "FAKE-BETA-02")]["outcome"], "pending_review")
        self.assertEqual(by[("simple", "FAKE-ABS-01")]["outcome"], "correct_abstention")
        self.assertEqual(by[("simple", "FAKE-ABS-02")]["outcome"], "should_have_abstained")
        self.assertEqual(by[("complex", "FAKE-BETA-03")]["outcome"], "correct")
        self.assertEqual(by[("complex", "FAKE-DELTA-01")]["outcome"], "wrong_value")
        self.assertEqual(by[("complex", "FAKE-EMPTY-01")]["outcome"], "not_scoreable")
        self.assertEqual(by[("complex", "FAKE-EMPTY-01")]["is_correct"], "")
        for c in claims:  # format rules
            for col in ["is_correct", "is_hallucination", "answered", "abstained", "citation_ok"]:
                self.assertIn(c[col], ("true", "false", ""), col)
            self.assertNotIn(c["outcome"], ("N/A", "-"))

        overall = {r["metric"]: r for r in read(latest / "overall_comparison.csv")}
        for m in ["hallucination_rate", "accuracy", "critical_error_rate", "stale_rate_recently_changed"]:
            self.assertIn(m, overall)
            self.assertNotEqual(overall[m]["ci_low"], "")
            self.assertTrue(overall[m]["note"])

    def test_review_loop(self):
        latest = self.run_eval(label="first")
        pending = read(latest / "needs_review.csv")
        self.assertGreater(len(pending), 0)
        first_claims = read(latest / "claim_scores.csv")

        labels = self.tmp / "truth" / "manual_labels.csv"
        with open(labels, "a", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            for p in pending:
                w.writerow([p["arm"], p["run_id"], p["question_id"], p["suggested_label"] or "correct",
                            "test", "2099-01-01", "FAKE label"])

        latest = self.run_eval(label="second")
        self.assertEqual(read(latest / "needs_review.csv"), [])
        manual = [r for r in read(latest / "claim_trace.csv") if r["review_source"] == "manual"]
        self.assertEqual(len(manual), len(pending))
        self.assertTrue(all(r["manual_labeled_by"] == "test" and r["manual_labeled_on"] == "2099-01-01" for r in manual))
        meta = json.loads((latest / "run_metadata.json").read_text())
        self.assertEqual(meta["manual_labels"]["n_applied"], len(pending))
        self.assertEqual(meta["counts"]["n_pending_review"], 0)

        # Nothing else changed: unlabeled rows are identical apart from run id / timestamp.
        second = {(c["arm"], c["question_id"]): c for c in read(latest / "claim_scores.csv")}
        labeled = {(p["arm"], p["question_id"]) for p in pending}
        for c in first_claims:
            key = (c["arm"], c["question_id"])
            other = second[key]
            if key in labeled:
                self.assertEqual(other["review_source"], "manual")
                continue
            for col in c:
                if col not in ("eval_run_id", "scored_at"):
                    self.assertEqual(c[col], other[col], (key, col))

        history = read(self.results / "history.csv")
        self.assertEqual(len({h["eval_run_id"] for h in history}), 2)  # appended, not rewritten

    def test_only_verified(self):
        latest = self.run_eval("--only-verified")
        summary = read(latest / "summary_by_arm.csv")
        self.assertEqual({s["n_questions"] for s in summary}, {"2"})

    def test_missing_arm_still_runs(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        latest = self.run_eval(complex_=empty)
        meta = json.loads((latest / "run_metadata.json").read_text())
        self.assertFalse(meta["comparison_complete"])
        self.assertTrue(any("incomplete" in w for w in meta["warnings"]))
        self.assertEqual([s["arm"] for s in read(latest / "summary_by_arm.csv")], ["simple"])
        self.assertEqual({r["winner"] for r in read(latest / "comparison_by_question.csv")}, {"n/a"})

    def test_claim_trace(self):
        latest = self.run_eval()
        trace = read(latest / "claim_trace.csv")
        claims = read(latest / "claim_scores.csv")
        self.assertEqual(header(latest / "claim_trace.csv")[:4], ["eval_run_id", "arm", "run_id", "question_id"])
        self.assertIn("source_line", trace[0])
        # one trace row per claim, with the same keys and outcomes
        key = lambda r: (r["arm"], r["run_id"], r["question_id"])
        self.assertEqual({key(r): r["outcome"] for r in trace}, {key(r): r["outcome"] for r in claims})
        by = {(r["arm"], r["question_id"]): r for r in trace}
        # simple fixture: header is line 1, FAKE-ALPHA-01 is the first data row; the duplicate on line 13 was dropped
        self.assertEqual(by[("simple", "FAKE-ALPHA-01")]["source_line"], "2")
        self.assertEqual(by[("simple", "FAKE-ALPHA-01")]["raw_answer"], "$1,234")
        self.assertEqual(by[("simple", "FAKE-ALPHA-01")]["extracted_numbers"], "1234")
        self.assertEqual(by[("simple", "FAKE-DELTA-01")]["stale_matches"], "450 (stale)")
        self.assertEqual(by[("simple", "FAKE-BETA-03")]["yes_no_tokens"], "yes")
        self.assertEqual(by[("simple", "FAKE-ABS-01")]["abstention_detected"], "true")
        self.assertEqual(by[("simple", "FAKE-GAMMA-02")]["matched_by"], "missing")
        self.assertEqual(by[("simple", "FAKE-GAMMA-02")]["source_line"], "")
        self.assertEqual(by[("complex", "FAKE-ABS-02")]["matched_by"], "question_text")
        self.assertIn("unit basis differs", by[("complex", "FAKE-DELTA-01")]["scoring_reason"])
        # complex fixture: FAKE-GAMMA-01 has a quoted newline, so the row after it starts one line later
        self.assertEqual(by[("complex", "FAKE-GAMMA-01")]["source_line"], "8")
        self.assertEqual(by[("complex", "FAKE-GAMMA-02")]["source_line"], "10")

    def test_two_runs_consistency(self):
        two = self.tmp / "two"
        two.mkdir()
        src = FIXTURES / "complex-discovery" / "fake_complex_run.csv"
        shutil.copy(src, two / "run_a.csv")
        shutil.copy(src, two / "run_b.csv")
        latest = self.run_eval(complex_=two)
        summary = {s["arm"]: s for s in read(latest / "summary_by_arm.csv")}
        self.assertEqual(summary["complex"]["n_runs"], "2")
        self.assertEqual(summary["complex"]["consistency"], "1")
        self.assertEqual(summary["simple"]["consistency"], "")


if __name__ == "__main__":
    unittest.main()
