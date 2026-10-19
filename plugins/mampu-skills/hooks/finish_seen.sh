#!/bin/sh
# PostToolUse (team_task_finish): the close-out happened — mark finished and clear the milestone and the
# recorded change so the Stop gate lets the session end. Needs no server; silent always.
. "$(dirname "$0")/lib/work_api.sh"
input=$(cat)
sid=$(printf '%s' "$input" | session_id_from_input)
[ -n "$sid" ] || exit 0
# The project as it is now becomes the new starting point, so later changes are counted afresh.
print=$(project_print "$(printf '%s' "$input" | json_get cwd)")
[ -n "$print" ] && baseline="\"$print\"" || baseline=null
state_set "$sid" finished true milestone null changed null baseline "$baseline"
exit 0
