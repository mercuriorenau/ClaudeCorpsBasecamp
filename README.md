# ClaudeCorpsBasecamp

An evaluation harness for measuring **hallucinations in Claude**.

## Purpose

This repository will host tooling to systematically test whether Claude produces
false, fabricated, or unsupported information, and to track how often that
happens across prompts, models, and configurations.

## Planned scope

- **Datasets** – curated prompts with known ground truth (factual QA, citation
  checks, unanswerable questions, source-grounded summarization).
- **Runners** – scripts that send prompts to Claude models and record responses.
- **Graders** – automated and model-based scoring of responses for accuracy,
  fabrication, and appropriate abstention ("I don't know").
- **Reports** – aggregated metrics and comparisons across models and runs.

## Status

🚧 Early stage – repository just initialized. Structure and tooling are coming.

## Contributing

Ideas, eval cases, and grader improvements are welcome once the initial
structure lands.
