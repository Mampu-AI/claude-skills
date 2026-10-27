#!/bin/sh
# Windows only: the team tools' sign-in step is started with `sh`, which Claude Code looks up on the Windows path.
# Git for Windows puts `sh` in its bin folder, which many machines leave off the path; the sign-in step then never
# runs and every team tool is refused although this computer is signed in. Prints one word:
#   sh scripts/windows-path.sh check   ok | missing | nogit | skip (not Windows, or no PowerShell)
#   sh scripts/windows-path.sh fix     ok | fixed | nogit | skip   (fix appends Git's bin folder to the USER path)
# It reads the saved user and machine paths, not this shell's, because Git Bash adds its own folders to its own.
mode=${1:-check}
case "${SAPOT_OS:-$(uname -s 2>/dev/null)}" in MINGW*|MSYS*|CYGWIN*) ;; *) echo skip; exit 0 ;; esac
ps=${SAPOT_POWERSHELL:-powershell.exe}
command -v "$ps" >/dev/null 2>&1 || { echo skip; exit 0; }
root=${SAPOT_GIT_ROOT_WIN:-$(cygpath -w / 2>/dev/null)}   # e.g. C:\Program Files\Git\
[ -n "$root" ] || { echo nogit; exit 0; }
SAPOT_GIT_BIN="${root%\\}\\bin" SAPOT_PATH_MODE=$mode "$ps" -NoProfile -NonInteractive -Command '
$d = $env:SAPOT_GIT_BIN
if (-not (Test-Path (Join-Path $d "sh.exe"))) { "nogit"; exit }
$u = [Environment]::GetEnvironmentVariable("Path", "User"); if (-not $u) { $u = "" }
$m = [Environment]::GetEnvironmentVariable("Path", "Machine"); if (-not $m) { $m = "" }
foreach ($p in (($u + ";" + $m) -split ";")) {
  if ($p -and (Test-Path (Join-Path ([Environment]::ExpandEnvironmentVariables($p)) "sh.exe"))) { "ok"; exit }
}
if ($env:SAPOT_PATH_MODE -eq "fix") {
  [Environment]::SetEnvironmentVariable("Path", (($u.TrimEnd(";") + ";" + $d).TrimStart(";")), "User"); "fixed"
} else { "missing" }' 2>/dev/null | tr -d '\r' | tail -n 1
