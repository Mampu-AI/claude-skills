#!/usr/bin/env python3
"""Whether a finished tool call CHANGED something the team should see on a task, and what kind.

    file    Edit / Write / NotebookEdit on a file inside a git project (not Claude's own ~/.claude)
    commit  a Bash command that runs git commit or git push (not inside quotes)
    sapot   a Sapot Chat tool that is not a look-only one (list_, get_, search_, ...), e.g. a client
            contact, flow, knowledge entry or reply changed through the flows plugin

`python3 change_kind.py` reads the PostToolUse hook JSON from stdin and prints the kind, or nothing.
Unknown Sapot Chat verbs count as changes, so a new write tool is covered without a plugin release.
"""
import json
import os
import re
import subprocess
import sys

QUOTED = re.compile(r"'[^']*'|\"(?:\\.|[^\"\\])*\"")
GIT_WRITE = re.compile(r"(?:^|[;&|]\s*)git\s+(?:-C\s+\S+\s+)?(?:commit|push)\b")
SAPOT_TOOL = re.compile(r"^mcp__.*sapot-flows__([a-z0-9_]+)$")
LOOK_ONLY = ("list", "get", "search", "count", "filter", "preview", "check", "test")


def in_project(path):
    if not path:
        return False
    # HOME first: on Windows, Python's "~" is the profile folder, while the hooks run with Git Bash's HOME.
    home = os.environ.get("HOME") or os.path.expanduser("~")
    path = os.path.abspath(os.path.expanduser(path))
    real = os.path.normcase(os.path.realpath(path))
    claude = os.path.normcase(os.path.realpath(os.path.join(home, ".claude")))
    if real == claude or real.startswith(claude + os.sep):
        return False
    folder = os.path.dirname(path)
    while folder and not os.path.isdir(folder):
        parent = os.path.dirname(folder)
        if parent == folder:
            return False
        folder = parent
    try:
        out = subprocess.run(["git", "-C", folder, "rev-parse", "--is-inside-work-tree"],
                             capture_output=True, text=True, timeout=3)
    except Exception:
        return False
    return out.returncode == 0 and out.stdout.strip() == "true"


def kind_of(data):
    tool = str(data.get("tool_name") or "")
    args = data.get("tool_input") or {}
    if tool in ("Edit", "Write", "NotebookEdit"):
        return "file" if in_project(args.get("file_path") or args.get("notebook_path")) else None
    if tool == "Bash":
        return "commit" if GIT_WRITE.search(QUOTED.sub("", str(args.get("command") or ""))) else None
    match = SAPOT_TOOL.match(tool)
    if match and match.group(1).split("_")[0] not in LOOK_ONLY:
        return "sapot"
    return None


if __name__ == "__main__":
    try:
        found = kind_of(json.load(sys.stdin))
    except Exception:
        found = None
    if found:
        print(found)
