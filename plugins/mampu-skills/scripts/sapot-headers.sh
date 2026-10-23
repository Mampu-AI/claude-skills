#!/bin/sh
# headersHelper for the mampu-tech-team MCP server: prints the auth header as JSON.
# The only login sent is this computer's "Sign in with Lark" (scripts/login.sh): from the OS keychain, else the
# private sign-in file. An old Sapot staff token is never sent; the server refuses it. No sign-in → {} and the
# tools answer "Missing access token".
token=""
if command -v security >/dev/null 2>&1; then            # macOS Keychain
  token=$(security find-generic-password -s sapot-work-login -w 2>/dev/null)
elif command -v secret-tool >/dev/null 2>&1; then       # Linux (GNOME Keyring / libsecret)
  token=$(secret-tool lookup service sapot-work-login 2>/dev/null)
fi
f="${SAPOT_WORK_LOGIN_FILE:-$HOME/.config/sapot/work-login}"
if [ -z "$token" ] && [ -r "$f" ]; then token=$(head -n 1 "$f" 2>/dev/null); fi
[ -n "$token" ] || token="${SAPOT_WORK_TOKEN:-}"
copy=""  # which plugin copy, for the owner's team usage view
[ -n "${CLAUDE_PLUGIN_ROOT:-}" ] && copy=$(basename "$CLAUDE_PLUGIN_ROOT" | tr -cd 'A-Za-z0-9._-')
# the release number: the server turns away copies below its minimum with "update and reload"
release=$(tr -cd '0-9' < "$(dirname "$0")/../RELEASE" 2>/dev/null)
out=""
[ -n "$token" ] && out="\"Authorization\": \"Bearer $token\""
[ -n "$copy" ] && out="${out:+$out, }\"X-Work-Plugin\": \"$copy\""
[ -n "$release" ] && out="${out:+$out, }\"X-Work-Plugin-Release\": \"$release\""
printf '{%s}\n' "$out"
