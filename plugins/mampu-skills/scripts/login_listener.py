#!/usr/bin/env python3
"""Local half of "Sign in with Lark": listens once on 127.0.0.1 for the server's callback redirect
(`/?token=swl_…&name=…`), stores the token in the OS keychain under the given service, and exits.

  python3 login_listener.py <keychain-service>

First stdout line: the port. Then, after the token arrives: "Signed in as <name>." Exit 0 on success,
1 on timeout (5 minutes) or when no keychain is available (the token is then printed ONCE so it can be
saved by hand with save-token.sh --work).
"""
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

TIMEOUT_SECONDS = 300
PAGE = b"<!doctype html><meta charset=utf-8><body style='font-family:system-ui;margin:4rem'>" \
       b"<h1>Done</h1><p>You are signed in. Return to the terminal; this tab can be closed.</p></body>"
result = {}


def store(service: str, token: str) -> bool:
    if shutil.which("security"):
        cmd = ["security", "add-generic-password", "-U", "-a", "sapot", "-s", service, "-w", token]
        return subprocess.run(cmd, capture_output=True).returncode == 0
    if shutil.which("secret-tool"):
        cmd = ["secret-tool", "store", "--label=Sapot work login", "service", service]
        return subprocess.run(cmd, input=token.encode(), capture_output=True).returncode == 0
    return False


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (http.server API)
        query = parse_qs(urlparse(self.path).query)
        token = (query.get("token") or [""])[0]
        if not token.startswith("swl_"):
            self.send_response(404)
            self.end_headers()
            return
        result["token"] = token
        result["name"] = (query.get("name") or [""])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(PAGE)
        threading.Thread(target=self.server.shutdown, daemon=True).start()

    def log_message(self, *_args):  # keep the terminal quiet
        return


def main() -> int:
    service = sys.argv[1] if len(sys.argv) > 1 else "sapot-work-login"
    server = HTTPServer(("127.0.0.1", 0), Handler)
    print(server.server_address[1], flush=True)
    timer = threading.Timer(TIMEOUT_SECONDS, server.shutdown)
    timer.daemon = True
    timer.start()
    server.serve_forever()
    timer.cancel()
    if "token" not in result:
        print("Timed out waiting for the browser sign-in. Run the login again.")
        return 1
    who = result.get("name") or "you"
    if store(service, result["token"]):
        print(f"Signed in as {who}. The login is saved in this computer's keychain.")
        return 0
    print(f"Signed in as {who}, but no keychain is available here. Save this once with: save-token.sh --work")
    print(result["token"])
    return 1


if __name__ == "__main__":
    sys.exit(main())
