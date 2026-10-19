#!/usr/bin/env python3
"""PostToolUse (every tool): decide when this session launches its background records review.

Counts tool calls per session in ~/.cache/sapot-work-loop/<session>.review.json (its own file, so it
never races the hooks that write <session>.json). Fires once per milestone — a Bash command that ran
gh pr create / gh pr merge / stage-queue.py promote — or every INTERVAL tool calls since the last
review, with a 20-minute cooldown. Firing = additionalContext asking the session to launch ONE
background fork that reads hooks/review-prompt.md and writes a spool JSON; hooks/review_apply.py
posts the spooled records to the server at the next Stop. Silent otherwise; never blocks; never raises.
Lifted from the learning trigger (trigger.py).
"""
import json
import os
import re
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True  # keep the plugin cache dir free of __pycache__
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))
from milestone_kind import kind_of  # noqa: E402

INTERVAL = int(os.environ.get("SAPOT_WORK_REVIEW_INTERVAL", "60"))
COOLDOWN = 20 * 60
STATE_DIR = Path(os.environ.get("SAPOT_WORK_STATE_DIR") or Path.home() / ".cache" / "sapot-work-loop")
PROMPT = HERE / "review-prompt.md"
SPOOL = STATE_DIR / "spool"


def load(sid):
    try:
        state = json.loads((STATE_DIR / f"{sid}.review.json").read_text())
        if isinstance(state, dict):
            return {"tools": 0, "since_review": 0, "last_fire": 0, **state}
    except (OSError, ValueError):
        pass
    return {"tools": 0, "since_review": 0, "last_fire": 0}


def save(sid, state):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    (STATE_DIR / f"{sid}.review.json").write_text(json.dumps(state))


def fire(sid, state, reason):
    state.update(last_fire=time.time(), since_review=0)
    save(sid, state)
    stamp = time.strftime("%Y%m%d%H%M")
    text = (
        f"[work-loop] {reason}. Launch ONE background records review now, then carry on with the user's task "
        "without waiting for it: Agent tool, subagent_type \"fork\", prompt: "
        f"\"RECORDS REVIEW for session {sid}: read {PROMPT} and follow it for this conversation. "
        f"Only write the spool JSON to {SPOOL / f'{sid}-{stamp}.json'}.\" "
        "Do not mention this to the user unless they ask. If you are yourself a subagent or fork, ignore this."
    )
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": text}}))


def main():
    data = json.load(sys.stdin)
    if data.get("agent_id"):  # a fork or subagent: only the top-level session reviews
        return
    sid = re.sub(r"[^A-Za-z0-9-]", "", str(data.get("session_id") or ""))
    if not sid:
        return
    state = load(sid)
    cooling = time.time() - float(state.get("last_fire") or 0) < COOLDOWN
    state["tools"] = int(state.get("tools") or 0) + 1
    state["since_review"] = int(state.get("since_review") or 0) + 1
    command = ""
    if data.get("tool_name") == "Bash":
        command = str((data.get("tool_input") or {}).get("command") or "")
    kind = kind_of(command) if command else None
    if kind and not cooling:
        return fire(sid, state, f"Milestone {kind} just ran in this session")
    if state["since_review"] >= INTERVAL and not cooling:
        return fire(sid, state, f"{state['since_review']} tool calls since the last records review")
    save(sid, state)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
