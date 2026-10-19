#!/bin/sh
# Save (or replace) your Sapot access token in the OS keychain for the sapot-flows tools.
#   sh save-token.sh          → asks for the token (input hidden) and stores it
#   sh save-token.sh --remove → deletes it
# The token is never echoed, written to a file, or put in your shell history.
SERVICE="sapot-staff-token"
if [ "${1:-}" = "--work" ]; then SERVICE="sapot-work-login"; shift; fi  # a Lark login token pasted by hand

if [ "$1" = "--remove" ]; then
  if command -v security >/dev/null 2>&1; then
    security delete-generic-password -s "$SERVICE" >/dev/null 2>&1 && echo "Removed from Keychain." || echo "Nothing stored."
  elif command -v secret-tool >/dev/null 2>&1; then
    secret-tool clear service "$SERVICE" && echo "Removed from the keyring."
  fi
  exit 0
fi

printf 'Paste your Sapot access token (input hidden): '
stty -echo 2>/dev/null
read -r token
stty echo 2>/dev/null
printf '\n'
[ -n "$token" ] || { echo "No token entered; nothing saved."; exit 1; }

if command -v security >/dev/null 2>&1; then
  security add-generic-password -U -a "${USER:-sapot}" -s "$SERVICE" -w "$token" && echo "Saved to macOS Keychain."
elif command -v secret-tool >/dev/null 2>&1; then
  printf '%s' "$token" | secret-tool store --label='Sapot staff token' service "$SERVICE" && echo "Saved to the keyring."
else
  if [ "$SERVICE" = "sapot-work-login" ]; then
    f="${SAPOT_WORK_LOGIN_FILE:-$HOME/.config/sapot/work-login}"; mkdir -p "$(dirname "$f")"; umask 077
    printf '%s\n' "$token" > "$f" && chmod 600 "$f" 2>/dev/null; echo "No keychain here; saved to $f (private to your user)."
  else
    echo "No keychain found (needs macOS 'security' or Linux 'secret-tool')."
    echo "Fallback: set SAPOT_STAFF_TOKEN in your environment instead."
  fi
  exit 1
fi
echo "Restart Claude Code so the flow tools pick it up."
