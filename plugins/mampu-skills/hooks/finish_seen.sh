#!/bin/sh
# PostToolUse (team_task_finish): the close-out happened — mark finished and clear the milestone so the
# Stop gate lets the session end. Needs no server; silent always.
. "$(dirname "$0")/lib/work_api.sh"
input=$(cat)
sid=$(printf '%s' "$input" | session_id_from_input)
[ -n "$sid" ] || exit 0
state_set "$sid" finished true milestone null
exit 0
