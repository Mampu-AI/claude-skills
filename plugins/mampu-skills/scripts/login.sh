#!/bin/sh
# Sign in with Lark for the Mampu work loop service, once per computer and OS user.
#
#   sh scripts/login.sh            # opens the browser, waits for Lark, saves the login in the keychain
#   sh scripts/login.sh --logout   # revokes this computer's login on the server and clears the keychain
#
# A tiny local listener on 127.0.0.1 receives the login token from the server's callback page, so
# nothing is pasted. If no browser can be opened here (SSH box), the URL is printed: open it anywhere,
# sign in, then paste the token the page shows into `save-token.sh --work`.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
API="${SAPOT_API_URL:-https://work.mampuai.com}"
PREFIX="${SAPOT_WORK_API_PREFIX:-/v1/work}"
SERVICE="sapot-work-login"
DEVICE="${SAPOT_DEVICE_LABEL:-$(hostname 2>/dev/null || echo unknown)-${USER:-user}}"

keychain_get() {
  if command -v security >/dev/null 2>&1; then security find-generic-password -s "$SERVICE" -w 2>/dev/null
  elif command -v secret-tool >/dev/null 2>&1; then secret-tool lookup service "$SERVICE" 2>/dev/null
  fi
  f="${SAPOT_WORK_LOGIN_FILE:-$HOME/.config/sapot/work-login}"; [ -r "$f" ] && head -n 1 "$f"
}

if [ "${1:-}" = "--logout" ]; then
  token=$(keychain_get)
  if [ -n "$token" ]; then
    hdr=$(mktemp); chmod 600 "$hdr"; printf 'api_access_token: %s\n' "$token" > "$hdr"
    curl -sS --max-time 8 -X POST -H "@$hdr" "$API$PREFIX/auth/logout" >/dev/null 2>&1 && echo "Revoked on the server."
    rm -f "$hdr"
  fi
  if command -v security >/dev/null 2>&1; then security delete-generic-password -s "$SERVICE" >/dev/null 2>&1 && echo "Removed from Keychain."
  elif command -v secret-tool >/dev/null 2>&1; then secret-tool clear service "$SERVICE" 2>/dev/null && echo "Removed from the keyring."
  fi
  f="${SAPOT_WORK_LOGIN_FILE:-$HOME/.config/sapot/work-login}"; [ -f "$f" ] && rm -f "$f" && echo "Removed the saved login file."
  exit 0
fi

LOGIN_FILE="${SAPOT_WORK_LOGIN_FILE:-$HOME/.config/sapot/work-login}"
# The listener prints the port it chose on its first line, then blocks until the token arrives (or 5 minutes).
# Node ships with Claude Code everywhere; python3 is the fallback.
if command -v node >/dev/null 2>&1; then
  node "$HERE/login_listener.js" "$SERVICE" "$LOGIN_FILE" > "${TMPDIR:-/tmp}/sapot-login.$$" 2>&1 &
elif command -v python3 >/dev/null 2>&1; then
  python3 "$HERE/login_listener.py" "$SERVICE" > "${TMPDIR:-/tmp}/sapot-login.$$" 2>&1 &
else
  echo "Neither node nor python3 is available for the login listener."; exit 1
fi
LISTENER=$!
port=""
for _ in 1 2 3 4 5 6 7 8 9 10; do
  port=$(head -n 1 "${TMPDIR:-/tmp}/sapot-login.$$" 2>/dev/null)
  [ -n "$port" ] && break
  sleep 0.3
done
[ -n "$port" ] || { echo "Could not start the local listener."; kill "$LISTENER" 2>/dev/null; exit 1; }

device_q=$(printf '%s' "$DEVICE" | sed 's/[^A-Za-z0-9._-]/-/g')
url="$API$PREFIX/auth/lark/start?device=$device_q&port=$port"
echo "Opening Lark sign-in in your browser…"
if command -v open >/dev/null 2>&1; then open "$url"
elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$url" >/dev/null 2>&1
elif command -v wslview >/dev/null 2>&1; then wslview "$url" >/dev/null 2>&1
# WSL without wslu: PowerShell keeps the whole URL. cmd.exe's `start` splits an unquoted command line at `&`
# (WSL passes a space-free argument unquoted), so it would open the URL without the port and the sign-in
# would never reach this listener.
elif command -v powershell.exe >/dev/null 2>&1; then powershell.exe -NoProfile -Command "Start-Process '$url'" >/dev/null 2>&1
elif command -v cmd.exe >/dev/null 2>&1; then cmd.exe /c start "" "$(printf '%s' "$url" | sed 's/&/^\&/g')" >/dev/null 2>&1
else echo "No browser here. Open this URL anywhere:"; echo "$url"
fi

wait "$LISTENER"
status=$?
tail -n +2 "${TMPDIR:-/tmp}/sapot-login.$$"
rm -f "${TMPDIR:-/tmp}/sapot-login.$$"
exit $status
