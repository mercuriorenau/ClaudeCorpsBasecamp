import unittest

from harness.metrics import bootstrap_diff, majority_outcome

PAIRS = [(1, 0), (0, 0), (1, 1), (1, 0), (0, 1), (1, 0), (0, 0), (1, 0), (0, 0), (1, 1)]


class Bootstrap(unittest.TestCase):
    def test_fixed_seed_fixed_interval(self):
        self.assertEqual(bootstrap_diff(PAIRS, 2000, 20261105, 0.95), (-0.7, 0.1))
        self.assertEqual(bootstrap_diff(PAIRS, 2000, 20261105), bootstrap_diff(PAIRS, 2000, 20261105))

    def test_interval_contains_point_estimate(self):
        lo, hi = bootstrap_diff(PAIRS, 2000, 1)
        point = sum(c - s for s, c in PAIRS) / len(PAIRS)
        self.assertLessEqual(lo, point)
        self.assertGreaterEqual(hi, point)

    def test_too_few(self):
        self.assertEqual(bootstrap_diff([(1, 0)], 2000, 1), (None, None))


class Majority(unittest.TestCase):
    def test_majority(self):
        self.assertEqual(majority_outcome(["correct", "correct", "wrong_value"]), "correct")

    def test_tie_goes_to_worse(self):
        self.assertEqual(majority_outcome(["correct", "wrong_value"]), "wrong_value")
        self.assertEqual(majority_outcome(["correct", "no_answer"]), "no_answer")

    def test_pending_ignored(self):
        self.assertEqual(majority_outcome(["pending_review", "correct"]), "correct")
        self.assertIsNone(majority_outcome(["pending_review"]))


if __name__ == "__main__":
    unittest.main()
