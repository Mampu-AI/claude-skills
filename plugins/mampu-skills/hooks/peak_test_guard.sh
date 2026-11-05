#!/bin/sh
# PreToolUse on any connector's flow test tool (test_flow). DeepSeek, which runs most flow steps on the platform
# key, charges double 09:00-12:00 and 14:00-18:00 MYT (01-04 and 06-10 UTC). At peak, the first three flow tests
# in 15 minutes run as usual (someone fixing one thing needs the answer now); a fourth is held back once and the
# agent asks the person: run now at double price, or wait for the off-peak hours. Every test in that same burst
# (within 20 s of the hold) is held back with it, so a batch fired at once gets one question; after that the
# session's tests run without asking until the window ends. Off-peak it does nothing. Needs no server, writes only
# the session's own state files, and runs with python3 or node. SAPOT_PEAK_CLOCK (epoch seconds) is for the tests.
. "$(dirname "$0")/lib/work_api.sh"
input=$(cat)
sid=$(printf '%s' "$input" | work_json '
d = json.load(sys.stdin)
if str(d.get("tool_name") or "").startswith("mcp__") and str(d.get("tool_name")).endswith("__test_flow"):
    print("".join(c for c in str(d.get("session_id") or "") if c.isalnum() or c == "-"))
' 'const d=JSON.parse(require("fs").readFileSync(0,"utf8"));const t=String(d.tool_name||"");
if(t.startsWith("mcp__")&&t.endsWith("__test_flow"))console.log(String(d.session_id||"").replace(/[^A-Za-z0-9-]/g,""));' 2>/dev/null)
[ -n "$sid" ] || exit 0
now=${SAPOT_PEAK_CLOCK:-$(date +%s)}
hour=$(( (now % 86400) / 3600 ))
if [ "$hour" -ge 1 ] && [ "$hour" -lt 4 ]; then ends=4
elif [ "$hour" -ge 6 ] && [ "$hour" -lt 10 ]; then ends=10
else exit 0
fi
window_end=$(( now - now % 86400 + ends * 3600 ))
mkdir -p "$WORK_STATE_DIR" 2>/dev/null || exit 0
log="$WORK_STATE_DIR/$sid.peak-tests"
asked="$WORK_STATE_DIR/$sid.peak-asked"   # "<time of the hold> <end of that peak window>"
held_at=""; held_end=""
[ -f "$asked" ] && read -r held_at held_end < "$asked" 2>/dev/null
if [ "$held_end" = "$window_end" ] && [ -n "$held_at" ]; then
  [ $(( now - held_at )) -le 20 ] || exit 0   # the person already answered for this window
  first=""                                    # same burst: hold it too, but the person saw the notice already
else
  first=1
  echo "$now" >> "$log"
  recent=0
  while read -r t; do [ $(( now - t )) -lt 900 ] 2>/dev/null && recent=$((recent + 1)); done < "$log"
  [ "$recent" -ge 4 ] || exit 0
  echo "$now $window_end" > "$asked"
fi
myt=$(( (now + 28800) % 86400 ))
clock=$(printf '%02d:%02d' $(( myt / 3600 )) $(( myt % 3600 / 60 )))
until_myt=$(printf '%02d:00' $(( (ends + 8) % 24 )))
reason="[work-loop] DeepSeek peak price: it is $clock MYT and DeepSeek charges double until $until_myt MYT. This flow test is the fourth or later in 15 minutes, so it was held back once (with the rest of this batch). Do not retry yet. Ask the person in one line: run these tests now at double price, or wait until $until_myt MYT (off-peak is 12:00-14:00 and after 18:00 MYT). If they say run now, call test_flow again with the same input; this session's tests then run without asking until $until_myt MYT. If they say wait, stop and tell them when to run them."
notice="Work loop: DeepSeek charges double until $until_myt MYT. Claude will ask before running more flow tests."
if [ -n "$first" ]; then
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"},"systemMessage":"%s"}\n' "$reason" "$notice"
else
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$reason"
fi
exit 0
