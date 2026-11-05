"""Shared helpers for tests. All values are FAKE."""

from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FAKE_TRUTH = FIXTURES / "truth" / "fake_truth_set.csv"


def truth_row(**kw):
    row = {
        "question_id": "FAKE-T-01", "program": "Fake Program", "jurisdiction": "Colorado",
        "mfb_screener_status": "", "category": "numeric threshold",
        "question": "What is the maximum monthly income, in dollars, for a household of 3 for Fake Program?",
        "answer_type": "number", "unit": "USD per month", "expected_answer": "1234",
        "supporting_quote": "", "effective_date": "", "recently_changed": "N",
        "official_source_url": "https://fake.example.gov/x", "source_check": "", "date_verified": "",
        "verified_by": "", "second_check_by": "", "status": "draft - needs human check", "notes": "",
        "preparer_note": "",
    }
    row.update(kw)
    row["_question_norm"] = " ".join(row["question"].lower().split())
    return row


def answer(text, url="https://fake.example.gov/x", abstain=False):
    return {"answer": text, "source_url": url, "supporting_quote": "", "abstain": abstain, "confidence": ""}
