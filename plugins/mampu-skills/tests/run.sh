#!/bin/sh
# Hook tests for the work-loop plugin. Starts the fake work API on a free port, points the hooks at
# it with a throwaway token and a temp HOME (no real keychain, state or spool is touched), then runs
# tests/cases.py, which feeds each hook a realistic hook-input JSON and asserts the output and the
# state-file transitions, including silence when the server is down or the token is missing.
#   sh plugins/mampu-skills/tests/run.sh
set -u
here=$(cd "$(dirname "$0")" && pwd)
plugin=$(cd "$here/.." && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/work-loop-tests.XXXXXX") || exit 1
trap 'kill "$server_pid" 2>/dev/null; rm -rf "$work"' EXIT INT TERM

# A stub keychain so a real token on this machine never leaks into the test: both lookups fail,
# which makes the hooks fall through to SAPOT_WORK_TOKEN (a Lark sign-in) exactly as on a machine without a keychain.
mkdir -p "$work/bin" "$work/home"
printf '#!/bin/sh\nexit 1\n' > "$work/bin/security"
printf '#!/bin/sh\nexit 1\n' > "$work/bin/secret-tool"
chmod +x "$work/bin/security" "$work/bin/secret-tool"

python3 "$here/fake_server.py" --port 0 --log "$work/requests.jsonl" --ready-file "$work/port" > "$work/server.out" 2>&1 &
server_pid=$!
tries=0
# up to 30 s: the first Python start on a fresh macOS or Windows machine is slow
while [ ! -s "$work/port" ] && [ $tries -lt 300 ]; do sleep 0.1; tries=$((tries + 1)); done
[ -s "$work/port" ] || { echo "fake server did not start"; cat "$work/server.out"; exit 1; }
port=$(cat "$work/port")

# SAPOT_POWERSHELL: the Windows path check never calls the real PowerShell; the Windows cases use a stub.
PATH="$work/bin:$PATH" HOME="$work/home" SAPOT_API_URL="http://127.0.0.1:$port" SAPOT_WORK_TOKEN=test \
  SAPOT_POWERSHELL=no-powershell-in-tests \
  PLUGIN_ROOT="$plugin" REQUEST_LOG="$work/requests.jsonl" WORK_DIR="$work" \
  python3 "$here/cases.py"
status=$?
exit $status
