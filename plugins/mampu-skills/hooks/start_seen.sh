#!/bin/sh
# PostToolUse (team_task_start): copy the task the server answered with into the session state —
# started, task_guid, task_title, created — and reset finished (a second team_task_start is the
# "not that one?" correction). Needs no server; silent always.
. "$(dirname "$0")/lib/work_api.sh"
input=$(cat)
sid=$(printf '%s' "$input" | session_id_from_input)
[ -n "$sid" ] || exit 0
fields=$(printf '%s' "$input" | python3 -c '
import json, sys

def unwrap(node):
    """MCP tool responses reach hooks as the dict, as {structuredContent}, or as content blocks
    whose text is the JSON; return the dict that carries "task"."""
    for _ in range(4):
        if isinstance(node, str):
            try:
                node = json.loads(node)
            except ValueError:
                return None
        elif isinstance(node, list):
            texts = [b.get("text") for b in node if isinstance(b, dict) and b.get("type") == "text"]
            node = texts[0] if texts else None
        elif isinstance(node, dict):
            if "task" in node:
                return node
            node = node.get("structuredContent") or node.get("result") or node.get("content")
        else:
            return None
    return None

data = json.load(sys.stdin)
result = unwrap(data.get("tool_response"))
task = (result or {}).get("task")
if not isinstance(task, dict) or not task.get("guid"):
    sys.exit(0)
print(json.dumps(str(task.get("guid"))))
print(json.dumps(task.get("title")))
print(json.dumps(bool(task.get("created"))))
' 2>/dev/null) || exit 0
[ -n "$fields" ] || exit 0
guid=$(printf '%s\n' "$fields" | sed -n 1p)
title=$(printf '%s\n' "$fields" | sed -n 2p)
created=$(printf '%s\n' "$fields" | sed -n 3p)
state_set "$sid" started true task_guid "$guid" task_title "$title" created "$created" finished false
exit 0
