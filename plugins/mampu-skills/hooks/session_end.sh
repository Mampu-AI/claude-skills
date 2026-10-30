#!/bin/sh
# SessionEnd: a task was started and never finished, or the session changed something after closing its task
# out → POST work/milestone kind=session_end with the last assistant line as the note, so the task carries a
# trace (the server deletes a stray agent-created task with no change recorded). Exits 0 whatever happens.
. "$(dirname "$0")/lib/work_api.sh"
input=$(cat)
sid=$(printf '%s' "$input" | session_id_from_input)
[ -n "$sid" ] || exit 0
started=$(state_get "$sid" started)
finished=$(state_get "$sid" finished)
[ "$finished" = "true" ] && exit 0
[ "$started" = "true" ] || [ -n "$(state_get "$sid" changed)" ] || exit 0
guid=$(state_get "$sid" task_guid)
[ -n "$guid" ] || exit 0
body=$(python3 -c '
import json, sys
sid, guid, note = sys.argv[1:4]
print(json.dumps({"task_guid": guid, "kind": "session_end", "url": None, "note": note or None, "session_id": sid}))
' "$sid" "$guid" "$(state_get "$sid" last_assistant)" 2>/dev/null) || exit 0
printf '%s' "$body" | work_api POST milestone >/dev/null 2>&1
exit 0
