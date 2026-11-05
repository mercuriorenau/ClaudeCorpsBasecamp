"""Load config.json. Every key has a built-in default so a partial config still works."""

import copy
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.json"

_DEFAULTS = {
    "arm_folders": {"simple": "simple-discovery", "complex": "complex-discovery"},
    "verified_statuses": ["answered", "second-checked"],
    "abstention_markers": ["", "abstain", "n/a", "na", "unknown"],
    "abstention_phrases": ["cannot determine", "can't verify", "not published",
                           "not available", "unable to find", "no official source"],
    "hedge_phrases": ["it depends", "maybe", "possibly", "unclear"],
    "competing_number_ratio": [0.5, 2.0],
    "year_range": [1900, 2100],
    "per_month_words": ["per month", "monthly", "a month"],
    "per_year_words": ["per year", "annual", "annually", "yearly", "a year"],
    "suggested_correct_coverage": 0.8,
    "stopwords": ["the", "and", "for", "with"],
    "gov_domain_suffixes": [".gov", ".us", ".mil"],
    "multi_label_suffixes": ["state.co.us", "co.us"],
    "critical_error": {
        "always_categories": ["eligibility yes/no"],
        "categories_if_question_matches": {"numeric threshold": "\\bincome\\b"},
    },
    "bootstrap": {"n_resamples": 2000, "seed": 20261105, "confidence": 0.95},
}


def load_config(path=None):
    cfg = copy.deepcopy(_DEFAULTS)
    p = Path(path) if path else DEFAULT_CONFIG_PATH
    if p.exists():
        with open(p, encoding="utf-8") as f:
            user = json.load(f)
        for key, value in user.items():
            if isinstance(value, dict) and isinstance(cfg.get(key), dict):
                cfg[key].update(value)
            else:
                cfg[key] = value
    return cfg
