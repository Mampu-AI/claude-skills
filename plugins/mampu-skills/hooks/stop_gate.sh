#!/bin/sh
# Stop: remember the last assistant line (SessionEnd posts it as the session_end note), then
# block the stop once when a milestone or a change was recorded and team_task_finish has not run — a
# change with no task started asks for the task first. Passes through when stop_hook_active is set (we
# already blocked once) or nothing is pending.
. "$(dirname "$0")/lib/work_api.sh"
input=$(cat)
sid=$(printf '%s' "$input" | session_id_from_input)
[ -n "$sid" ] || exit 0

last=$(printf '%s' "$input" | python3 -c '
import json, sys
data = json.load(sys.stdin)
path = data.get("transcript_path")
last = None
try:
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if entry.get("type") != "assistant":
                continue
            content = (entry.get("message") or {}).get("content")
            texts = [b.get("text") for b in content if isinstance(b, dict) and b.get("type") == "text"] \
                if isinstance(content, list) else ([content] if isinstance(content, str) else [])
            text = " ".join(t.strip() for t in texts if isinstance(t, str) and t.strip())
            if text:
                last = text
except Exception:
    last = None
if last:
    print(json.dumps(" ".join(last.split())[:300]))
' 2>/dev/null)
[ -n "$last" ] && state_set "$sid" last_assistant "$last"

active=$(printf '%s' "$input" | json_get stop_hook_active)
[ "$active" = "true" ] && exit 0
milestone=$(state_get "$sid" milestone)
finished=$(state_get "$sid" finished)
changed=$(state_get "$sid" changed)
baseline=$(state_get "$sid" baseline)
if [ -z "$changed" ] && [ -n "$baseline" ]; then
  print=$(project_print "$(printf '%s' "$input" | json_get cwd)")
  if [ -n "$print" ] && [ "$print" != "$baseline" ]; then
    changed=file
    state_set "$sid" changed '"file"'
  fi
fi
[ -n "$milestone" ] || [ -n "$changed" ] || exit 0
[ "$finished" = "true" ] && exit 0
if [ -z "$milestone" ]; then
  # A change without a PR step (a client updated in Sapot Chat, a file edit, a commit). An unconnected
  # machine cannot start a task, so it is not held; the connect-me nudge covers it.
  work_token >/dev/null || exit 0
  if [ "$(state_get "$sid" started)" != "true" ]; then
    python3 -c '
import json
print(json.dumps({"decision": "block", "reason": (
    "[work-loop] This session changed something (project files, a commit, or a client in Sapot Chat) and no "
    "team task is started. Without asking the person, call team_task_start with the matching task, or create "
    "one when none fits, then team_task_finish with state done, doing, waiting or blocked, the one-line summary "
    "and the debrief; then print the close-out status block.")}))
' 2>/dev/null
    exit 0
  fi
fi
title=$(state_get "$sid" task_title)
[ -n "$title" ] || title="(no task started)"
python3 -c '
import json, sys
title = sys.argv[1]
reason = ("[work-loop] Close-out owed for task \"%s\": call team_task_finish with state done, doing, waiting or "
          "blocked, the one-line summary, the debrief (how, pitfalls, findings), changed paths, any record updates, "
          "and the help pages you checked; then print the close-out status block." % title)
print(json.dumps({"decision": "block", "reason": reason}))
' "$title" 2>/dev/null
exit 0
