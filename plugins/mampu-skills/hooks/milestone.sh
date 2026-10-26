#!/bin/sh
# PostToolUse (Bash): when the command RAN gh pr create / gh pr merge / stage-queue.py promote
# (not --dry-run, not inside quotes), record the milestone in the session state and ask the
# session to call team_task_milestone. Needs no server; silent otherwise.
. "$(dirname "$0")/lib/work_api.sh"
input=$(cat)
sid=$(printf '%s' "$input" | session_id_from_input)
[ -n "$sid" ] || exit 0
command=$(printf '%s' "$input" | json_get tool_input.command)
[ -n "$command" ] || exit 0
kind=$(printf '%s' "$command" | python3 "$(dirname "$0")/lib/milestone_kind.py" 2>/dev/null)
[ -n "$kind" ] || exit 0
state_set "$sid" milestone "\"$kind\"" finished false || exit 0
hook_context PostToolUse "[work-loop] milestone $kind detected. Call team_task_milestone with the URL if known; when the work is complete, call team_task_finish."
exit 0
