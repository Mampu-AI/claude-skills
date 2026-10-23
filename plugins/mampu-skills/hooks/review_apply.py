#!/usr/bin/env python3
"""Stop hook: post the background records review's spool files to the work API.

The review fork only writes spool JSON under ~/.cache/sapot-work-loop/spool/; this is the only reader.
Per file: refuse the whole file when any string looks like a secret (same regex the server applies),
otherwise POST each record to work/records (python3 urllib, 5 s timeout, token resolved like
hooks/lib/work_api.sh). A file whose records all reached the server (2xx or a 4xx refusal that will not
change on retry) moves to spool/done/; a file the server could not be reached for stays for the next Stop,
up to MAX_ATTEMPTS, then moves to done/ with the attempt count. Each posted record is marked in the file at
once, so a run Claude Code kills at the hook timeout resumes where it stopped. Never prints, never raises.
Lifted from the learning applier (apply_spool.py).

    review_apply.py            process every spool file
    review_apply.py FILE ...   process the named files (testing)
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

# HOME first, like the shell hooks: on Windows, Python's own home is the profile folder, not Git Bash's HOME
HOME = os.environ.get("HOME") or str(Path.home())
STATE_DIR = Path(os.environ.get("SAPOT_WORK_STATE_DIR") or Path(HOME) / ".cache" / "sapot-work-loop")
SPOOL = STATE_DIR / "spool"
DONE = SPOOL / "done"
LOG = STATE_DIR / "review_apply.log"
BASE = (os.environ.get("SAPOT_API_URL") or "https://work.mampuai.com").rstrip("/")
PREFIX = os.environ.get("SAPOT_WORK_API_PREFIX") or "/v1/work"
KEYCHAIN_SERVICE = "sapot-work-login"  # the Lark sign-in; an old staff token is never sent
MAX_ATTEMPTS = 5
TIMEOUT = 5
SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SECRET = re.compile(r"(\bsk-[A-Za-z0-9_-]{16,}|\bghp_[A-Za-z0-9]{20,}|\bgithub_pat_|\bxox[bap]-|\bAKIA[0-9A-Z]{16}|"
                    r"-----BEGIN [A-Z ]*PRIVATE KEY|(password|passwd|secret|token)['\"]?\s*[:=]\s*['\"]?[A-Za-z0-9/+_-]{12,})", re.I)
RECORD_FIELDS = ("slug", "area", "name", "description", "type", "audience", "body")
# The server's fixed lists and limit. The reviewing agent picks topics freely ("dashboard", "flow-runtime") and nobody
# is there to rewrite a refused record, so fit() files it under the nearest topic instead of losing it.
AREAS = ("dev", "flows", "channels", "clients", "docs", "ops", "sales", "support")
AUDIENCES = ("all", "dev", "sales", "ops", "support")
DESCRIPTION_MAX = 220
AREA_OF = {
    "flows": ("flow", "knowledge", "automation", "calendar", "message-sequence", "ai-attribute"),
    "channels": ("whatsapp", "social", "comment", "conversation", "assignment", "inbox", "channel"),
    "docs": ("help", "website", "doc"),
    "sales": ("billing", "sales"),
}


def log(msg):
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")
    except OSError:
        pass


def keychain(cmd):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def token():
    """Same order as scripts/sapot-headers.sh: the Lark sign-in from the macOS Keychain or Linux secret-tool,
    then the sign-in file, then the env."""
    found = ""
    if which("security"):
        found = keychain(["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"])
    elif which("secret-tool"):
        found = keychain(["secret-tool", "lookup", "service", KEYCHAIN_SERVICE])
    if found:
        return found
    login_file = os.environ.get("SAPOT_WORK_LOGIN_FILE") or os.path.join(HOME, ".config", "sapot", "work-login")
    try:
        with open(login_file, encoding="utf-8") as fh:
            found = fh.readline().strip()
        if found:
            return found
    except OSError:
        pass
    return os.environ.get("SAPOT_WORK_TOKEN", "")


def which(name):
    for folder in os.environ.get("PATH", "").split(os.pathsep):
        if folder and os.access(os.path.join(folder, name), os.X_OK):
            return True
    return False


def strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from strings(value)


def fit(record):
    """The record as the server will take it: a topic and audience from its lists, a description within its limit."""
    fitted = {field: record.get(field) for field in RECORD_FIELDS}
    area = str(fitted.get("area") or "").strip().lower()
    if area not in AREAS:
        area = next((name for name, starts in AREA_OF.items() if area.startswith(starts)), "dev")
    fitted["area"] = area
    if fitted.get("audience") not in AUDIENCES:
        fitted["audience"] = "all"
    description = " ".join(str(fitted.get("description") or "").split())
    if len(description) > DESCRIPTION_MAX:
        description = description[: DESCRIPTION_MAX - 1].rsplit(" ", 1)[0].rstrip(" ,;:-") + "…"
    fitted["description"] = description
    return fitted


def post_record(record, access_token):
    """Returns ('ok' | 'refused' | 'unreachable', the server's reason for a refusal). A refusal is a 4xx that a retry
    will not change."""
    body = json.dumps(fit(record)).encode()
    headers = {"api_access_token": access_token, "Content-Type": "application/json", "Accept": "application/json"}
    copy = os.path.basename(os.environ.get("CLAUDE_PLUGIN_ROOT", "").rstrip("/"))
    if copy:
        headers["x-work-plugin"] = copy  # which plugin copy made the call, for the owner's team usage view
    request = urllib.request.Request(f"{BASE}{PREFIX}/records", data=body, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return ("ok" if 200 <= response.status < 300 else "unreachable"), ""
    except urllib.error.HTTPError as err:
        if not 400 <= err.code < 500:
            return "unreachable", ""
        try:
            reason = str(json.loads(err.read().decode("utf-8", "replace")).get("error") or "")
        except (ValueError, AttributeError, OSError):
            reason = ""
        return "refused", reason or f"HTTP {err.code}"
    except (urllib.error.URLError, OSError, ValueError):
        return "unreachable", ""


def save(path, data):
    """Write through a temp file so a kill mid-write never leaves half a spool file."""
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data), encoding="utf-8")
    temp.replace(path)


def finish(path, note):
    DONE.mkdir(parents=True, exist_ok=True)
    path.rename(DONE / path.name)
    log(f"{path.name}: {note}")


def process(path, access_token):
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return finish(path, "REJECTED: not a JSON object")
    if any(SECRET.search(text) for text in strings(data)):
        return finish(path, "REJECTED: looks like it contains a secret")
    records = [r for r in (data.get("records") or []) if isinstance(r, dict)]
    pending = []
    for record in records:
        slug = str(record.get("slug") or "")
        if not SLUG.match(slug) or record.get("type") not in ("procedure", "decision") or not record.get("body"):
            log(f"{path.name}: SKIP record {slug!r}: bad slug, type or empty body")
            continue
        if record.get("_posted"):
            continue
        result, reason = post_record(record, access_token)
        if result == "unreachable":
            pending.append(slug)
            continue
        record["_posted"] = result
        save(path, data)  # Claude Code kills the hook at its timeout; a killed run must not re-send this one
        log(f"{path.name}: {result.upper()} {slug}" + (f": {reason}" if reason else ""))
    if not pending:
        return finish(path, f"done ({len(records)} record(s))")
    data["_attempts"] = int(data.get("_attempts") or 0) + 1
    save(path, data)
    if data["_attempts"] >= MAX_ATTEMPTS:
        return finish(path, f"GAVE UP after {MAX_ATTEMPTS} attempts; unposted: {', '.join(pending)}")
    log(f"{path.name}: server unreachable, {len(pending)} record(s) kept for the next Stop")


def main():
    files = [Path(a) for a in sys.argv[1:]] or sorted(p for p in SPOOL.glob("*.json") if p.is_file())
    if not files:
        return
    access_token = token()
    if not access_token:
        log("no token: spool kept")
        return
    for path in files:
        try:
            process(path, access_token)
        except Exception as err:  # leave the file for inspection, keep the hook silent
            log(f"ERROR {path.name}: {err!r}")
            try:
                path.rename(path.with_suffix(".failed"))
            except OSError:
                pass


if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        log(f"FATAL {err!r}")
    sys.exit(0)
