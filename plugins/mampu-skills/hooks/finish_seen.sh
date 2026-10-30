#!/bin/sh
# PostToolUse (team_task_finish): the close-out happened — mark finished and clear the milestone and the
# recorded change so the Stop gate lets the session end. A task closed as done, waiting or blocked is no longer
# the session's task: the next work starts it again (same work) or starts another (different work). Only a
# close-out as doing keeps it running. Needs no server; silent always.
. "$(dirname "$0")/lib/work_api.sh"
input=$(cat)
sid=$(printf '%s' "$input" | session_id_from_input)
[ -n "$sid" ] || exit 0
# The project as it is now becomes the new starting point, so later changes are counted afresh.
print=$(project_print "$(printf '%s' "$input" | json_get cwd)")
[ -n "$print" ] && baseline="\"$print\"" || baseline=null
closed=$(printf '%s' "$input" | python3 -c '
import json, sys
state = str((json.load(sys.stdin).get("tool_input") or {}).get("state") or "")
print(json.dumps(state if state in ("done", "doing", "waiting", "blocked") else "done"))
' 2>/dev/null) || closed='"done"'
[ -n "$closed" ] || closed='"done"'
if [ "$closed" = '"doing"' ]; then started=true; else started=false; fi
# The task just closed becomes the session's task, even when another was started after it.
closed_task=$(printf '%s' "$input" | python3 -c '
import json, sys
data = json.load(sys.stdin)
node = data.get("tool_response")
for _ in range(4):
    if isinstance(node, str):
        try:
            node = json.loads(node)
        except ValueError:
            node = None
    elif isinstance(node, list):
        texts = [b.get("text") for b in node if isinstance(b, dict) and b.get("type") == "text"]
        node = texts[0] if texts else None
    elif isinstance(node, dict) and not isinstance(node.get("task"), dict):
        node = node.get("structuredContent") or node.get("result") or node.get("content")
task = node.get("task") if isinstance(node, dict) and isinstance(node.get("task"), dict) else {}
guid = task.get("guid") or (data.get("tool_input") or {}).get("task_guid")
if guid:
    print(json.dumps(str(guid)))
    print(json.dumps(task.get("title")) if task.get("title") else "")
' 2>/dev/null)
guid=$(printf '%s\n' "$closed_task" | sed -n 1p)
title=$(printf '%s\n' "$closed_task" | sed -n 2p)
state_set "$sid" finished true milestone null changed null baseline "$baseline" started "$started" task_state "$closed"
[ -n "$guid" ] && state_set "$sid" task_guid "$guid"
[ -n "$title" ] && state_set "$sid" task_title "$title"
exit 0
