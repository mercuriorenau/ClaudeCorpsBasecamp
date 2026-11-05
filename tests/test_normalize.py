import unittest

from harness import normalize as nz
from harness.config import load_config
from harness.score import detect_abstention

CFG = load_config()


class NumberNormalization(unittest.TestCase):
    def test_dollars_and_commas(self):
        self.assertEqual(nz.extract_numbers("$1,234"), [1234.0])

    def test_trailing_decimals(self):
        self.assertEqual(nz.extract_numbers("1234.00"), [1234.0])

    def test_percent(self):
        self.assertEqual(nz.extract_numbers("150%"), [150.0])
        self.assertEqual(nz.extract_numbers("150% of FPL"), [150.0])

    def test_multiple_values(self):
        self.assertEqual(nz.extract_numbers("100 (single); 200 (couple)"), [100.0, 200.0])
        self.assertEqual(nz.extract_numbers("$1,000 single, $2,500 couple"), [1000.0, 2500.0])

    def test_no_number(self):
        self.assertEqual(nz.extract_numbers("about four thousand"), [])

    def test_words_glued_to_digits_ignored(self):
        self.assertEqual(nz.extract_numbers("FY2099 value is 321"), [321.0])


class YesNo(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(nz.yes_no_polarities("Yes"), ["yes"])
        self.assertEqual(nz.yes_no_polarities("No."), ["no"])
        self.assertEqual(nz.yes_no_polarities("true"), ["yes"])
        self.assertEqual(nz.yes_no_polarities("FALSE"), ["no"])

    def test_generally(self):
        self.assertEqual(nz.first_polarity("Yes, generally"), "yes")

    def test_no_as_determiner_is_not_an_answer(self):
        self.assertEqual(nz.yes_no_polarities("Yes, workers with no qualifying children can"), ["yes"])

    def test_both(self):
        self.assertEqual(set(nz.yes_no_polarities("Yes for renters; no for owners.")), {"yes", "no"})

    def test_none(self):
        self.assertEqual(nz.yes_no_polarities("The credit is refundable"), [])


class Abstention(unittest.TestCase):
    def test_flag(self):
        self.assertTrue(detect_abstention("anything", True, "number", CFG)[0])

    def test_markers(self):
        for a in ["", "ABSTAIN", "N/A", "unknown", "  Unknown "]:
            self.assertTrue(detect_abstention(a, False, "number", CFG)[0], a)

    def test_phrases_without_value(self):
        for a in ["I cannot determine this", "This has not been published.",
                  "Unable to find an official figure", "No official source states this",
                  "Can't verify"]:
            self.assertTrue(detect_abstention(a, False, "number", CFG)[0], a)

    def test_phrase_with_value_is_not_abstention(self):
        # A correct 'No' answer that happens to contain 'not available'.
        self.assertFalse(detect_abstention("No, the credit is not available for tax year 2026.", False, "yes/no", CFG)[0])
        self.assertFalse(detect_abstention("$1,234; the 2099 figure is not published yet", False, "number", CFG)[0])

    def test_plain_value(self):
        self.assertFalse(detect_abstention("$1,234", False, "number", CFG)[0])

    def test_abstain_question(self):
        self.assertTrue(detect_abstention("It depends on your household income.", False, "abstain", CFG)[0])
        self.assertFalse(detect_abstention("No.", False, "abstain", CFG)[0])


class KeyTerms(unittest.TestCase):
    def test_months_and_prefixes(self):
        self.assertEqual(nz.term_coverage("Nov 1 to Apr 30", "November 1 through April 30", CFG["stopwords"]), 1.0)

    def test_partial(self):
        cov = nz.term_coverage("Online portal; paper application", "Online only", CFG["stopwords"])
        self.assertLess(cov, 0.8)


class Domains(unittest.TestCase):
    def test_registrable(self):
        sufs = CFG["multi_label_suffixes"]
        self.assertEqual(nz.registrable_domain("ed.cde.state.co.us", sufs), "cde.state.co.us")
        self.assertEqual(nz.registrable_domain("www.cde.state.co.us", sufs), "cde.state.co.us")
        self.assertEqual(nz.registrable_domain("hcpf.colorado.gov", sufs), "colorado.gov")

    def test_host(self):
        self.assertIsNone(nz.url_host("not a url"))
        self.assertIsNone(nz.url_host("ftp://x.gov/a"))
        self.assertEqual(nz.url_host("https://CDHS.Colorado.gov/snap"), "cdhs.colorado.gov")


if __name__ == "__main__":
    unittest.main()
