# truth/ (kept out of git)

This folder holds the answer key and is deliberately **not committed**, so the discovery prompts
(simple and complex) can never read the answers from the repo. Only this README is tracked.

To run the harness, put these files here on your machine:

| file | what it is | where to get it |
|---|---|---|
| `colorado_truth_set.csv` | the answer key (46 questions) | ask Santiago; share it outside the repo |
| `known_stale_values.csv` | old values that count as `stale` | same; it reveals answers too |
| `manual_labels.csv` | human labels for answers the harness can't score | starts with only the header row below |

Header for a new `manual_labels.csv`:

```
arm,run_id,question_id,label,labeled_by,labeled_on,note
```

Header for `known_stale_values.csv`:

```
question_id,value,rule,reason,source_note
```

Never copy anything from this folder into `simple-discovery/`, `complex-discovery/`, or a prompt.
