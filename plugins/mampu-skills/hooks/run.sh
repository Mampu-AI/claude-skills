#!/bin/sh
# Every hook runs through here: `sh run.sh <hook file>` runs that hook from the newest downloaded copy of this
# plugin, so a fix reaches a running session's hooks without /reload-plugins (the team tools and skills still need
# it). CLAUDE_PLUGIN_ROOT keeps naming the copy the session loaded: the reload notice and the copy sent to the server
# read it. Falls back to this copy when the install record cannot be read or the newest copy lacks the hook.
name=$1
case "$name" in ''|*/*|*\\*) exit 0 ;; esac
here=$(cd "$(dirname "$0")/.." && pwd)
root=$here
record="${CLAUDE_CODE_PLUGIN_CACHE_DIR:-$HOME/.claude/plugins}/installed_plugins.json"
# the copy Claude Code installed last: "installPath": ".../mampu-skills/<copy>" (backslashes on Windows)
newest=$(sed -n 's/.*"installPath": *".*mampu-skills[\\/]\{1,\}\([A-Za-z0-9._-]\{1,\}\)".*/\1/p' "$record" 2>/dev/null | head -n 1)
if [ -n "$newest" ] && [ -f "$(dirname "$here")/$newest/hooks/$name" ]; then root="$(dirname "$here")/$newest"; fi
case "$name" in
  *.py) PYTHONUTF8=1 exec python3 "$root/hooks/$name" ;;
  *) exec sh "$root/hooks/$name" ;;
esac
