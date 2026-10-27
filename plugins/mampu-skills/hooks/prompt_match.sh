#!/bin/sh
# UserPromptSubmit: POST work/match with the prompt → inject task / record / help-page candidates
# and the team_task_start instruction. Skips prompts under 12 characters and slash commands.
# Silent (exit 0, no output) when there is no token or the server does not answer.
. "$(dirname "$0")/lib/work_api.sh"
input=$(cat)
body=$(printf '%s' "$input" | python3 -c '
import json, sys
data = json.load(sys.stdin)
prompt = str(data.get("prompt") or "")
if len(prompt.strip()) < 12 or prompt.lstrip().startswith("/"):
    sys.exit(0)
print(json.dumps({"prompt": prompt, "repo": None, "surface": "claude-code"}))
' 2>/dev/null) || exit 0
[ -n "$body" ] || exit 0
pending=$(plugin_update_pending) || pending=""
UPDATE_NOTICE="Work loop plugin updated. Run /reload-plugins to use it (or restart Claude Code)."
UPDATE_CONTEXT="[work-loop] A newer copy of this plugin is installed ($pending) but this session still runs the old one. Tell the person in one line to run /reload-plugins or restart Claude Code, then continue."
if ! work_token >/dev/null 2>&1; then
  # Not signed in: on every work-shaped prompt until it is done, the agent opens the sign-in itself. Nothing is sent.
  hook_context UserPromptSubmit \
    "[work-loop] This computer is not signed in to the work loop yet. Before anything else, sign the person in yourself with the onboard skill (step 2: it opens the Lark sign-in in their browser and waits). Do not wait for them to ask or say \"connect me\"; tell them in one line to approve the Lark page, then continue with their request." \
    "Work loop: this computer is not signed in yet. Claude will open the Lark sign-in; approve it in the browser."
  exit 0
fi
response=$(printf '%s' "$body" | work_api POST match) || {
  [ -n "$pending" ] && hook_context UserPromptSubmit "$UPDATE_CONTEXT" "$UPDATE_NOTICE"
  exit 0
}
text=$(printf '%s' "$response" | python3 -c '
import json, sys
data = json.load(sys.stdin)
def rows(key):
    return [r for r in (data.get(key) or []) if isinstance(r, dict)]
tasks = "; ".join("%s (%s, %s)" % (t.get("title"), t.get("guid"), t.get("status") or "open") for t in rows("tasks")) or "none"
issues = "; ".join("#%s %s" % (i.get("number"), i.get("title")) for i in rows("github_issues"))
records = "; ".join("%s — %s" % (r.get("slug"), r.get("description") or r.get("name")) for r in rows("records")) or "none"
pages = "; ".join("%s (%s)" % (p.get("title"), p.get("path")) for p in rows("help_pages")) or "none"
text = "[work-loop] For this prompt — Task candidates: " + tasks + "."
if issues:
    text += " GitHub issues (not team tasks): " + issues + "."
text += (" Records: " + records + ". Help pages: " + pages + ". If this prompt is work: call team_task_start with "
         "the matching task_guid, or with create:{title} when nothing matches, then open your reply with the "
         "status block. A question or a read is not work: no task, no block.")
block = data.get("block")
if isinstance(block, str) and block.strip():
    text += "\nServer block:\n" + block.strip()
print(text)
' 2>/dev/null) || exit 0
[ -n "$text" ] || exit 0
# Remember the top matched task, so the Stop gate can hold a session that works on it without starting one.
sid=$(printf '%s' "$input" | session_id_from_input)
top=$(printf '%s' "$response" | python3 -c '
import json, sys
tasks = [t for t in (json.load(sys.stdin).get("tasks") or []) if isinstance(t, dict) and t.get("guid")]
print(tasks[0]["guid"] if tasks else "")
' 2>/dev/null | tr -cd 'A-Za-z0-9-')
[ -n "$sid" ] && [ -n "$top" ] && state_set "$sid" matched "\"$top\""
# Name the session's own task, so a follow-up continues it and different work gets its own task.
if [ -n "$sid" ] && [ -n "$(state_get "$sid" task_guid)" ]; then
  current=$(python3 -c '
import json, sys
guid, title, started, closed = sys.argv[1:5]
if started == "true":
    print("This session is on team task \"%s\" (%s). If this prompt continues that work, carry on with it: no new "
          "team_task_start. If it is different work, close that task out first (team_task_finish, state done or "
          "waiting), then start the matching task or create one." % (title, guid))
else:
    print("This session last worked on team task \"%s\" (%s), closed as %s. If this prompt continues that work, call "
          "team_task_start with that same task_guid. If it is different work, start the matching task or create one; "
          "never record different work under that task." % (title, guid, closed or "done"))
' "$(state_get "$sid" task_guid)" "$(state_get "$sid" task_title)" "$(state_get "$sid" started)" "$(state_get "$sid" task_state)" 2>/dev/null)
  [ -n "$current" ] && text="$text
$current"
fi
grant=$(printf '%s' "$response" | permission_context) || grant=""
[ -n "$grant" ] && text="$text
$grant"
if [ -n "$pending" ]; then
  hook_context UserPromptSubmit "$UPDATE_CONTEXT $text" "$UPDATE_NOTICE"
else
  hook_context UserPromptSubmit "$text"
fi
exit 0
