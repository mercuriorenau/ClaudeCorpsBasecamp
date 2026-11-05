"""Hook 3: final answer check.

Runs when Chat B tries to finish. If answers.csv exists, it checks it against
the discovery task's format (discovery_output_template.csv):
- the same 7 columns, in the same order
- every question_id exactly once, with the question text unchanged
- abstain is true or false; abstentions have an empty answer
- every answered row cites an approved site that Chat B actually opened,
  has a supporting quote, and has confidence high, medium or low
If anything is wrong, Chat B is sent back to fix it (up to 3 times).
"""
import csv
import json
import os
import sys

from common import LOG_DIR, is_allowed, normalize, sources_log

MAX_RETRIES = 3
COLUMNS = ["question_id", "question", "answer", "source_url", "supporting_quote", "abstain", "confidence"]
TEMPLATE = "discovery_output_template.csv"


def opened_pages(session_id):
    path = sources_log(session_id)
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        return {normalize(line.split("\t", 1)[-1]) for line in f if line.strip()}


def template_questions(project_dir):
    path = os.path.join(project_dir, "..", TEMPLATE)
    if not os.path.exists(path):
        return {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        return {row["question_id"].strip(): row["question"].strip() for row in csv.DictReader(f)}


def check(answers_path, project_dir, session_id):
    problems = []
    with open(answers_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        header = [h.strip() for h in (reader.fieldnames or [])]
        if header != COLUMNS:
            return [f"answers.csv must have exactly these columns, in this order: {','.join(COLUMNS)} (found: {','.join(header)})"]
        rows = [{k.strip(): (v or "").strip() for k, v in row.items() if k} for row in reader]

    expected = template_questions(project_dir)
    opened = opened_pages(session_id)
    seen = {}
    for row in rows:
        qid = row["question_id"]
        seen[qid] = seen.get(qid, 0) + 1
        if expected and qid in expected and row["question"] != expected[qid]:
            problems.append(f"{qid}: the question text was changed. Copy it exactly from the template.")

        abstain = row["abstain"].lower()
        if abstain not in ("true", "false"):
            problems.append(f"{qid}: abstain must be true or false.")
            continue
        if abstain == "true":
            if row["answer"]:
                problems.append(f"{qid}: abstain is true, so answer must be empty.")
            continue

        if not row["answer"]:
            problems.append(f"{qid}: abstain is false but answer is empty. Answer it, or set abstain to true.")
        if row["confidence"].lower() not in ("high", "medium", "low"):
            problems.append(f"{qid}: confidence must be high, medium or low.")
        if not row["supporting_quote"]:
            problems.append(f"{qid}: answered rows need a supporting_quote copied from the source. If you can't quote it, abstain.")
        source = row["source_url"]
        if not source.lower().startswith(("http://", "https://")):
            problems.append(f"{qid}: source_url must be the full URL of the page you quoted.")
        elif not is_allowed(source):
            problems.append(f"{qid}: {source} is not an approved official site.")
        elif normalize(source) not in opened:
            problems.append(
                f"{qid}: you cited {source} but never opened it in this session. "
                "Open it and confirm the answer, or abstain."
            )

    for qid in expected:
        if qid not in seen:
            problems.append(f"{qid}: missing from answers.csv.")
    for qid, count in seen.items():
        if count > 1:
            problems.append(f"{qid}: appears {count} times; keep one row.")
        if expected and qid not in expected:
            problems.append(f"{qid}: not a question in the template.")
    return problems


def main():
    data = json.load(sys.stdin)
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()
    answers_path = os.path.join(data.get("cwd") or project_dir, "answers.csv")
    if not os.path.exists(answers_path):
        sys.exit(0)  # not an answer run; nothing to check

    session_id = data.get("session_id", "unknown")
    problems = check(answers_path, project_dir, session_id)

    os.makedirs(LOG_DIR, exist_ok=True)
    counter = os.path.join(LOG_DIR, f"retries-{session_id}.txt")
    tries = int(open(counter).read()) if os.path.exists(counter) else 0

    if problems and tries < MAX_RETRIES:
        with open(counter, "w") as f:
            f.write(str(tries + 1))
        reason = "The final answer check found problems in answers.csv. Fix them and save the file again:\n- " + "\n- ".join(problems)
        print(json.dumps({"decision": "block", "reason": reason}))
        sys.exit(0)

    with open(os.path.join(LOG_DIR, f"check-{session_id}.txt"), "w", encoding="utf-8") as f:
        f.write("PASSED\n" if not problems else "STILL FAILING AFTER RETRIES:\n" + "\n".join(problems) + "\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
