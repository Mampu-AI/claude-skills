#!/bin/sh
# Shared helper for the work-loop hooks. Source it: . "$(dirname "$0")/lib/work_api.sh"
#
# Design rule: a hook must never block or slow a session because the server is unreachable.
# work_api prints the response body and returns 0 only on a 2xx; on no token, a network
# error, a timeout or any other status it prints nothing and returns 1, and the calling hook
# exits 0 without output.
#
# The token is resolved exactly like scripts/sapot-headers.sh: OS keychain (service
# sapot-staff-token) first, then SAPOT_STAFF_TOKEN. It is passed to curl through a 0600 temp
# header file, never on the command line, and never written anywhere else.
#
# JSON work (hook input, state file) goes through python3 one-liners, as the sibling plugin's
# hooks already do; python3 ships with macOS and every Linux Claude Code runs on.

# Every python3 step reads and prints UTF-8: Windows Python otherwise uses the old ANSI code page, and a task
# title with a dash, an arrow or Chinese text makes the step fail and the hook go silent.
export PYTHONUTF8=1
WORK_KEYCHAIN_SERVICES="sapot-work-login sapot-staff-token"  # a Lark login wins over a pasted staff token
WORK_API_BASE="${SAPOT_API_URL:-https://work.mampuai.com}"
WORK_API_PREFIX="${SAPOT_WORK_API_PREFIX:-/v1/work}"
WORK_STATE_DIR="${SAPOT_WORK_STATE_DIR:-$HOME/.cache/sapot-work-loop}"
WORK_LOGIN_FILE="${SAPOT_WORK_LOGIN_FILE:-$HOME/.config/sapot/work-login}"  # where login.sh stores the login without a keychain

work_token() {
  token=""
  for service in $WORK_KEYCHAIN_SERVICES; do
    if command -v security >/dev/null 2>&1; then            # macOS Keychain
      token=$(security find-generic-password -s "$service" -w 2>/dev/null)
    elif command -v secret-tool >/dev/null 2>&1; then       # Linux (GNOME Keyring / libsecret)
      token=$(secret-tool lookup service "$service" 2>/dev/null)
    fi
    [ -n "$token" ] && break
  done
  if [ -z "$token" ] && [ -r "$WORK_LOGIN_FILE" ]; then token=$(head -n 1 "$WORK_LOGIN_FILE" 2>/dev/null); fi
  [ -n "$token" ] || token="${SAPOT_WORK_TOKEN:-${SAPOT_STAFF_TOKEN:-}}"
  [ -n "$token" ] || return 1
  printf '%s' "$token"
}

# work_fetch METHOD ROUTE — like work_api, but prints the HTTP status on the first line (000 when the
# server did not answer) and the body after it, so one call can both classify the login and be used.
work_fetch() {
  method=$1
  route=$2
  token=$(work_token) || { echo 000; return 0; }
  url="${WORK_API_BASE%/}${WORK_API_PREFIX}/${route}"
  old_umask=$(umask); umask 077
  hdr=$(mktemp "${TMPDIR:-/tmp}/sapot-work-hdr.XXXXXX") || { umask "$old_umask"; echo 000; return 0; }
  body=$(mktemp "${TMPDIR:-/tmp}/sapot-work-body.XXXXXX") || { umask "$old_umask"; rm -f "$hdr"; echo 000; return 0; }
  umask "$old_umask"
  printf 'api_access_token: %s\n' "$token" > "$hdr"
  copy=$(plugin_copy); [ -n "$copy" ] && printf 'x-work-plugin: %s\n' "$copy" >> "$hdr"
  code=$(curl -sS --max-time 5 -o "$body" -w '%{http_code}' -X "$method" -H @"$hdr" -H 'Accept: application/json' "$url" 2>/dev/null)
  rm -f "$hdr"
  printf '%s\n' "${code:-000}"
  cat "$body"
  rm -f "$body"
}

# work_login_state → none (no token here) | ok | refused (401/403) | off (503) | down (no answer)
work_login_state() {
  token=$(work_token) || { echo none; return 0; }
  old_umask=$(umask); umask 077
  hdr=$(mktemp "${TMPDIR:-/tmp}/sapot-work-hdr.XXXXXX") || { umask "$old_umask"; echo down; return 0; }
  umask "$old_umask"
  printf 'api_access_token: %s\n' "$token" > "$hdr"
  copy=$(plugin_copy); [ -n "$copy" ] && printf 'x-work-plugin: %s\n' "$copy" >> "$hdr"
  code=$(curl -sS --max-time 5 -o /dev/null -w '%{http_code}' -H @"$hdr" -H 'Accept: application/json' \
    "${WORK_API_BASE%/}${WORK_API_PREFIX}/access" 2>/dev/null)
  rm -f "$hdr"
  case "$code" in
    2[0-9][0-9]) echo ok ;;
    401|403) echo refused ;;
    503) echo off ;;
    *) echo down ;;
  esac
}

# plugin_copy   the plugin copy these hooks run from (its cache folder name), sent with every call so the owner can
# see who still runs an old copy. Prints nothing outside a plugin install.
plugin_copy() {
  [ -n "${CLAUDE_PLUGIN_ROOT:-}" ] && basename "$CLAUDE_PLUGIN_ROOT" | tr -cd 'A-Za-z0-9._-'
}

# work_json PY_SCRIPT NODE_SCRIPT  — runs the JSON script on stdin with python3, else node (Windows has node, not python3)
work_json() {
  if command -v python3 >/dev/null 2>&1; then python3 -c "import json, sys
$1"
  elif command -v node >/dev/null 2>&1; then node -e "$2"
  else return 1
  fi
}

# work_api METHOD ROUTE   (POST/PUT body is read from stdin)
work_api() {
  method=$1
  route=$2
  token=$(work_token) || return 1
  url="${WORK_API_BASE%/}${WORK_API_PREFIX}/${route}"
  old_umask=$(umask)
  umask 077
  hdr=$(mktemp "${TMPDIR:-/tmp}/sapot-work-hdr.XXXXXX") || { umask "$old_umask"; return 1; }
  body=$(mktemp "${TMPDIR:-/tmp}/sapot-work-body.XXXXXX") || { umask "$old_umask"; rm -f "$hdr"; return 1; }
  umask "$old_umask"
  printf 'api_access_token: %s\n' "$token" > "$hdr"
  copy=$(plugin_copy); [ -n "$copy" ] && printf 'x-work-plugin: %s\n' "$copy" >> "$hdr"
  if [ "$method" = "GET" ]; then
    code=$(curl -sS --max-time 5 -o "$body" -w '%{http_code}' -H @"$hdr" -H 'Accept: application/json' "$url" 2>/dev/null)
  else
    code=$(curl -sS --max-time 5 -o "$body" -w '%{http_code}' -X "$method" -H @"$hdr" \
      -H 'Content-Type: application/json' -H 'Accept: application/json' --data-binary @- "$url" 2>/dev/null)
  fi
  rm -f "$hdr"
  case "$code" in
    2[0-9][0-9]) cat "$body"; rm -f "$body"; return 0 ;;
    *) rm -f "$body"; return 1 ;;
  esac
}

# json_get KEY[.KEY...]   reads a JSON document from stdin, prints the value at the dotted
# path: strings raw, true/false for booleans, nothing for null/missing, JSON for objects/lists.
json_get() {
  python3 -c '
import json, sys
try:
    node = json.load(sys.stdin)
    for key in sys.argv[1].split("."):
        node = node[key] if isinstance(node, dict) else None
except Exception:
    node = None
if node is None:
    sys.exit(0)
if isinstance(node, bool):
    print("true" if node else "false")
elif isinstance(node, (str, int, float)):
    print(node)
else:
    print(json.dumps(node))
' "$1" 2>/dev/null
}

# session_id_from_input   reads hook JSON from stdin, prints the session id restricted to
# [A-Za-z0-9-] (it becomes a file name); prints nothing when absent.
session_id_from_input() {
  json_get session_id | tr -cd 'A-Za-z0-9-'
}

state_file() {
  printf '%s/%s.json' "$WORK_STATE_DIR" "$1"
}

# state_get SID KEY   prints one field of the session state (same rendering as json_get).
state_get() {
  f=$(state_file "$1")
  [ -f "$f" ] || return 0
  json_get "$2" < "$f"
}

# state_set SID KEY JSON_VALUE [KEY JSON_VALUE ...]   merges fields into the state file,
# creating it with the contract's defaults. Values are JSON literals ("x", true, null, 3).
state_set() {
  sid=$1
  shift
  mkdir -p "$WORK_STATE_DIR" 2>/dev/null || return 1
  python3 - "$(state_file "$sid")" "$@" <<'PY' 2>/dev/null
import json, os, sys, tempfile
path, pairs = sys.argv[1], sys.argv[2:]
defaults = {"task_guid": None, "task_title": None, "started": False, "created": False,
            "milestone": None, "changed": None, "finished": False, "last_assistant": None}
try:
    state = json.load(open(path))
    if not isinstance(state, dict):
        state = {}
except Exception:
    state = {}
merged = dict(defaults)
merged.update(state)
for key, raw in zip(pairs[0::2], pairs[1::2]):
    try:
        merged[key] = json.loads(raw)
    except ValueError:
        merged[key] = raw
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".state.")
with os.fdopen(fd, "w") as fh:
    json.dump(merged, fh)
os.replace(tmp, path)
PY
}

# hook_context EVENT TEXT   prints the hook JSON that injects TEXT as additionalContext.
# plugin_update_pending: prints the installed version of this plugin when it differs from the copy these hooks
# run from (Claude Code updates plugins in the background but a running session keeps the old copy until
# /reload-plugins or a restart). Silent for in-place loads and when the install record cannot be read.
plugin_update_pending() {
  root="${CLAUDE_PLUGIN_ROOT:-}"
  [ -n "$root" ] || return 1
  record="${CLAUDE_CODE_PLUGIN_CACHE_DIR:-$HOME/.claude/plugins}/installed_plugins.json"
  [ -r "$record" ] || return 1
  python3 - "$record" "$root" 2>/dev/null <<'PY'
import json, os, sys
record, root = sys.argv[1], os.path.normpath(sys.argv[2])
data = json.load(open(record))
entries = data.get("plugins") if isinstance(data.get("plugins"), dict) else data
for installs in (entries or {}).values():
    for entry in installs if isinstance(installs, list) else [installs]:
        path = os.path.normpath(str(entry.get("installPath") or ""))
        if path and os.path.dirname(path) == os.path.dirname(root) and path != root:
            print(entry.get("version") or os.path.basename(path)); sys.exit(0)
sys.exit(1)
PY
}

# hook_context EVENT CONTEXT [NOTICE]: CONTEXT goes to the agent; NOTICE, when given, is shown to the person
# as the hook's systemMessage (the only hook output a person sees without the agent repeating it).
# permission_notice / permission_context — read a work API answer on stdin; when it carries `permissions`
# {why, url} (a Lark permission the loop needs and this sign-in has not granted), print the one line the
# person sees, or the instruction for the agent. Print nothing otherwise.
permission_notice() {
  python3 -c '
import json, sys
p = (json.load(sys.stdin) or {}).get("permissions") or {}
if p.get("url"):
    print("Work loop: one more Lark permission needed. %s Approve it here (one click in Lark, nothing to restart): %s"
          % (p.get("why") or "", p["url"]))
' 2>/dev/null
}

permission_context() {
  python3 -c '
import json, sys
p = (json.load(sys.stdin) or {}).get("permissions") or {}
if p.get("url"):
    print("[work-loop] This sign-in lacks a Lark permission the loop needs. Tell the person once this session, in "
          "one line, why (%s) and give them this link to approve it: %s. Then carry on." % (p.get("why") or "", p["url"]))
' 2>/dev/null
}

# project_print DIR   prints a short fingerprint of the git project DIR is in (last commit, changed and new
# files, uncommitted diff), or nothing when DIR is not in a project or is Claude's own ~/.claude. Two
# different prints mean the project changed, however it was changed (an edit tool, sed, a heredoc, a commit).
project_print() {
  top=$(git -C "$1" rev-parse --show-toplevel 2>/dev/null) || return 0
  case "$top" in "$HOME/.claude"|"$HOME/.claude/"*) return 0 ;; esac
  { git -C "$top" rev-parse HEAD 2>/dev/null; git -C "$top" status --porcelain=v1 -uall 2>/dev/null
    git -C "$top" diff HEAD 2>/dev/null; } | cksum | cut -d' ' -f1
}

hook_context() {
  if command -v python3 >/dev/null 2>&1; then
    python3 -c '
import json, sys
# Windows Python writes \r\n for every newline it prints; captured text keeps the \r, so drop it here.
out = {"hookSpecificOutput": {"hookEventName": sys.argv[1], "additionalContext": sys.argv[2].replace("\r", "")}}
if len(sys.argv) > 3 and sys.argv[3]:
    out["systemMessage"] = sys.argv[3].replace("\r", "")
print(json.dumps(out))
' "$1" "$2" "${3:-}" 2>/dev/null
  elif command -v node >/dev/null 2>&1; then
    node -e '
const out = {hookSpecificOutput: {hookEventName: process.argv[1], additionalContext: process.argv[2]}};
if (process.argv[3]) out.systemMessage = process.argv[3];
console.log(JSON.stringify(out));' "$1" "$2" "${3:-}" 2>/dev/null
  fi
}
