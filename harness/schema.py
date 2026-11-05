"""Single source of truth for output files and columns. Writers and SCHEMA.md both use this."""

OUTCOME_DOC = (
    "`correct`, `wrong_value`, `stale`, `correct_abstention`, `should_have_abstained`, "
    "`wrong_abstention`, `no_answer`, `pending_review`, `not_scoreable`"
)

_METRIC_DOCS = {
    "n_runs": "Number of run files (CSVs) read for this arm.",
    "n_questions": "Number of truth questions in this eval run (after `--only-verified`, if used).",
    "n_scored": "Claims with a final outcome (everything except `pending_review` and `not_scoreable`). Denominator of every rate unless stated.",
    "n_pending_review": "Claims waiting for a human label in `truth/manual_labels.csv`. Excluded from rates.",
    "n_not_scoreable": "Claims whose truth row has no expected answer. Excluded from rates.",
    "hallucination_rate": "(`wrong_value` + `stale` + `should_have_abstained`) / n_scored. 0-1.",
    "accuracy": "(`correct` + `correct_abstention`) / n_scored. 0-1.",
    "critical_error_count": "Hallucinations on eligibility yes/no questions or income-threshold questions (rule in config.json). Target: 0.",
    "critical_error_rate": "critical_error_count / n_scored. 0-1.",
    "no_answer_rate": "`no_answer` / n_scored. 0-1.",
    "abstention_rate": "(`correct_abstention` + `wrong_abstention`) / n_scored. 0-1.",
    "correct_abstention_rate": "`correct_abstention` / scored claims whose truth is ABSTAIN. Blank if none.",
    "wrong_abstention_rate": "`wrong_abstention` / scored claims whose truth has a value. Blank if none.",
    "citation_ok_rate": "Share of answered claims whose cited URL is well formed and on a government domain (config.json). Not checked against page content. Not part of the hallucination rate.",
    "citation_matches_truth_domain_rate": "Share of answered claims whose cited URL has the same registrable domain as the truth row's `official_source_url`. Not part of the hallucination rate.",
    "consistency": "Only when an arm has 2+ runs: share of scoreable questions where every run gave the same normalized answer. Blank otherwise.",
    "stale_rate": "`stale` / scored claims whose truth row is `recently_changed = Y` (within the slice). Blank if none.",
}

FILES = {
    "claim_scores.csv": {
        "about": "Main fact table. One row per arm x run x question.",
        "columns": [
            ("eval_run_id", "Eval run id, `YYYYMMDD-HHMMSS` in UTC plus an optional `-label`."),
            ("scored_at", "UTC timestamp of the eval run, ISO 8601."),
            ("arm", "`simple` or `complex`."),
            ("run_id", "Input file name without `.csv`."),
            ("question_id", "Truth question id."),
            ("program", "From the truth file."),
            ("jurisdiction", "From the truth file (`Colorado` or `Federal`)."),
            ("category", "`numeric threshold`, `eligibility yes/no`, `procedural` or `should abstain`."),
            ("answer_type", "`number`, `yes/no`, `text`, `date` or `abstain`."),
            ("unit", "What the number means, from the truth file."),
            ("recently_changed", "`Y` or `N`. `Y` rows are the stale-answer traps."),
            ("effective_date", "From the truth file. ISO date or blank."),
            ("truth_status", "The truth row's `status`, carried as-is for filtering."),
            ("expected_answer", "The answer key value."),
            ("given_answer", "The answer from the run (blank if missing)."),
            ("given_source_url", "The URL the run cited."),
            ("outcome", OUTCOME_DOC + "."),
            ("is_correct", "`true` for `correct`/`correct_abstention`, else `false`. Blank for `pending_review`/`not_scoreable`."),
            ("is_hallucination", "`true` for `wrong_value`/`stale`/`should_have_abstained`. Blank for `pending_review`/`not_scoreable`."),
            ("is_critical_error", "`true` if a hallucination on a critical question. Blank for `pending_review`/`not_scoreable`."),
            ("answered", "`true` if the run gave a non-abstaining, non-blank answer."),
            ("abstained", "`true` if the run abstained (flag, marker, or abstention phrase). Blank if the row is missing."),
            ("citation_ok", "`true` if the cited URL is well formed and on a government domain. Blank unless answered."),
            ("citation_matches_truth_domain", "`true` if the cited URL's registrable domain equals the truth URL's. Blank unless answered and the truth row has a URL."),
            ("review_source", "`auto` (scored by rules), `manual` (from `truth/manual_labels.csv`), blank for `not_scoreable`."),
        ],
    },
    "claim_trace.csv": {
        "about": "Provenance of every claim, one row per arm x run x question (same keys as claim_scores.csv). "
                 "Use it to track a number back to the input file, the exact line, what the harness extracted, "
                 "and the rule that set the outcome.",
        "columns": [
            ("eval_run_id", "Eval run id."),
            ("arm", "`simple` or `complex`."),
            ("run_id", "Input file name without `.csv`."),
            ("question_id", "Truth question id."),
            ("source_file", "Path of the input CSV this claim came from."),
            ("source_line", "Line in that CSV where the row starts (the header is line 1). Blank if the question is missing from the file."),
            ("matched_by", "`question_id`, `question_text` (no usable id, matched on the question wording) or `missing`."),
            ("raw_answer", "The answer cell exactly as read (trimmed)."),
            ("raw_source_url", "The source URL cell as read."),
            ("raw_supporting_quote", "The supporting quote cell as read."),
            ("raw_abstain", "The abstain cell as read, before it is turned into true/false."),
            ("raw_confidence", "The confidence cell as read."),
            ("answer_type", "From the truth file: how the answer is compared."),
            ("unit", "From the truth file."),
            ("expected_answer", "The answer key value."),
            ("extracted_numbers", "Number answers: every number the harness found in the answer, `; `-separated. Blank otherwise."),
            ("expected_numbers", "Number answers: the numbers that must all be present."),
            ("yes_no_tokens", "Yes/no answers: the yes/no tokens found, in order, `; `-separated."),
            ("abstention_detected", "`true` if the answer counted as an abstention. Blank if the row is missing."),
            ("abstention_reason", "Why it counted as an abstention (flag, marker, phrase), or a possible-abstention note for text answers."),
            ("stale_matches", "Known stale/review values from `truth/known_stale_values.csv` found in the answer, as `value (rule)`."),
            ("outcome", "Same as claim_scores.csv."),
            ("review_source", "`auto`, `manual`, or blank for `not_scoreable`."),
            ("scoring_reason", "The rule that decided the outcome, in words. Blank for a plain match."),
            ("suggested_label", "Harness suggestion for pending text/date answers. Not an outcome."),
            ("manual_labeled_by", "Who set the manual label, if any."),
            ("manual_labeled_on", "When the manual label was set."),
            ("manual_note", "Note on the manual label."),
            ("truth_supporting_quote", "The answer key's supporting quote."),
            ("truth_source_url", "The answer key's official source URL."),
            ("truth_status", "The truth row's `status`."),
        ],
    },
    "summary_by_arm.csv": {
        "about": "One row per arm. All runs of the arm pooled.",
        "columns": [("eval_run_id", "Eval run id."), ("arm", "`simple` or `complex`.")] + [
            (c, _METRIC_DOCS[c]) for c in [
                "n_runs", "n_questions", "n_scored", "n_pending_review", "n_not_scoreable",
                "hallucination_rate", "accuracy", "critical_error_count", "critical_error_rate",
                "no_answer_rate", "abstention_rate", "correct_abstention_rate", "wrong_abstention_rate",
                "citation_ok_rate", "citation_matches_truth_domain_rate", "consistency",
            ]
        ],
    },
    "summary_by_run.csv": {
        "about": "Same metrics as summary_by_arm.csv, one row per arm x run (useful once an arm has several runs).",
        "columns": [("eval_run_id", "Eval run id."), ("arm", "`simple` or `complex`."), ("run_id", "Input file name without `.csv`.")] + [
            (c, _METRIC_DOCS[c]) for c in [
                "n_scored", "n_pending_review", "n_not_scoreable",
                "hallucination_rate", "accuracy", "critical_error_count", "critical_error_rate",
                "no_answer_rate", "abstention_rate", "correct_abstention_rate", "wrong_abstention_rate",
                "stale_rate", "citation_ok_rate", "citation_matches_truth_domain_rate",
            ]
        ],
    },
    "summary_by_slice.csv": {
        "about": "Long format. One row per arm x slice.",
        "columns": [
            ("eval_run_id", "Eval run id."),
            ("arm", "`simple` or `complex`."),
            ("slice_type", "`category`, `program`, `jurisdiction` or `recently_changed`."),
            ("slice_value", "The value of the slice (e.g. `SNAP`, `Federal`, `Y`)."),
            ("n_scored", _METRIC_DOCS["n_scored"]),
            ("hallucination_rate", _METRIC_DOCS["hallucination_rate"]),
            ("accuracy", _METRIC_DOCS["accuracy"]),
            ("critical_error_count", _METRIC_DOCS["critical_error_count"]),
            ("stale_rate", _METRIC_DOCS["stale_rate"]),
        ],
    },
    "comparison_by_question.csv": {
        "about": "Side-by-side, one row per question. Outcomes are the majority outcome across runs (ties go to the worse outcome).",
        "columns": [
            ("eval_run_id", "Eval run id."),
            ("question_id", "Truth question id."),
            ("program", "From the truth file."),
            ("category", "From the truth file."),
            ("recently_changed", "`Y` or `N`."),
            ("expected_answer", "The answer key value."),
            ("simple_given_answer", "Answer from the simple arm (from a run with the majority outcome)."),
            ("complex_given_answer", "Answer from the complex arm."),
            ("simple_outcome", "Majority outcome for the simple arm; `pending_review`/`not_scoreable` if no run is scored; blank if the arm has no runs."),
            ("complex_outcome", "Same for the complex arm."),
            ("simple_correct_rate", "Share of the simple arm's scored runs that were correct. Blank if none scored."),
            ("complex_correct_rate", "Same for the complex arm."),
            ("difference", "complex_correct_rate - simple_correct_rate. Blank if either side is blank."),
            ("winner", "`simple`, `complex`, `tie`, or `n/a` when either side is unscored."),
        ],
    },
    "overall_comparison.csv": {
        "about": "Headline comparison, paired by question over questions scored in both arms, with a 95% bootstrap CI resampling questions.",
        "columns": [
            ("eval_run_id", "Eval run id."),
            ("metric", "`hallucination_rate`, `accuracy`, `critical_error_rate`, `no_answer_rate`, `wrong_abstention_rate`, `stale_rate_recently_changed`."),
            ("simple", "Metric for the simple arm over the paired questions (majority outcome per question)."),
            ("complex", "Metric for the complex arm over the paired questions."),
            ("difference_complex_minus_simple", "complex - simple. Negative is better for error rates, positive is better for accuracy."),
            ("ci_low", "Lower bound of the bootstrap interval for the difference. Blank if not computable."),
            ("ci_high", "Upper bound of the bootstrap interval."),
            ("n_questions", "Number of paired questions used."),
            ("note", "Plain-language caveats (sample size, interval includes 0, incomplete comparison)."),
        ],
    },
    "needs_review.csv": {
        "about": "Every `pending_review` claim. Copy rows into `truth/manual_labels.csv` with a label and re-run.",
        "columns": [
            ("eval_run_id", "Eval run id."),
            ("arm", "`simple` or `complex`."),
            ("run_id", "Input file name without `.csv`."),
            ("question_id", "Truth question id."),
            ("question", "Question text."),
            ("expected_answer", "The answer key value."),
            ("given_answer", "The answer from the run."),
            ("supporting_quote", "The quote the run relied on."),
            ("suggested_label", "Harness suggestion (text/date: key-term coverage >= threshold -> `correct`, else `wrong_value`). Blank if none."),
            ("reason", "Why the harness could not decide."),
        ],
    },
    "ingestion_report.csv": {
        "about": "Everything unusual found while reading inputs (aliases, duplicates, unmatched rows, missing questions, label problems).",
        "columns": [
            ("eval_run_id", "Eval run id."),
            ("arm", "`simple`, `complex`, or blank for truth/label files."),
            ("run_id", "Input file name without `.csv`, or blank."),
            ("file", "Path of the file the issue is about."),
            ("issue", "Short issue type."),
            ("detail", "Details (line number, values)."),
        ],
    },
}

HISTORY_COLUMNS = [
    ("eval_run_id", "Eval run id."),
    ("scored_at", "UTC timestamp, ISO 8601."),
    ("label", "The `--label` given, or blank."),
    ("truth_sha256", "SHA-256 of the truth file used, so runs on different answer keys can be told apart."),
    ("arm", "`simple` or `complex`; blank for `complex_minus_simple_*` rows."),
    ("metric", "Metric name (per-arm metrics, or `complex_minus_simple_<metric>` for the paired difference)."),
    ("value", "Metric value (rates 0-1)."),
    ("ci_low", "Bootstrap CI low (difference rows only)."),
    ("ci_high", "Bootstrap CI high (difference rows only)."),
    ("n_scored", "Denominator: scored claims for arm rows, paired questions for difference rows."),
    ("comparison_complete", "`true` if both arms had at least one run."),
]

HISTORY_ARM_METRICS = [
    "hallucination_rate", "accuracy", "critical_error_count", "critical_error_rate",
    "no_answer_rate", "abstention_rate", "wrong_abstention_rate", "citation_ok_rate",
    "citation_matches_truth_domain_rate", "n_pending_review", "n_not_scoreable",
]


def columns(file_name):
    return [c for c, _ in FILES[file_name]["columns"]]


def render_schema_md():
    lines = [
        "# Results data dictionary",
        "",
        "Generated by the harness on every run. All CSVs are UTF-8 with one header row, snake_case columns,",
        "long/tidy format, ISO 8601 dates and UTC timestamps, booleans as `true`/`false`, rates as decimals",
        "from 0 to 1, and an empty cell for \"not applicable\". Arm names are always `simple` and `complex`.",
        "Column names and order never change between eval runs.",
        "",
        "## Layout",
        "",
        "- `results/<eval_run_id>/`: one folder per eval run with every file below.",
        "- `results/latest/`: a copy of the most recent eval run.",
        "- `results/history.csv`: append-only, headline metrics of every eval run (plot this over time).",
        "",
        "## Outcomes",
        "",
        "| outcome | hallucination? | in rates? |",
        "|---|---|---|",
        "| `correct` | no | yes |",
        "| `wrong_value` | **yes** | yes |",
        "| `stale` | **yes** | yes |",
        "| `correct_abstention` | no | yes |",
        "| `should_have_abstained` | **yes** | yes |",
        "| `wrong_abstention` | no (counted separately) | yes |",
        "| `no_answer` | no (counted separately) | yes |",
        "| `pending_review` | until labeled | no |",
        "| `not_scoreable` | no | no |",
        "",
    ]
    for name, spec in FILES.items():
        lines += [f"## `{name}`", "", spec["about"], "", "| column | description |", "|---|---|"]
        lines += [f"| `{c}` | {d} |" for c, d in spec["columns"]]
        lines.append("")
    lines += ["## `history.csv`", "", "Append-only. One row per arm x metric per eval run, plus difference rows.",
              "", "| column | description |", "|---|---|"]
    lines += [f"| `{c}` | {d} |" for c, d in HISTORY_COLUMNS]
    lines += ["", "## `run_metadata.json`", "",
              "Eval run id, UTC timestamp, label, folders and files read with row counts, truth file name and SHA-256,",
              "truth status counts, the full config used, whether `--only-verified` was on, manual labels applied,",
              "pending/not-scoreable counts, `comparison_complete`, and a plain-language `warnings` list.", ""]
    return "\n".join(lines)
