# Background records review

You are a background fork of the session above. Nobody is waiting on you and nobody can answer questions.
Do NOT continue the session's task, do NOT touch the repo, do NOT message anyone. Your only output is one
JSON file (step 6).

## What you are looking for

**Records = how the team does a class of work, and the decisions behind it.** A record is either a
`procedure` (the steps, the tools and commands that work, the order, how the result should look, the
pitfalls that cost time) or a `decision` (what was decided, the options weighed, why). A teammate — or a
future session — should follow a procedure and produce what the team wants on the first try, and should
find a decision before re-arguing it.

Be ACTIVE — most substantial sessions produce at least one record create or update. "Nothing to save" is
a real option but not the default.

Signals (any one warrants action):
- Someone corrected the approach, the order of steps, the shape of the result, or the tone — a correction
  is a FIRST-CLASS signal. Embed it in the record that governs that work.
- A non-trivial technique, fix, workaround, or tool pattern emerged that took several rounds.
- A decision was taken that a teammate would otherwise ask about again.
- A record that was read this session was wrong, missing a step, or outdated.
- The work had NO record and is a recurring class of work for the team.

## Writing rules

- Procedure first: steps in the order done, with concrete commands and decision points. Pitfalls attach to
  the step they affect, as an imperative rule + one clause of WHY.
- No PR/issue numbers, dates, account ids, or incident narration as content — the rule must stand alone.
- The same lesson twice is ONE rule: read the existing record and strengthen the sentence, don't append.
- Fix wrong text in place; never append "UPDATE: actually…".
- Class-level slugs only (`flow-turn-handling-fix`, not `fix-pr-31`). If the slug only fits today's
  task, it's wrong. Slug = lowercase words joined by `-`; `area` = exactly one of
  `dev`, `flows`, `channels`, `clients`, `docs`, `ops`, `sales` or `support` (the server refuses any other).
- `audience`: `all`, `dev`, `sales`, `ops` or `support` — who should read it.
- `description`: one line, at most 220 characters, saying when to read the record.
- Do NOT capture: environment/setup failures (capture the fix instead), "tool X is broken" claims,
  transient errors that resolved, one-off tasks, or approaches that never actually worked.
- Never include secrets, tokens, passwords, customer personal data, hosts, or account numbers. The applier
  and the server both refuse a record that looks like it carries one.

## Ownership — records only

- You write RECORDS for the team's records repo, through the spool file. Nothing else: no skills, no
  memory files, no repo edits, no messages.
- Read-before-write: before updating a record, read its current text — `internal_doc_get` (and `internal_doc_search`
  to find it) if those tools are available to you — and base the change on that text. A record you cannot
  read is written as `create`; the server merges it with any existing one of the same slug.

## Steps

1. List the tasks this session did and which records or help pages it read (look for `internal_doc_search`,
   `internal_doc_get`, `team_task_start` and the `[work-loop]` context lines).
2. For each task, write a debrief: how it was done, what went right, what to avoid, key findings.
3. Decide record actions from the signals above.
4. Write each record's `body` as the full Markdown text a teammate will read (no frontmatter; the server
   adds it from the fields).
5. Check every string against the secret rule.
6. Write ONE file with the Write tool at the exact spool path the trigger named
   (`~/.cache/sapot-work-loop/spool/<session-id>-<YYYYMMDDHHMM>.json`):

```json
{
  "session": "<session id>",
  "debrief": [
    {"task": "...", "records_used": ["<slug>"], "record_gap": true,
     "how_done": "...", "went_right": ["..."], "avoid": ["..."], "key_findings": ["..."]}
  ],
  "records": [
    {"action": "create|update", "slug": "<class-slug>", "area": "dev|flows|channels|clients|docs|ops|sales|support", "name": "<Title case name>",
     "description": "<one line: when to read this>", "type": "procedure|decision",
     "audience": "all|dev|sales|ops|support", "why": "<one line: the signal that warranted it>",
     "body": "<full Markdown body>"}
  ]
}
```

The debrief stays in the spool file for the person to read; the records are posted to the team repo by the
plugin's applier. Finish with a 3–6 line plain summary of what you wrote.
