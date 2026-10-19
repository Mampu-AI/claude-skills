#!/bin/sh
# PostToolUse (Edit, Write, NotebookEdit, Bash, Sapot Chat tools): when the call changed something —
# a file in a project, a git commit or push, a client change in Sapot Chat — record it in the session
# state so the Stop gate asks for a team task and its close-out. Needs no server; silent always.
. "$(dirname "$0")/lib/work_api.sh"
input=$(cat)
sid=$(printf '%s' "$input" | session_id_from_input)
[ -n "$sid" ] || exit 0
kind=$(printf '%s' "$input" | python3 "$(dirname "$0")/lib/change_kind.py" 2>/dev/null)
[ -n "$kind" ] || exit 0
state_set "$sid" changed "\"$kind\""
exit 0
