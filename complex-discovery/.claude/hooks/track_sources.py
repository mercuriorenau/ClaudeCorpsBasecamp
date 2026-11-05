"""Hook 2: source tracker.

Runs after every WebFetch or browser page visit and writes the page address to a log, so the final
check can tell real sources from made-up ones.
"""
import json
import sys
from datetime import datetime, timezone

from common import sources_log


def main():
    data = json.load(sys.stdin)
    url = (data.get("tool_input", {}) or {}).get("url", "")
    if url:
        with open(sources_log(data.get("session_id")), "a", encoding="utf-8") as f:
            f.write(f"{datetime.now(timezone.utc).isoformat()}\t{url}\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
