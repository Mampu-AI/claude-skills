#!/bin/sh
# PostToolUse / PostToolUseFailure on the team tools: when a call is refused because it did not carry this computer's
# sign-in (missing, lapsed, or an "old copy" answer, which on Windows means the sign-in step never ran), tell the
# agent to run the repair at once, without asking the person, and show the person that it is happening. Once per
# session. Needs no server, and runs with python3 or node (many Windows machines have only node).
. "$(dirname "$0")/lib/work_api.sh"
input=$(cat)
# prints "<session id> <event>" when this is a team tool whose answer IS a sign-in refusal; a record or task that
# merely mentions these words is longer and does not count
found=$(printf '%s' "$input" | work_json '
d = json.load(sys.stdin)
said = d.get("error") or d.get("tool_response") or ""
if isinstance(said, dict):
    said = said.get("content") or said.get("text") or ""
if isinstance(said, list):
    said = " ".join(str(b.get("text") or "") if isinstance(b, dict) else str(b) for b in said)
said = str(said)
tool = str(d.get("tool_name") or "")
refused = ("Missing access token", "Invalid or lapsed login", "old copy of the Mampu team plugin")
if tool.startswith("mcp__") and "mampu-tech-team__" in tool and len(said) < 400 and any(r in said for r in refused):
    sid = "".join(c for c in str(d.get("session_id") or "") if c.isalnum() or c == "-")
    print(sid, d.get("hook_event_name") or "PostToolUse")
' 'const d=JSON.parse(require("fs").readFileSync(0,"utf8"));let s=d.error||d.tool_response||"";
if(s&&typeof s==="object"&&!Array.isArray(s))s=s.content||s.text||"";
if(Array.isArray(s))s=s.map(b=>b&&typeof b==="object"?String(b.text||""):String(b)).join(" ");s=String(s);
const t=String(d.tool_name||"");
const hit=["Missing access token","Invalid or lapsed login","old copy of the Mampu team plugin"].some(r=>s.includes(r));
if(t.startsWith("mcp__")&&t.includes("mampu-tech-team__")&&s.length<400&&hit)
  console.log(String(d.session_id||"").replace(/[^A-Za-z0-9-]/g,""),d.hook_event_name||"PostToolUse");' 2>/dev/null)
sid=${found%% *}
event=${found#* }
[ -n "$sid" ] && [ "$sid" != "$found" ] || exit 0
marker="$WORK_STATE_DIR/$sid.repair-told"
[ -f "$marker" ] && exit 0
mkdir -p "$WORK_STATE_DIR" 2>/dev/null && : > "$marker"
doctor="$(cd "$(dirname "$0")/.." && pwd)/scripts/doctor.sh"
hook_context "$event" \
  "[work-loop] A team tool was refused because it did not get this computer's work-loop sign-in. Repair it now, without asking the person: run sh \"$doctor\" and act on its last line. NEXT: sign-in → sign them in with the onboard skill (step 2). NEXT: reopen → tell them in one line that a Windows setting was fixed and they must close every VS Code window and terminal and open them again, once. NEXT: reload → tell them in one line to run /reload-plugins, then retry the team tool. NEXT: admin → tell them the work-loop server is not reachable and to tell their Mampu admin. Then carry on with their request." \
  "Work loop: the team tools did not get this computer's sign-in. Claude is repairing it."
exit 0
