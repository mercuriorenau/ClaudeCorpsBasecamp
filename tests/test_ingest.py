import tempfile
import unittest
from pathlib import Path

from harness.ingest import header_key, read_run, ALIASES
from harness.truth import load_stale_values, load_truth
from tests.helpers import FAKE_TRUTH, FIXTURES


class AliasMatching(unittest.TestCase):
    def test_header_keys(self):
        for name, canon in [("Question ID", "question_id"), ("question-id", "question_id"), ("QID", "question_id"),
                            ("id", "question_id"), ("Final_Answer", "answer"), ("Response", "answer"),
                            ("value", "answer"), ("URL", "source_url"), ("Citation", "source_url"),
                            ("source", "source_url"), ("Evidence", "supporting_quote"), ("quote", "supporting_quote")]:
            self.assertEqual(ALIASES[header_key(name)], canon, name)


class ReadRun(unittest.TestCase):
    def setUp(self):
        self.truth, _ = load_truth(FAKE_TRUTH)

    def test_complex_fixture(self):
        ans, issues, stats = read_run(FIXTURES / "complex-discovery" / "fake_complex_run.csv", "complex", self.truth)
        kinds = [i["issue"] for i in issues]
        self.assertIn("column alias used", kinds)
        self.assertIn("matched by question text", kinds)
        self.assertIn("unmatched row", kinds)
        self.assertIn("FAKE-ABS-02", ans)                     # matched by question text
        self.assertIn("\n", ans["FAKE-GAMMA-01"]["answer"])   # embedded newline kept
        self.assertEqual(ans["FAKE-ALPHA-01"]["answer"], "1234 per month")  # BOM header handled

    def test_simple_fixture_duplicate_and_missing(self):
        ans, issues, _ = read_run(FIXTURES / "simple-discovery" / "fake_simple_run.csv", "simple", self.truth)
        self.assertEqual(ans["FAKE-ALPHA-01"]["answer"], "$1,234")  # first kept
        kinds = [i["issue"] for i in issues]
        self.assertIn("duplicate question_id; kept the first", kinds)
        self.assertIn("questions missing from run (scored as no_answer)", kinds)
        self.assertTrue(ans["FAKE-ABS-01"]["abstain"])

    def test_bad_inputs_do_not_crash(self):
        with tempfile.TemporaryDirectory() as d:
            empty = Path(d) / "empty.csv"
            empty.write_text("")
            ans, issues, _ = read_run(empty, "simple", self.truth)
            self.assertEqual(ans, {})
            self.assertEqual(issues[0]["issue"], "file is empty")
            junk = Path(d) / "junk.csv"
            junk.write_bytes(b"foo,bar\n\xff\xfe,1\n")
            ans, issues, _ = read_run(junk, "simple", self.truth)
            self.assertEqual(ans, {})

    def test_no_question_id_column_uses_text(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "run.csv"
            f.write_text("Question,Answer\n\"  can a RENTER qualify for fake program beta? \",Yes\n", encoding="utf-8")
            ans, _, _ = read_run(f, "simple", self.truth)
            self.assertEqual(ans["FAKE-BETA-01"]["answer"], "Yes")


class StaleFile(unittest.TestCase):
    def test_load(self):
        stale, problems = load_stale_values(FIXTURES / "truth" / "known_stale_values.csv")
        self.assertEqual(problems, [])
        self.assertEqual({s["rule"] for s in stale["FAKE-ALPHA-01"]}, {"stale", "review"})


if __name__ == "__main__":
    unittest.main()
