---
name: onboard
description: >-
  Connect a Mampu AI teammate to the company Lark and docs and onboard them into the work loop. Use when someone says connect me, onboard me, sign me in, set me up, join the work loop, "I want to be connected to the company Lark / docs", "how do I get started", or when the session-start context says they are not connected or their sign-in lapsed. Guided and conversational: you run the steps, they only approve a browser sign-in.
---

# Onboard a teammate

You do the setup; the person only approves one Lark sign-in in their browser. Keep each message to two
or three lines. Never ask them to run a script, paste a token, or read a README.

## 1. Find the plugin and check the state

```sh
ROOT=$(ls -d ~/.claude/plugins/cache/mampu/mampu-skills/*/ 2>/dev/null | sort -V | tail -n 1); sh "${ROOT}scripts/whoami.sh"
```

- `Signed in as …` → skip to step 3.
- `Not connected.` or `Sign-in lapsed or refused.` → step 2.
- `Work loop switched off on the server.` or `Server unreachable.` → tell them the server side is not ready
  and to ask their Mampu admin; stop.
- `ROOT` empty → the plugin is not installed: tell them to restart Claude Code once (the org provisions it);
  if still missing, their Mampu admin must add them to the Claude org.

## 2. Sign them in (one browser tab)

Say: "A browser tab will open on Lark. Approve it, then come back here." Then run, and wait for it to finish
(it blocks until the sign-in completes, up to five minutes):

```sh
sh "${ROOT}scripts/login.sh"
```

- `Signed in as …` → run `whoami.sh` again to confirm, then say they must **restart Claude Code once** (or
  run `/mcp` and reconnect `mampu-tech-team`) so the tools pick up the login; after that nothing is ever asked again.
- The page said *Sign-in refused* → read the reason back to them in plain words: not in the company Lark
  workspace, no company email on their Lark account, or no Sapot user with that email (they sign up to Sapot
  with the company email first). Do not retry blindly.
- `No browser here` with a URL → they open that URL on any device, sign in, and the page shows a one-time
  token; then run `sh "${ROOT}scripts/save-token.sh" --work` and let them paste it there (never into chat).
- Timed out → run step 2 again once.

## 3. The two-minute brief

Tell them, in your own words, these five things and nothing more:

1. From now on, when they describe work, you find or create the team task in Lark and mark it doing, read the
   matching internal records, and open your reply with a four-line status block. They never have to ask.
2. When the work is done, you complete the task, write or update the record of how it was done, and flag any
   public help page that needs an update. Questions and reads create nothing.
3. If you picked the wrong task, they say "not that one" and you fix it.
4. Their sign-in lives on this computer and lasts while they use it; another laptop needs its own sign-in.
   `login.sh --logout` revokes it.
5. Offer a first task: "Describe something you are about to do today and I will show you the loop."

## Rules

- Never ask for, accept, print or store a token in the chat. If one appears, tell them to run `login.sh --logout`
  and sign in again.
- If `whoami.sh` keeps saying the server is unreachable, stop and hand it to their Mampu admin; do not work around it.
