import unittest

from harness.config import load_config
from harness.score import score_claim
from tests.helpers import answer, truth_row

CFG = load_config()
STALE = [{"value": "1111", "rule": "stale", "reason": "FAKE old", "source_note": ""},
         {"value": "999", "rule": "review", "reason": "FAKE alt", "source_note": ""}]


def outcome(truth, text, stale=(), abstain=False, label=None, present=True):
    row = answer(text, abstain=abstain) if present else None
    return score_claim(truth, row, list(stale), label, CFG)["outcome"]


class NumberScoring(unittest.TestCase):
    t = truth_row()

    def test_correct_formats(self):
        for a in ["$1,234", "1234", "1234.00", "$1,234 per month", "$1,234 for a household of 3"]:
            self.assertEqual(outcome(self.t, a), "correct", a)

    def test_wrong(self):
        self.assertEqual(outcome(self.t, "$1,300"), "wrong_value")

    def test_unit_basis(self):
        self.assertEqual(outcome(self.t, "$1,234 per year"), "wrong_value")

    def test_stale(self):
        self.assertEqual(outcome(self.t, "$1,111", STALE), "stale")

    def test_review_rule(self):
        self.assertEqual(outcome(self.t, "$999", STALE), "pending_review")

    def test_expected_plus_stale_goes_to_review(self):
        self.assertEqual(outcome(self.t, "$1,234 (older pages say $1,111)", STALE), "pending_review")

    def test_expected_plus_competing_goes_to_review(self):
        self.assertEqual(outcome(self.t, "$1,234 or $1,500"), "pending_review")

    def test_question_numbers_and_years_are_not_competing(self):
        self.assertEqual(outcome(self.t, "$1,234 for 3 people in 2026"), "correct")

    def test_multi_value(self):
        t = truth_row(expected_answer="100 (single); 200 (couple)", unit="USD")
        self.assertEqual(outcome(t, "$100 single, $200 couple"), "correct")
        self.assertEqual(outcome(t, "$100"), "wrong_value")

    def test_no_number(self):
        self.assertEqual(outcome(self.t, "about a thousand"), "pending_review")


class YesNoScoring(unittest.TestCase):
    t = truth_row(category="eligibility yes/no", answer_type="yes/no", unit="",
                  question="Can a renter qualify for Fake Program?", expected_answer="Yes, generally")

    def test_correct(self):
        self.assertEqual(outcome(self.t, "Yes."), "correct")

    def test_wrong_is_critical(self):
        res = score_claim(self.t, answer("No"), [], None, CFG)
        self.assertEqual(res["outcome"], "wrong_value")
        self.assertTrue(res["is_hallucination"])
        self.assertTrue(res["is_critical_error"])

    def test_hedged(self):
        self.assertEqual(outcome(self.t, "Yes, but it depends on the county"), "pending_review")

    def test_both(self):
        self.assertEqual(outcome(self.t, "Yes for renters; no for owners."), "pending_review")

    def test_stale(self):
        t = truth_row(category="eligibility yes/no", answer_type="yes/no", expected_answer="No")
        stale = [{"value": "Yes", "rule": "stale", "reason": "FAKE", "source_note": ""}]
        self.assertEqual(outcome(t, "Yes", stale), "stale")
        self.assertEqual(outcome(t, "No, it is not available for 2099.", stale), "correct")


class AbstainAndMissing(unittest.TestCase):
    def test_should_abstain(self):
        t = truth_row(category="should abstain", answer_type="abstain", expected_answer="ABSTAIN", unit="")
        self.assertEqual(outcome(t, "", abstain=True), "correct_abstention")
        self.assertEqual(outcome(t, "Cannot be known yet."), "correct_abstention")
        self.assertEqual(outcome(t, "$1,500"), "should_have_abstained")

    def test_wrong_abstention(self):
        self.assertEqual(outcome(truth_row(), "N/A"), "wrong_abstention")
        self.assertEqual(outcome(truth_row(), "anything", abstain=True), "wrong_abstention")

    def test_no_answer(self):
        self.assertEqual(outcome(truth_row(), "", present=False), "no_answer")
        self.assertEqual(outcome(truth_row(), ""), "no_answer")

    def test_not_scoreable(self):
        self.assertEqual(outcome(truth_row(expected_answer=""), "$5"), "not_scoreable")

    def test_text_is_pending_with_suggestion(self):
        t = truth_row(answer_type="text", category="procedural", unit="", expected_answer="Online portal; paper application")
        res = score_claim(t, answer("Apply on the online portal or with a paper application"), [], None, CFG)
        self.assertEqual(res["outcome"], "pending_review")
        self.assertEqual(res["suggested_label"], "correct")
        self.assertIsNone(res["is_correct"])

    def test_manual_label_wins(self):
        t = truth_row(answer_type="text", expected_answer="Online portal")
        res = score_claim(t, answer("whatever"), [], {"label": "wrong_value", "labeled_by": "fake"}, CFG)
        self.assertEqual((res["outcome"], res["review_source"]), ("wrong_value", "manual"))


class Citations(unittest.TestCase):
    def test_citation_flags(self):
        t = truth_row()
        res = score_claim(t, answer("$1,234", url="https://www.fake.example.gov/other"), [], None, CFG)
        self.assertTrue(res["citation_ok"])
        self.assertTrue(res["citation_matches_truth_domain"])
        res = score_claim(t, answer("$1,234", url="https://blog.example.com/x"), [], None, CFG)
        self.assertFalse(res["citation_ok"])
        self.assertFalse(res["citation_matches_truth_domain"])
        res = score_claim(t, answer("$1,234", url=""), [], None, CFG)
        self.assertFalse(res["citation_ok"])


if __name__ == "__main__":
    unittest.main()
