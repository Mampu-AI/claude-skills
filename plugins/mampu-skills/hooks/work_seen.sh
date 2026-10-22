#!/bin/sh
# PostToolUse (every tool): once a prompt matched a team task and none is started yet, count the tool calls
# the session makes (the work loop's own tools excluded), so the Stop gate can hold a session that worked on
# a matched task without recording it. Needs no server; silent always.
. "$(dirname "$0")/lib/work_api.sh"
input=$(cat)
sid=$(printf '%s' "$input" | session_id_from_input)
[ -n "$sid" ] || exit 0
[ -n "$(state_get "$sid" matched)" ] || exit 0
[ "$(state_get "$sid" started)" = "true" ] && exit 0
case "$(printf '%s' "$input" | json_get tool_name)" in
  mcp__*mampu-tech-team__*) exit 0 ;;
esac
worked=$(state_get "$sid" worked)
state_set "$sid" worked "$(( ${worked:-0} + 1 ))"
exit 0
