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
# Windows: once a day, make sure Git's shell is on the saved path, or the team tools' sign-in step never starts and
# every team tool is refused although this computer is signed in. Fixed here, before anything is refused.
windows_context=""
windows_notice=""
win_marker="$WORK_STATE_DIR/windows-path-checked"
if [ "$(cat "$win_marker" 2>/dev/null)" != "$(date +%F)" ]; then
  win=$(sh "$(dirname "$0")/../scripts/windows-path.sh" fix)
  case "$win" in ''|skip) ;; *) mkdir -p "$WORK_STATE_DIR" 2>/dev/null && date +%F > "$win_marker" ;; esac
  if [ "$win" = "fixed" ]; then
    windows_context=" A Windows setting the team tools need was just fixed on this computer (Git's shell added to the path). Tell the person in one line, before anything else, to close every VS Code window and terminal and open them again, once; until then the team tools may be refused."
    windows_notice="Work loop: fixed a Windows setting the team tools need. Close every VS Code window and terminal and open them again, once."
  fi
fi
if ! work_token >/dev/null 2>&1; then
  # Not signed in: the agent opens the Lark sign-in itself (the person only approves it), and the person is told.
  hook_context SessionStart \
    "[work-loop] This computer is not signed in to the work loop yet. Before anything else, sign the person in yourself with the onboard skill (step 2: it opens the Lark sign-in in their browser and waits). Do not wait for them to ask or say \"connect me\"; tell them in one line to approve the Lark page, then continue with their request.$windows_context" \
    "Work loop: this computer is not signed in yet. Claude will open the Lark sign-in; approve it in the browser.${windows_notice:+ $windows_notice}"
  exit 0
fi
fetched=$(work_fetch GET open)
code=$(printf '%s\n' "$fetched" | head -n 1)
response=$(printf '%s\n' "$fetched" | tail -n +2)
case "$code" in
  2[0-9][0-9]) ;;
  401|403)
    hook_context SessionStart \
      "[work-loop] This computer's work-loop sign-in has lapsed or was refused. Before anything else, sign the person in again yourself with the onboard skill (step 2); do not wait for them to ask. Tell them in one line to approve the Lark page, then continue." \
      "Work loop: this computer's sign-in lapsed. Claude will open the Lark sign-in again; approve it in the browser."
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
text="$text$windows_context"
# Stale tasks (shipped but still open, never noted, or untouched for a while): the owner is asked once a day per
# computer, and the agent records their answer. Never closed without their word.
stale=""
marker="$WORK_STATE_DIR/stale-asked"
today=$(date +%F)
if [ "$(cat "$marker" 2>/dev/null)" != "$today" ]; then
  stale=$(printf '%s' "$response" | python3 -c '
import json, sys
tasks = [t for t in (json.load(sys.stdin).get("tasks") or []) if isinstance(t, dict) and t.get("stale") and t.get("title")]
if tasks:
    listed = "; ".join("%d. %s (%s) — %s" % (i, t["title"], t.get("status") or "doing",
                       "last note: " + t["last_note"] if t.get("last_note") else "no note yet")
                       for i, t in enumerate(tasks, 1))
    print(len(tasks))
    print(" Stale, ask the owner before other work: " + listed + ". Show the person this numbered list and ask in one "
          "line which are done, waiting (on whom), blocked or still doing; then call team_task_finish for each from "
          "the answer. Never close one without their word.")
' 2>/dev/null) || stale=""
fi
notices="$windows_notice"
if [ -n "$stale" ]; then
  count=$(printf '%s\n' "$stale" | head -n 1)
  text="$text$(printf '%s\n' "$stale" | tail -n +2)"
  notices="${notices:+$notices }Work loop: $count of your tasks look stale; Claude will ask you about them."
  mkdir -p "$WORK_STATE_DIR" 2>/dev/null && printf '%s\n' "$today" > "$marker"
fi
# A Lark permission the loop needs and this sign-in has not granted: the person sees why and the link.
notice=$(printf '%s' "$response" | permission_notice) || notice=""
if [ -n "$notice" ]; then
  text="$text $(printf '%s' "$response" | permission_context)"
  notices="${notices:+$notices }$notice"
fi
hook_context SessionStart "$text" "$notices"
exit 0
