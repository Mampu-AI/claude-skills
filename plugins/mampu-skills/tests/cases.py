#!/usr/bin/env python3
"""The hook cases run by tests/run.sh (env: PLUGIN_ROOT, REQUEST_LOG, WORK_DIR, HOME, SAPOT_API_URL,
SAPOT_STAFF_TOKEN). Each case feeds a hook a realistic hook-input JSON on stdin and asserts the exact
output, the request the fake server saw, and the state-file transition. Prints one line per case."""
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

PLUGIN = Path(os.environ["PLUGIN_ROOT"])
HOOKS = PLUGIN / "hooks"
LOG = Path(os.environ["REQUEST_LOG"])
WORK = Path(os.environ["WORK_DIR"])
STATE_DIR = Path(os.environ["HOME"]) / ".cache" / "sapot-work-loop"
SPOOL = STATE_DIR / "spool"
CWD = "/tmp/some-repo"

TASK_TITLE = "Collect step keeps old menu pick"
BLOCK = ("Task:      Collect step keeps old menu pick — found, open → marked doing\n"
         "Records:   flow-turn-handling-fix — found, reading it\n"
         "Help page: Collect steps — found, will check after the change\n"
         "Client:    none on this task")
SESSION_START_CONTEXT = (
    "[work-loop] Open for you: Collect step keeps old menu pick (doing). Rule: a reply that starts work opens with "
    "the four-line status block (Task / Records / Help page / Client); call team_task_start on the matching task or with "
    "create when none matches; call team_task_milestone on PR open/merge/promote; call team_task_finish before you finish. "
    "No code detail (source paths, function or table names, code) in titles, summaries or records. "
    "Details: the work-loop skill.")
PROMPT = "Fix the collect step that keeps the old menu pick"
PROMPT_CONTEXT = (
    "[work-loop] For this prompt — Task candidates: Collect step keeps old menu pick (task-guid-001, open). "
    "GitHub issues (not team tasks): #2301 Flow designer: duplicate End nodes. "
    "Records: flow-turn-handling-fix — How to fix how the runtime handles one customer turn at a blocking step; "
    "stage-queue-release — Queue, fire and verify a staging batch. Help pages: Collect steps (flow-agents/collect-steps.md). "
    "If this prompt is work: call team_task_start with the matching task_guid, or with create:{title} when nothing matches, "
    "then open your reply with the status block. A question or a read is not work: no task, no block.\n"
    "Server block:\n" + BLOCK)
MILESTONE_CONTEXT = ("[work-loop] milestone %s detected. Call team_task_milestone with the URL if known; when the work is "
                     "complete, call team_task_finish.")
STOP_REASON = ('[work-loop] Close-out owed for task "%s": call team_task_finish with state done, doing, waiting or '
               "blocked, the one-line summary, the debrief (how, pitfalls, findings), changed paths, any record updates, and the "
               "help pages you checked; then print the close-out status block.")
START_TOOL = "mcp__plugin_mampu-skills_mampu-tech-team__team_task_start"
FINISH_TOOL = "mcp__plugin_mampu-skills_mampu-tech-team__team_task_finish"

results = []


def check(name, condition, detail=""):
    results.append((name, bool(condition), detail))
    print(("PASS " if condition else "FAIL ") + name + ("" if condition or not detail else f"  -- {detail}"))


def run(script, payload, env=None, timeout=20):
    cmd = ["sh", str(HOOKS / script)] if script.endswith(".sh") else ["python3", str(HOOKS / script)]
    full = dict(os.environ)
    full.update(env or {})
    started = time.time()
    proc = subprocess.run(cmd, input=json.dumps(payload), capture_output=True, text=True, env=full, timeout=timeout)
    return proc.returncode, proc.stdout, proc.stderr, time.time() - started


def requests(clear=True):
    rows = [json.loads(line) for line in LOG.read_text().splitlines() if line.strip()] if LOG.exists() else []
    if clear:
        LOG.write_text("")
    return rows


def state(sid):
    path = STATE_DIR / f"{sid}.json"
    return json.loads(path.read_text()) if path.exists() else None


def review_state(sid):
    path = STATE_DIR / f"{sid}.review.json"
    return json.loads(path.read_text()) if path.exists() else None


def context(out, event):
    try:
        data = json.loads(out)
    except ValueError:
        return None
    hso = data.get("hookSpecificOutput") or {}
    return hso.get("additionalContext") if hso.get("hookEventName") == event else None


def base(sid, event, **extra):
    payload = {"session_id": sid, "transcript_path": str(WORK / f"{sid}.jsonl"), "cwd": CWD,
               "hook_event_name": event, "permission_mode": "default"}
    payload.update(extra)
    return payload


def post_tool(sid, tool_name, tool_input, tool_response):
    return base(sid, "PostToolUse", tool_name=tool_name, tool_input=tool_input, tool_response=tool_response)


def write_transcript(sid, text):
    lines = [
        {"type": "user", "message": {"role": "user", "content": "please merge it"}},
        {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}},
        {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "name": "Bash", "input": {}}]}},
    ]
    (WORK / f"{sid}.jsonl").write_text("\n".join(json.dumps(l) for l in lines) + "\n")


def start_response(created=False, as_blocks=True):
    task = {"guid": "task-guid-new" if created else "task-guid-001",
            "title": "New thing" if created else TASK_TITLE, "status": "doing",
            "url": "https://tasks.example.invalid/x", "github_issue": None if created else 2268, "created": created}
    payload = {"task": task, "block_line": "Task:      %s — found, open → marked doing" % task["title"]}
    return [{"type": "text", "text": json.dumps(payload)}] if as_blocks else payload


def silent(name, rc, out, err=""):
    check(name, rc == 0 and out == "", f"rc={rc} out={out!r} err={err.strip()[:200]!r}")


def closed_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


# ---------------------------------------------------------------- SessionStart
sid = "sess-aaaa-0001"
requests()
rc, out, err, _ = run("session_start.sh", base(sid, "SessionStart", source="startup"))
check("SessionStart exits 0", rc == 0, err)
check("SessionStart injects the open tasks + rule", context(out, "SessionStart") == SESSION_START_CONTEXT, out)
reqs = requests()
check("SessionStart made one authenticated GET work/open",
      [(r["method"], r["path"], r["token_ok"]) for r in reqs] == [("GET", "/v1/work/open", True)], reqs)

# ---------------------------------------------------------------- UserPromptSubmit
rc, out, err, _ = run("prompt_match.sh", base(sid, "UserPromptSubmit", prompt=PROMPT))
check("UserPromptSubmit exits 0", rc == 0, err)
check("UserPromptSubmit injects candidates + instruction + server block",
      context(out, "UserPromptSubmit") == PROMPT_CONTEXT, out)
reqs = requests()
check("UserPromptSubmit posted the contract body to work/match",
      len(reqs) == 1 and (reqs[0]["method"], reqs[0]["path"], reqs[0]["token_ok"]) == ("POST", "/v1/work/match", True)
      and reqs[0]["body"] == {"prompt": PROMPT, "repo": None, "surface": "claude-code"}, reqs)
rc, out, err, _ = run("prompt_match.sh", base(sid, "UserPromptSubmit", prompt="hi there"))
silent("UserPromptSubmit skips a prompt under 12 characters", rc, out, err)
rc, out, err, _ = run("prompt_match.sh", base(sid, "UserPromptSubmit", prompt="/retro curate the memory index"))
silent("UserPromptSubmit skips a slash command", rc, out, err)
check("skipped prompts made no request", requests() == [])

# ---------------------------------------------------------------- PostToolUse Bash milestones
rc, out, err, _ = run("milestone.sh", post_tool(sid, "Bash", {"command": "gh pr merge 123 --squash --delete-branch"},
                                                 {"stdout": "✓ Merged", "stderr": "", "interrupted": False}))
check("gh pr merge → milestone context", rc == 0 and context(out, "PostToolUse") == MILESTONE_CONTEXT % "pr_merged", out)
check("gh pr merge → state.milestone = pr_merged", (state(sid) or {}).get("milestone") == "pr_merged", state(sid))
check("milestone hook needs no server request", requests() == [])

quoted_sid = "sess-aaaa-0002"
rc, out, err, _ = run("milestone.sh", post_tool(quoted_sid, "Bash", {"command": 'echo "gh pr merge"'}, {"stdout": "gh pr merge"}))
silent("quoted `echo \"gh pr merge\"` does not count", rc, out, err)
check("quoted command wrote no state", state(quoted_sid) is None, state(quoted_sid))
rc, out, err, _ = run("milestone.sh", post_tool(quoted_sid, "Bash", {"command": "git commit -m 'before gh pr create' && gh pr create --fill"}, {}))
check("gh pr create after && → pr_opened", context(out, "PostToolUse") == MILESTONE_CONTEXT % "pr_opened"
      and (state(quoted_sid) or {}).get("milestone") == "pr_opened", out)
promote_sid = "sess-aaaa-0003"
rc, out, err, _ = run("milestone.sh", post_tool(promote_sid, "Bash", {"command": "python3 ~/tools/stage-queue.py promote --dry-run"}, {}))
silent("stage-queue.py promote --dry-run does not count", rc, out, err)
rc, out, err, _ = run("milestone.sh", post_tool(promote_sid, "Bash", {"command": "python3 ~/tools/stage-queue.py promote"}, {}))
check("stage-queue.py promote → promoted", context(out, "PostToolUse") == MILESTONE_CONTEXT % "promoted"
      and (state(promote_sid) or {}).get("milestone") == "promoted", out)
rc, out, err, _ = run("milestone.sh", post_tool(promote_sid, "Bash", {"command": "ls -la"}, {}))
silent("a plain command is silent", rc, out, err)

# ---------------------------------------------------------------- PostToolUse team_task_start
rc, out, err, _ = run("start_seen.sh", post_tool(sid, START_TOOL, {"task_guid": "task-guid-001"}, start_response()))
st = state(sid) or {}
silent("team_task_start seen (content blocks) is silent", rc, out, err)
check("team_task_start seen → started/task_guid/task_title/created recorded, milestone kept",
      (st.get("started"), st.get("task_guid"), st.get("task_title"), st.get("created"), st.get("milestone"), st.get("finished"))
      == (True, "task-guid-001", TASK_TITLE, False, "pr_merged", False), st)
created_sid = "sess-aaaa-0004"
rc, out, err, _ = run("start_seen.sh", post_tool(created_sid, START_TOOL, {"create": {"title": "New thing"}},
                                                  start_response(created=True, as_blocks=False)))
st = state(created_sid) or {}
check("team_task_start seen (dict response, create) → created true",
      (st.get("started"), st.get("task_guid"), st.get("task_title"), st.get("created")) == (True, "task-guid-new", "New thing", True), st)
error_sid = "sess-aaaa-0005"
rc, out, err, _ = run("start_seen.sh", post_tool(error_sid, START_TOOL, {"task_guid": "nope"},
                                                  [{"type": "text", "text": json.dumps({"error": "unknown task"})}]))
silent("team_task_start error response is ignored", rc, out, err)
check("team_task_start error wrote no state", state(error_sid) is None)

# ---------------------------------------------------------------- Stop gate
write_transcript(sid, "Merged the PR and verified on staging.")
rc, out, err, _ = run("stop_gate.sh", base(sid, "Stop", stop_hook_active=False))
check("Stop with milestone pending and not finished → block with the task title",
      rc == 0 and json.loads(out or "{}") == {"decision": "block", "reason": STOP_REASON % TASK_TITLE}, out)
check("Stop stored last_assistant from the transcript",
      (state(sid) or {}).get("last_assistant") == "Merged the PR and verified on staging.", state(sid))
rc, out, err, _ = run("stop_gate.sh", base(sid, "Stop", stop_hook_active=True))
silent("Stop with stop_hook_active passes through", rc, out, err)
rc, out, err, _ = run("stop_gate.sh", base(created_sid, "Stop", stop_hook_active=False))
silent("Stop with no milestone passes through", rc, out, err)
no_task_sid = "sess-aaaa-0006"
run("milestone.sh", post_tool(no_task_sid, "Bash", {"command": "gh pr create --fill"}, {}))
rc, out, err, _ = run("stop_gate.sh", base(no_task_sid, "Stop", stop_hook_active=False))
check("Stop blocks even when no task was started (team_task_finish takes task_guid null)",
      json.loads(out or "{}") == {"decision": "block", "reason": STOP_REASON % "(no task started)"}, out)

# ---------------------------------------------------------------- PostToolUse team_task_finish, then Stop
rc, out, err, _ = run("finish_seen.sh", post_tool(sid, FINISH_TOOL, {"task_guid": "task-guid-001", "state": "done"},
                                                   [{"type": "text", "text": json.dumps({"task": {}, "block": BLOCK})}]))
st = state(sid) or {}
silent("team_task_finish seen is silent", rc, out, err)
check("team_task_finish seen → finished true, milestone cleared, task kept",
      (st.get("finished"), st.get("milestone"), st.get("task_guid"), st.get("started")) == (True, None, "task-guid-001", True), st)
rc, out, err, _ = run("stop_gate.sh", base(sid, "Stop", stop_hook_active=False))
silent("Stop after team_task_finish passes through", rc, out, err)
check("state-file hooks made no requests", requests() == [])

# ---------------------------------------------------------------- PostToolUse changes, then Stop
repo = WORK / "client-repo"
(repo / "src").mkdir(parents=True)
subprocess.run(["git", "init", "-q", str(repo)], check=True)
loose = WORK / "loose-notes"
loose.mkdir()
claude_dir = Path(os.environ["HOME"]) / ".claude" / "projects" / "x" / "memory"
claude_dir.mkdir(parents=True)
subprocess.run(["git", "init", "-q", str(Path(os.environ["HOME"]) / ".claude")], check=True)

edit_sid = "sess-cccc-0001"
rc, out, err, _ = run("change_seen.sh", post_tool(edit_sid, "Edit", {"file_path": str(repo / "src" / "a.py")}, {}))
silent("an edit inside a project is silent", rc, out, err)
check("an edit inside a project → state.changed = file", (state(edit_sid) or {}).get("changed") == "file", state(edit_sid))
write_sid = "sess-cccc-0002"
run("change_seen.sh", post_tool(write_sid, "Write", {"file_path": str(repo / "src" / "new" / "b.md")}, {}))
check("a new file in a new folder inside a project counts", (state(write_sid) or {}).get("changed") == "file", state(write_sid))
skip_sid = "sess-cccc-0003"
run("change_seen.sh", post_tool(skip_sid, "Write", {"file_path": str(loose / "scratch.txt")}, {}))
run("change_seen.sh", post_tool(skip_sid, "Edit", {"file_path": str(claude_dir / "note.md")}, {}))
run("change_seen.sh", post_tool(skip_sid, "NotebookEdit", {"notebook_path": "/nowhere/at/all.ipynb"}, {}))
check("scratch files, Claude's own notes and missing folders do not count", state(skip_sid) is None, state(skip_sid))

commit_sid = "sess-cccc-0004"
run("change_seen.sh", post_tool(commit_sid, "Bash", {"command": 'echo "git commit -m x"'}, {}))
run("change_seen.sh", post_tool(commit_sid, "Bash", {"command": "git status && git log -1"}, {}))
check("a quoted or read-only git command does not count", state(commit_sid) is None, state(commit_sid))
rc, out, err, _ = run("change_seen.sh", post_tool(commit_sid, "Bash", {"command": "git add -A && git commit -m 'fix the menu'"}, {}))
silent("git commit is silent", rc, out, err)
check("git commit → state.changed = commit", (state(commit_sid) or {}).get("changed") == "commit", state(commit_sid))
push_sid = "sess-cccc-0005"
run("change_seen.sh", post_tool(push_sid, "Bash", {"command": "git -C ~/work/repo push origin HEAD:feat/x"}, {}))
check("git -C … push → changed = commit", (state(push_sid) or {}).get("changed") == "commit", state(push_sid))

SAPOT = "mcp__plugin_mampu-chat_sapot-flows__"
read_sid = "sess-cccc-0006"
for name in ("list_accounts", "get_flow_graph", "search_contacts", "count_conversations", "filter_contacts",
             "preview_campaign_audience", "check_graph", "test_flow", "get_knowledge_upload_link"):
    run("change_seen.sh", post_tool(read_sid, SAPOT + name, {"account_id": 2}, {}))
check("Sapot Chat tools that only look do not count", state(read_sid) is None, state(read_sid))
sapot_sid = "sess-cccc-0007"
rc, out, err, _ = run("change_seen.sh", post_tool(sapot_sid, SAPOT + "update_contact", {"account_id": 2}, {}))
silent("a Sapot Chat change is silent", rc, out, err)
check("a Sapot Chat change (update_contact) → changed = sapot", (state(sapot_sid) or {}).get("changed") == "sapot", state(sapot_sid))
for name in ("save_flow", "reply_to_conversation", "create_knowledge_entry", "set_flow_agent_inboxes", "patch_flow"):
    other = "sess-cccc-07" + name[:2]
    run("change_seen.sh", post_tool(other, SAPOT + name, {"account_id": 2}, {}))
    check(f"Sapot Chat {name} counts as a change", (state(other) or {}).get("changed") == "sapot", state(other))
check("change hooks made no requests", requests() == [])

CHANGE_REASON = ("[work-loop] This session changed something (project files, a commit, or a client in Sapot Chat) and no "
                 "team task is started. Without asking the person, call team_task_start with the matching task, or create "
                 "one when none fits, then team_task_finish with state done, doing, waiting or blocked, the one-line summary and the debrief; then print the close-out "
                 "status block.")
rc, out, err, _ = run("stop_gate.sh", base(sapot_sid, "Stop", stop_hook_active=False))
check("Stop after a change with no task → block: start a task and close it out",
      rc == 0 and json.loads(out or "{}") == {"decision": "block", "reason": CHANGE_REASON}, out)
rc, out, err, _ = run("stop_gate.sh", base(sapot_sid, "Stop", stop_hook_active=True))
silent("Stop after a change with stop_hook_active passes through", rc, out, err)
run("start_seen.sh", post_tool(edit_sid, START_TOOL, {"task_guid": "task-guid-001"}, start_response()))
rc, out, err, _ = run("stop_gate.sh", base(edit_sid, "Stop", stop_hook_active=False))
check("Stop after a change with a task started and not finished → block for the close-out",
      json.loads(out or "{}") == {"decision": "block", "reason": STOP_REASON % TASK_TITLE}, out)
run("finish_seen.sh", post_tool(edit_sid, FINISH_TOOL, {"state": "doing"}, [{"type": "text", "text": "{}"}]))
check("team_task_finish clears the change", (state(edit_sid) or {}).get("changed") is None, state(edit_sid))
rc, out, err, _ = run("stop_gate.sh", base(edit_sid, "Stop", stop_hook_active=False))
silent("Stop after the close-out passes through", rc, out, err)
rc, out, err, _ = run("stop_gate.sh", base(push_sid, "Stop", stop_hook_active=False), env={"SAPOT_STAFF_TOKEN": ""})
silent("Stop after a change on a machine that is not connected passes through", rc, out, err)
check("change gate made no requests", requests() == [])

# a change made by a shell command (sed, a heredoc, echo >) is seen by comparing the project at Stop
shell_sid = "sess-cccc-0008"
in_repo = dict(cwd=str(repo))
run("session_start.sh", base(shell_sid, "SessionStart", source="startup", **in_repo))
requests()
check("SessionStart remembers where the project stood", bool((state(shell_sid) or {}).get("baseline")), state(shell_sid))
rc, out, err, _ = run("stop_gate.sh", base(shell_sid, "Stop", stop_hook_active=False, **in_repo))
silent("Stop with the project unchanged passes through", rc, out, err)
(repo / "hello.txt").write_text("hello\n")
rc, out, err, _ = run("stop_gate.sh", base(shell_sid, "Stop", stop_hook_active=False, **in_repo))
check("Stop after a file was written outside the edit tools → block: start a task and close it out",
      json.loads(out or "{}") == {"decision": "block", "reason": CHANGE_REASON}, out)
run("start_seen.sh", post_tool(shell_sid, START_TOOL, {"task_guid": "task-guid-001"}, start_response()))
run("finish_seen.sh", base(shell_sid, "PostToolUse", tool_name=FINISH_TOOL, tool_input={}, tool_response="{}", **in_repo))
rc, out, err, _ = run("stop_gate.sh", base(shell_sid, "Stop", stop_hook_active=False, **in_repo))
silent("Stop after the close-out, project unchanged since, passes through", rc, out, err)
first = (state(shell_sid) or {}).get("baseline")
run("session_start.sh", base(shell_sid, "SessionStart", source="compact", **in_repo))
requests()
check("a later SessionStart (compact, resume) keeps the starting point", (state(shell_sid) or {}).get("baseline") == first)
outside_sid = "sess-cccc-0009"
run("session_start.sh", base(outside_sid, "SessionStart", source="startup", cwd=str(loose)))
requests()
check("a session outside any project has no starting point", not (state(outside_sid) or {}).get("baseline"), state(outside_sid))

# ---------------------------------------------------------------- SessionEnd
rc, out, err, _ = run("session_end.sh", base(sid, "SessionEnd", reason="exit"))
silent("SessionEnd on a finished task is silent", rc, out, err)
check("SessionEnd on a finished task posts nothing", requests() == [])
unfinished_sid = "sess-aaaa-0007"
run("start_seen.sh", post_tool(unfinished_sid, START_TOOL, {"task_guid": "task-guid-001"}, start_response()))
write_transcript(unfinished_sid, "Half way: the spec is drafted, the PR is not opened yet.")
run("stop_gate.sh", base(unfinished_sid, "Stop", stop_hook_active=False))
rc, out, err, _ = run("session_end.sh", base(unfinished_sid, "SessionEnd", reason="exit"))
silent("SessionEnd on an unfinished task is silent", rc, out, err)
reqs = requests()
check("SessionEnd on an unfinished task posts kind=session_end with the last assistant line",
      len(reqs) == 1 and (reqs[0]["method"], reqs[0]["path"], reqs[0]["token_ok"]) == ("POST", "/v1/work/milestone", True)
      and reqs[0]["body"] == {"task_guid": "task-guid-001", "kind": "session_end", "url": None,
                              "note": "Half way: the spec is drafted, the PR is not opened yet.", "session_id": unfinished_sid}, reqs)
rc, out, err, _ = run("session_end.sh", base("sess-aaaa-0008", "SessionEnd", reason="exit"))
silent("SessionEnd with no task started is silent", rc, out, err)
check("SessionEnd with no task started posts nothing", requests() == [])

# ---------------------------------------------------------------- review_trigger.py
rsid = "sess-rrrr-0001"
fired_early = False
for i in range(59):
    rc, out, err, _ = run("review_trigger.py", post_tool(rsid, "Read", {"file_path": "/x"}, {"ok": True}))
    fired_early = fired_early or bool(out)
check("review trigger stays silent for 59 tool calls", not fired_early and (review_state(rsid) or {}).get("tools") == 59, review_state(rsid))
rc, out, err, _ = run("review_trigger.py", post_tool(rsid, "Read", {"file_path": "/x"}, {"ok": True}))
ctx = context(out, "PostToolUse") or ""
check("review trigger fires on the 60th tool call, naming the fork, prompt file and spool path",
      rc == 0 and "60 tool calls since the last records review" in ctx and f"RECORDS REVIEW for session {rsid}" in ctx
      and str(HOOKS / "review-prompt.md") in ctx and str(SPOOL / f"{rsid}-") in ctx and 'subagent_type "fork"' in ctx, ctx)
rs = review_state(rsid) or {}
check("review trigger reset since_review and stamped last_fire", rs.get("since_review") == 0 and rs.get("tools") == 60 and rs.get("last_fire", 0) > 0, rs)
rc, out, err, _ = run("review_trigger.py", post_tool(rsid, "Bash", {"command": "gh pr merge 5"}, {}))
silent("a milestone inside the 20-minute cooldown does not fire again", rc, out, err)
msid = "sess-rrrr-0002"
rc, out, err, _ = run("review_trigger.py", post_tool(msid, "Bash", {"command": "gh pr merge 5 --squash"}, {}))
check("review trigger fires at once on a real gh pr merge", "Milestone pr_merged just ran in this session" in (context(out, "PostToolUse") or ""), out)
dsid = "sess-rrrr-0003"
rc, out, err, _ = run("review_trigger.py", post_tool(dsid, "Bash", {"command": "python3 stage-queue.py promote --dry-run"}, {}))
silent("review trigger ignores a dry-run promote", rc, out, err)
check("review trigger counted the dry-run call", (review_state(dsid) or {}).get("tools") == 1)
rc, out, err, _ = run("review_trigger.py", dict(post_tool("sess-rrrr-0004", "Bash", {"command": "gh pr merge 1"}, {}), agent_id="agent-1"))
silent("review trigger ignores subagent calls", rc, out, err)
check("review trigger wrote no state for a subagent", review_state("sess-rrrr-0004") is None)

# ---------------------------------------------------------------- review_apply.py
SPOOL.mkdir(parents=True, exist_ok=True)
good = {"slug": "flow-collect-stale-pick-fix", "area": "flow-runtime", "name": "Flow collect stale pick fix",
        "description": "When a collect step keeps an old menu pick", "type": "procedure", "audience": "dev",
        "body": "# Steps\n\n1. Reproduce on the recorded turn.\n", "action": "create", "why": "took three rounds"}
bad = dict(good, slug="Bad Slug")
spool_file = SPOOL / f"{sid}-202610141200.json"
spool_file.write_text(json.dumps({"session": sid, "debrief": [{"task": "fix", "how_done": "tdd"}], "records": [good, bad]}))
rc, out, err, _ = run("review_apply.py", base(sid, "Stop", stop_hook_active=False))
silent("review_apply is silent", rc, out, err)
reqs = requests()
check("review_apply posted only the valid record with the contract fields",
      len(reqs) == 1 and (reqs[0]["method"], reqs[0]["path"], reqs[0]["token_ok"]) == ("POST", "/v1/work/records", True)
      and reqs[0]["body"] == {k: good[k] for k in ("slug", "area", "name", "description", "type", "audience", "body")}, reqs)
check("review_apply moved the processed spool file to spool/done/",
      not spool_file.exists() and (SPOOL / "done" / spool_file.name).exists())
log_text = (STATE_DIR / "review_apply.log").read_text() if (STATE_DIR / "review_apply.log").exists() else ""
check("review_apply logged the skipped bad slug", "SKIP record 'Bad Slug'" in log_text, log_text[-400:])

secret_file = SPOOL / f"{sid}-202610141201.json"
secret_file.write_text(json.dumps({"session": sid, "records": [dict(good, slug="leaky-record",
                                                                       body="Set token: abcdefghijklmnop1234 in the env")]}))
rc, out, err, _ = run("review_apply.py", base(sid, "Stop", stop_hook_active=False))
check("review_apply refuses a spool file that looks like it holds a secret, without posting",
      rc == 0 and out == "" and requests() == [] and not secret_file.exists() and (SPOOL / "done" / secret_file.name).exists(), out)
log_text = (STATE_DIR / "review_apply.log").read_text()
check("review_apply logged the secret rejection", "REJECTED: looks like it contains a secret" in log_text, log_text[-300:])

refused_file = SPOOL / f"{sid}-202610141202.json"
refused_file.write_text(json.dumps({"session": sid, "records": [dict(good, slug="server-refuses-this")]}))
run("review_apply.py", base(sid, "Stop", stop_hook_active=False))
check("review_apply treats a 422 as final (moved to done, not retried)",
      len(requests()) == 1 and (SPOOL / "done" / refused_file.name).exists())

# ---------------------------------------------------------------- server down: silent, fast, exit 0
down = {"SAPOT_API_URL": f"http://127.0.0.1:{closed_port()}"}
dsid = "sess-dddd-0001"
rc, out, err, took = run("session_start.sh", base(dsid, "SessionStart", source="startup"), env=down)
silent("server down: SessionStart", rc, out, err)
check("server down: SessionStart returns quickly", took < 8, f"{took:.1f}s")
rc, out, err, _ = run("prompt_match.sh", base(dsid, "UserPromptSubmit", prompt=PROMPT), env=down)
silent("server down: UserPromptSubmit", rc, out, err)
rc, out, err, _ = run("milestone.sh", post_tool(dsid, "Bash", {"command": "ls -la"}, {}), env=down)
silent("server down: PostToolUse Bash", rc, out, err)
rc, out, err, _ = run("start_seen.sh", post_tool(dsid, START_TOOL, {"task_guid": "task-guid-001"}, start_response()), env=down)
silent("server down: PostToolUse team_task_start", rc, out, err)
rc, out, err, _ = run("finish_seen.sh", post_tool("sess-dddd-0002", FINISH_TOOL, {}, {}), env=down)
silent("server down: PostToolUse team_task_finish", rc, out, err)
rc, out, err, _ = run("stop_gate.sh", base(dsid, "Stop", stop_hook_active=False), env=down)
silent("server down: Stop with nothing pending", rc, out, err)
rc, out, err, _ = run("session_end.sh", base(dsid, "SessionEnd", reason="exit"), env=down)
silent("server down: SessionEnd (started, unfinished) swallows the failed POST", rc, out, err)
rc, out, err, _ = run("review_trigger.py", post_tool(dsid, "Read", {}, {}), env=down)
silent("server down: review_trigger", rc, out, err)
stuck = SPOOL / f"{dsid}-202610141203.json"
stuck.write_text(json.dumps({"session": dsid, "records": [good]}))
rc, out, err, _ = run("review_apply.py", base(dsid, "Stop", stop_hook_active=False), env=down)
silent("server down: review_apply", rc, out, err)
check("server down: review_apply keeps the spool file for the next Stop with one attempt counted",
      stuck.exists() and json.loads(stuck.read_text()).get("_attempts") == 1, stuck.exists())
stuck.unlink()
check("server down: no hook reached the real server", requests() == [])


# a server that accepts the connection and never answers: the 5 s curl cap must hold
def hang_forever():
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(5)
    hang_forever.port = listener.getsockname()[1]
    hang_forever.ready.set()
    while True:
        conn, _ = listener.accept()
        hang_forever.conns.append(conn)


hang_forever.ready = threading.Event()
hang_forever.conns = []
threading.Thread(target=hang_forever, daemon=True).start()
hang_forever.ready.wait(5)
rc, out, err, took = run("session_start.sh", base("sess-dddd-0003", "SessionStart", source="startup"),
                         env={"SAPOT_API_URL": f"http://127.0.0.1:{hang_forever.port}"})
silent("hanging server: SessionStart", rc, out, err)
check("hanging server: SessionStart gives up within the 5 s cap", 4 <= took < 9, f"{took:.1f}s")

# ---------------------------------------------------------------- a newer plugin copy is installed
pcache = Path(os.environ["WORK_DIR"]) / "pcache"
(pcache / "cache" / "mampu" / "mampu-skills").mkdir(parents=True, exist_ok=True)
running_root = pcache / "cache" / "mampu" / "mampu-skills" / "aaaaaaaaaaaa"
(pcache / "installed_plugins.json").write_text(json.dumps({"version": 2, "plugins": {"mampu-skills@mampu": [
    {"scope": "managed", "version": "bbbbbbbbbbbb", "installPath": str(pcache / "cache" / "mampu" / "mampu-skills" / "bbbbbbbbbbbb")}]}}))
stale = {"CLAUDE_PLUGIN_ROOT": str(running_root), "CLAUDE_CODE_PLUGIN_CACHE_DIR": str(pcache)}
rc, out, err, _ = run("prompt_match.sh", base("sess-uuuu-0001", "UserPromptSubmit", prompt=PROMPT), env=stale)
check("newer copy installed: the prompt hook shows the person a reload notice and keeps the candidates",
      rc == 0 and json.loads(out).get("systemMessage") == "Work loop plugin updated. Run /reload-plugins to use it (or restart Claude Code)."
      and context(out, "UserPromptSubmit").startswith("[work-loop] A newer copy of this plugin is installed (bbbbbbbbbbbb)")
      and "Task candidates: Collect step keeps old menu pick" in context(out, "UserPromptSubmit"), out)
requests()
rc, out, err, _ = run("prompt_match.sh", base("sess-uuuu-0001", "UserPromptSubmit", prompt=PROMPT),
                      env={**stale, "SAPOT_API_URL": "http://127.0.0.1:9"})
check("newer copy installed, server down: the reload notice still shows",
      rc == 0 and json.loads(out).get("systemMessage", "").startswith("Work loop plugin updated"), out)
same = {"CLAUDE_PLUGIN_ROOT": str(pcache / "cache" / "mampu" / "mampu-skills" / "bbbbbbbbbbbb"), "CLAUDE_CODE_PLUGIN_CACHE_DIR": str(pcache)}
rc, out, err, _ = run("prompt_match.sh", base("sess-uuuu-0002", "UserPromptSubmit", prompt=PROMPT), env=same)
check("running copy is the installed one: no notice", rc == 0 and "systemMessage" not in json.loads(out), out)
requests()

# ---------------------------------------------------------------- no token / wrong token
no_token = {"SAPOT_STAFF_TOKEN": ""}
rc, out, err, _ = run("session_start.sh", base("sess-tttt-0001", "SessionStart", source="startup"), env=no_token)
check("no token: SessionStart tells the agent to ask for 'connect me' at each reply",
      rc == 0 and context(out, "SessionStart").startswith("[work-loop] You are not connected to the company Lark and docs yet. Before anything else, ask the person")
      and "Keep asking at each reply" in context(out, "SessionStart"), out)
check("no token: SessionStart shows the person a notice too",
      json.loads(out).get("systemMessage") == "Work loop: not connected. Say \"connect me\" to sign in with Lark (one browser step).", out)
check("no token: the nudge sent nothing to the server", requests() == [])
rc, out, err, _ = run("prompt_match.sh", base("sess-tttt-0001", "UserPromptSubmit", prompt=PROMPT), env=no_token)
check("no token: UserPromptSubmit nudges on every work-shaped prompt, agent and person",
      rc == 0 and context(out, "UserPromptSubmit").startswith("[work-loop] This person is not connected to the work loop. Before anything else, ask them")
      and json.loads(out).get("systemMessage") == "Work loop: not connected. Say \"connect me\" to sign in with Lark.", out)
check("no token: the prompt nudge sent nothing to the server", requests() == [])
rc, out, err, _ = run("prompt_match.sh", base("sess-tttt-0001", "UserPromptSubmit", prompt="/help"), env=no_token)
silent("no token: a slash command gets no nudge", rc, out, err)
rc, out, err, _ = run("session_end.sh", base(unfinished_sid, "SessionEnd", reason="exit"), env=no_token)
silent("no token: SessionEnd", rc, out, err)
stuck = SPOOL / "sess-tttt-0001-202610141204.json"
stuck.write_text(json.dumps({"session": "sess-tttt-0001", "records": [good]}))
rc, out, err, _ = run("review_apply.py", base("sess-tttt-0001", "Stop", stop_hook_active=False), env=no_token)
silent("no token: review_apply", rc, out, err)
check("no token: nothing was sent and the spool file is kept", requests() == [] and stuck.exists())
stuck.unlink()
rc, out, err, _ = run("session_start.sh", base("sess-tttt-0002", "SessionStart", source="startup"), env={"SAPOT_STAFF_TOKEN": "wrong"})
check("wrong token (401): SessionStart says the sign-in lapsed",
      rc == 0 and "has lapsed or was refused" in context(out, "SessionStart"), out)
reqs = requests()
check("wrong token reached the server once and was refused", len(reqs) == 1 and reqs[0]["token_ok"] is False, reqs)

# ---------------------------------------------------------------- onboarding: whoami, the login file, the node listener
import subprocess, time, urllib.request
SCRIPTS = HOOKS.parent / "scripts"
def script(name, env=None, timeout=20):
    full = dict(os.environ); full.update(env or {})
    p = subprocess.run(["sh", str(SCRIPTS / name)], capture_output=True, text=True, env=full, timeout=timeout)
    return p.returncode, p.stdout.strip(), p.stderr.strip()
rc, out, _ = script("whoami.sh", env=no_token)
check("whoami: no token → Not connected, exit 1", rc == 1 and out == "Not connected.", out)
rc, out, _ = script("whoami.sh")
check("whoami: staff token → connected line, exit 0", rc == 0 and out.startswith("Connected with a staff token as"), out)
rc, out, _ = script("whoami.sh", env={"SAPOT_STAFF_TOKEN": "wrong"})
check("whoami: refused token → lapsed line, exit 1", rc == 1 and out == "Sign-in lapsed or refused.", out)
login_file = Path(os.environ["HOME"]) / ".config" / "sapot" / "work-login"
login_file.parent.mkdir(parents=True, exist_ok=True)
login_file.write_text("test\n")
rc, out, err, _ = run("session_start.sh", base("sess-tttt-0003", "SessionStart", source="startup"), env=no_token)
check("login file: SessionStart authenticates from ~/.config/sapot/work-login when no keychain", context(out, "SessionStart") == SESSION_START_CONTEXT, out)
login_file.unlink()
listener_file = Path(os.environ["HOME"]) / "listener-login"
lp = subprocess.Popen(["node", str(SCRIPTS / "login_listener.js"), "sapot-work-login", str(listener_file)],
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
port_line = lp.stdout.readline().strip()
check("node listener prints its port first", port_line.isdigit(), port_line)
try:
    page = urllib.request.urlopen(f"http://127.0.0.1:{port_line}/?token=swl_test123&name=Bob", timeout=5).read().decode()
except Exception as exc:  # noqa: BLE001
    page = f"ERR {exc}"
lp.wait(timeout=10)
check("node listener answers the browser with a Done page and exits 0", "Done" in page and lp.returncode == 0, page[:80])
check("node listener stored the token in the fallback file (no keychain on this box)",
      listener_file.exists() and listener_file.read_text().strip() == "swl_test123", listener_file.read_text() if listener_file.exists() else "missing")
check("node listener reports who signed in", "Signed in as Bob" in lp.stdout.read())
listener_file.unlink(missing_ok=True)

# ---------------------------------------------------------------- a new Lark permission to grant
grant = {"SAPOT_STAFF_TOKEN": "test-grant"}
GRANT_URL = "https://work.example.invalid/v1/work/auth/lark/grant?ticket=t1"
rc, out, err, _ = run("session_start.sh", base("sess-gggg-0001", "SessionStart", source="startup"), env=grant)
check("SessionStart shows the person why and the link when a Lark permission is missing",
      rc == 0 and json.loads(out).get("systemMessage") ==
      "Work loop: one more Lark permission needed. Client tracking: find the client you are working on in the "
      "client Base. Approve it here (one click in Lark, nothing to restart): " + GRANT_URL, out)
check("SessionStart still injects the open tasks and tells the agent about the link",
      context(out, "SessionStart").startswith(SESSION_START_CONTEXT) and GRANT_URL in context(out, "SessionStart"), out)
rc, out, err, _ = run("prompt_match.sh", base("sess-gggg-0001", "UserPromptSubmit", prompt=PROMPT), env=grant)
check("UserPromptSubmit tells the agent about the missing permission without a notice on every prompt",
      rc == 0 and context(out, "UserPromptSubmit").startswith(PROMPT_CONTEXT.split("\n")[0])
      and GRANT_URL in context(out, "UserPromptSubmit") and "systemMessage" not in json.loads(out), out)
requests()

# ---------------------------------------------------------------- stale tasks: ask the owner once a day
stale = {"SAPOT_STAFF_TOKEN": "test-stale"}
STALE_ASK = (" Stale, ask the owner before other work: 1. Pause an ad from the report (waiting) — last note: "
             "Promoted to production: https://example.invalid/pr/9; 2. Mobile calendar tab (doing) — no note yet. Show "
             "the person this numbered list and ask in one line which are done, waiting (on whom), blocked or still "
             "doing; then call team_task_finish for each from the answer. Never close one without their word.")
rc, out, err, _ = run("session_start.sh", base("sess-ssss-0001", "SessionStart", source="startup"), env=stale)
check("SessionStart lists the stale tasks and tells the agent to ask the owner",
      rc == 0 and context(out, "SessionStart").endswith(STALE_ASK)
      and "Pause an ad from the report (waiting)" in context(out, "SessionStart").split(" Stale,")[0], out)
check("SessionStart shows the person the stale count",
      json.loads(out).get("systemMessage") == "Work loop: 2 of your tasks look stale; Claude will ask you about them.", out)
rc, out, err, _ = run("session_start.sh", base("sess-ssss-0002", "SessionStart", source="startup"), env=stale)
check("a second session the same day does not ask again",
      rc == 0 and "Stale," not in context(out, "SessionStart") and "systemMessage" not in json.loads(out), out)
requests()

# ---------------------------------------------------------------- hygiene
check("no hook wrote outside the temp HOME state dir",
      all(p.parent == STATE_DIR or p.parent == SPOOL or p.parent == SPOOL / "done" for p in STATE_DIR.rglob("*") if p.is_file()))
hooks_json = json.loads((HOOKS / "hooks.json").read_text())
timeouts = [h.get("timeout", 60) for event in hooks_json["hooks"].values() for group in event for h in group["hooks"]]
check("every hook is type command with a timeout of 10 s or less",
      all(h["type"] == "command" for event in hooks_json["hooks"].values() for group in event for h in group["hooks"])
      and all(t <= 10 for t in timeouts), timeouts)

failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
