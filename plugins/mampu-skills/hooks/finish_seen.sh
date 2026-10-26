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
state_set "$sid" finished true milestone null changed null baseline "$baseline" started "$started" task_state "$closed"
exit 0
