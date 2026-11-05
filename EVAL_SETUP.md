# Eval setup: Chat A vs. Chat B (version 1)

Both chats are Claude Code with web search and the Chrome browser on, the same model, the same clean Claude profile, and the same prompt (`discovery-task-prompt.md`). The only difference is what Chat B has in its folder.

| | Chat A (control) | Chat B (skills and hooks) |
|---|---|---|
| Web search and web fetch | Yes | Yes, limited to approved official sites |
| Skills | None | benefits-research, colorado-programs, dates-and-periods, quote-then-answer |
| CLAUDE.md | None | Core rules |
| Subagent | None | verifier (re-checks each answer against its source) |
| Hooks | None | official-sites-only, source tracker, final answer check |

## Files
- `discovery-task-prompt.md`: the exact prompt both chats get
- `discovery_output_template.csv`: the template both chats fill in (46 questions, no answers)
- `chat-a/`, `chat-b/`: start Claude Code inside one of these folders
- `runs/`: saved `answers.csv` files from each run
- `chat-b/.claude/hooks/allowed_sites.txt`: the approved website list

## The answer key
Never commit the answer key. This repo is public, and Chat B's web search could find it. Keep it outside the repo (for example `Documents/answer-key-private/`). Both chats are blocked from reading that folder.

## Output format (for scoring)
Each run writes `answers.csv` in its chat folder, in the template's format:
`question_id,question,answer,source_url,supporting_quote,abstain,confidence`
`abstain` = true (with an empty answer) means the chat declined to answer.

## Requirements
Chat B's hooks need Python 3 on the computer (`python --version`).

## Versions
Each change to Chat B's skills or hooks is a new commit tagged `chat-b-v1`, `chat-b-v2`, and so on. A new version replaces the best one only if it scores better across 3 runs.
