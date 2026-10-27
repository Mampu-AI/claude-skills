#!/bin/sh
# Check and repair this computer's work-loop sign-in for the team tools. Run by the agent when a team tool is
# refused for a missing or lapsed login. Prints what it found and fixed in plain words, never the sign-in itself,
# and ends with one line saying what happens next:
#   NEXT: sign-in   no working Lark sign-in here: the agent signs the person in (onboard skill, step 2)
#   NEXT: reopen    a Windows setting was fixed: the person closes every VS Code window and terminal and reopens once
#   NEXT: reload    the sign-in is fine now: the person runs /reload-plugins so the team tools reconnect with it
#   NEXT: admin     the work-loop server is switched off or unreachable: nothing to repair on this computer
here=$(cd "$(dirname "$0")" && pwd)
. "$here/../hooks/lib/work_api.sh"

case "$(work_login_state)" in
  none) echo "Sign-in: none on this computer."; echo "NEXT: sign-in"; exit 0 ;;
  refused) echo "Sign-in: lapsed or refused by the server."; echo "NEXT: sign-in"; exit 0 ;;
  off|down) echo "Server: switched off or not reachable."; echo "NEXT: admin"; exit 0 ;;
esac
echo "Sign-in: valid."

# The team tools read the sign-in without this session's environment (Claude Code removes login-like variables for
# them), so a sign-in held only in the environment never reaches them: keep it in the private sign-in file.
helper_sends_login() {
  env -u SAPOT_WORK_TOKEN sh "$here/sapot-headers.sh" 2>/dev/null | grep -q '"Authorization"'
}
if ! helper_sends_login; then
  token=$(work_token)
  old_umask=$(umask); umask 077
  mkdir -p "$(dirname "$WORK_LOGIN_FILE")" && printf '%s\n' "$token" > "$WORK_LOGIN_FILE"
  umask "$old_umask"
  if helper_sends_login; then echo "Team tools: saved the sign-in where they can read it."
  else echo "Team tools: still cannot read the sign-in."; fi
fi

case "$(sh "$here/windows-path.sh" fix)" in
  fixed) echo "Windows: added Git's shell folder to the path the team tools need."; echo "NEXT: reopen"; exit 0 ;;
  nogit) echo "Windows: Git for Windows was not found where Claude Code installed it." ;;
esac
echo "NEXT: reload"
