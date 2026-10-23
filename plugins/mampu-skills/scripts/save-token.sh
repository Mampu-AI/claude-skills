#!/bin/sh
# Save (or replace) this computer's Lark sign-in by hand: for a machine with no browser, where the sign-in page
# shows a one-time login to paste here.
#   sh save-token.sh          → asks for the login (input hidden) and stores it
#   sh save-token.sh --remove → deletes it
# (--work is still accepted and means the same.) The login is never echoed or put in your shell history.
SERVICE="sapot-work-login"
[ "${1:-}" = "--work" ] && shift

if [ "${1:-}" = "--remove" ]; then
  if command -v security >/dev/null 2>&1; then
    security delete-generic-password -s "$SERVICE" >/dev/null 2>&1 && echo "Removed from Keychain." || echo "Nothing stored."
  elif command -v secret-tool >/dev/null 2>&1; then
    secret-tool clear service "$SERVICE" && echo "Removed from the keyring."
  else
    rm -f "${SAPOT_WORK_LOGIN_FILE:-$HOME/.config/sapot/work-login}" && echo "Removed."
  fi
  exit 0
fi

printf 'Paste the one-time login from the Lark sign-in page (input hidden): '
stty -echo 2>/dev/null
read -r token
stty echo 2>/dev/null
printf '\n'
[ -n "$token" ] || { echo "Nothing entered; nothing saved."; exit 1; }

if command -v security >/dev/null 2>&1; then
  security add-generic-password -U -a "${USER:-sapot}" -s "$SERVICE" -w "$token" && echo "Saved to macOS Keychain."
elif command -v secret-tool >/dev/null 2>&1; then
  printf '%s' "$token" | secret-tool store --label='Mampu work-loop Lark sign-in' service "$SERVICE" && echo "Saved to the keyring."
else
  f="${SAPOT_WORK_LOGIN_FILE:-$HOME/.config/sapot/work-login}"; mkdir -p "$(dirname "$f")"; umask 077
  printf '%s\n' "$token" > "$f" && chmod 600 "$f" 2>/dev/null; echo "No keychain here; saved to $f (private to your user)."
fi
echo "Restart Claude Code (or reconnect mampu-tech-team in /mcp) so the team tools pick it up."
