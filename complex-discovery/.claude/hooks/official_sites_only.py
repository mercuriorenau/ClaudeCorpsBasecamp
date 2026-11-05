"""Hook 1: official sites only.

Runs before Chat B uses WebFetch, WebSearch, Bash or the Chrome browser tools.
- WebFetch and browser navigation: blocks any page that isn't on allowed_sites.txt
  (including file:// and other non-web addresses).
- WebSearch: limits search results to the approved sites.
- Bash: blocks commands that try to reach the internet (a way around this hook)
  or touch the answer key.
"""
import json
import re
import sys

from common import allowed_sites, is_allowed


def deny(reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def main():
    data = json.load(sys.stdin)
    tool = data.get("tool_name", "")
    tool_input = data.get("tool_input", {}) or {}

    url = tool_input.get("url", "")
    if tool == "WebFetch" or (tool.startswith("mcp__claude-in-chrome__") and url):
        if not url.lower().startswith(("http://", "https://")) or not is_allowed(url):
            deny(
                f"Blocked: {url} is not an approved official source. "
                "Only Colorado state sites and federal agency sites are allowed "
                "(see the colorado-programs skill). Find the same information on an "
                "approved site, or answer ABSTAIN."
            )
        sys.exit(0)

    if tool == "WebSearch":
        new_input = dict(tool_input)
        new_input["allowed_domains"] = allowed_sites()
        new_input.pop("blocked_domains", None)
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "Search limited to approved official sites.",
                "updatedInput": new_input,
            }
        }))
        sys.exit(0)

    if tool == "Bash":
        command = tool_input.get("command", "")
        if re.search(r"https?://|curl|wget|invoke-webrequest|\biwr\b|urllib|requests\.", command, re.I):
            deny("Blocked: use WebFetch to open web pages, not terminal commands.")
        if re.search(r"answer[-_ ]?key", command, re.I):
            deny("Blocked: the answer key is off limits.")
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
