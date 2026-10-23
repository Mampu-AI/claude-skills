#!/usr/bin/env python3
"""Fake Sapot work API for the hook tests: answers the slice-1 contract routes with fixture JSON and
appends every request to a JSONL log ({method, path, token_ok, body}).

    python3 fake_server.py --port 0 --log requests.jsonl --ready-file port.txt [--token test]

Binds the port (0 = any free port), writes the bound port to --ready-file, then serves until killed.
A request whose api_access_token header is not the expected token gets 401 {"error"}.
"""
import argparse
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

PREFIX = "/v1/work"
TASK = {"guid": "task-guid-001", "title": "Collect step keeps old menu pick", "status": "doing",
        "url": "https://tasks.example.invalid/task-guid-001", "github_issue": 2268,
        "last_note": "Doing — Alvin via claude-code", "updated_at": "2026-10-14T03:00:00Z"}
RECORDS = [
    {"slug": "flow-turn-handling-fix", "area": "flow-runtime", "name": "Flow turn handling fix",
     "description": "How to fix how the runtime handles one customer turn at a blocking step",
     "type": "procedure", "audience": "dev", "last_verified": "2026-10-01", "score": 0.81,
     "path": "records/flow-runtime/flow-turn-handling-fix.md"},
    {"slug": "stage-queue-release", "area": "ops", "name": "Stage queue release",
     "description": "Queue, fire and verify a staging batch", "type": "procedure", "audience": "dev",
     "last_verified": "2026-09-20", "score": 0.42, "path": "records/ops/stage-queue-release.md"},
]
HELP_PAGES = [{"title": "Collect steps", "path": "flow-agents/collect-steps.md", "score": 0.77}]
GITHUB_ISSUES = [{"number": 2301, "title": "Flow designer: duplicate End nodes", "url": "https://github.com/example/x/issues/2301",
                  "score": 0.3}]
PERMISSIONS = {"missing": ["bitable:app"], "why": "Client tracking: find the client you are working on in the client Base.",
               "url": "https://work.example.invalid/v1/work/auth/lark/grant?ticket=t1"}
GRANT_TOKEN = "test-grant"  # a login that has not granted the newest Lark permission
STALE_TOKEN = "test-stale"  # a login with tasks the owner should be asked about
STALE_TASKS = [dict(TASK, guid="task-guid-002", title="Pause an ad from the report", status="waiting",
                    last_note="Promoted to production: https://example.invalid/pr/9", stale=True),
               dict(TASK, guid="task-guid-003", title="Mobile calendar tab", last_note=None, stale=True)]
BLOCK = ("Task:      Collect step keeps old menu pick — found, open → marked doing\n"
         "Records:   flow-turn-handling-fix — found, reading it\n"
         "Help page: Collect steps — found, will check after the change\n"
         "Client:    none on this task")


def routes(method, path, body, needs_grant=False, stale=False):
    """Return (status, payload) for a contract route, or None when unknown."""
    answer = _routes(method, path, body)
    if stale and answer and answer[0] == 200 and path.rstrip("/").endswith("/open"):
        answer = (200, {"tasks": [TASK] + STALE_TASKS})
    if needs_grant and answer and answer[0] == 200 and path.rstrip("/").split("/")[-1] in ("open", "match"):
        answer = (200, dict(answer[1], permissions=PERMISSIONS))
    return answer


def _routes(method, path, body):
    route = path[len(PREFIX):].lstrip("/") if path.startswith(PREFIX) else None
    if route is None:
        return None
    if method == "GET" and route == "access":
        return 200, {"ok": True, "user": {"id": 1, "name": "Test Staff", "email": "staff@example.invalid"}}
    if method == "GET" and route.startswith("guide"):
        return 200, {"section": "loop", "content": "fixture guide", "notice": "internal"}
    if method == "GET" and route == "open":
        return 200, {"tasks": [TASK]}
    if method == "POST" and route == "match":
        if isinstance(body, dict) and "no match here" in str(body.get("prompt")):
            return 200, {"tasks": [], "github_issues": [], "records": [], "help_pages": [], "block": BLOCK}
        task = dict(TASK, status="open", score=0.9)
        task.pop("last_note"); task.pop("updated_at")
        records = [{k: r[k] for k in ("slug", "area", "name", "description", "audience", "score")} for r in RECORDS]
        return 200, {"tasks": [task], "github_issues": GITHUB_ISSUES, "records": records, "help_pages": HELP_PAGES,
                     "block": BLOCK}
    if method == "POST" and route == "start":
        create = body.get("create") if isinstance(body, dict) else None
        if isinstance(create, dict):
            task = {"guid": "task-guid-new", "title": create.get("title"), "status": "doing",
                    "url": "https://tasks.example.invalid/task-guid-new", "github_issue": None, "created": True}
        elif body.get("task_guid") == TASK["guid"]:
            task = {k: TASK[k] for k in ("guid", "title", "status", "url", "github_issue")}
            task["created"] = False
        else:
            return 404, {"error": "unknown task"}
        return 200, {"task": task, "block_line": "Task:      %s — found, open → marked doing" % task["title"]}
    if method == "POST" and route == "milestone":
        return 200, {"ok": True}
    if method == "POST" and route == "finish":
        return 200, {"task": dict(TASK, status="done"), "records": [], "help_pages": HELP_PAGES, "block": BLOCK}
    if method == "GET" and route.startswith("records/"):
        slug = route.split("/", 1)[1]
        for r in RECORDS:
            if r["slug"] == slug:
                return 200, dict(r, owner="Test Staff", body="# fixture body", url="https://github.invalid/r")
        return 404, {"error": "unknown record"}
    if method == "GET" and route.startswith("records"):
        return 200, {"records": RECORDS}
    if method == "POST" and route == "records":
        if not isinstance(body, dict) or not body.get("slug"):
            return 422, {"error": "slug required"}
        if body.get("slug") == "server-refuses-this":
            return 422, {"error": "looks like it contains a secret"}
        if body.get("slug") == "slow-record":
            time.sleep(3)  # longer than the caller waits: stands in for Claude Code killing the hook at its timeout
        return 200, {"slug": body["slug"], "action": "created", "url": "https://github.invalid/records/%s" % body["slug"]}
    return None


class Handler(BaseHTTPRequestHandler):
    expected_token = "test"
    log_path = None

    def log_message(self, *args):  # keep the test output clean
        pass

    def _handle(self, method):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw) if raw else None
        except ValueError:
            body = raw.decode(errors="replace")
        sent = self.headers.get("api_access_token")
        token_ok = sent in (self.expected_token, GRANT_TOKEN, STALE_TOKEN)
        path = self.path.split("?", 1)[0]
        with open(self.log_path, "a") as fh:
            fh.write(json.dumps({"method": method, "path": self.path, "token_ok": token_ok, "body": body,
                                 "plugin": self.headers.get("x-work-plugin")}) + "\n")
        if not token_ok:
            status, payload = 401, {"error": "not staff"}
        else:
            answer = routes(method, path, body, needs_grant=sent == GRANT_TOKEN, stale=sent == STALE_TOKEN)
            status, payload = answer if answer else (404, {"error": "no route"})
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--log", required=True)
    parser.add_argument("--ready-file")
    parser.add_argument("--token", default="test")
    args = parser.parse_args()
    Handler.expected_token = args.token
    Handler.log_path = args.log
    open(args.log, "a").close()
    server = HTTPServer(("127.0.0.1", args.port), Handler)
    port = server.server_address[1]
    if args.ready_file:
        with open(args.ready_file, "w") as fh:
            fh.write(str(port))
    print(port, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    sys.exit(main())
