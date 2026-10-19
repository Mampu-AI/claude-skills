#!/bin/sh
# The work-loop sign-in state of this computer, in one line. Exit 0 when signed in, 1 otherwise.
#   Signed in as <name> on <device>, valid until <date>.
#   Not connected.  |  Sign-in lapsed or refused.  |  Work loop switched off on the server.  |  Server unreachable.
. "$(dirname "$0")/../hooks/lib/work_api.sh"
case "$(work_login_state)" in
  ok)
    body=$(work_api GET access) || { echo "Server unreachable."; exit 1; }
    printf '%s' "$body" | work_json '
d=json.load(sys.stdin); u=d.get("user") or {}; l=d.get("login") or {}
if l: print("Signed in as %s on %s, valid until %s." % (l.get("lark_name") or u.get("name"), l.get("device") or "this computer", (l.get("expires_at") or "")[:10]))
else: print("Connected with a staff token as %s (no Lark sign-in on this computer)." % (u.get("name") or u.get("email")))' \
      'const d=JSON.parse(require("fs").readFileSync(0,"utf8"));const u=d.user||{};const l=d.login||{};
console.log(Object.keys(l).length?`Signed in as ${l.lark_name||u.name} on ${l.device||"this computer"}, valid until ${(l.expires_at||"").slice(0,10)}.`:`Connected with a staff token as ${u.name||u.email} (no Lark sign-in on this computer).`)'
    exit 0 ;;
  none) echo "Not connected."; exit 1 ;;
  refused) echo "Sign-in lapsed or refused."; exit 1 ;;
  off) echo "Work loop switched off on the server."; exit 1 ;;
  *) echo "Server unreachable."; exit 1 ;;
esac
