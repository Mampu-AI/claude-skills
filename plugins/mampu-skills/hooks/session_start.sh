#!/bin/sh
# SessionStart: GET work/open → inject the caller's open tasks and the one-line loop rule.
# Silent (exit 0, no output) when there is no token or the server does not answer.
. "$(dirname "$0")/lib/work_api.sh"
input=$(cat)
# Remember the project as it was when the session began, so the Stop gate sees changes made by any means.
sid=$(printf '%s' "$input" | session_id_from_input)
if [ -n "$sid" ] && [ -z "$(state_get "$sid" baseline)" ]; then
  print=$(project_print "$(printf '%s' "$input" | json_get cwd)")
  [ -n "$print" ] && state_set "$sid" baseline "\"$print\""
fi
if ! work_token >/dev/null 2>&1; then
  # Not connected: the person sees the notice directly, and the agent is told to ask before anything else.
  hook_context SessionStart \
    "[work-loop] You are not connected to the company Lark and docs yet. Before anything else, ask the person in one line to say \"connect me\": one browser sign-in with Lark, then everything else is automatic. Keep asking at each reply until the sign-in is done." \
    "Work loop: not connected. Say \"connect me\" to sign in with Lark (one browser step)."
  exit 0
fi
fetched=$(work_fetch GET open)
code=$(printf '%s\n' "$fetched" | head -n 1)
response=$(printf '%s\n' "$fetched" | tail -n +2)
case "$code" in
  2[0-9][0-9]) ;;
  401|403)
    hook_context SessionStart "[work-loop] Your work-loop sign-in on this computer has lapsed or was refused. Say \"connect me\" and I will sign you in again."
    exit 0 ;;
  *) exit 0 ;;  # switched off or unreachable: stay silent, never slow the session
esac
text=$(printf '%s' "$response" | python3 -c '
import json, sys
data = json.load(sys.stdin)
tasks = [t for t in (data.get("tasks") or []) if isinstance(t, dict) and t.get("title")]
listed = "; ".join("%s (%s)" % (t["title"], t.get("status") or "open") for t in tasks) or "none"
print("[work-loop] Open for you: " + listed + ". Rule: a reply that starts work opens with the four-line "
      "status block (Task / Records / Help page / Client); call team_task_start on the matching task or with "
      "create when none matches; call team_task_milestone on PR open/merge/promote; call team_task_finish before "
      "you finish. No code detail (source paths, function or table names, code) in titles, summaries or records. "
      "Details: the work-loop skill.")
' 2>/dev/null) || exit 0
[ -n "$text" ] || exit 0
# A Lark permission the loop needs and this sign-in has not granted: the person sees why and the link.
notice=$(printf '%s' "$response" | permission_notice) || notice=""
if [ -n "$notice" ]; then
  hook_context SessionStart "$text $(printf '%s' "$response" | permission_context)" "$notice"
else
  hook_context SessionStart "$text"
fi
exit 0
