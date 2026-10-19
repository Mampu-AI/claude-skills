#!/usr/bin/env python3
"""Which work-loop milestone, if any, a Bash command RUNS.

    kind_of("gh pr merge 12 --squash")            -> "pr_merged"
    kind_of("gh pr create --fill")                -> "pr_opened"
    kind_of("python3 stage-queue.py promote")     -> "promoted"
    kind_of("python3 stage-queue.py promote --dry-run") -> None
    kind_of('echo "gh pr merge"')                 -> None   (quoted text is stripped first)

Only a command at the start of the line or after ; && || | counts, never one inside quotes, so an
echo, a commit message or a grep pattern that mentions the command does not fire. Lifted from the
learning trigger's MILESTONE_CMD / QUOTED idea. Shared by hooks/milestone.sh and
hooks/review_trigger.py; `python3 milestone_kind.py` reads one command from stdin and prints the kind.
"""
import re
import sys

QUOTED = re.compile(r"'[^']*'|\"(?:\\.|[^\"\\])*\"")
HEAD = r"(?:^|[;&|]\s*)"
PATTERNS = (
    ("promoted", re.compile(HEAD + r"(?:\S*python3?\s+)?\S*stage-queue\.py\s+promote\b(?![^\n;&|]*--dry-run)")),
    ("pr_merged", re.compile(HEAD + r"gh\s+pr\s+merge\b")),
    ("pr_opened", re.compile(HEAD + r"gh\s+pr\s+create\b")),
)


def kind_of(command):
    if not command:
        return None
    bare = QUOTED.sub("", str(command))
    for kind, pattern in PATTERNS:
        if pattern.search(bare):
            return kind
    return None


if __name__ == "__main__":
    found = kind_of(sys.stdin.read())
    if found:
        print(found)
