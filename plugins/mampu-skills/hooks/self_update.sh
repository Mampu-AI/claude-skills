#!/bin/sh
# SessionStart: download a newer release of this plugin in the background. Claude Code's own auto-update skips
# plugins whose team tools use a sign-in step (ours does), so without this a release reaches nobody. At most once an
# hour per computer; it never slows the session and says nothing. The hooks follow the new copy at once (run.sh);
# the team tools and skills load it at /reload-plugins or the next start, and the prompt hook says so.
# SAPOT_PLUGIN_SELF_UPDATE=0 switches it off.
. "$(dirname "$0")/lib/work_api.sh"
cat >/dev/null
[ "${SAPOT_PLUGIN_SELF_UPDATE:-1}" = "0" ] && exit 0
claude_bin="${SAPOT_CLAUDE_BIN:-claude}"
command -v "$claude_bin" >/dev/null 2>&1 || exit 0
mkdir -p "$WORK_STATE_DIR" 2>/dev/null || exit 0
marker="$WORK_STATE_DIR/self-update-checked"
now=$(date +%s)
last=$(cat "$marker" 2>/dev/null)
case "$last" in ''|*[!0-9]*) last=0 ;; esac
[ $((now - last)) -ge 3600 ] || exit 0
lock="$WORK_STATE_DIR/self-update.lock"
# a lock left behind by a killed run is cleared after 30 minutes
[ -n "$(find "$lock" -maxdepth 0 -mmin +30 2>/dev/null)" ] && rmdir "$lock" 2>/dev/null
mkdir "$lock" 2>/dev/null || exit 0
printf '%s\n' "$now" > "$marker"
nohup sh -c '"$1" plugin marketplace update mampu && "$1" plugin update mampu-skills@mampu; rmdir "$2"' \
  sh "$claude_bin" "$lock" </dev/null >/dev/null 2>&1 &
exit 0
