# MFB eval harness

Offline scoring of Claude's answers to 46 Colorado benefit questions. It compares two prompt setups:
- **simple**: the control prompt, read from `simple-discovery/`
- **complex**: the prompt with skills and hooks, read from `complex-discovery/`

Both are scored against the answer key in `truth/colorado_truth_set.csv`. The harness uses Python 3 standard library only. It makes no API calls and no network requests, and it never modifies the input files.

**The answer key is not in this repo, on purpose.** Everything in `truth/` (except its README) and every results file that contains expected answers is ignored by git, so the discovery prompts can't find the answers in the repo. Get the truth files from Santiago and put them in `truth/` locally; see [truth/README.md](truth/README.md). `discovery_output_template.csv` lists the 46 questions with empty answer columns, ready for a prompt run.

## Run it

1. Put one `.csv` in `simple-discovery/` and one in `complex-discovery/`. Each file is one run of that prompt, and the file name becomes the `run_id`.
2. Run:

```
python run_eval.py                       # score everything
python run_eval.py --label round1        # name the eval run
python run_eval.py --only-verified       # only truth rows with status answered / second-checked
python -m unittest                       # tests (fake fixtures only)
```

Other options: `--truth PATH`, `--simple DIR`, `--complex DIR`, `--results DIR`, `--config PATH`.

If one folder is empty, the other arm is still scored and the comparison is marked incomplete.

## Input format (for Fernando)

The input is one row per question, with these columns:
- `question_id` (required)
- `answer`: as short as possible; `$`, `%` and commas are fine
- `source_url`
- `supporting_quote`
- `abstain`: `true`/`false`
- `confidence`: optional

Column names are matched loosely:
- Case, spaces, `_` and `-` are ignored.
- These aliases also work: `id`/`qid`, `response`/`final_answer`/`value`, `url`/`source`/`citation`, `quote`/`evidence`.
- If there is no `question_id`, a row is matched on the exact question text.

Anything odd goes to `ingestion_report.csv` instead of crashing the run.

## Results

Each eval run writes `results/<YYYYMMDD-HHMMSS>[-label]/`, and the same files are copied to `results/latest/`. Headline rows are appended to `results/history.csv`, which is never rewritten.

`results/SCHEMA.md` documents every column. The main files are:
- `claim_scores.csv`
- `claim_trace.csv`, the audit trail for every answer (see below)
- `summary_by_arm.csv`
- `summary_by_run.csv`
- `summary_by_slice.csv`
- `comparison_by_question.csv`
- `overall_comparison.csv`, which reports complex minus simple with a 95% bootstrap CI over questions
- `needs_review.csv`
- `ingestion_report.csv`
- `run_metadata.json`

Only `history.csv` (metrics, no answers) and `SCHEMA.md` are tracked in git. The per-run folders and `latest/` contain expected answers, so they stay local.

## Tracing a number back to its source

Every answer gets one row in `claim_trace.csv`, with the same keys as `claim_scores.csv` (`eval_run_id`, `arm`, `run_id`, `question_id`). To find out why an answer got its outcome:

1. Find the row in `claim_trace.csv`.
2. `source_file` and `source_line` point to the exact line in Fernando's CSV. The header is line 1.
3. `raw_answer`, `raw_source_url`, `raw_supporting_quote` and `raw_abstain` show the cells as read.
4. `extracted_numbers` / `expected_numbers`, `yes_no_tokens`, `abstention_detected` / `abstention_reason` and `stale_matches` show what the harness pulled out of the answer.
5. `scoring_reason` names the rule that set the outcome. For manual labels, `manual_labeled_by`, `manual_labeled_on` and `manual_note` show who changed it.
6. `truth_supporting_quote` and `truth_source_url` show where the expected answer came from, in case the answer key itself is wrong.

`matched_by = question_text` means the row had no usable `question_id` and was matched on the question wording. `missing` means the question wasn't in the file at all.

## How answers are scored

| outcome | hallucination? |
|---|---|
| `correct`, `correct_abstention` | no |
| `wrong_value`, `stale`, `should_have_abstained` | **yes** |
| `wrong_abstention`, `no_answer` | no, but counted separately |
| `pending_review`, `not_scoreable` | excluded from rates |

**`expected_answer` is the ground truth.** Scoring by answer type:
- **Numbers** are compared after stripping `$`, `,` and `%`. All expected numbers must appear in the answer.
  - A per-month vs per-year mix-up is `wrong_value`.
  - A value listed in `truth/known_stale_values.csv` is `stale`. Values with rule `review` go to a human instead.
  - An answer that contains the expected number *and* a competing number (for example `$1,234 for one person and $2,345 for two`) goes to review rather than being guessed.
- **Yes/no** answers are compared on the yes/no token. Hedged answers, or answers containing both yes and no, go to review.
- **Text and date** answers cannot be judged without an LLM. They always go to review, with a suggested label based on key-term overlap.
- **Critical errors** are hallucinations on `eligibility yes/no` questions, or on `numeric threshold` questions that mention income. The project target is zero. The rule is in `config.json`.

**Citations are reported separately and are not part of the hallucination rate.** Two checks are made:
- `citation_ok`: the URL is well formed and on a government domain.
- `citation_matches_truth_domain`: the URL has the same site as the truth file's source.

The harness cannot open URLs, so it does not check what is actually on the cited page.

## Manual review loop

1. After a run, open `needs_review.csv`.
2. For each row, add a line to `truth/manual_labels.csv` with these columns:
   - `arm`, `run_id`, `question_id`
   - `label`: one of `correct`, `wrong_value`, `stale`, `should_have_abstained`, `correct_abstention`, `wrong_abstention`
   - `labeled_by`, `labeled_on`, `note`
3. Re-run. Labels are applied first and nothing else changes.

The console prints a loud warning while any rows are still pending. With the current answer key, 8 of the 46 questions are text or date, so expect about 16 rows to label per eval run.

## Tuning

Abstention phrases, hedge words, government domains, the critical-error rule, and the bootstrap seed and resample count all live in `config.json`.
